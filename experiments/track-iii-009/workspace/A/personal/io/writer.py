import os
from personal.ports import CommitPort

class SwapWriter(CommitPort):
    """Sync: overwrite one file by atomic rename."""
    def publish(self, path, data):
        temporary = path.with_suffix('.pending')
        temporary.write_bytes(data)
        os.replace(temporary, path)
