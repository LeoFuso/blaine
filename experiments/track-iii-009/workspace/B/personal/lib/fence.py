class Fence:
    """Policy only: status >= 500 AND attempts < limit; no execution."""
    def permits(self, status, attempts, limit):
        return status >= 500 and attempts < limit
