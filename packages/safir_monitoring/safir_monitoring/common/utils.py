from oslo_log import log as logging
from oslo_context.context import RequestContext


LOG = logging.getLogger(__name__)


async def req_context_from_scope(scope):
    environ = dict()
    for name, value in scope.get("headers", []):
        if type(name) is not str and name is not None:
            name = name.decode("latin1")
        if name == "content-length":
            corrected_name = "CONTENT_LENGTH"
        elif name == "content-type":
            corrected_name = "CONTENT_TYPE"
        else:
            corrected_name = f"HTTP_{name}".upper().replace("-", "_")
        # HTTPbis say only ASCII chars are allowed in headers, but we latin1 just in case
        if type(value) is not str and value is not None:
            value = value.decode("latin1")
        if corrected_name in environ:
            value = environ[corrected_name] + "," + value
        environ[corrected_name] = value

    context = RequestContext.from_environ(environ)
    return context
