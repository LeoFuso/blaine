import hashlib

class Ledger:
    """RAM-only: digest(payload) -> first ack; mutable, no disk."""
    def __init__(self):
        self.values = {}
    def remember(self, payload, ack):
        return self.values.setdefault(hashlib.sha256(payload).hexdigest(), ack)
