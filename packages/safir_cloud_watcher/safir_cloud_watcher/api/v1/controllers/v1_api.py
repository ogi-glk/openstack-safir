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

from pecan import rest

from safir_cloud_watcher.api.v1.controllers import event as event_api
from safir_cloud_watcher.api.v1.controllers import handshake as handshake_api
from safir_cloud_watcher.api.v1.controllers import licence as licence_api


class V1Controller(rest.RestController):
    """API version 1 controller.

    """
    events = event_api.EventController()
    handshake = handshake_api.HandshakeController()
    licence = licence_api.LicenceController()
