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

import datetime
import logging
from oslo_config import cfg
from safir_cloud_watcher.cloud_operator.operation import Operation
from safir_cloud_watcher.common import utils
from safir_cloud_watcher.licence.licence_checker import LicenceChecker


# Notification e-mail options
email_notifier_opts = [
    cfg.StrOpt('email_host',
               default='',
               help="""
E-mail Host

SMTP Server host which will be used to send notification e-mails.
"""),
    cfg.StrOpt('email_port',
               default='',
               help="""
E-mail Host Port number
"""),
    cfg.StrOpt('email_host_user',
               default='',
               help="""
E-mail Host Username
"""),
    cfg.StrOpt('email_host_password',
               default='',
               help="""
E-mail Host Password
"""),
    cfg.StrOpt('email_use_tls',
               default='True',
               help="""
Use TLS protocol if True.

Possible values:

* True, False
"""),
    cfg.StrOpt('email_admin_user',
               default='',
               help="""
E-mail Administrator Username

Using send e-mail related with administration topics
""")

]

# Watcher options
watcher_opts = [
    cfg.StrOpt('method',
               default='licence_watcher',
               help="""
Watcher Method

This is used to define the watcher method.

Possible values:
* licence_watcher

"""),
]

# General options
general_opts = {
    cfg.IntOpt('attempt_number',
               default=5,
               help="""
Attempt number

When any operation failure, retry operation as many as the number of attempts

Possible values:

* Any integer value, can be either below zero.
"""),
    cfg.IntOpt('delay_time',
               default=60,
               help="""
Delay time

When any operation failure, before retry operation wait delay time.

Possible values:

* Any integer value, can be either below zero.

Related options:

* This option is define as second.
"""),
    cfg.IntOpt('mail_attempt_number',
               default=5,
               help="""
Attempt number
When e-mail send operation failure,
retry send mail as many as the number of attempts

Possible values:

* Any integer value, can be either below zero.
"""),
    cfg.StrOpt('notification_mails_to',
               default='',
               help="""
Notification e-mails will be sent to this e-mail address

Possible values:

* Any e-mail address.
"""),
}

CONF = cfg.CONF
CONF.register_opts(watcher_opts, 'watcher')
CONF.register_opts(email_notifier_opts, 'email_notifier')
CONF.register_opts(general_opts, 'general')


LOG = logging.getLogger(__name__)

# WARNING!: Decryption key is set here, the source code needs to be obfuscated

# >>> key = Fernet.generate_key()
# >>> print(key)


class LicenceWatcher:

    def __init__(self, context):
        self.operation_manager = Operation()
        self.licence_checker = LicenceChecker(context)

        super(LicenceWatcher, self).__init__()

    @property
    def enabled(self):
        """Check if the module is enabled

        :returns: bool if module is enabled
        """
        return True

    def reload_config(self):
        pass

    def process(self, used_resource_count, period):
        """Run licence watcher process

        Check compute resources, limit additional resources and
        notify by e-mail when quota exceeded.

        :param used_resource_count: Used Compute node or CPU core count
        :param period: Run period
        :return:
        """
        LOG.info('Licence watcher process started.')

        licence_info = self.licence_checker.check_licence()
        LOG.info('Licence status: %s.', licence_info.licence_status)
        if licence_info.valid_until is not None:
            LOG.info("Licence valid until: %s.", licence_info.valid_until.strftime("%d-%m-%Y"))

        t = datetime.timedelta(seconds=period)
        if licence_info.last_notification_time > utils.utcnow() - t:
            # do nothing
            return

        used_resource_count_exceeding_limit = 0
        limit = self.licence_checker.get_limit()
        if used_resource_count > limit:
            used_resource_count_exceeding_limit = used_resource_count - limit

        try:
            notification_counter = self.operation_manager.run(licence_info.licence_status,
                                                              licence_info.valid_until,
                                                              licence_info.notification_address,
                                                              licence_info.notification_counter,
                                                              used_resource_count_exceeding_limit)
        except Exception as ex:
            notification_counter = licence_info.notification_counter
            LOG.error(str(ex))

        self.licence_checker.set_notification(notification_counter)
