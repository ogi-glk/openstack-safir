from __future__ import annotations

import asyncio
import aiohttp
import aiosmtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import List, Dict
from fastapi import APIRouter, Request, HTTPException, status, BackgroundTasks
from oslo_config import cfg
from pydantic import BaseModel
from oslo_log import log as logging

from safir_monitoring.db import api as db_api

LOG = logging.getLogger(__name__)
router = APIRouter()
CONF = cfg.CONF


class AlertmanagerAlert(BaseModel):
    status: str  # firing | resolved
    labels: Dict[str, str]
    annotations: Dict[str, str]
    startsAt: datetime
    endsAt: datetime
    fingerprint: str


class AlertmanagerWebhook(BaseModel):
    version: str
    groupKey: str
    status: str  # firing | resolved
    alerts: List[AlertmanagerAlert]


def _make_ssl_connector():
    """SSL doğrulama kapalı connector — self-signed cert için"""
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    return aiohttp.TCPConnector(ssl=ssl_context)


def _parse_smtp_host() -> tuple[str, int]:
    raw = CONF.email_notifier.smtp_host
    if ":" in raw:
        host, port_str = raw.rsplit(":", 1)
        return host, int(port_str)
    return raw, 587


@router.post(
    "/alerts/webhook",
    description="Alertmanager webhook endpoint — OpenSearch kayıt + bildirim gönderimi",
    responses={
        200: {"description": "Webhook processed successfully"},
        400: {"description": "Invalid payload"},
        500: {"description": "Internal server error"},
    },
    status_code=status.HTTP_200_OK,
)
async def handle_alert_webhook(
    webhook: AlertmanagerWebhook,
    background_tasks: BackgroundTasks,
):
    LOG.info(
        f"[WEBHOOK] Received webhook: status={webhook.status}, "
        f"group_key={webhook.groupKey}, alerts_count={len(webhook.alerts)}"
    )
    background_tasks.add_task(_process_alerts_in_background, webhook)
    return {"status": "ok"}


async def _process_alerts_in_background(webhook: AlertmanagerWebhook):
    LOG.info(f"[BACKGROUND] Processing {len(webhook.alerts)} alerts in background")
    for alert in webhook.alerts:
        fingerprint = alert.fingerprint
        alert_name = alert.labels.get("alertname", "unknown")
        project_id = alert.labels.get("project_id", "unknown")
        rule_id = alert.labels.get("rule_id", "unknown")

        LOG.info(
            f"[BACKGROUND] Processing alert: fingerprint={fingerprint}, "
            f"alert_name={alert_name}, status={alert.status}, "
            f"project_id={project_id}, rule_id={rule_id}"
        )
        try:
            await _send_to_opensearch(alert)
            if alert.status == "firing":
                await _send_notifications(alert)
            elif alert.status == "resolved":
                LOG.info(
                    f"[BACKGROUND] Alert resolved, skipping notifications: "
                    f"fingerprint={fingerprint}, alert_name={alert_name}"
                )
        except Exception as e:
            LOG.error(
                f"[BACKGROUND] Error processing alert: fingerprint={fingerprint}, "
                f"alert_name={alert_name}, error={str(e)}",
                exc_info=True,
            )
    LOG.info(f"[BACKGROUND] Finished processing {len(webhook.alerts)} alerts")


