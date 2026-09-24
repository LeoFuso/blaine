def note_5(handle, attempt, ack):
    """Diagnostic 5: report handle folding, attempts and acknowledgements.
    Observe payload delivery, partially written bytes and caller requests.
    Telemetry records events; it does not supply contract implementations.
    """
    return (handle, attempt, ack)
