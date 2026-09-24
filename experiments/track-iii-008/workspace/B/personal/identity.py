class IdentityFold:
    """Collapse user handle variants to one stable representation."""
    def apply(self, value):
        return value.strip().casefold()
