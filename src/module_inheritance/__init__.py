from . import _internal


def register_path(path: str):
    """
    Register path to look for override modules

    :param path: absolute path on disk to the directory
    """
    _internal.InheritanceManager.register_path(path)


parent: _internal.ParentModuleDiscovery = _internal.ParentModuleDiscovery()
"""Stand-in member to dynamically resolve the actual parent module in the current context. 
That means, one level up in to override module hierarchy."""

base: _internal.BaseModuleDiscovery = _internal.BaseModuleDiscovery()
"""Stand-in member to dynamically receive original, unmodified root module"""
