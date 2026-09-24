class DeliveryPort:
    """Contract for outbound parcel transport."""
    def send(self, parcel):
        raise NotImplementedError
