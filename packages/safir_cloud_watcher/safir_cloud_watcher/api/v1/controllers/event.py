# -*- coding: utf-8 -*-
# Copyright 2021 TUBITAK B3LAB
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

import os

from oslo_config import cfg
from oslo_log import log as logging
import pecan
from pecan import rest
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan
import yaml

from safir_cloud_watcher.event.storage.opensearch import OpenSearchStore

LOG = logging.getLogger(__name__)
CONF = cfg.CONF

_HIDDEN_EVENTS = None


def _load_hidden_events():
    global _HIDDEN_EVENTS
    if _HIDDEN_EVENTS is not None:
        return _HIDDEN_EVENTS
    import safir_cloud_watcher.event.helpers.converter as converter
    hidden_file = os.path.join(converter.BASE_DIR, '../data/hidden_events.yaml')
    try:
        with open(hidden_file) as f:
            _HIDDEN_EVENTS = yaml.safe_load(f) or []
    except Exception as ex:
        LOG.warning("Could not load hidden events file: %s", str(ex))
        _HIDDEN_EVENTS = []
    return _HIDDEN_EVENTS


class Event(wtypes.Base):
    project_id = wtypes.text
    user_id = wtypes.text
    resource_id = wtypes.text
    resource_type = wtypes.text
    display_name = wtypes.text
    request_id = wtypes.text
    event_type = wtypes.text
    start_timestamp = int
    end_timestamp = int
    duration = int
    state = wtypes.text

    def to_json(self):
        res_dict = {'project_id': self.project_id,
                    'user_id': self.user_id,
                    'resource_id': self.resource_id,
                    'resource_type': self.resource_type,
                    'display_name': self.display_name,
                    'request_id': self.request_id,
                    'event_type': self.event_type,
                    'start_timestamp': self.start_timestamp,
                    'end_timestamp': self.end_timestamp,
                    'duration': self.duration,
                    'state': self.state}
        return res_dict


class SubEvent(wtypes.Base):
    message_id = wtypes.text
    event_type = wtypes.text
    state = wtypes.text
    old_state = wtypes.text
    timestamp = wtypes.text
    resource_id = wtypes.text
    resource_type = wtypes.text
    display_name = wtypes.text
    user_id = wtypes.text
    user_name = wtypes.text
    project_id = wtypes.text
    instance_type = wtypes.text
    host = wtypes.text


class SubEventCollection(wtypes.Base):
    sub_events = [SubEvent]


class EventCollection(wtypes.Base):
    events = [Event]


class SubEventController(rest.RestController):
    @wsme_pecan.wsexpose(SubEventCollection, wtypes.text)
    def get_all(self, request_id=""):
        ctx = pecan.request.context
        ctx.can('event:list')

        if not request_id or request_id == "Unset":
            return SubEventCollection(sub_events=[])

        store = OpenSearchStore()
        sub_events = store.get_sub_events(request_id)

        sub_event_list = list()
        for se in sub_events:
            s = SubEvent()
            s.message_id = se["message_id"]
            s.event_type = se["event_type"]
            s.state = se["state"]
            s.old_state = se.get("old_state", "")
            s.timestamp = se["timestamp"]
            s.resource_id = se["resource_id"]
            s.resource_type = se["resource_type"]
            s.display_name = se["display_name"]
            s.user_id = se["user_id"]
            s.user_name = se.get("user_name", "")
            s.project_id = se["project_id"]
            s.instance_type = se.get("instance_type", "")
            s.host = se.get("host", "")
            sub_event_list.append(s)

        return SubEventCollection(sub_events=sub_event_list)


class EventController(rest.RestController):
    sub_events = SubEventController()

    @wsme_pecan.wsexpose(EventCollection, wtypes.text, int, int)
    def get_all(self, resource_id="", pagination_from=0, size=10):
        ctx = pecan.request.context
        ctx.can('event:list')

        if resource_id == "Unset" or resource_id == "":
            resource_id = None

        project_id = None
        if not ctx.is_admin:
            project_id = ctx.project_id

        store = OpenSearchStore()
        hidden_events = _load_hidden_events()
        events = store.get_events(resource_id, project_id, pagination_from=pagination_from, size=size,
                                  hidden_events=hidden_events)

        event_list = list()
        for event in events:
            e = Event()
            e.project_id = event["project_id"]
            e.user_id = event["user_id"]
            e.resource_id = event["resource_id"]
            e.resource_type = event["resource_type"]
            e.display_name = event["display_name"]
            e.request_id = event["request_id"]
            e.event_type = event["event_type"]
            e.start_timestamp = event["start_timestamp"]
            e.end_timestamp = event.get("end_timestamp", event["start_timestamp"])  # set start timestamp if instant event
            e.duration = event.get("duration", -1)
            e.state = event["state"]

            event_list.append(e)

        return EventCollection(events=event_list)
