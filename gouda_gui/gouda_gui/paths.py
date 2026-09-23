"""Portable user-owned storage. Runtime state and calibration never live in Git."""
import os
from pathlib import Path


def config_dir():
    return Path(os.environ.get('XDG_CONFIG_HOME', Path.home()/'.config'))/'gouda'


def data_dir():
    return Path(os.environ.get('XDG_DATA_HOME', Path.home()/'.local/share'))/'gouda'
