"""Workspace-owned storage paths; maps and host settings stay with the workspace."""
import json
import os
from pathlib import Path


def workspace_dir():
    configured = os.environ.get('GOUDA_WORKSPACE')
    if configured:
        return Path(configured).expanduser().resolve()
    legacy = Path(os.environ.get('XDG_CONFIG_HOME', Path.home()/'.config'))/'gouda/host.json'
    source = Path(__file__).resolve()
    for ancestor in source.parents:
        if ancestor.name == 'tsukuba-autonomous-robot' and ancestor.parent.name == 'src':
            return ancestor.parent.parent.resolve()
    if legacy.is_file():
        try:
            value = json.loads(legacy.read_text()).get('workspace')
            if value:
                return Path(value).expanduser().resolve()
        except (OSError, ValueError):
            pass
    return (Path.home()/'gouda_ws').resolve()


def config_dir():
    return workspace_dir()/'bags'/'gouda'


def data_dir():
    return workspace_dir()


def runtime_dir():
    return config_dir()/'runtime'


def logs_dir():
    return config_dir()/'logs'
