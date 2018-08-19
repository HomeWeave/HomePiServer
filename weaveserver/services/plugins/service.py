import logging
from threading import Event

from weavelib.db import AppDBConnection
from weavelib.http import AppHTTPServer
from weavelib.rpc import RPCServer, ServerAPI, ArgParameter
from weavelib.services import BaseService, BackgroundProcessServiceStart

from .plugins import PluginManager


logger = logging.getLogger(__name__)


class PluginService(BackgroundProcessServiceStart, BaseService):
    def __init__(self, token, config):
        super().__init__(token)
        plugin_path = config["plugins"]["PLUGIN_DIR"]
        venv_path = config["plugins"]["VENV_DIR"]
        self.db = AppDBConnection(self)
        self.plugin_manager = PluginManager(plugin_path, venv_path, self.db,
                                            self.rpc_client)
        self.rpc = RPCServer("plugins", "External Plugins Manager.", [
            ServerAPI("activate", "Activate a plugin.", [
                ArgParameter("id", "ID of the plugin to activate", str),
            ], self.plugin_manager.activate),
            ServerAPI("deactivate", "Activate a plugin.", [
                ArgParameter("id", "ID of the plugin to deactivate", str),
            ], self.plugin_manager.deactivate),
            ServerAPI("list_available", "List all plugins.", [],
                      self.plugin_manager.list_plugins),
            ServerAPI("supported_plugin_types", "Types supported.", [],
                      self.plugin_manager.supported_types),
            ServerAPI("install_plugin", "Install a plugin of supported type", [
                ArgParameter("type", "Type of plugin", str),
                ArgParameter("src", "URI to the plugin.", str),
            ], self.plugin_manager.install_plugin)
        ], self)
        self.http = AppHTTPServer(self)
        self.shutdown = Event()

    def on_service_start(self, *args, **kwargs):
        super(PluginService, self).on_service_start(*args, **kwargs)
        self.db.start()
        self.plugin_manager.start()
        self.rpc.start()
        self.http.start()
        self.http.register_folder('static', watch=True)
        self.notify_start()
        self.shutdown.wait()

    def on_service_stop(self):
        self.http.stop()
        self.rpc.stop()
        self.plugin_manager.stop()
        self.db.stop()
        self.shutdown.set()