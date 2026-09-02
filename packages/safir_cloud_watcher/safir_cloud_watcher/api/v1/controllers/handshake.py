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

from oslo_config import cfg
import pecan
from pecan import rest
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan

from safir_cloud_watcher.common import utils as safir_cloud_watcher_utils
from safir_cloud_watcher.licence.licence_checker import LicenceChecker
from safir_cloud_watcher.licence.helper import Helper

CONF = cfg.CONF


class Handshake(wtypes.Base):

    safir_app = wtypes.text
    time = wtypes.text

    @classmethod
    def sample(cls, safir_app, time):
        return cls(safir_app=safir_app,
                   time=time)

    def to_json(self):
        res_dict = {'safir_app': self.safir_app,
                    'time': self.time}
        return res_dict


class HandshakeController(rest.RestController):
    @wsme_pecan.wsexpose(Handshake, wtypes.text)
    def get_one(self, safir_app):
        ctx = pecan.request.context
        ctx.can('handshake:show')

        licence_checker = LicenceChecker(ctx)
        licence_info = licence_checker.check_licence()
        if licence_info.licence_status not in (safir_cloud_watcher_utils.LICENCE_STATUS.LICENCE_VALID,
                                               safir_cloud_watcher_utils.LICENCE_STATUS.DUE_DATE_SOON) :
            if licence_info.notification_counter >= safir_cloud_watcher_utils.MAX_NOTIFICATION_COUNT:
                pecan.abort(404, 'Licence not valid.')

        cryptographer = Helper()
        now = cryptographer.encrypt(safir_cloud_watcher_utils.utcnow())
        handshake = Handshake()
        handshake.safir_app = safir_app
        handshake.time = now
        return handshake
