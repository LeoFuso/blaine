"""The spike's deterministic operation; no execution state lives here."""

import hashlib


def validate_request(request: object) -> tuple[str, int]:
    if not isinstance(request, dict):
        raise ValueError("request must be a JSON object")
    objective = request.get("objective")
    if not isinstance(objective, str) or not objective.strip():
        raise ValueError("objective must be a non-empty string")
    delay = request.get("delay_seconds", 30)
    if type(delay) is not int or not 0 <= delay <= 300:
        raise ValueError("delay_seconds must be an integer between 0 and 300")
    return objective, delay


def summarize_objective(objective: str) -> dict:
    return {
        "objective": objective,
        "word_count": len(objective.split()),
        "sha256": hashlib.sha256(objective.encode("utf-8")).hexdigest(),
    }
