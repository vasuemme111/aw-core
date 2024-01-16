import os
import sys
from functools import wraps
from typing import Callable, Optional

import platformdirs

GetDirFunc = Callable[[Optional[str]], str]


def ensure_path_exists(path: str) -> None:
    """
     Ensure path exists if not create it. This is useful for creating directories in case they don't exist before we're going to use them.
     
     @param path - Path to check for existence. It will be created if it doesn't exist
     
     @return True if path exists
    """
    # Create a directory if it doesn t exist.
    if not os.path.exists(path):
        os.makedirs(path)


def _ensure_returned_path_exists(f: GetDirFunc) -> GetDirFunc:
    """
     Decorator to ensure returned path exists. This is useful for functions that need to be wrapped in a get_dir function.
     
     @param f - function that takes a subpath and returns a path
     
     @return wrapped function that returns the path that was passed to the function and ensures it exists in the path_
    """
    @wraps(f)
    def wrapper(subpath: Optional[str] = None) -> str:
        """
         Wrapper for : func : ` waflib. Tools. check_path ` that ensures the path exists.
         
         @param subpath - Path to check for existence. If None path is assumed to be a directory.
         
         @return Path to the file or directory that was checked for existence. This is a convenience function that wraps the function
        """
        path = f(subpath)
        ensure_path_exists(path)
        return path

    return wrapper


@_ensure_returned_path_exists
def get_data_dir(module_name: Optional[str] = None) -> str:
    """
     Get the Sundial data directory. If module_name is specified return the path to that module otherwise return the full path to the user's data directory.
     
     @param module_name - The name of the module to get the path to.
     
     @return The path to the Sundial data directory or the full path to the module's data directory
    """
    data_dir = platformdirs.user_data_dir("Sundial")
    return os.path.join(data_dir, module_name) if module_name else data_dir


@_ensure_returned_path_exists
def get_cache_dir(module_name: Optional[str] = None) -> str:
    """
     Get the cache directory for Sundial. If module_name is specified it will be appended to the cache directory.
     
     @param module_name - The name of the module that is going to be cached.
     
     @return The path to the cache directory for Sundial or the path to the module itself if no module name
    """
    cache_dir = platformdirs.user_cache_dir("Sundial")
    return os.path.join(cache_dir, module_name) if module_name else cache_dir


@_ensure_returned_path_exists
def get_config_dir(module_name: Optional[str] = None) -> str:
    """
     Get the Sundial config directory. If module_name is specified return the path to that module otherwise return the path to the user's config directory.
     
     @param module_name - The name of the module to get the path to.
     
     @return The path to the Sundial config directory or the user's config directory if module_name is None
    """
    config_dir = platformdirs.user_config_dir("Sundial")
    return os.path.join(config_dir, module_name) if module_name else config_dir


@_ensure_returned_path_exists
def get_log_dir(module_name: Optional[str] = None) -> str:  # pragma: no cover
    """
     Get the path to Sundial's log directory. If module_name is specified it will be appended to the log directory to form a fully qualified path
     
     @param module_name - name of module to append to the log directory
     
     @return full path to log directory or None if not found ( in which case we're in an untrusted
    """
    # on Linux/Unix, platformdirs changed to using XDG_STATE_HOME instead of XDG_DATA_HOME for log_dir in v2.6
    # we want to keep using XDG_DATA_HOME for backwards compatibility
    # https://github.com/Sundial/aw-core/pull/122#issuecomment-1768020335
    # Return the path to the log directory for the current user s log files.
    if sys.platform.startswith("linux"):
        log_dir = platformdirs.user_cache_path("Sundial") / "log"
    else:
        log_dir = platformdirs.user_log_dir("Sundial")
    return os.path.join(log_dir, module_name) if module_name else log_dir
