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

import logging

from safir_cloud_watcher.common.notification.notifier import Notifier
from safir_cloud_watcher.common import utils
from safir_cloud_watcher.openstack.nova import NovaConnector

LOG = logging.getLogger(__name__)


class Operation(object):
    """ Disable compute nodes according to the given operation type.
    """

    def __init__(self):
        self.nova = NovaConnector()
        # E-mail notifier
        self.informer = Notifier()

    def send_notification_mail(self, operation_type, notification_address):
        self.informer.send_notification_mail(operation_type, notification_address)

    def run(self, licence_status,
            valid_until,
            notification_address,
            notification_counter,
            used_resource_count_exceeding_limit):
        """Running operation

        Limit compute resources when licence quota exceeded.

        :return:
        """
        operation_type = utils.OPERATION_TYPE.NONE
        if licence_status == utils.LICENCE_STATUS.DUE_DATE_SOON:
            notification_type = "Licence will expire at " + valid_until.strftime("%d-%m-%Y")
            self.send_notification_mail(notification_type, notification_address)

        notification_type = None
        if licence_status == utils.LICENCE_STATUS.LICENCE_NOT_FOUND:
            notification_type = "Licence key not found"
            operation_type = utils.OPERATION_TYPE.DISABLE_ALL_HYPERVISORS
        elif licence_status == utils.LICENCE_STATUS.LICENCE_NOT_VALID:
            notification_type = "Licence not valid"
            operation_type = utils.OPERATION_TYPE.DISABLE_ALL_HYPERVISORS
        elif licence_status == utils.LICENCE_STATUS.DUE_DATE_EXCEEDED:
            notification_type = "Licence due date exceeded"
            operation_type = utils.OPERATION_TYPE.DISABLE_ALL_HYPERVISORS
        elif used_resource_count_exceeding_limit > 0:
            notification_type = "Licence limit exceeded"
            operation_type = utils.OPERATION_TYPE.DISABLE_SOME_HYPERVISORS

        if notification_type is not None:
            notification_counter += 1
            self.send_notification_mail(notification_type, notification_address)
        else:
            notification_counter = 0

        if notification_counter >= utils.MAX_NOTIFICATION_COUNT:
            if operation_type == utils.OPERATION_TYPE.DISABLE_ALL_HYPERVISORS:
                # disable all compute nodes...
                # existing servers will still be reachable
                # nodes will be disabled periodically
                self.nova.disable_all_hosts()
                # TODO!: do we need to enable the hosts if licence becomes valid?
            elif operation_type == utils.OPERATION_TYPE.DISABLE_SOME_HYPERVISORS:
                # disable whichever node has the least vms
                LOG.info('One node with least vm will be shut down in this period.')
                self.nova.disable_one_host()

        return notification_counter
