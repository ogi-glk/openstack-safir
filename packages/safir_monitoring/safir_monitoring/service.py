# -*- coding: utf-8 -*-
# Copyright 2014 Objectif Libre
# Copyright 2017 TUBITAK B3LAB
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
from oslo_log import log

from safir_monitoring import version


def prepare_service(config_file=None):
    log.register_options(cfg.CONF)
    log.set_defaults()

    if config_file:
        config_files = [config_file]
    else:
        config_files = ['/etc/safir_monitoring/safir_monitoring.conf']

    argv = ['main.py', '--config-file', config_files[0]]

    cfg.CONF(argv[1:], project='safir_monitoring', validate_default_values=True,
             version=version.version_info.version_string(),
             default_config_files=config_files)
    log.setup(cfg.CONF, 'safir_monitoring')
