import os
import re
import yaml
import aiohttp
import urllib.parse
from typing import List, Dict, Any
from fastapi import HTTPException, status
from oslo_config import cfg
from oslo_log import log as logging

LOG = logging.getLogger(__name__)
CONF = cfg.CONF

_PROMQL_KEYWORDS = {
    "sum", "avg", "max", "min", "count", "rate", "irate", "increase",
    "delta", "by", "without", "bool", "and", "or", "unless", "topk",
    "bottomk", "quantile", "histogram_quantile", "label_replace",
    "label_join", "vector", "scalar", "absent", "ceil", "floor",
    "round", "changes", "resets", "deriv", "predict_linear", "idelta",
    "stddev", "stdvar", "count_values", "sort", "sort_desc",
}


def inject_project_id(expr: str, project_id: str) -> str:
    expr = re.sub(r'\{\s*\}', '', expr)
    if f'project_id="{project_id}"' in expr:
        return expr

    metric_with_labels = re.compile(r'\b([a-zA-Z_:][a-zA-Z0-9_:]*)\s*\{([^}]*)\}')
    metric_without_labels = re.compile(r'\b([a-zA-Z_:][a-zA-Z0-9_:]*)\b(?!\s*\{)(?!\s*\()')

    def inject_into_labels(match):
        metric_name = match.group(1)
        labels_inner = match.group(2)
        if metric_name.lower() in _PROMQL_KEYWORDS:
            return match.group(0)
        if "project_id" in labels_inner:
            return match.group(0)
        if labels_inner.strip():
            return f'{metric_name}{{project_id="{project_id}",{labels_inner}}}'
        else:
            return f'{metric_name}{{project_id="{project_id}"}}'

    def inject_bare_metric(match):
        metric_name = match.group(1)
        if metric_name.lower() in _PROMQL_KEYWORDS:
            return match.group(0)
        return f'{metric_name}{{project_id="{project_id}"}}'

    result = metric_with_labels.sub(inject_into_labels, expr)
    result = metric_without_labels.sub(inject_bare_metric, result)
    return result


async def validate_promql_expression(expr: str) -> None:
    async with aiohttp.ClientSession() as session:
        try:
            url = f"{CONF.thanos.querier_endpoint}/api/v1/query"
            params = {"query": expr, "time": "1"}

            async with session.get(
                url, params=params, timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                data = await response.json()

                if data.get("status") == "error" and data.get("errorType") == "bad_data":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid PromQL expression: {data.get('error')}"
                    )

                LOG.debug(f"PromQL validation passed: {expr}")

        except HTTPException:
            raise
        except Exception as e:
            LOG.warning(f"PromQL validation skipped (thanos unreachable): {str(e)}")


async def update_project_rules_file(project_id: str, rules: List[Dict[str, Any]]) -> None:
    try:
        rules_dir = CONF.thanos.rules_dir
        yaml_path = os.path.join(rules_dir, f"{project_id}.yaml")

        yaml_content = {"groups": []}

        if rules:
            groups_dict = {}
            for rule in rules:
                group_name = rule.get("rule_group", "default")
                if group_name not in groups_dict:
                    groups_dict[group_name] = {
                        "name": f"{project_id}-{group_name}",
                        "interval": "30s",
                        "rules": []
                    }

                labels = rule.get("labels") or {}
                labels.update({
                    "alertname": rule["rule_name"],
                    "project_id": project_id,
                    "severity": rule.get("severity", "warning"),
                    "rule_id": str(rule["id"])
                })

                alert_rule = {
                    "alert": rule["rule_name"],
                    "expr": rule["expr"],
                    "for": rule.get("for_duration", "5m"),
                    "labels": labels,
                    "annotations": rule.get("annotations") or {}
                }

                groups_dict[group_name]["rules"].append(alert_rule)

            yaml_content["groups"] = list(groups_dict.values())

        os.makedirs(rules_dir, exist_ok=True)

        temp_path = yaml_path + ".tmp"
        with open(temp_path, 'w') as f:
            yaml.dump(yaml_content, f, default_flow_style=False, sort_keys=False)
        os.rename(temp_path, yaml_path)

        LOG.info(f"Updated rules file for project {project_id}: {yaml_path} ({len(rules)} rules)")

    except Exception as e:
        LOG.error(f"Failed to update rules file for project {project_id}: {str(e)}", exc_info=True)
        raise


