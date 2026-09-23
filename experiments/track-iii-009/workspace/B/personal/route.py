class RoutePick:
    """Choose a destination name; no IO, sessions or cancellation."""
    def choose(self, local):
        return 'near' if local else 'far'
