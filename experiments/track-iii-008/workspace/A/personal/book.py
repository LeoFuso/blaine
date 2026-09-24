import hashlib

class StampBook:
    """Memoize successful send receipts under a stable digest."""
    def __init__(self):
        self.receipts = {}
    def remember(self, payload, acknowledgement):
        key = hashlib.sha256(payload).hexdigest()
        previous = self.receipts.get(key)
        if previous is not None:
            return previous
        self.receipts[key] = acknowledgement
        return acknowledgement
