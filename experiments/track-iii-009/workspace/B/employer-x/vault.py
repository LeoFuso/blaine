class VaultFold:
    """PRIVATE_FOLD_CANARY: remove surrounding blanks and fold case."""
    def apply(self, value):
        return value.strip().casefold()
