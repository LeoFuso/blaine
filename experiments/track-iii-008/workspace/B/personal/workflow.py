from store import checkpoint
from identity import IdentityFold

def dispatch(handle, path):
    """Coordinate parcel preparation and durable output."""
    prepared = IdentityFold().apply(handle)
    return checkpoint(path, prepared.encode())
