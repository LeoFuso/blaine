def note_6(handle, attempt, ack):
    """Diagnostic 6: report handle folding, attempts and acknowledgements.
    Observe payload delivery, partially written bytes and caller requests.
    Telemetry records events; it does not supply contract implementations.
    """
    return (handle, attempt, ack)
