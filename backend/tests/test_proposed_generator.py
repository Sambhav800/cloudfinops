from app.architecture.proposed_generator import _extract_retry_delay_seconds


def test_extract_retry_delay_seconds_prefers_structured_retry_delay():
    message = "resource exhausted. retry_delay { seconds: 17 }"

    assert _extract_retry_delay_seconds(message) == 17


def test_extract_retry_delay_seconds_supports_retry_after_text():
    message = "429 too many requests; retry-after: 9"

    assert _extract_retry_delay_seconds(message) == 9


def test_extract_retry_delay_seconds_returns_zero_when_missing():
    assert _extract_retry_delay_seconds("plain validation error") == 0
