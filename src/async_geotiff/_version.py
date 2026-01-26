from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("async-geotiff")
except PackageNotFoundError:
    __version__ = "uninstalled"
