import json
import socket
from datetime import datetime, timezone

from oslo_config import cfg
from oslo_log import log

LOG = log.getLogger(__name__)
CONF = cfg.CONF

syslog_forward_opts = [
    cfg.BoolOpt('enabled',
                default=False,
                help='Enable forwarding events to a remote syslog server.'),
    cfg.StrOpt('host',
               default='',
               help='Remote syslog server host/IP.'),
    cfg.IntOpt('port',
               default=514,
               help='Remote syslog server port.'),
    cfg.StrOpt('protocol',
               default='udp',
               help='Syslog protocol: udp or tcp.'),
    cfg.StrOpt('facility',
               default='local0',
               help='Syslog facility (local0-local7).'),
    cfg.ListOpt('exclude_fields',
                default=['user_id', 'resource_id', 'volume_type', 'image_id',
                         'message_id'],
                help='List of fields to exclude from syslog messages.'),
]

CONF.register_opts(syslog_forward_opts, 'syslog_forward')

FACILITY_MAP = {
    'local0': 16, 'local1': 17, 'local2': 18, 'local3': 19,
    'local4': 20, 'local5': 21, 'local6': 22, 'local7': 23,
}


class SyslogForwarder(object):
    """Forwards event data to a remote syslog server via UDP or TCP."""

    def __init__(self):
        self._sock = None
        self._enabled = CONF.syslog_forward.enabled
        self._host = CONF.syslog_forward.host
        self._port = CONF.syslog_forward.port
        self._protocol = CONF.syslog_forward.protocol.lower()
        facility_name = CONF.syslog_forward.facility.lower()
        self._facility = FACILITY_MAP.get(facility_name, 16)
        
        self._exclude_fields = set(CONF.syslog_forward.exclude_fields)

        if self._enabled and not self._host:
            LOG.warning("Syslog forwarding enabled but no host configured. Disabling.")
            self._enabled = False

        if self._enabled:
            LOG.info("Syslog forwarding enabled: %s://%s:%s (facility=%s)",
                     self._protocol, self._host, self._port, facility_name)

    @property
    def enabled(self):
        return self._enabled

    def _get_socket(self):
        if self._sock is not None:
            return self._sock
        try:
            if self._protocol == 'tcp':
                self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._sock.settimeout(5)
                self._sock.connect((self._host, self._port))
            else:
                self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        except Exception as ex:
            LOG.error("Could not create syslog socket: %s", str(ex))
            self._sock = None
        return self._sock

    def _build_syslog_message(self, event_data):
        # RFC 5424: <priority>version timestamp hostname app-name procid msgid structured-data msg
        # priority = facility * 8 + severity (6 = INFO)
        priority = self._facility * 8 + 6
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        hostname = socket.gethostname()

        # Clean None values for JSON serialization
        clean_data = {k: v for k, v in event_data.items()
                      if v is not None and k not in self._exclude_fields}
        msg = json.dumps(clean_data, default=str)

        syslog_msg = "<%d>1 %s %s safir-cloud-watcher event_manager - - %s" % (
            priority, timestamp, hostname, msg)
        return syslog_msg

    def forward(self, event_data):
        if not self._enabled:
            return
        try:
            msg = self._build_syslog_message(event_data)
            sock = self._get_socket()
            if sock is None:
                return
            encoded = msg.encode('utf-8')
            if self._protocol == 'tcp':
                sock.sendall(encoded + b'\n')
            else:
                sock.sendto(encoded, (self._host, self._port))
        except (ConnectionError, OSError) as ex:
            LOG.warning("Syslog forward failed, reconnecting: %s", str(ex))
            self._sock = None
        except Exception as ex:
            LOG.error("Syslog forward error: %s", str(ex))

    def forward_batch(self, events_sources):
        if not self._enabled:
            return
        for source in events_sources:
            self.forward(source)
