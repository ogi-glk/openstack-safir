from starlette.types import ASGIApp, Scope, Receive, Send
from keystonemiddleware import auth_token_asgi
from oslo_config import cfg
from oslo_log import log as logging

CONF = cfg.CONF
LOG = logging.getLogger(__name__)


class AuthTokenMiddleware(auth_token_asgi.AuthProtocol):

    def __init__(self, app: ASGIApp, conf, public_api_routes):
        self._app = app
        self._public_routes = public_api_routes
        super(AuthTokenMiddleware, self).__init__(self._app, conf)

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] == "http":
            path = scope.get('path').rstrip('/') or '/'
            if path in self._public_routes:
                return await self._app(scope, receive, send)

        return await super(AuthTokenMiddleware, self).__call__(scope, receive, send)

    @classmethod
    def factory(cls, global_config, **local_conf):
        public_routes = local_conf.get('acl_public_routes', '')
        public_api_routes = [path.strip() for path in public_routes.split(',')]

        def _factory(app):
            return cls(app, global_config, public_api_routes=public_api_routes)
        return _factory