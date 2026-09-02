# -*- coding: utf-8 -*-
# Copyright 2021 TUBITAK B3LAB
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

from safir_cloud_watcher.common import utils
from safir_cloud_watcher.db import api as db_api
from safir_cloud_watcher.licence.helper import Helper

from datetime import datetime
from datetime import timedelta
import logging
import subprocess

LOG = logging.getLogger(__name__)
N_DAYS_AGO = 10  # start notifications N days before due date
LICENCE_LENGTH = 59  # licence format: TUBITAK_BILGEM_DEPLOYMENT_ADDRES_20260101000500_SAFIR_BULUT


class LicenceInfo:
    licence_status = None
    destination_address = None
    valid_until = None
    notification_address = None
    notification_counter = None
    last_notification_time = None


class LicenceChecker:
    """ Check licence

        If licence is invalid, licence watcher will send e-mail
        to the cloud admin, and other Safir services will stop working
    """
    def __init__(self, context):
        self.context = context
        self.limit = 0
        self.poc = 0
        self.helper = Helper()

    @staticmethod
    def get_hardware_id():
        # process needs to be started by sudoers
        proc = subprocess.Popen('sudo dmidecode -s system-uuid'.split(),
                                stdout=subprocess.PIPE)
        id = proc.stdout.read().decode("utf-8").strip()

        return id

    def get_limit(self):
        return self.limit

    def is_poc(self):
        return bool(self.poc)

    def set_licence(self, encrypted_licence_key, notification_address):
        try:
            notification_counter = utils.MAX_NOTIFICATION_COUNT
            encrypted_notification_counter = self.helper.encrypt(notification_counter)
            db_api.set_licence(self.context, {"licence_key": encrypted_licence_key,
                                              "notification_address": notification_address,
                                              "notification_counter": encrypted_notification_counter})
        except Exception:
            pass

    def set_notification(self, count):
        try:
            encrypted_notification_counter = self.helper.encrypt(count)
            encrypted_last_notification_time = self.helper.encrypt(utils.utcnow_ts())
            db_api.set_licence(self.context, {"notification_counter": encrypted_notification_counter,
                                              "last_notification_time": encrypted_last_notification_time})
        except Exception:
            pass

    def check_licence(self):

        notification_counter = utils.MAX_NOTIFICATION_COUNT
        last_notification_time = datetime.fromtimestamp(0)

        licence_info = LicenceInfo()
        licence_info.licence_status = utils.LICENCE_STATUS.LICENCE_NOT_FOUND
        licence_info.destination_address = None
        licence_info.valid_until = None
        licence_info.notification_address = None
        licence_info.notification_counter = notification_counter
        licence_info.last_notification_time = last_notification_time

        try:
            licence = db_api.get_licence(self.context)
        except Exception:
            LOG.error("Licence key not found.")
            return licence_info

        notification_address = licence.notification_address

        encrypted_licence_key = licence.licence_key
        encrypted_notification_counter = licence.notification_counter
        encrypted_last_notification_timestamp = licence.last_notification_time
        last_notification_timestamp = 0
        try:
            notification_counter = int(self.helper.decrypt(encrypted_notification_counter))
            if encrypted_last_notification_timestamp is not None:
                last_notification_timestamp = int(self.helper.decrypt(encrypted_last_notification_timestamp))
        except ValueError:
            notification_counter = utils.MAX_NOTIFICATION_COUNT

        last_notification_time = utils.ts2utc(last_notification_timestamp)

        licence_info.notification_address = notification_address
        licence_info.notification_counter = notification_counter
        licence_info.last_notification_time = last_notification_time

        if encrypted_licence_key is None or len(encrypted_licence_key) == 0:
            LOG.error("Licence key not found.")
            return licence_info

        licence_key = self.helper.decrypt(encrypted_licence_key)
        if len(licence_key) != LICENCE_LENGTH:
            licence_info.licence_status = utils.LICENCE_STATUS.LICENCE_NOT_VALID
            LOG.error("Licence key not valid.")
            return licence_info

        destination_address_ = licence_key[15:32].strip()
        valid_until_str_ = licence_key[33:41]
        valid_until_ = datetime.strptime(valid_until_str_, '%Y%m%d')

        self.limit = int(licence_key[41:46])

        self.poc = int(licence_key[46:47])

        licence_info.destination_address = destination_address_
        licence_info.valid_until = valid_until_
        if datetime.now() > valid_until_:
            licence_info.licence_status = utils.LICENCE_STATUS.DUE_DATE_EXCEEDED
            LOG.warning("Licence expired.")
            return licence_info

        n_days_ago = valid_until_ - timedelta(days=N_DAYS_AGO)
        if datetime.now() > n_days_ago:
            licence_info.licence_status = utils.LICENCE_STATUS.DUE_DATE_SOON
            LOG.warning("Licence expiring soon.")
            return licence_info

        licence_info.licence_status = utils.LICENCE_STATUS.LICENCE_VALID
        if self.poc == 1:
            LOG.info("POC Licence valid until " + valid_until_str_ + " for " + str(self.limit) + " resources.")
        else:
            LOG.info("Licence valid until " + valid_until_str_ + " for " + str(self.limit) + " resources.")

        return licence_info
