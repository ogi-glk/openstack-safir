# Copyright 2012-2014 eNovance <licensing@enovance.com>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
import cotyledon
from oslo_config import cfg
from oslo_log import log
import oslo_messaging
import time

from safir_cloud_watcher.event.event_manager import EventEndpoint
from safir_cloud_watcher.i18n import _
from safir_cloud_watcher import messaging

LOG = log.getLogger(__name__)


notification_opts = [
    cfg.BoolOpt('ack_on_event_error',
                default=True,
                help='Acknowledge message when event persistence fails.'),
    cfg.MultiStrOpt('messaging_urls',
                    default=[],
                    secret=True,
                    help="Messaging URLs to listen for notifications. "
                         "Example: rabbit://user:pass@host1:port1"
                         "[,user:pass@hostN:portN]/virtual_host "
                         "(DEFAULT/transport_url is used if empty). This "
                         "is useful when you have dedicate messaging nodes "
                         "for each service, for example, all nova "
                         "notifications go to rabbit-nova:5672, while all "
                         "cinder notifications go to rabbit-cinder:5672."),
    cfg.ListOpt('supported_events',
                default=["*"],
                help="This option can be used to filter the events for recording. "
                     "To define the list of included event, use the event_name syntax. "
                     "To define the list of excluded event, use the !event_name syntax. "
                     "For example ['compute.*','storage.*','!disk.*']"),
    cfg.IntOpt('batch_size',
               default=1, min=1,
               help='Number of notification messages to wait before '
                    'publishing them.'),
    cfg.IntOpt('batch_timeout',
               help='Number of seconds to wait before dispatching samples '
                    'when batch_size is not reached (None means indefinitely).'
               ),
    cfg.IntOpt('workers',
               default=1,
               min=1,
               help='Number of workers for notification service, '
                    'default value is 1.'),
    cfg.StrOpt('definitions_cfg_file',
               default="event_definitions.yaml",
               help="Configuration file for event definitions."
               ),
    cfg.BoolOpt('drop_unmatched_notifications',
                default=False,
                help='Drop notifications if no event definition matches. '
                '(Otherwise, we convert them with just the default traits)'),
    cfg.MultiStrOpt('store_raw',
                    default=[],
                    help='Store the raw notification for select priority '
                    'levels (info and/or error). By default, raw details are '
                    'not captured.'),
    cfg.IntOpt('max_parallel_requests',
               default=64,
               min=1,
               help='Maximum number of parallel requests for '
               'services to handle at the same time.'),
    cfg.ListOpt('service_users',
                default=['nova', 'cinder', 'neutron', 'glance', 'heat',
                         'octavia', 'manila', 'magnum', 'masakari', 'zun',
                         'watcher', 'barbican', 'placement', 'swift'],
                help='List of service user names to exclude from '
                     'identity.authenticate events. Only real user '
                     'logins will be recorded.'),
]

CONF = cfg.CONF
CONF.register_opts(notification_opts, 'notification')


class EventService(cotyledon.Service):
    """Notification service.

    When running multiple agents, additional queuing sequence is required for
    inter process communication. Each agent has two listeners: one to listen
    to the main OpenStack queue and another listener(and notifier) for IPC to
    divide pipeline sink endpoints. Coordination should be enabled to have
    proper active/active HA.
    """

    NOTIFICATION_NAMESPACE = 'safir_cloud_watcher.notification.v2'

    def __init__(self, worker_id, conf, coordination_id=None):
        super(EventService, self).__init__(worker_id)
        self.startup_delay = worker_id
        self.conf = conf
        self.listeners = []

    def get_targets(self):
        """Return a sequence of oslo_messaging.Target

        This sequence is defining the exchange and topics to be connected.
        """
        exchanges = ['nova', 'glance', 'neutron', 'cinder', 'heat',
                             'keystone', 'trove', 'zaqar', 'swift',
                             'ceilometer', 'magnum', 'dns', 'ironic', 'aodh']
        # TODO!: burada conf.notification.supported_events kullanılabilir mi?
        topics = (self.conf.notification_topics
                  if 'notification_topics' in self.conf
                  else self.conf.oslo_messaging_notifications.topics)
        return [oslo_messaging.Target(topic=topic, exchange=exchange)
                for topic in set(topics)
                for exchange in exchanges]
                #set(self.conf.notification.notification_control_exchanges)]

    @staticmethod
    def _log_missing_pipeline(names):
        LOG.error(_('Could not load the following pipelines: %s'), names)

    def run(self):
        # Delay startup so workers are jittered
        time.sleep(self.startup_delay)

        super(EventService, self).run()


        # FIXME(sileht): endpoint uses the notification_topics option
        # and it should not because this is an oslo_messaging option
        # not a ceilometer. Until we have something to get the
        # notification_topics in another way, we must create a transport
        # to ensure the option has been registered by oslo_messaging.
        messaging.get_notifier(messaging.get_transport(self.conf), '')

        endpoints = [EventEndpoint(self.conf)]
        LOG.debug("Loaded endpoint %s for events.",
                  endpoints)

        targets = self.get_targets()

        urls = self.conf.notification.messaging_urls or [None]
        for url in urls:
            transport = messaging.get_transport(self.conf, url)
            # NOTE(gordc): ignore batching as we want pull
            # to maintain sequencing as much as possible.
            listener = messaging.get_batch_notification_listener(
                transport, targets, endpoints, allow_requeue=True,
                batch_size=self.conf.notification.batch_size,
                batch_timeout=self.conf.notification.batch_timeout)
            listener.start(
                override_pool_size=self.conf.notification.max_parallel_requests
            )
            self.listeners.append(listener)

    @staticmethod
    def kill_listeners(listeners):
        # NOTE(gordc): correct usage of oslo.messaging listener is to stop(),
        # which stops new messages, and wait(), which processes remaining
        # messages and closes connection
        for listener in listeners:
            listener.stop()
            listener.wait()

    def terminate(self):
        self.kill_listeners(self.listeners)

        super(EventService, self).terminate()
