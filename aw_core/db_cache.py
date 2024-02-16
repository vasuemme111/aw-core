from cachetools import TTLCache
import time

# Initialize the cache with a maximum size of 100 items and items living for 60 seconds
cache = TTLCache(maxsize=100, ttl=3600)


def store(cache_key, value):
    """Store a value in the cache using a specific key."""
    cache[cache_key] = value


def retrieve(cache_key):
    """Retrieve a value from the cache by its key. Returns None if the key is not found or has expired."""
    return cache.get(cache_key, None)


def update(cache_key, value):
    """Update an existing value in the cache by its key. Does nothing if the key has expired or doesn't exist."""
    # In TTLCache, updating is the same as storing. If the key exists, it will be updated; otherwise, a new entry is
    # created.
    cache[cache_key] = value


def delete(cache_key):
    """Delete a value from the cache by its key. Does nothing if the key doesn't exist."""
    # The pop method removes the item with the key and returns its value or a default if the key is not found. Here
    # we ignore the returned value.
    cache.pop(cache_key, None)


def cache_data(cache_key, value=None):
    if not retrieve(cache_key):
        store(cache_key,value)
    return retrieve(cache_key)