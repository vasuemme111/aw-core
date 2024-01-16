import logging
import os
from typing import Union

import tomlkit
from deprecation import deprecated

from aw_core import dirs
from aw_core.__about__ import __version__

logger = logging.getLogger(__name__)


def _merge(a: dict, b: dict, path=None):
    """
     Merge two dictionaries into one. This is a recursive function to merge two dictionaries and return the result.
     
     @param a - The first dictionary to merge into. It is modified in place.
     @param b - The second dictionary to merge into ` a `.
     @param path - The path to the dictionary that was used to merge ` b `.
     
     @return The merged dictionary ` a `. If a and b have the same leaf value the value of the leaf will be set in ` a `
    """
    """
    Recursively merges b into a, with b taking precedence.

    From: https://stackoverflow.com/a/7205107/965332
    """
    # Remove all path elements from the path list.
    if path is None:
        path = []
    # merge two dicts and merge them with the same leaf value
    for key in b:
        # merge two dicts and merge the same leaf value
        if key in a:
            # merge two dicts and merge the same leaf value
            if isinstance(a[key], dict) and isinstance(b[key], dict):
                _merge(a[key], b[key], path + [str(key)])
            elif a[key] == b[key]:
                pass  # same leaf value
            else:
                a[key] = b[key]
        else:
            a[key] = b[key]
    return a


def _comment_out_toml(s: str):
    """
     Comment out lines that don't start with #. This is used to ensure that comments are added to TOML files and not to the file's header.
     
     @param s - The string to comment out. Must be a string of key / value pairs separated by newline characters.
     
     @return The string with comments added to each line in the TOML file. Note that the comment out keys are ignored
    """
    # Only comment out keys, not headers or empty lines
    return "\n".join(
        [
            "#" + line if line.strip() and not line.strip().startswith("[") else line
            for line in s.split("\n")
        ]
    )


def load_config_toml(
    appname: str, default_config: str
) -> Union[dict, tomlkit.container.Container]:
    """
     Load config file or create it if it doesn't exist. This is used to load configuration files that are specific to an application
     
     @param appname - The name of the application
     @param default_config - The default configuration as a string.
     
     @return A dict or tomlkit container. Container of the config file or the default config if not found or
    """
    config_dir = dirs.get_config_dir(appname)
    config_file_path = os.path.join(config_dir, f"{appname}.toml")

    # Run early to ensure input is valid toml before writing
    default_config_toml = tomlkit.parse(default_config)

    # Override defaults from existing config file
    # Load the tomlkit configuration file and return a dictionary of config_toml.
    if os.path.isfile(config_file_path):
        with open(config_file_path) as f:
            config = f.read()
        config_toml = tomlkit.parse(config)
    else:
        # If file doesn't exist, write with commented-out default config
        with open(config_file_path, "w") as f:
            f.write(_comment_out_toml(default_config))
        config_toml = dict()

    config = _merge(default_config_toml, config_toml)

    return config


def save_config_toml(appname: str, config: str) -> None:
    """
     Save config string to app's config directory. This is a convenience function for saving a config string to the app's config directory.
     
     @param appname - The name of the application to save the config for.
     @param config - The config string to save. Must be valid TOML
    """
    # Check that passed config string is valid toml
    assert tomlkit.parse(config)

    config_dir = dirs.get_config_dir(appname)
    config_file_path = os.path.join(config_dir, f"{appname}.toml")

    with open(config_file_path, "w") as f:
        f.write(config)


@deprecated(
    details="Use the load_config_toml function instead",
    deprecated_in="0.5.3",
    current_version=__version__,
)
def load_config(appname, default_config):
    """
     Load config for an application. This is a helper function for load_config_from_file and load_config_from_file
     
     @param appname - The name of the application to load config for
     @param default_config - The default config to use if no config file exists
     
     @return The loaded config or default_config if no config file exists for the given application. It is assumed that the application has been loaded
    """
    """
    Take the defaults, and if a config file exists, use the settings specified
    there as overrides for their respective defaults.
    """
    config = default_config

    config_dir = dirs.get_config_dir(appname)
    config_file_path = os.path.join(config_dir, f"{appname}.toml")

    # Override defaults from existing config file
    # Read the config file if it exists.
    if os.path.isfile(config_file_path):
        with open(config_file_path) as f:
            config.read_file(f)

    # Overwrite current config file (necessary in case new default would be added)
    save_config(appname, config)

    return config


@deprecated(
    details="Use the save_config_toml function instead",
    deprecated_in="0.5.3",
    current_version=__version__,
)
def save_config(appname, config):
    """
     Save config to disk. This is a convenience function for use in unit tests. It will create a file named appname. ini in the config directory with the contents of config.
     
     @param appname - The name of the application to save the config for.
     @param config - The config to save as a file. See : func : ` get_config ` for details
    """
    config_dir = dirs.get_config_dir(appname)
    config_file_path = os.path.join(config_dir, f"{appname}.ini")
    with open(config_file_path, "w") as f:
        config.write(f)
        # Flush and fsync to lower risk of corrupted files
        f.flush()
        os.fsync(f.fileno())
