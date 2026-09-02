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

import datetime
from oslo_config import cfg
import pecan
from pecan import rest
import six
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan

from safir_cloud_watcher.db import api as db_api
from safir_cloud_watcher.licence.licence_checker import LicenceChecker
from safir_cloud_watcher.common import utils as safir_cloud_watcher_utils

CONF = cfg.CONF


class Licence(wtypes.Base):

    licence_key = wtypes.text  # encrypted licence key
    destination_address = wtypes.text  # Company name of the licence
    licence_valid = bool
    valid_until = datetime.datetime
    limit = int
    notification_address = wtypes.text  # e-mail address of the cloud admin

    @classmethod
    def sample(cls, licence_key):
        return cls(licence_key=licence_key)

    def to_json(self):
        res_dict = {'licence_key': self.licence_key}
        return res_dict


class LicenceController(rest.RestController):

    @wsme_pecan.wsexpose(Licence)
    def get_all(self):
        ctx = pecan.request.context
        ctx.can('licence:show')

        licence = Licence()
        licence_checker = LicenceChecker(ctx)
        try:
            l = db_api.get_licence(ctx)
            licence_info = licence_checker.check_licence()
            licence.licence_key = l.licence_key
            licence.licence_valid = licence_info.licence_status in (safir_cloud_watcher_utils.LICENCE_STATUS.LICENCE_VALID,
                                                                    safir_cloud_watcher_utils.LICENCE_STATUS.DUE_DATE_SOON)
            licence.destination_address = licence_info.destination_address
            licence.valid_until = licence_info.valid_until
            licence.notification_address = licence_info.notification_address
            licence.limit = licence_checker.get_limit()

            return licence
        except Exception as e:
            pecan.abort(404, six.text_type(e))

    @wsme_pecan.wsexpose(body=Licence,
                         status_code=200)
    def put(self, info):
        ctx = pecan.request.context
        ctx.can('licence:update')

        try:
            licence = Licence()

            licence_checker = LicenceChecker(ctx)
            licence_checker.set_licence(info.licence_key, info.notification_address)

            l = db_api.get_licence(ctx)

            licence_info = licence_checker.check_licence()
            licence.licence_key = l.licence_key
            licence.licence_valid = licence_info.licence_status in (safir_cloud_watcher_utils.LICENCE_STATUS.LICENCE_VALID,
                                                                    safir_cloud_watcher_utils.LICENCE_STATUS.DUE_DATE_SOON)
            licence.destination_address = licence_info.destination_address
            licence.valid_until = licence_info.valid_until
            licence.notification_address = licence_info.notification_address
            licence.limit = licence_checker.get_limit()

            return licence
        except Exception as e:
            pecan.abort(404, six.text_type(e))

    @wsme_pecan.wsexpose(status_code=204)
    def delete(self):
        ctx = pecan.request.context
        ctx.can('licence:delete')

        try:
            db_api.delete_licence(ctx)
        except Exception as e:
            pecan.abort(404, six.text_type(e))
