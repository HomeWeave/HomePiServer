import logging
import os
from threading import Thread

from github3 import GitHub

from weavelib.exceptions import ObjectNotFound, BadArguments

from weaveserver.core.plugins import load_plugin_from_path, GitPlugin
from weaveserver.core.plugins import FilePlugin, VirtualEnvManager
from weaveserver.core.plugins import get_plugin_id

logger = logging.getLogger(__name__)


def list_plugins(base_dir):
    res = []
    for name in os.listdir(base_dir):
        plugin_info = load_plugin_from_path(base_dir, name)
        if plugin_info:
            res.append(plugin_info)
    return res


def run_plugin(service, timeout):
    service.service_start()
    if not service.wait_for_start(timeout=timeout):
        service.service_stop()
        return False
    return True


def stop_plugin(service):
    service.service_stop()


class PluginManager(object):
    def __init__(self, base_dir, venv_dir, database, appmgr_rpc):
        self.base_dir = base_dir
        self.venv_dir = venv_dir
        self.database = database
        self.appmgr_rpc = appmgr_rpc
        self.enabled_plugins = set()
        self.running_plugins = {}
        self.all_plugins = {}
        self.github_weave_org = GitHub().organization('HomeWeave')

    def start(self):
        self.init_structure(self.base_dir)
        self.init_structure(self.venv_dir)

        try:
            enabled_plugins = self.database["ENABLED_PLUGINS"]
        except KeyError:
            self.database["ENABLED_PLUGINS"] = []
            enabled_plugins = []

        for plugin in list_plugins(self.base_dir):
            plugin["enabled"] = plugin["id"] in enabled_plugins
            self.all_plugins[plugin["id"]] = plugin

        self.enabled_plugins = set(self.all_plugins) & set(enabled_plugins)

        # Fetch all repos from HomeWeave
        for repo in self.github_weave_org.repositories():
            contents = repo.directory_contents("/", return_as=dict)
            plugin_id = get_plugin_id(repo.clone_url)
            if plugin_id in self.all_plugins:
                continue

            if "plugin.json" in contents:
                self.all_plugins[plugin_id] = {
                    "id": plugin_id,
                    "name": repo.name,
                    "url": repo.clone_url,
                    "description": repo.description,
                    "enabled": False,
                    "installed": False,
                }

        thread = Thread(target=self.start_async, args=(self.enabled_plugins,))
        thread.start()

    def start_async(self, enabled_plugins):
        for plugin_id in enabled_plugins:
            self.activate(plugin_id)

        logger.info("Started %d of %d plugins.", len(self.running_plugins),
                    len(self.all_plugins))

    def stop(self):
        for id, service in self.running_plugins.items():
            stop_plugin(service)

    def init_structure(self, path):
        if not os.path.isdir(path):
            try:
                os.makedirs(path)
            except:
                pass
            if not os.path.isdir(path):
                raise Exception("Unable to create directory: " + path)

    def list_plugins(self):
        subset = {"id", "name", "description", "enabled", "installed", "url"}
        return [{k: x[k] for k in subset} for x in self.all_plugins.values()]

    def supported_types(self):
        return ["git", "file"]

    def install_plugin(self, plugin_type, src):
        if plugin_type not in ("git", "file"):
            raise BadArguments("Invalid plugin type.")

        cls = {"git": GitPlugin, "file": FilePlugin}[plugin_type]
        plugin = cls(src, self.base_dir)
        plugin.create()

        venv_path = os.path.join(self.venv_dir, plugin.unique_id())
        venv = VirtualEnvManager(venv_path)
        requirements_file = os.path.join(plugin.get_plugin_dir(),
                                         "requirements.txt")
        if not os.path.isfile(requirements_file):
            requirements_file = None
        venv.install(requirements_file=requirements_file)

        plugin_name = os.path.basename(plugin.get_plugin_dir())
        plugin_info = load_plugin_from_path(self.base_dir, plugin_name)
        self.all_plugins[plugin.unique_id()] = plugin_info
        return plugin_info["id"]

    def activate(self, id):
        try:
            plugin = self.all_plugins[id]
        except KeyError:
            raise ObjectNotFound(id)

        if id in self.running_plugins:
            return True

        venv_dir = os.path.join(self.venv_dir, plugin["id"])
        if not os.path.isdir(venv_dir):
            logger.error("VirtualEnv directory %s not found.", venv_dir)
            return False

        appmgr_plugin_info = {"package": plugin["package_path"]}
        token = self.appmgr_rpc["register_plugin"](appmgr_plugin_info,
                                                   _block=True)
        service = plugin["cls"](token, plugin["config"], venv_dir)
        if not run_plugin(service, timeout=plugin["start_timeout"]):
            return False

        logger.info("Started plugin: %s", plugin["package_path"])
        self.running_plugins[id] = service

        return True

    def deactivate(self, id):
        pass
