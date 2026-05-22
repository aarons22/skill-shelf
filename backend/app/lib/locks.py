"""Per-marketplace write locks to prevent concurrent working-tree races."""
import threading

_registry_lock = threading.Lock()
_locks: dict[str, threading.Lock] = {}


def marketplace_write_lock(slug: str) -> threading.Lock:
    """Return (or create) the per-marketplace threading.Lock for write operations."""
    with _registry_lock:
        if slug not in _locks:
            _locks[slug] = threading.Lock()
        return _locks[slug]
