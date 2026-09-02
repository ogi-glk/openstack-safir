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

import fnmatch

from oslo_log import log
import oslo_messaging
from stevedore import extension

from safir_cloud_watcher.event.helpers import converter
from safir_cloud_watcher.event.storage.opensearch import OpenSearchStore

LOG = log.getLogger(__name__)


class EventEndpoint(object):
    """Base Endpoint for plugins that support the notification API."""

    event_types = []
    """List of strings to filter messages on."""

    def __init__(self, conf):
        LOG.info('Loading event definitions')
        # NOTE(gordc): this is filter rule used by oslo.messaging to dispatch
        # messages to an endpoint.
        if self.event_types:
            self.filter_rule = oslo_messaging.NotificationFilter(
                event_type='|'.join(self.event_types))
        self.conf = conf
        self.event_converter = converter.setup_events(
            conf,
            extension.ExtensionManager(
                namespace='safir_cloud_watcher.event.helpers.trait_plugin'))

        self.store = OpenSearchStore(upgrade=True)

    @staticmethod
    def is_supported(dataset, data_name):
        # Support wildcard like storage.* and !disk.*
        # Start with negation, we consider that the order is deny, allow
        if any(fnmatch.fnmatch(data_name, datapoint[1:])
               for datapoint in dataset if datapoint[0] == '!'):
            return False

        if any(fnmatch.fnmatch(data_name, datapoint)
               for datapoint in dataset if datapoint[0] != '!'):
            return True

        # if we only have negation, we suppose the default is allow
        return all(datapoint.startswith('!') for datapoint in dataset)

    def support_event(self, event_name):
        supported_events = self.conf.notification.supported_events
        return self.is_supported(supported_events, event_name)

    def publish_events(self, events):
        if not isinstance(events, list):
            events = [events]
        supported = [e for e in events if self.support_event(e.event_type)]
        self.store.record_events(supported)

    def process_notifications(self, priority, notifications):
        """Return a sequence of Counter instances for the given message.
        """
        for message in notifications:
            try:
                event = self.event_converter.to_event(priority, message)
                if event is not None:
                    self.publish_events(event)
            except Exception:
                if not self.conf.notification.ack_on_event_error:
                    return oslo_messaging.NotificationResult.REQUEUE
                LOG.error('Fail to process a notification', exc_info=True)
        return oslo_messaging.NotificationResult.HANDLED

    @classmethod
    def _consume_and_drop(cls, notifications):
        """RPC endpoint for useless notification level"""
        # NOTE(sileht): nothing special todo here, but because we listen
        # for the generic notification exchange we have to consume all its
        # queues

    audit = _consume_and_drop
    critical = _consume_and_drop
    debug = _consume_and_drop
    #error = _consume_and_drop
    #info = _consume_and_drop
    sample = _consume_and_drop
    warn = _consume_and_drop

    def info(self, notifications):
        """Convert message at info level to Event.

        :param notifications: list of notifications
        """
        return self.process_notifications('info', notifications)

    def error(self, notifications):
        """Convert message at error level to Event.

        :param notifications: list of notifications
        """
        return self.process_notifications('error', notifications)
