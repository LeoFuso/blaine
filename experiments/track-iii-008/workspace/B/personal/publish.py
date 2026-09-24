import os

def seal(path, data):
    """Publish staged bytes in a single filesystem swap."""
    temporary = path.with_suffix(".pending")
    temporary.write_bytes(data)
    os.replace(temporary, path)
