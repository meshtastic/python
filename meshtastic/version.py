import sys
try:
    from importlib.metadata import version
except:
    import pkg_resources

def get_active_version():
    if "importlib.metadata" in sys.modules:
        return version("meshtastic")
    else:
        return pkg_resources.get_distribution("meshtastic").version
