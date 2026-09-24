from publish import seal

def persist(path, payload):
    """Store a completed parcel snapshot."""
    return seal(path, payload)
