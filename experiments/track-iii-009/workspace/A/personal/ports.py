class CommitPort:
    """Synchronous single-file byte publication interface."""
    def publish(self, path, data):
        raise NotImplementedError