async def _send_to_opensearch(alert: AlertmanagerAlert) -> None:
    """Alert'i proje bazlı OpenSearch index'ine kaydeder"""
    project_id = alert.labels.get("project_id", "")
    alert_name = alert.labels.get("alertname", "")

    if not project_id or not alert_name:
        LOG.warning(
            f"[OPENSEARCH] Missing required labels (project_id or alertname), skipping: "
            f"fingerprint={alert.fingerprint}"
        )
        return

    # firing alert'lerde endsAt=0001-01-01 gelir, None olarak kaydet
    ends_at = alert.endsAt if alert.endsAt.year > 1 else None

    document = {
        "timestamp": datetime.utcnow().isoformat(),
        "status": alert.status,
        "project_id": project_id,
        "alert_name": alert_name,
        "rule_id": alert.labels.get("rule_id", ""),
        "severity": alert.labels.get("severity", "unknown"),
        "cluster": alert.labels.get("cluster", "unknown"),
        "fingerprint": alert.fingerprint,
        "starts_at": alert.startsAt.isoformat(),
        "ends_at": ends_at.isoformat() if ends_at else None,
        "duration_seconds": (
            (ends_at - alert.startsAt).total_seconds()
            if alert.status == "resolved" and ends_at
            else None
        ),
        "labels": alert.labels,
        "annotations": alert.annotations,
    }

    url = f"{CONF.opensearch.url}/alarm-{project_id}/_doc"

    LOG.debug(
        f"[OPENSEARCH] Sending document: url={url}, "
        f"fingerprint={alert.fingerprint}, status={alert.status}"
    )

    async with aiohttp.ClientSession(
        connector=_make_ssl_connector(),
        auth=aiohttp.BasicAuth(CONF.opensearch.username, CONF.opensearch.password),
    ) as session:
        async with session.post(
            url,
            json=document,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as response:
            if response.status < 200 or response.status >= 300:
                error_text = await response.text()
                raise Exception(f"OpenSearch returned {response.status}: {error_text}")

            LOG.info(
                f"[OPENSEARCH] Alert saved: project_id={project_id}, "
                f"alert_name={alert_name}, status={alert.status}, "
                f"fingerprint={alert.fingerprint}"
            )


async def _send_notifications(alert: AlertmanagerAlert) -> None:
    project_id = alert.labels.get("project_id", "")
    rule_id = alert.labels.get("rule_id", "")
    alert_name = alert.labels.get("alertname", "unknown")

    if not project_id or not rule_id:
        LOG.debug(
            f"[NOTIFY] Missing project_id or rule_id, skipping: "
            f"fingerprint={alert.fingerprint}"
        )
        return

    LOG.info(
        f"[NOTIFY] Fetching rule: rule_id={rule_id}, "
        f"project_id={project_id}, alert_name={alert_name}"
    )

    try:
        rule = await asyncio.wait_for(db_api.get_alarm_rule(rule_id), timeout=5.0)
    except asyncio.TimeoutError:
        LOG.error(f"[NOTIFY] Timeout fetching alarm rule: rule_id={rule_id}")
        return
    except Exception as e:
        LOG.error(f"[NOTIFY] Failed to fetch alarm rule: rule_id={rule_id}, error={str(e)}")
        return

    notification_ids = rule.get("notification_ids") or []
    if not notification_ids:
        LOG.info(
            f"[NOTIFY] No notifications configured for rule: "
            f"rule_id={rule_id}, alert_name={alert_name}"
        )
        return

    LOG.info(
        f"[NOTIFY] Found {len(notification_ids)} notification(s) for rule: "
        f"rule_id={rule_id}, alert_name={alert_name}"
    )

    for notif_id in notification_ids:
        LOG.debug(f"[NOTIFY] Fetching notification: notif_id={notif_id}")
        try:
            notif = await asyncio.wait_for(
                db_api.get_notification(notif_id), timeout=5.0
            )
        except asyncio.TimeoutError:
            LOG.error(f"[NOTIFY] Timeout fetching notification: notif_id={notif_id}")
            continue
        except Exception as e:
            LOG.error(
                f"[NOTIFY] Failed to fetch notification: "
                f"notif_id={notif_id}, error={str(e)}"
            )
            continue

        notif_type = notif["type"]
        notif_value = notif["value"]
        notif_name = notif["name"]

        LOG.info(
            f"[NOTIFY] Sending {notif_type} notification: "
            f"name={notif_name}, target={notif_value}, "
            f"alert_name={alert_name}, project_id={project_id}"
        )

        try:
            if notif_type == "email":
                await _send_email(alert, notif_value)
                LOG.info(
                    f"[NOTIFY] Email sent: to={notif_value}, name={notif_name}, "
                    f"alert={alert_name}, project={project_id}"
                )
            elif notif_type == "webhook":
                await _send_webhook(alert, notif_value)
                LOG.info(
                    f"[NOTIFY] Webhook sent: url={notif_value}, name={notif_name}, "
                    f"alert={alert_name}, project={project_id}"
                )
            else:
                LOG.warning(
                    f"[NOTIFY] Unknown notification type '{notif_type}': "
                    f"notif_id={notif_id}, name={notif_name}"
                )
        except Exception as e:
            LOG.error(
                f"[NOTIFY] Failed to send {notif_type}: "
                f"target={notif_value}, name={notif_name}, "
                f"alert={alert_name}, error={str(e)}",
                exc_info=True,
            )


async def _send_email(alert: AlertmanagerAlert, to_email: str) -> None:
    alert_name = alert.labels.get("alertname", "")
    severity = alert.labels.get("severity", "unknown")
    project_id = alert.labels.get("project_id", "")
    summary = alert.annotations.get("summary", "")

    subject = f"[SAFIR] {alert_name} - {severity}"
    color = "#d32f2f" if severity == "critical" else "#f57c00"

    body_html = f"""
    <html><body>
    <h2 style="color: {color}">&#9888; SAFIR Alarm: {alert_name}</h2>
    <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse">
        <tr><td><b>Durum</b></td><td>{alert.status.upper()}</td></tr>
        <tr><td><b>Severity</b></td><td>{severity}</td></tr>
        <tr><td><b>Project ID</b></td><td>{project_id}</td></tr>
        <tr><td><b>Özet</b></td><td>{summary}</td></tr>
        <tr><td><b>Başlangıç</b></td><td>{alert.startsAt.isoformat()}</td></tr>
        <tr><td><b>Bitiş</b></td><td>{alert.endsAt.isoformat()}</td></tr>
        <tr><td><b>Fingerprint</b></td><td>{alert.fingerprint}</td></tr>
    </table>
    </body></html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = CONF.email_notifier.smtp_from
    msg["To"] = to_email
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    smtp_host, smtp_port = _parse_smtp_host()

    LOG.debug(
        f"[EMAIL] Connecting to SMTP: host={smtp_host}, port={smtp_port}, to={to_email}"
    )

    await aiosmtplib.send(
        msg,
        hostname=smtp_host,
        port=smtp_port,
        username=CONF.email_notifier.smtp_user,
        password=CONF.email_notifier.smtp_pass,
        start_tls=True,
        timeout=15,
    )

    LOG.debug(f"[EMAIL] SMTP send completed: to={to_email}, alert={alert_name}")


async def _send_webhook(alert: AlertmanagerAlert, url: str) -> None:
    payload = {
        "status": alert.status,
        "fingerprint": alert.fingerprint,
        "labels": alert.labels,
        "annotations": alert.annotations,
        "startsAt": alert.startsAt.isoformat(),
        "endsAt": alert.endsAt.isoformat(),
    }

    LOG.debug(f"[WEBHOOK_OUT] Sending to external webhook: url={url}")

    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as response:
            if response.status < 200 or response.status >= 300:
                body = await response.text()
                raise Exception(f"Webhook target returned {response.status}: {body}")

            LOG.debug(f"[WEBHOOK_OUT] External webhook success: url={url}, status={response.status}")


async def mark_rule_deleted_in_opensearch(project_id: str, rule_id: str) -> None:
    url = f"{CONF.opensearch.url}/alarm-{project_id}/_update_by_query"

    payload = {
        "script": {
            "source": "ctx._source.status = 'deleted'",
            "lang": "painless",
        },
        "query": {
            "term": {
                "rule_id.keyword": rule_id,
            }
        },
    }

    LOG.info(
        f"[OPENSEARCH] Marking docs as deleted: "
        f"project_id={project_id}, rule_id={rule_id}"
    )

    async with aiohttp.ClientSession(
        connector=_make_ssl_connector(),
        auth=aiohttp.BasicAuth(CONF.opensearch.username, CONF.opensearch.password),
    ) as session:
        async with session.post(
            url,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as response:
            if response.status < 200 or response.status >= 300:
                error_text = await response.text()
                raise Exception(f"OpenSearch update_by_query failed: {error_text}")

            result = await response.json()
            updated = result.get("updated", 0)
            LOG.info(
                f"[OPENSEARCH] Marked {updated} docs as deleted: "
                f"project_id={project_id}, rule_id={rule_id}"
            )