async def delete_project_rules_file(project_id: str) -> None:
    try:
        yaml_path = os.path.join(CONF.thanos.rules_dir, f"{project_id}.yaml")
        if os.path.exists(yaml_path):
            os.remove(yaml_path)
            LOG.info(f"Deleted rules file for project {project_id}: {yaml_path}")
    except Exception as e:
        LOG.error(f"Failed to delete rules file for project {project_id}: {str(e)}", exc_info=True)
        raise


async def execute_instant_query(query: str) -> str:
    async with aiohttp.ClientSession() as session:
        try:
            url = f"{CONF.thanos.querier_endpoint}/api/v1/query?query={urllib.parse.quote(query)}"
            LOG.debug(f"Executing Thanos instant query: {query}")

            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status != 200:
                    body = await response.text()
                    raise Exception(f"Thanos returned status {response.status}: {body}")

                data = await response.json()
                if data.get("status") != "success":
                    raise Exception(f"Thanos query unsuccessful: {data}")

                result = data.get("data", {}).get("result", [])
                if not result:
                    LOG.warning(f"No data returned for query: {query}")
                    return "0"

                value = result[0].get("value", [])
                if len(value) != 2:
                    raise Exception(f"Invalid value format: {value}")

                try:
                    return f"{float(value[1]):.2f}"
                except ValueError:
                    return value[1]

        except aiohttp.ClientError as e:
            LOG.error(f"HTTP error during Thanos query: {str(e)}")
            raise Exception(f"Failed to execute Thanos query: {str(e)}")
        except Exception as e:
            LOG.error(f"Error executing Thanos query: {str(e)}", exc_info=True)
            raise


async def execute_range_query(query: str) -> List[Dict[str, Any]]:
    async with aiohttp.ClientSession() as session:
        try:
            url = f"{CONF.thanos.querier_endpoint}/api/v1/query?query={urllib.parse.quote(query)}"
            LOG.debug(f"Executing Thanos range query: {query}")

            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status != 200:
                    body = await response.text()
                    raise Exception(f"Thanos returned status {response.status}: {body}")

                data = await response.json()
                if data.get("status") != "success":
                    raise Exception(f"Thanos query unsuccessful: {data}")

                result = data.get("data", {}).get("result", [])
                if not result:
                    LOG.warning(f"No data returned for query: {query}")
                    return []

                return result

        except aiohttp.ClientError as e:
            LOG.error(f"HTTP error during Thanos query: {str(e)}")
            raise Exception(f"Failed to execute Thanos query: {str(e)}")
        except Exception as e:
            LOG.error(f"Error executing Thanos query: {str(e)}", exc_info=True)
            raise


async def execute_range_query_with_time(
    query: str,
    start: int,
    end: int,
    step: str = "5m"
) -> List[Dict[str, Any]]:
    async with aiohttp.ClientSession() as session:
        try:
            data = {"query": query, "start": start, "end": end, "step": step}
            url = f"{CONF.thanos.querier_endpoint}/api/v1/query_range"
            LOG.debug(
                f"Executing Thanos range query with time: query={query}, "
                f"start={start}, end={end}, step={step}"
            )

            async with session.post(
                url, data=data, timeout=aiohttp.ClientTimeout(total=180)
            ) as response:
                if response.status != 200:
                    body = await response.text()
                    raise Exception(f"Thanos returned status {response.status}: {body}")

                data = await response.json()
                if data.get("status") != "success":
                    raise Exception(f"Thanos range query unsuccessful: {data}")

                result = data.get("data", {}).get("result", [])
                if not result:
                    LOG.warning(
                        f"No data returned for range query: query={query}, "
                        f"start={start}, end={end}"
                    )
                    return []

                LOG.info(f"Thanos range query successful: {len(result)} time series")
                return result

        except aiohttp.ClientError as e:
            LOG.error(f"HTTP error during Thanos range query: {str(e)}")
            raise Exception(f"Failed to execute Thanos range query: {str(e)}")
        except Exception as e:
            LOG.error(f"Error executing Thanos range query: {str(e)}", exc_info=True)
            raise


