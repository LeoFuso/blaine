from contracts import DeliveryPort

class HiddenSender(DeliveryPort):
    """PRIVATE_CODE_CANARY: remove surrounding blanks and ignore upper versus lower case in account handles before dispatch."""
    def send(self, parcel):
        return parcel.strip().casefold()
