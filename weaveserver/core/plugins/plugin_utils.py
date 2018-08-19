import importlib
import hashlib
import json
import logging
import os
import shutil
import sys
from uuid import uuid4

import git


logger = logging.getLogger(__name__)


class BasePlugin(object):
    def __init__(self, src, dest):
        self.src = src
        self.dest = dest
        self.plugin_dir = self.get_plugin_dir()
        self.appid = "plugin-token-" + str(uuid4())

    def get_plugin_dir(self):
        return os.path.join(self.dest, self.unique_id())

    def unique_id(self):
        return get_plugin_id(self.src)

    def needs_create(self):
        return not os.path.isdir(self.plugin_dir)


class GitPlugin(BasePlugin):
    def __init__(self, src, dest):
        if src is None:
            self.git = git.Repo(dest)
            src = next(self.git.remote('origin').urls)
            dest = os.path.dirname(dest)
        super(GitPlugin, self).__init__(src, dest)

    def create(self):
        git.Repo.clone_from(self.src, self.plugin_dir)


class FilePlugin(BasePlugin):
    def __init__(self, src, dest):
        if src is None:
            src = open(os.path.join(dest, "source")).read().strip()
            dest = os.path.dirname(dest)
        super(FilePlugin, self).__init__(src, dest)

    def create(self):
        shutil.copytree(self.src, self.plugin_dir)
        with open(os.path.join(self.plugin_dir, "source"), "w") as f:
            f.write(self.src)


def get_plugin_id(url):
    return hashlib.md5(url.encode('utf-8')).hexdigest()


def create_plugin(base, name):
    if os.path.isdir(os.path.join(base, name, '.git')):
        plugin = GitPlugin(None, os.path.join(base, name))
    else:
        plugin = FilePlugin(None, os.path.join(base, name))
    if plugin.get_plugin_dir() != os.path.join(base, name):
        logger.warning("Plugin directory name mismatch: %s/%s v/s %s",
                       base, name, plugin.get_plugin_dir())
        return None
    return plugin


def load_plugin_from_path(base_dir, name):
    try:
        with open(os.path.join(base_dir, name, "plugin.json")) as inp:
            plugin_info = json.load(inp)
    except IOError:
        logger.warning("Error opening plugin.json within %s", name)
        return None
    except ValueError:
        logger.warning("Error parsing plugin.json within %s", name)
        return None

    sys.path.append(os.path.join(base_dir, name))
    try:
        fully_qualified = plugin_info["service"]
        if '.' not in fully_qualified:
            logger.warning("Bad 'service' specification in plugin.json.")
            return None
        mod, cls = plugin_info["service"].rsplit('.', 1)
        module = getattr(importlib.import_module(mod), cls)
    except AttributeError:
        logger.warning("Possibly bad 'service' specification in plugin.json")
        return None
    except ImportError:
        logger.warning("Failed to import dependencies for %s", name)
        return None
    except KeyError:
        logger.warning("Required field not found in %s/plugin.json.", name)
        return None
    finally:
        sys.path.pop(-1)

    plugin = create_plugin(base_dir, name)
    return {
        "plugin": plugin,
        "description": "",
        "cls": module,
        "name": name,
        "url": plugin.src,
        "deps": plugin_info.get("deps"),
        "id": plugin.unique_id(),
        "package_path": plugin_info["service"],
        "config": plugin_info.get("config", {}),
        "start_timeout": plugin_info.get("start_timeout", 30),
        "installed": True,
        "enabled": False,
    }