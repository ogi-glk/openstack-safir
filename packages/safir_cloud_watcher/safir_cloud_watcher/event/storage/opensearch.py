from opensearchpy import OpenSearch
from opensearchpy import exceptions as opensearchpy_exceptions
from opensearchpy.helpers import bulk

from urllib3 import exceptions as urllib3_exceptions

from oslo_config import cfg
from oslo_log import log as logging

from safir_cloud_watcher.event.storage.syslog_forwarder import SyslogForwarder

import fnmatch
import uuid
from datetime import datetime, timezone  

LOG = logging.getLogger(__name__)

opensearch_opts = [
    cfg.StrOpt('host',
               default='',
               help="OpenSearch Host URL"),
    cfg.StrOpt('port',
               default='9200',
               help="OpenSearch Port"),
    cfg.StrOpt('username',
               default='admin'),
    cfg.StrOpt('password',
               default=''),
    cfg.BoolOpt('http_compress',
                default='False'),
    cfg.BoolOpt('use_ssl',
                default='False'),
    cfg.BoolOpt('verify_certs',
                default='False'),
    cfg.BoolOpt('ssl_assert_hostname',
                default='False'),
    cfg.BoolOpt('ssl_show_warn',
                default='False'),
    cfg.StrOpt('ca_certs_path',
               default=''),
    cfg.StrOpt('index_name',
               default='events'),
    cfg.StrOpt('audit_index_name',
               default='audit_events'),
]

CONF = cfg.CONF
CONF.register_opts(opensearch_opts, 'opensearch')


