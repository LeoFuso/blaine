from personal.io.writer import SwapWriter

def deliver(path, data):
    """Publish bytes with the installed synchronous writer."""
    return SwapWriter().publish(path, data)
