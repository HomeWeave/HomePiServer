import json
import logging
import os

from bottle import Bottle, static_file, request, response
from weavelib.rpc import RPCClient


logger = logging.getLogger(__name__)


def return_response(code, obj):
    response.status = code
    response.content_type = 'application/json'
    return json.dumps(obj)


class HTTPServer(Bottle):
    def __init__(self, service, plugin_path):
        super().__init__()
        self.service = service

        self.static_path = os.path.join(os.path.dirname(__file__), "static")
        self.plugin_path = plugin_path

        self.route("/")(self.handle_root)
        self.route("/apps/<path:path>")(self.handle_apps)
        self.route("/api/rpc", method="POST")(self.handle_rpc)

        logger.info("Temp Dir for HTTP: %s", plugin_path)

    def handle_root(self):
        return self.handle_static("/index.html")

    def handle_apps(self, path):
        return static_file(path, root=os.path.join(self.plugin_path))

    def handle_rpc(self):
        body = json.load(request.body)
        # TODO: Should be able to deduce package_name.
        package_name = body.get("package_name")
        rpc_name = body.get("rpc_name")
        api_name = body.get("api_name")
        args = body.get("args")
        kwargs = body.get("kwargs")

        current_app = None
        for app in self.service.registry.all_apps.values():
            if app.package_name == package_name:
                current_app = app
                break

        if not current_app:
            return return_response(404, {"error": "No such app."})

        rpc_info = current_app.rpcs.get(rpc_name)

        if not rpc_info or not api_name:
            return return_response(404, {"error": "No such API."})

        rpc_client = RPCClient(rpc_info.to_json(), self.service.token)

        rpc_client.start()
        try:
            res = rpc_client[api_name](*args, _block=True, **kwargs)
        except (TypeError, KeyError):
            return return_response(400, {"error": "Bad request for API."})

        rpc_client.stop()

        return return_response(200, res)
