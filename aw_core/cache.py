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
    """
     Check if the operating system is Mac OS. This is a helper function to check if the current OS is Mac OS.
     
     
     @return True if the operating system is Mac OS False otherwise. >>> is_macos () Traceback ( most recent call last ) : Exception : OS not Mac OS
    """
    """Check if the current OS is macOS."""
    logger.info("Checking the operating system.")
    return platform.system() == 'Darwin'


def run_keychain_command(command):
    """
     Run a keychain command for macOS Keychain. This is a wrapper around subprocess. run that does not raise exceptions
     
     @param command - Command to run as list of strings
     
     @return True if command ran without errors False if command failed or not run as a command ( stdout and stderr
    """
    """Run a command for macOS Keychain."""
    try:
        logger.info(f"Running keychain command: {' '.join(command)}")
        subprocess.run(command, check=True, text=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Keychain command failed. Error: {e}")
        return False


def add_password(service, password):
    """
     Add or update a password in the system's secure storage. This is a wrapper around keyring. set_password to allow users to change passwords without affecting the security system.
     
     @param service - The name of the service e. g. " TTim "
     @param password - The password to add or update. If the password is invalid it will be left untouched
     
     @return " Success " if successful " Failed "
    """
    """Add or update a password in the system's secure storage."""
    logger.info(f"Adding/updating password for service {service}.")
    # The following commands are used to add generic password to the keyring.
    if is_macos():
        command = ['security', 'add-generic-password', '-s', service, '-a', "com.ralvie.TTim", '-w', password, '-U']
        return "Success" if run_keychain_command(command) else "Failed"
    else:
        keyring.set_password(service, "com.ralvie.TTim", password)
        return "Success"


def keychain_item_exists(service):
    """
     Check if a keychain item exists in the system secure storage. This is a wrapper around keyring. get_password to avoid issues with macOS's security find - generic - password
     
     @param service - service to check for a keychain item
     
     @return True if a keychain item exists False if it doesn't exist or is not a keychain
    """
    """Check if a keychain item exists in the system's secure storage."""
    logger.info(f"Checking if a keychain item exists for service {service}.")
    # Returns True if the user is a macOS password.
    if is_macos():
        command = ['security', 'find-generic-password', '-s', service, '-a', "com.ralvie.TTim"]
        try:
            subprocess.run(command, check=True, text=True, capture_output=True)
            return True
        except subprocess.CalledProcessError:
            return False
    else:
        return keyring.get_password(service, "com.ralvie.TTim") is not None


def delete_password(service):
    """
     Delete a password from the system's secure storage. This is useful for security reasons such as passwords that are stored in an unencrypted keychain.
     
     @param service - The TTim service to delete the password for.
     
     @return " Success " if deletion was successful " Failed " otherwise. >>> import fabtools >>> from fabtools. tools import delete_password
    """
    """Delete a password from the system's secure storage if it exists."""
    logger.info(f"Deleting password for service {service}.")
    # Keychain item exists in the keyring.
    if keychain_item_exists(service):
        # Delete the password for the service.
        if is_macos():
            command = ['security', 'delete-generic-password', '-s', service, '-a', "com.ralvie.TTim"]
            return "Success" if run_keychain_command(command) else "Failed"
        else:
            keyring.delete_password(service, "com.ralvie.TTim")
            return "Success"
    else:
        logger.warning("Keychain item not found.")
        return "Keychain item not found"


def get_password(service):
    """
     Retrieve a password for a service. This is a wrapper around keyring. get_password to handle macOS systems that don't have security.
     
     @param service - The name of the service. e. g.
     
     @return The password or None
    """
    """Retrieve a password from the system's secure storage."""
    logger.info(f"Retrieving password for service {service}.")
    # Get the password for the service.
    if is_macos():
        command = ['security', 'find-generic-password', '-s', service, '-a', "com.ralvie.TTim", '-w']
        try:
            result = subprocess.run(command, check=True, text=True, capture_output=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return None
    else:
        return keyring.get_password(service, "com.ralvie.TTim")


def store_credentials(key, password):
    """
     Store a password in the cache. This is used to allow users to log in to the API without having to re - authenticate the user
     
     @param key - The key to store the password under
     @param password - The password to store in the cache ( string
    """
    """Store a password in the cache."""
    credentials_cache[key] = password


def get_credentials(key):
    """
     Retrieve a password from the cache. This is a wrapper around the : func : ` credentials_cache ` function.
     
     @param key - The key to look up. Must be a string that uniquely identifies the credentials
     
     @return The password or None if not
    """
    """Retrieve a password from the cache."""
    return credentials_cache.get(key)


def clear_credentials(key):
    """
     Clear a password from the cache. This is a no - op if the key doesn't exist
     
     @param key - The key to clear
    """
    """Clear a password from the cache."""
    # Remove the key from credentials_cache.
    if key in credentials_cache:
        del credentials_cache[key]


def clear_all_credentials():
    """
     Clear all credentials from the cache. Clears all passwords from the cache which is used to make sure passwords are not lost
    """
    """Clear all passwords from the cache."""
    credentials_cache.clear()


def cache_user_credentials(cache_key, service):
    """
     Cache user credentials for the given service. This is a wrapper around get_credentials to allow us to cache credentials in the secure storage or as provided by the user
     
     @param cache_key - The cache key to use for the credentials
     @param service - The service we are interested in. Can be'ssh'or'sss '
     
     @return Dictionary or None if credentials cannot be retrieved from the secure storage or decoded from JSON and stored in the
    """
    """Cache user credentials from the secure storage or as provided."""

    cached_credentials = get_credentials(cache_key)
    # Returns the credentials for the service.
    if cached_credentials is None:
        credentials_str = get_password(service)
        # Returns the credentials from the JSON string.
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
