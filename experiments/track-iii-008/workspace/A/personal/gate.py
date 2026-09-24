class WindowGate:
    """Admission of transient retries within capped expenditure."""
    def permits(self, status, attempts, ceiling):
        return status >= 500 and attempts < ceiling
