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

import itertools

from safir_cloud_watcher.policies import base
from safir_cloud_watcher.policies import event
from safir_cloud_watcher.policies import handshake
from safir_cloud_watcher.policies import licence


def list_rules():
    return itertools.chain(
        base.list_rules(),
        event.list_rules(),
        handshake.list_rules(),
        licence.list_rules(),
    )
