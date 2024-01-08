import base64
import ctypes
import sys
from typing import Tuple
from aw_core.cache import *
import logging
from cryptography.fernet import Fernet
import keyring
import pam
from aw_qt.manager import Manager

manager = Manager()

logger = logging.getLogger(__name__)


class VersionException(Exception):
    ...


def _version_info_tuple() -> Tuple[int, int, int]:  # pragma: no cover
    return (sys.version_info.major, sys.version_info.minor, sys.version_info.micro)


def assert_version(required_version: Tuple[int, ...] = (3, 5)):  # pragma: no cover
    actual_version = _version_info_tuple()
    if actual_version <= required_version:
        raise VersionException(
            (
                    "Python version {} not supported, you need to upgrade your Python"
                    + " version to at least {}."
            ).format(required_version)
        )
    logger.debug(f"Python version: {_version_info_tuple()}")


def generate_key(service_name, user_name):
    key = Fernet.generate_key()
    key_string = base64.urlsafe_b64encode(key).decode('utf-8')
    keyring.set_password(service_name, user_name, key_string)


# Load the secret key from a file
def load_key(service_name):
    cache_key = "sundial"
    cached_credentials = cache_user_credentials(cache_key, "SD_KEYS")
    if cached_credentials != None:
        return cached_credentials.get(service_name)
    else:
        return None


def str_to_fernet(key):
    return base64.urlsafe_b64decode(key.encode('utf-8'))


# Encrypt the UUID
def encrypt_uuid(uuid_str, key):
    try:
        fernet = Fernet(key)
        encrypted_uuid = fernet.encrypt(str(uuid_str).encode())
        return base64.urlsafe_b64encode(encrypted_uuid).decode('utf-8')
    except Exception as e:
        print(f"encrypt_uuid error: {e}")
        return None


# Decrypt the UUID
def decrypt_uuid(encrypted_uuid, key):
    try:
        fernet = Fernet(key)
        encrypted_uuid_byte = base64.urlsafe_b64decode(encrypted_uuid.encode('utf-8'))
        decrypted_uuid = fernet.decrypt(encrypted_uuid_byte)
        return decrypted_uuid.decode()
    except Exception as e:
        reset_user()
        print(f"decrypt_uuid error: {e}")
        return None


def authenticate(username, password):
    if sys.platform != "darwin":
        return authenticateWindows(username=username, password=password)
    else:
        return authenticateMac(username=username, password=password)


def authenticateWindows(username, password):
    try:
        handle = ctypes.windll.advapi32.LogonUserW(
            username,
            None,
            password,
            2,  # LOGON32_LOGON_NETWORK
            0,  # LOGON32_PROVIDER_DEFAULT
            ctypes.byref(ctypes.c_void_p())
        )
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        else:
            return False
    except Exception as e:
        print(f"Authentication error: {e}")
        return False


def authenticateMac(username, password):
    try:
        # Attempt to authenticate the user with the provided username and password
        if pam.authenticate(username, password):
            return True
        else:
            return False
    except pam.PAMError as e:
        print(f"Authentication error: {e}")
        return False


def reset_user():
    try:
        delete_password("SD_KEYS")
        cache_key = "sundial"
        clear_credentials(cache_key)
        stop_all_module()
    except Exception as e:
        print(f"Authentication error: {e}")


def list_modules():
    modules = manager.status()
    print(modules)
    return modules


def start_module( module_name):
    manager.start(module_name)


def stop_module( module_name):
    manager.stop_modules(module_name)


def stop_all_module():
    modules = list_modules()
    for module in modules:
        if not module["watcher_name"] == "aw-server":
            manager.stop_modules(module["watcher_name"])


def start_all_module():
    modules = list_modules()
    for module in modules:
        if not module["watcher_name"] == "aw-server":
            manager.start(module["watcher_name"])


import requests


def is_internet_connected():
    try:
        # Try making a simple HTTP GET request to a well-known website
        response = requests.get("http://www.google.com")
        # If the request is successful, return True
        return response.status_code == 200
    except requests.ConnectionError:
        # If there's a connection error, return False
        return False
