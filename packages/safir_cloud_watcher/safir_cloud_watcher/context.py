# Copyright 2024 TUBITAK
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""
RequestContext: context for db requests
"""
from http import HTTPStatus

from oslo_context import context
from oslo_db.sqlalchemy import enginefacade
from oslo_log import log as logging
from oslo_utils import timeutils

from safir_cloud_watcher import policy

LOG = logging.getLogger(__name__)


class Forbidden(Exception):
    msg_fmt = "Forbidden"
    code = HTTPStatus.FORBIDDEN


@enginefacade.transaction_context_provider
class RequestContext(context.RequestContext):
    """Security context and request information.

    Represents the user taking a given action within the system.

    """
    FROM_DICT_EXTRA_KEYS = [
        'read_deleted', 'remote_address',
        'timestamp', 'service_catalog',
    ]

    def __init__(self, user_id=None, project_id=None,
                 is_admin=None, read_deleted="no",
                 roles=None, remote_address=None, timestamp=None,
                 request_id=None, auth_token=None, overwrite=True,
                 user_name=None, project_name=None, service_catalog=None,
                 **kwargs):
        """:param read_deleted: 'no' indicates deleted records are hidden,
                'yes' indicates deleted records are visible,
                'only' indicates that *only* deleted records are visible.

           :param overwrite: Set to False to ensure that the greenthread local
                copy of the index is not overwritten.

           :param kwargs: Extra arguments that might be present, but we ignore
                because they possibly came in from older rpc messages.
        """
        user = kwargs.pop('user', None)
        tenant = kwargs.pop('tenant', None)
        super(RequestContext, self).__init__(
            auth_token=auth_token,
            user_id=user_id or user,
            project_id=project_id or tenant,
            domain_id=kwargs.pop('domain', None),
            user_domain_id=kwargs.pop('user_domain', None),
            project_domain_id=kwargs.pop('project_domain', None),
            is_admin=is_admin,
            read_only=kwargs.pop('read_only', False),
            show_deleted=kwargs.pop('show_deleted', False),
            request_id=request_id,
            resource_uuid=kwargs.pop('resource_uuid', None),
            overwrite=overwrite,
            roles=roles,
            user_name=user_name,
            project_name=project_name,
            is_admin_project=kwargs.pop('is_admin_project', True),
            global_request_id=kwargs.pop('global_request_id', None))
        # oslo_context's RequestContext.to_dict() generates this field, we can
        # safely ignore this as we don't use it.
        kwargs.pop('user_identity', None)
        if kwargs:
            LOG.debug('Arguments dropped when creating context: %s',
                      str(kwargs))

        if read_deleted is None:
            # If we did not get a value for read_deleted, ensure we default
            # it to "no" as code expects it to be a string.
            self.read_deleted = 'no'
        else:
            self.read_deleted = read_deleted
        self.remote_address = remote_address
        if not timestamp:
            timestamp = timeutils.utcnow()
        if isinstance(timestamp, str):
            timestamp = timeutils.parse_strtime(timestamp)
        self.timestamp = timestamp

        if service_catalog:
            # Only include required parts of service_catalog
            self.service_catalog = [
                s for s in service_catalog if s.get('type') in (
                    'compute', 'identity')]
        else:
            # if list is empty or none
            self.service_catalog = []

        if self.is_admin is None:
            self.is_admin = policy.check_is_admin(self)

    def _get_read_deleted(self):
        return self._read_deleted

    def _set_read_deleted(self, read_deleted):
        if read_deleted not in ('no', 'yes', 'only'):
            raise ValueError(("read_deleted can only be one of 'no', "
                              "'yes' or 'only', not %r") % read_deleted)
        self._read_deleted = read_deleted

    def _del_read_deleted(self):
        del self._read_deleted

    read_deleted = property(_get_read_deleted, _set_read_deleted,
                            _del_read_deleted)

    def can(self, action, target=None, fatal=True):
        """Verifies that the given action is valid on the target in this
        context.

        :param action: string representing the action to be checked.
        :param target: dictionary representing the object of the action
            for object creation this should be a dictionary representing the
            location of the object e.g. ``{'project_id': context.project_id}``.
            If None, then this default target will be considered:
            {'project_id': self.project_id, 'user_id': self.user_id}
        :param fatal: if False, will return False when an exception.Forbidden
           occurs.

        :raises masakari.exception.Forbidden: if verification fails and fatal
            is True.

        :return: returns a non-False value (not necessarily "True") if
            authorized and False if not authorized and fatal is False.
        """
        if target is None:
            target = {'project_id': self.project_id,
                      'user_id': self.user_id}
        try:
            return policy.authorize(self, action, target)
        except Forbidden:
            if fatal:
                raise
            return False

    def to_policy_values(self):
        policy = super(RequestContext, self).to_policy_values()
        policy['is_admin'] = self.is_admin
        return policy

    def __str__(self):
        return "<Context %s>" % self.to_dict()


def get_admin_context(read_deleted="no"):
    return RequestContext(user_id=None,
                          project_id=None,
                          is_admin=True,
                          read_deleted=read_deleted,
                          overwrite=False)