async def get_label_names(metric_name: str = None) -> List[str]:
    """Thanos /api/v1/labels endpoint'inden label isimlerini getirir."""
    async with aiohttp.ClientSession() as session:
        try:
            url = f"{CONF.thanos.querier_endpoint}/api/v1/labels"
            params = {}
            if metric_name:
                params["match[]"] = metric_name

            LOG.debug(f"Fetching label names: metric_name={metric_name}")

            async with session.get(
                url, params=params, timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status != 200:
                    body = await response.text()
                    raise Exception(f"Thanos returned status {response.status}: {body}")

                data = await response.json()
                if data.get("status") != "success":
                    raise Exception(f"Thanos labels query unsuccessful: {data}")

                return data.get("data", [])

        except aiohttp.ClientError as e:
            LOG.error(f"HTTP error during Thanos labels query: {str(e)}")
            raise Exception(f"Failed to fetch label names: {str(e)}")
        except Exception as e:
            LOG.error(f"Error fetching label names: {str(e)}", exc_info=True)
            raise


async def get_label_values(label_name: str, metric_name: str = None) -> List[str]:
    """Thanos /api/v1/label/<name>/values endpoint'inden label degerlerini getirir."""
    async with aiohttp.ClientSession() as session:
        try:
            url = f"{CONF.thanos.querier_endpoint}/api/v1/label/{label_name}/values"
            params = {}
            if metric_name:
                params["match[]"] = metric_name

            LOG.debug(f"Fetching label values: label={label_name}, metric={metric_name}")

            async with session.get(
                url, params=params, timeout=aiohttp.ClientTimeout(total=120)
            ) as response:
                if response.status != 200:
                    body = await response.text()
                    raise Exception(f"Thanos returned status {response.status}: {body}")

                data = await response.json()
                if data.get("status") != "success":
                    raise Exception(f"Thanos label values query unsuccessful: {data}")

                return data.get("data", [])

        except aiohttp.ClientError as e:
            LOG.error(f"HTTP error during Thanos label values query: {str(e)}")
            raise Exception(f"Failed to fetch label values: {str(e)}")
        except Exception as e:
            LOG.error(f"Error fetching label values: {str(e)}", exc_info=True)
            raise


async def get_series(match: str) -> List[Dict[str, Any]]:
    """Thanos /api/v1/series endpoint'inden eslesen serileri getirir."""
    async with aiohttp.ClientSession() as session:
        try:
            url = f"{CONF.thanos.querier_endpoint}/api/v1/series"
            params = {"match[]": match}

            LOG.debug(f"Fetching series: match={match}")

            async with session.get(
                url, params=params, timeout=aiohttp.ClientTimeout(total=120)
            ) as response:
                if response.status != 200:
                    body = await response.text()
                    raise Exception(f"Thanos returned status {response.status}: {body}")

                data = await response.json()
                if data.get("status") != "success":
                    raise Exception(f"Thanos series query unsuccessful: {data}")

                return data.get("data", [])

        except aiohttp.ClientError as e:
            LOG.error(f"HTTP error during Thanos series query: {str(e)}")
            raise Exception(f"Failed to fetch series: {str(e)}")
        except Exception as e:
            LOG.error(f"Error fetching series: {str(e)}", exc_info=True)
            raise