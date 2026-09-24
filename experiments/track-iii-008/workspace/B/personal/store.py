from publish import seal

def checkpoint(path, payload):
    """Store a completed parcel snapshot."""
    return seal(path, payload)
