# cache.py
from cachetools import Cache
import json
import keyring
# Initialize a global cache
credentials_cache = Cache(maxsize=100)

def store_credentials(key, credentials):
    credentials_cache[key] = credentials

def get_credentials(key):
    return credentials_cache.get(key)

def clear_credentials(key):
    if key in credentials_cache:
        del credentials_cache[key]

# Optional: Function to clear the entire cache
def clear_all_credentials():
    credentials_cache.clear()

def cache_user_credentials(cache_key):
    cached_credentials = get_credentials(cache_key)
    if not cached_credentials:
        SD_KEYS = keyring.get_password("SD_KEYS", "SD_KEYS")
        if SD_KEYS:
            SD_KEYS = json.loads(SD_KEYS)
            store_credentials(cache_key, SD_KEYS)
    return get_credentials(cache_key)
    