class OpenSearchStore(object):
    def __init__(self, upgrade=False):
        host = CONF.opensearch.host
        port = CONF.opensearch.port

        auth = (CONF.opensearch.username, CONF.opensearch.password)

        self.index_name = CONF.opensearch.index_name
        self.audit_index_name = CONF.opensearch.audit_index_name
        self.syslog = SyslogForwarder()

        try:
            self.client = OpenSearch(
                hosts=[{'host': host, 'port': port}],
                http_compress=CONF.opensearch.http_compress,
                http_auth=auth,
                use_ssl=CONF.opensearch.use_ssl,
                verify_certs=CONF.opensearch.verify_certs,
                ssl_assert_hostname=CONF.opensearch.ssl_assert_hostname,
                ssl_show_warn=CONF.opensearch.ssl_show_warn,
                ca_certs=CONF.opensearch.ca_certs_path,
                pool_maxsize=10,
            )
        except urllib3_exceptions.LocationValueError as ex:
            self.client = None
            LOG.error("Could not connect OpenSearch: %s", str(ex))
        except Exception as ex:
            self.client = None
            LOG.error("Could not connect OpenSearch: %s", str(ex))

        if upgrade:
            self.upgrade()

    def check_connection(self):
        if self.client is None or not self.client.ping():
            LOG.warning("OpenSearch connection is not active")
            return False
        return True

    def upgrade(self):
        if not self.check_connection():
            return

        events_body = {
            "mappings": {
                "properties": {
                    "message_id": {"type": "text"},
                    "project_id": {"type": "text"},
                    "user_id": {"type": "text"},
                    "user_name": {"type": "keyword"},
                    "resource_id": {"type": "text"},
                    "resource_type": {"type": "text"},
                    "display_name": {"type": "text"},
                    "state": {"type": "text"},
                    "old_state": {"type": "keyword"},
                    "request_id": {"type": "keyword"},
                    "event_type": {"type": "keyword"},
                    "client_ip": {"type": "ip"},
                    "action": {"type": "keyword"},
                    "outcome": {"type": "keyword"},
                    "request_path": {"type": "keyword"},
                    "target_id": {"type": "keyword"},
                    "reason_code": {"type": "keyword"},
                    "instance_type": {"type": "keyword"},
                    "memory_mb": {"type": "integer"},
                    "vcpus": {"type": "integer"},
                    "disk_gb": {"type": "integer"},
                    "host": {"type": "keyword"},
                    "availability_zone": {"type": "keyword"},
                    "size": {"type": "integer"},
                    "volume_type": {"type": "keyword"},
                    "image_id": {"type": "keyword"},
                    "timestamp": {"type": "date"}
                }
            }
        }

        audit_body = {
            "mappings": {
                "properties": {
                    "message_id": {"type": "text"},
                    "project_id": {"type": "text"},
                    "user_id": {"type": "text"},
                    "user_name": {"type": "keyword"},
                    "resource_id": {"type": "text"},
                    "resource_type": {"type": "text"},
                    "request_id": {"type": "keyword"},
                    "event_type": {"type": "keyword"},
                    "client_ip": {"type": "ip"},
                    "action": {"type": "keyword"},
                    "outcome": {"type": "keyword"},
                    "request_path": {"type": "keyword"},
                    "target_id": {"type": "keyword"},
                    "reason_code": {"type": "keyword"},
                    "timestamp": {"type": "date"}
                }
            }
        }

        LOG.info("Create index templates...")
        templates = [
            ("%s_template" % self.index_name,
             "%s-*" % self.index_name, events_body["mappings"]),
            ("%s_template" % self.audit_index_name,
             "%s-*" % self.audit_index_name, audit_body["mappings"]),
        ]
        for template_name, pattern, mappings in templates:
            try:
                template_body = {
                    "index_patterns": [pattern],
                    "template": {
                        "mappings": mappings
                    }
                }
                self.client.indices.put_index_template(template_name,
                                                        body=template_body)
                LOG.info("Index template '%s' created for pattern '%s'",
                         template_name, pattern)
            except Exception as ex:
                LOG.error("Could not create index template '%s': %s",
                          template_name, str(ex))

    def _get_daily_index(self, base_name):                                                                                
         today = datetime.now(timezone.utc).strftime('%Y.%m.%d')                                                   
         return "%s-%s" % (base_name, today)
                                                                                                                  
    def _get_search_pattern(self, base_name):                                                                             
        return "%s-*" % base_name
     
    def _is_audit_event(self, event_type):
        return event_type.startswith('audit.http.')

    def _is_auth_event(self, event_type):
        return event_type in ('identity.authenticate', 'skyline.authenticate')

    def _is_skyline_auth_event(self, event_type):
        return event_type == 'skyline.authenticate'

    def _is_service_user_by_name(self, user_name):
        if not user_name:
            return False
        service_users = CONF.notification.service_users
        return any(fnmatch.fnmatch(user_name, pattern)
                   for pattern in service_users)


    def _get_audit_info(self, request_id):
        """Fetch audit info by request_id from audit_events index."""
        try:
            result = self.client.search(
                index=self._get_search_pattern(self.audit_index_name),
                body={
                    "query": {"term": {"request_id": request_id}},
                    "size": 1,
                    "sort": [{"timestamp": {"order": "desc"}}],
                    "_source": ["user_name", "client_ip", "action",
                                "outcome", "request_path", "target_id",
                                "reason_code"]
                }
            )
            hits = result.get("hits", {}).get("hits", [])
            if hits:
                return hits[0]["_source"]
        except Exception as ex:
            LOG.debug("Could not fetch audit info for request_id %s: %s",
                      request_id, str(ex))
        return {}

    def record_events(self, events):
        if not self.check_connection():
            return

        audit_bulk = list()
        standard_events = list()

        for event in events:
            traits = {t.name: t.value for t in event.traits}
            project_id = traits.get("project_id", "")
            user_id = traits.get("user_id", "")
            resource_id = traits.get("resource_id", "")
            request_id = traits.get("request_id", uuid.uuid4())
            resource_type = event.event_type.split('.')[0]

            if self._is_audit_event(event.event_type):
                audit_user_name = traits.get("initiator_name") or None
                audit_request_id = traits.get("initiator_request_id", request_id)
                audit_bulk.append({
                    "_index": self._get_daily_index(self.audit_index_name),
                    "_id": event.message_id,
                    "_source": {
                        "message_id": event.message_id,
                        "project_id": project_id,
                        "user_id": user_id,
                        "user_name": audit_user_name,
                        "resource_id": resource_id,
                        "resource_type": resource_type,
                        "request_id": audit_request_id,
                        "event_type": event.event_type,
                        "client_ip": traits.get("initiator_host_address") or None,
                        "action": traits.get("action") or None,
                        "outcome": traits.get("outcome") or None,
                        "request_path": traits.get("requestPath") or None,
                        "target_id": traits.get("target_id") or None,
                        "reason_code": traits.get("reason_code") or None,
                        "timestamp": event.generated.isoformat(),
                    }
                })
            elif self._is_auth_event(event.event_type):
                if self._is_skyline_auth_event(event.event_type):
                    auth_user_name = traits.get("user_name", "")
                else:
                    auth_user_name = traits.get("initiator_name", "")
                if auth_user_name and not self._is_service_user_by_name(auth_user_name):
                    standard_events.append((event, traits, project_id, user_id,
                                            resource_id, request_id, resource_type))
            else:
                standard_events.append((event, traits, project_id, user_id,
                                        resource_id, request_id, resource_type))

        # Phase 1: Write audit events first and refresh index
        if audit_bulk:
            try:
                bulk(self.client, audit_bulk)
                self.client.indices.refresh(index=self._get_daily_index(self.audit_index_name))
            except opensearchpy_exceptions.TransportError as ex:
                LOG.error(str(ex))

        # Phase 2: Process standard events (audit info is now searchable)
        events_bulk = list()
        for event, traits, project_id, user_id, resource_id, request_id, resource_type in standard_events:
                display_name = traits.get("display_name", traits.get("name", ""))
                state = traits.get("state", traits.get("status", ""))
                old_state = traits.get("old_state", "")

                source = {
                    "message_id": event.message_id,
                    "project_id": project_id,
                    "user_id": user_id,
                    "resource_id": resource_id,
                    "resource_type": resource_type,
                    "display_name": display_name,
                    "state": state,
                    "request_id": request_id,
                    "event_type": event.event_type,
                    "timestamp": event.generated.isoformat(),
                }

                # Add old_state if present (state change events)
                if old_state:
                    source["old_state"] = old_state

                # Compute-specific fields
                if resource_type == 'compute':
                    if traits.get("instance_type"):
                        source["instance_type"] = traits["instance_type"]
                    if traits.get("memory_mb"):
                        source["memory_mb"] = traits["memory_mb"]
                    if traits.get("vcpus"):
                        source["vcpus"] = traits["vcpus"]
                    if traits.get("disk_gb"):
                        source["disk_gb"] = traits["disk_gb"]
                    if traits.get("host"):
                        source["host"] = traits["host"]
                    if traits.get("availability_zone"):
                        source["availability_zone"] = traits["availability_zone"]

                # Volume/Snapshot-specific fields
                elif resource_type in ('volume', 'snapshot'):
                    if traits.get("size"):
                        source["size"] = traits["size"]
                    if traits.get("type"):
                        source["volume_type"] = traits["type"]
                    if traits.get("availability_zone"):
                        source["availability_zone"] = traits["availability_zone"]
                    if traits.get("image_id"):
                        source["image_id"] = traits["image_id"]

                # Image-specific fields
                elif resource_type == 'image':
                    if traits.get("size"):
                        source["size"] = traits["size"]

                # Auth events (identity.authenticate and skyline.authenticate)
                if self._is_auth_event(event.event_type):
                    if self._is_skyline_auth_event(event.event_type):
                        # skyline.authenticate — traits come directly from payload
                        source["user_id"] = traits.get("user_id") or user_id
                        source["user_name"] = traits.get("user_name") or None
                        source["client_ip"] = traits.get("client_ip") or None
                        source["outcome"] = traits.get("outcome") or None
                        source["action"] = traits.get("action") or "authenticate"
                    else:
                        # identity.authenticate — CADF traits
                        source["user_id"] = traits.get("initiator_user_id") or traits.get("initiator_id") or user_id
                        source["user_name"] = traits.get("initiator_name") or None
                        source["client_ip"] = traits.get("initiator_host_addr") or None
                        source["outcome"] = traits.get("outcome") or None
                        source["action"] = "authenticate"
                else:
                    # Enrich with audit info (user_name, client_ip, etc.)
                    audit_info = self._get_audit_info(request_id)
                    if audit_info:
                        source["user_name"] = audit_info.get("user_name")
                        source["client_ip"] = audit_info.get("client_ip")
                        source["action"] = audit_info.get("action")
                        source["outcome"] = audit_info.get("outcome")
                        source["request_path"] = audit_info.get("request_path")
                        source["target_id"] = audit_info.get("target_id")
                        source["reason_code"] = audit_info.get("reason_code")

                events_bulk.append({
                    "_index": self._get_daily_index(self.index_name),
                    "_id": event.message_id,
                    "_source": source,
                })

        if events_bulk:
            try:
                bulk(self.client, events_bulk)
            except opensearchpy_exceptions.TransportError as ex:
                LOG.error(str(ex))

            # Forward to syslog if enabled
            if self.syslog.enabled:
                self.syslog.forward_batch(
                    [item["_source"] for item in events_bulk]
                )

    def get_events(self, resource_id=None, project_id=None, pagination_from=0, size=10,
                   hidden_events=None):
        if not self.check_connection():
            return []

        query = self.build_query(resource_id, project_id, pagination_from, size,
                                 hidden_events=hidden_events)

        events = list()
        try:
            res = self.client.search(index=self._get_search_pattern(self.index_name), body=query)

            for h in res["hits"]["hits"]:
                try:
                    event = dict()
                    s = h["_source"]
                    event["request_id"] = s["request_id"]
                    event["project_id"] = s["project_id"]
                    event["user_id"] = s["user_id"]
                    event["user_name"] = s.get("user_name", "")
                    event["resource_type"] = s["resource_type"]
                    event["resource_id"] = s["resource_id"]
                    event["display_name"] = s["display_name"]
                    event["client_ip"] = s.get("client_ip", "")
                    event["action"] = s.get("action", "")
                    event["outcome"] = s.get("outcome", "")
                    event["request_path"] = s.get("request_path", "")
                    event["target_id"] = s.get("target_id", "")
                    event["reason_code"] = s.get("reason_code", "")

                    event_type_split = s["event_type"].rsplit('.', 1)
                    if len(event_type_split) > 1 and event_type_split[1] in ["start", "end"]:
                        event["event_type"] = event_type_split[0]  # ex: compute.instance.create
                    else:
                        event["event_type"] = s["event_type"]  # ex: compute.instance.volume.attach

                    i = 0
                    len_hits = len(h["inner_hits"]["request_events"]["hits"]["hits"])
                    for inner_hit in h["inner_hits"]["request_events"]["hits"]["hits"]:
                        e = inner_hit["_source"]
                        timestamp = inner_hit["sort"][0]
                        event["state"] = e["state"]
                        if i == 0:
                            event["start_timestamp"] = timestamp
                        if i == len_hits - 1:
                            event["end_timestamp"] = timestamp
                        i += 1
                    if "end_timestamp" in event:
                        event["duration"] = event["end_timestamp"] - event["start_timestamp"]
                    events.append(event)
                except KeyError:
                    LOG.warning("Event params key error occurred.")
                    pass
                except IndexError:
                    LOG.warning("Event params index error occurred.")
                    pass
        except KeyError as ex:
            LOG.error("Could not execute search command on Opensearch: %s", str(ex))
        except IndexError as ex:
            LOG.error("Could not execute search command on Opensearch: %s", str(ex))
        except opensearchpy_exceptions.TransportError as ex:
            LOG.error("Opensearch Transport Error: %s", str(ex))

        return events

    def get_sub_events(self, request_id):
        if not self.check_connection():
            return []

        query = {
            "size": 100,
            "sort": [{"timestamp": {"order": "asc"}}],
            "query": {"term": {"request_id": request_id}}
        }

        sub_events = list()
        try:
            res = self.client.search(index=self._get_search_pattern(self.index_name), body=query)
            for h in res["hits"]["hits"]:
                s = h["_source"]
                sub_events.append({
                    "message_id": s.get("message_id", ""),
                    "event_type": s.get("event_type", ""),
                    "state": s.get("state", ""),
                    "timestamp": s.get("timestamp", ""),
                    "resource_id": s.get("resource_id", ""),
                    "resource_type": s.get("resource_type", ""),
                    "display_name": s.get("display_name", ""),
                    "user_id": s.get("user_id", ""),
                    "user_name": s.get("user_name", ""),
                    "project_id": s.get("project_id", ""),
                    "old_state": s.get("old_state", ""),
                    "instance_type": s.get("instance_type", ""),
                    "host": s.get("host", ""),
                })
        except Exception as ex:
            LOG.error("Could not fetch sub events for request_id %s: %s",
                      request_id, str(ex))

        return sub_events

    @staticmethod
    def build_query(resource_id=None, project_id=None, pagination_from=0, size=10,
                    hidden_events=None):
        event_query = {
            "from": pagination_from,
            "size": size,
            "sort": [
                {"timestamp": {"order": "desc"}}
            ],
            "collapse": {
                "field": "request_id",
                "inner_hits": {
                    "name": "request_events",
                    "size": 100,
                    "sort": [{"timestamp": {"order": "asc"}}],
                    "_source": {
                        "includes": [
                            "timestamp",
                            "event_type",
                            "state"
                        ]
                    }
                }
            }
        }

        must_clauses = []
        must_not_clauses = []

        if project_id is not None:
            must_clauses.append({"match": {"project_id": project_id}})
        if resource_id is not None:
            must_clauses.append({"match": {"resource_id": resource_id}})
        if hidden_events:
            must_not_clauses.append({"terms": {"event_type": hidden_events}})

        if must_clauses or must_not_clauses:
            filter_query = {"bool": {}}
            if must_clauses:
                filter_query["bool"]["must"] = must_clauses
            if must_not_clauses:
                filter_query["bool"]["must_not"] = must_not_clauses
        else:
            filter_query = {"match_all": {}}

        event_query["query"] = filter_query
        return event_query
