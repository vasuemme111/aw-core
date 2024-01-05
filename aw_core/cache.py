import platform
import subprocess
import keyring  # Import keyring library
import json
from cachetools import TTLCache
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize a cache with a maximum size and a TTL (time-to-live)
credentials_cache = TTLCache(maxsize=100, ttl=3600)


def is_macos():
    """Check if the current OS is macOS."""
    logger.info("Checking the operating system.")
    return platform.system() == 'Darwin'


def run_keychain_command(command):
    """Run a command for macOS Keychain."""
    try:
        logger.info(f"Running keychain command: {' '.join(command)}")
        subprocess.run(command, check=True, text=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Keychain command failed. Error: {e}")
        return False


def add_password(service, password):
    """Add or update a password in the system's secure storage."""
    logger.info(f"Adding/updating password for service {service}.")
    if is_macos():
        command = ['security', 'add-generic-password', '-s', service, '-a', "com.ralvie.sundial", '-w', password, '-U']
        return "Success" if run_keychain_command(command) else "Failed"
    else:
        keyring.set_password(service, "com.ralvie.sundial", password)
        return "Success"


def keychain_item_exists(service):
    """Check if a keychain item exists in the system's secure storage."""
    logger.info(f"Checking if a keychain item exists for service {service}.")
    if is_macos():
        command = ['security', 'find-generic-password', '-s', service, '-a', "com.ralvie.sundial"]
        try:
            subprocess.run(command, check=True, text=True, capture_output=True)
            return True
        except subprocess.CalledProcessError:
            return False
    else:
        return keyring.get_password(service, "com.ralvie.sundial") is not None


def delete_password(service):
    """Delete a password from the system's secure storage if it exists."""
    logger.info(f"Deleting password for service {service}.")
    if keychain_item_exists(service):
        if is_macos():
            command = ['security', 'delete-generic-password', '-s', service, '-a', "com.ralvie.sundial"]
            return "Success" if run_keychain_command(command) else "Failed"
        else:
            keyring.delete_password(service, "com.ralvie.sundial")
            return "Success"
    else:
        logger.warning("Keychain item not found.")
        return "Keychain item not found"


def get_password(service):
    """Retrieve a password from the system's secure storage."""
    logger.info(f"Retrieving password for service {service}.")
    if is_macos():
        command = ['security', 'find-generic-password', '-s', service, '-a', "com.ralvie.sundial", '-w']
        try:
            result = subprocess.run(command, check=True, text=True, capture_output=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return None
    else:
        return keyring.get_password(service, "com.ralvie.sundial")


def store_credentials(key, password):
    """Store a password in the cache."""
    credentials_cache[key] = password


def get_credentials(key):
    """Retrieve a password from the cache."""
    return credentials_cache.get(key)


def clear_credentials(key):
    """Clear a password from the cache."""
    if key in credentials_cache:
        del credentials_cache[key]


def clear_all_credentials():
    """Clear all passwords from the cache."""
    credentials_cache.clear()


def cache_user_credentials(cache_key, service):
    """Cache user credentials from the secure storage or as provided."""

    cached_credentials = get_credentials(cache_key)
    if cached_credentials is None:
        credentials_str = get_password(service)
        if credentials_str:
            try:
                credentials = json.loads(credentials_str)  # Parse the JSON string to a dictionary
                store_credentials(cache_key, credentials)
                return credentials
            except json.JSONDecodeError:
                logger.error("Error decoding credentials from JSON.")
                return None
        else:
            logger.warning(f"No credentials found for {service}.")
            return None
    else:
        return cached_credentials
