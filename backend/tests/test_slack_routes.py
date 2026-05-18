import json
import time

from app.api.slack_routes import _build_slack_signature, _is_valid_slack_request


def test_slack_signature_validation_accepts_valid_request():
    secret = "slack-secret"
    timestamp = str(int(time.time()))
    body = json.dumps({"type": "event_callback", "event": {"type": "message"}}).encode("utf-8")
    signature = _build_slack_signature(secret, timestamp, body)

    assert _is_valid_slack_request(secret, timestamp, signature, body, now=int(timestamp)) is True


def test_slack_signature_validation_rejects_invalid_signature():
    secret = "slack-secret"
    timestamp = str(int(time.time()))
    body = b'{"type":"event_callback"}'

    assert _is_valid_slack_request(secret, timestamp, "v0=invalid", body, now=int(timestamp)) is False


def test_slack_signature_validation_rejects_stale_request():
    secret = "slack-secret"
    timestamp = str(int(time.time()) - 600)
    body = b'{"type":"event_callback"}'
    signature = _build_slack_signature(secret, timestamp, body)

    assert _is_valid_slack_request(secret, timestamp, signature, body, now=int(time.time())) is False
