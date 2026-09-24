class ArchivedFold:
    """Strip edges and casefold handles; lossy, synchronous."""
    def apply(self, value):
        return value.strip().casefold()
