# -*- coding: utf-8 -*-
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

from http import HTTPStatus

from oslo_log import log as logging
from oslo_middleware import request_id

from pecan import hooks

from safir_cloud_watcher import context
from safir_cloud_watcher import messaging

LOG = logging.getLogger(__name__)


class Unauthorized(Exception):
    msg_fmt = "Not authorized."
    code = HTTPStatus.UNAUTHORIZED


class RPCHook(hooks.PecanHook):
    def __init__(self):
        pass
        #self._rpc_client = messaging.get_client()

    # def before(self, state):
    #     state.request.rpc_client = self._rpc_client


class ContextHook(hooks.PecanHook):
    def on_route(self, state):
        req = state.request
        headers = state.request.headers

        user_id = headers.get('X_USER')
        user_id = headers.get('X_USER_ID', user_id)
        if user_id is None:
            LOG.debug("Neither X_USER_ID nor X_USER found in request")
            return Unauthorized()

        roles = self._get_roles(headers)

        if 'X_TENANT_ID' in headers:
            # This is the new header since Keystone went to ID/Name
            project_id = headers['X_TENANT_ID']
        else:
            # This is for legacy compatibility
            project_id = headers['X_TENANT']
        project_name = headers.get('X_TENANT_NAME')
        user_name = headers.get('X_USER_NAME')

        req_id = req.environ.get(request_id.ENV_REQUEST_ID)

        # Get the auth token
        auth_token = headers.get('X_AUTH_TOKEN',
                                 headers.get('X_STORAGE_TOKEN'))

        # Build a context, including the auth_token...
        remote_address = req.remote_addr
        # if CONF.use_forwarded_for:
        #    remote_address = headers.get('X-Forwarded-For', remote_address)

        #service_catalog = None
        #if headers.get('X_SERVICE_CATALOG') is not None:
        #    try:
        #        catalog_header = headers.get('X_SERVICE_CATALOG')
        #        service_catalog = jsonutils.loads(catalog_header)
        #    except ValueError:
        #        raise webob.exc.HTTPInternalServerError(
        #            _('Invalid service catalog json.'))

        # NOTE: This is a full auth plugin set by auth_token
        # middleware in newer versions.
        user_auth_plugin = req.environ.get('keystone.token_auth')

        ctx = context.RequestContext(user_id,
                                     project_id,
                                     user_name=user_name,
                                     project_name=project_name,
                                     roles=roles,
                                     auth_token=auth_token,
                                     remote_address=remote_address,
                                     request_id=req_id,
                                     user_auth_plugin=user_auth_plugin)

        req.context = ctx

    def _get_roles(self, headers):
        """Get the list of roles."""

        roles = headers.get('X_ROLES', '')
        return [r.strip() for r in roles.split(',')]


class NoAuthContextHook(hooks.PecanHook):
    def on_route(self, state):
        state.request.context = context.get_admin_context()
