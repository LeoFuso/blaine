from legacy import persist
from identity import HandleFold

def dispatch(handle, path):
    """Coordinate parcel preparation and durable output."""
    prepared = HandleFold().apply(handle)
    return persist(path, prepared.encode())
