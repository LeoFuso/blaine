from contracts import DeliveryPort

class AuditSender(DeliveryPort):
    """Transport implementation retaining a local acknowledgement."""
    def send(self, parcel):
        return {"accepted": True, "parcel": parcel}
