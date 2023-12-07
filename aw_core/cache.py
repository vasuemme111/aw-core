from cachetools import TTLCache
import json
import keyring

# Initialize a cache with a maximum size and a TTL (time-to-live) for cached items
credentials_cache = TTLCache(maxsize=100, ttl=3600)  # Adjust maxsize and ttl as needed

def store_credentials(key, credentials):
    credentials_cache[key] = credentials

def get_credentials(key):
    return credentials_cache.get(key)

def clear_credentials(key):
    if key in credentials_cache:
        del credentials_cache[key]

def clear_all_credentials():
    credentials_cache.clear()

def cache_user_credentials(cache_key):
    # Retrieve cached credentials if they exist
    cached_credentials = get_credentials(cache_key)

    if cached_credentials is None:
        SD_KEYS = keyring.get_password("SD_KEYS", "SD_KEYS")
        if SD_KEYS:
            # Parse the JSON stored in SD_KEYS
            SD_KEYS = json.loads(SD_KEYS.replace("'","\""))
            store_credentials(cache_key, SD_KEYS)
            return SD_KEYS  # Return the newly cached credentials

    return cached_credentials  # Return the cached or newly cached credentials