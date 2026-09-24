from contracts import DeliveryPort

class ParcelSender(DeliveryPort):
    """Transport implementation for outbound parcels."""
    def send(self, parcel):
        return {"sent": parcel}
