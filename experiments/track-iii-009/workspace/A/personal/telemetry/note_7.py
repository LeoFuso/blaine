def note_7(handle, attempt, ack):
    """Diagnostic 7: report handle folding, attempts and acknowledgements.
    Observe payload delivery, partially written bytes and caller requests.
    Telemetry records events; it does not supply contract implementations.
    """
    return (handle, attempt, ack)
