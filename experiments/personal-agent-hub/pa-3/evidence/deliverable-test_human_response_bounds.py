import pytest

from runtime.kernel.contracts import message
from runtime.kernel.human import request_digest, validate_response


def _request():
    payload = {
        "task_id": "task-1",
        "origin_task_id": "origin-1",
        "request_id": "r" * 64,
        "revision": 0,
        "question": "Approve?",
        "allowed_responses": ["APPROVE", "REJECT"],
    }
    return message("HumanDecisionRequest", payload)


def _response(value, request, digest, revision=None):
    req = request["payload"] if isinstance(request, dict) else request
    if revision is None:
        revision = req["revision"]
    payload = {
        "task_id": req["task_id"],
        "request_id": req["request_id"],
        "request_revision": revision,
        "request_digest": digest,
        "response_id": "resp-1",
        "value": value,
    }
    return message("HumanDecisionResponse", payload)


def test_valid_response_returns_payload():
    request = _request()
    digest = request_digest(request)
    response = _response("APPROVE", request, digest)
    result = validate_response(response, request, "task-1")
    assert result["value"] == "APPROVE"


def test_maybe_outside_allowed_responses_raises():
    request = _request()
    digest = request_digest(request)
    response = _response("MAYBE", request, digest)
    with pytest.raises(ValueError):
        validate_response(response, request, "task-1")


def test_stale_request_revision_raises():
    request = _request()
    digest = request_digest(request)
    response = _response("APPROVE", request, digest, revision=1)
    with pytest.raises(ValueError):
        validate_response(response, request, "task-1")


def test_wrong_request_digest_raises():
    request = _request()
    bad_digest = "0" * 64
    response = _response("APPROVE", request, bad_digest)
    with pytest.raises(ValueError):
        validate_response(response, request, "task-1")
