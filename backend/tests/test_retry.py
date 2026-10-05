from datetime import datetime, timezone
from email.utils import format_datetime
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest

from app.core import retry


NOW = datetime(2026, 9, 15, tzinfo=timezone.utc).timestamp()
AZURE_RETRY_HEADERS = (
    "x-ms-ratelimit-microsoft.costmanagement-entity-retry-after",
    "x-ms-ratelimit-microsoft.costmanagement-tenant-retry-after",
    "x-ms-ratelimit-microsoft.costmanagement-client-retry-after",
    "x-ms-ratelimit-microsoft.costmanagement-clienttype-retry-after",
    "x-ms-ratelimit-microsoft.costmanagement-qpu-retry-after",
)


def header_error(headers: object, message: str = "Too many requests") -> Exception:
    error = RuntimeError(message)
    error.response = SimpleNamespace(headers=headers, status_code=429)
    return error


def http_date(delay: float) -> str:
    return format_datetime(datetime.fromtimestamp(NOW + delay, timezone.utc), usegmt=True)


@pytest.mark.parametrize("header", AZURE_RETRY_HEADERS)
def test_azure_provider_delay_is_not_capped(header: str) -> None:
    error = header_error({"Retry-After": "2", header.swapcase(): "120"})

    assert retry._retry_after_seconds(error) == 120
    assert retry._backoff_delay(1, base_delay=1, max_delay=16, error=error) == 120


def test_maximum_delay_across_all_provider_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(retry.time, "time", lambda: NOW)
    headers = {name: str(index * 10) for index, name in enumerate(AZURE_RETRY_HEADERS, 1)}
    headers["rEtRy-AfTeR"] = http_date(90)
    headers["Retry-After"] = "5"

    assert retry._retry_after_seconds(header_error(headers)) == 90


@pytest.mark.parametrize("value", ["3", " 3 ", 3, "3.5"])
def test_numeric_retry_after(value: str | int) -> None:
    assert retry._retry_after_seconds(header_error({"Retry-After": value})) == float(value)


@pytest.mark.parametrize("delay, expected", [(120, 120), (0, 0), (-120, 0)])
def test_http_date_retry_after(
    monkeypatch: pytest.MonkeyPatch, delay: int, expected: int
) -> None:
    monkeypatch.setattr(retry.time, "time", lambda: NOW)
    error = header_error({"Retry-After": http_date(delay)})

    assert retry._retry_after_seconds(error) == expected
    assert retry._backoff_delay(1, base_delay=1, max_delay=16, error=error) == expected


@pytest.mark.parametrize("header", ("Retry-After", *AZURE_RETRY_HEADERS))
@pytest.mark.parametrize("zero", ["0", 0, "0.0"])
def test_zero_is_valid_and_overrides_message_hint(header: str, zero: str | int) -> None:
    error = header_error({header: zero}, "retry_delay { seconds: 9 }")

    assert retry._retry_after_seconds(error) == 0
    assert retry._backoff_delay(2, base_delay=1, max_delay=16, error=error) == 0


@pytest.mark.parametrize(
    "value",
    ["4, 60, malformed, 10", ["4", "60", None, "malformed"], ("60", "2")],
)
@pytest.mark.parametrize("header", ["ReTrY-aFtEr", AZURE_RETRY_HEADERS[0]])
def test_multiple_header_values_select_maximum(header: str, value: object) -> None:
    assert retry._retry_after_seconds(header_error({header: value})) == 60


def test_repeated_httpx_headers_and_dates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(retry.time, "time", lambda: NOW)
    headers = httpx.Headers([
        ("Retry-After", http_date(30)),
        ("retry-after", "10"),
        ("RETRY-AFTER", http_date(120)),
        (AZURE_RETRY_HEADERS[0], "5"),
        (AZURE_RETRY_HEADERS[0].upper(), "90"),
    ])

    assert retry._retry_after_seconds(header_error(headers)) == 120


@pytest.mark.parametrize(
    "value", [None, "", "nonsense", "-1", -1, "NaN", "inf", "-inf", "1e999", {}, []]
)
@pytest.mark.parametrize("header", ["Retry-After", AZURE_RETRY_HEADERS[-1]])
def test_malformed_delays_fall_back_to_backoff(
    monkeypatch: pytest.MonkeyPatch, header: str, value: object
) -> None:
    monkeypatch.setattr(retry.random, "uniform", lambda _low, _high: 1.0)
    error = header_error({header: value})

    assert retry._retry_after_seconds(error) is None
    assert retry._backoff_delay(2, base_delay=2, max_delay=16, error=error) == 4


def test_malformed_values_do_not_hide_valid_delay() -> None:
    error = header_error({
        "Retry-After": "invalid, NaN, 0, inf, -1, 45",
        AZURE_RETRY_HEADERS[0]: None,
        AZURE_RETRY_HEADERS[1]: "60, malformed",
        "x-unrelated-retry-after": "999",
    })

    assert retry._retry_after_seconds(error) == 60


@pytest.mark.parametrize("headers", [None, {}])
def test_missing_headers(headers: object) -> None:
    assert retry._retry_after_seconds(header_error(headers)) is None
    assert retry._retry_after_seconds(RuntimeError("validation failed")) is None


@pytest.mark.parametrize("attribute", ["retry_after", "retry_after_seconds"])
def test_exception_retry_attributes_still_work(attribute: str) -> None:
    error = header_error({"Retry-After": "invalid"})
    setattr(error, attribute, "7")

    assert retry._retry_after_seconds(error) == 7


@pytest.mark.parametrize(
    "message", ["retry_delay { seconds: 7 }", "retry-after: 7", "RETRY_AFTER=7"]
)
def test_gemini_and_other_message_hints_still_work(message: str) -> None:
    error = RuntimeError(message)

    assert retry._retry_after_seconds(error) == 7
    assert retry._backoff_delay(1, base_delay=1, max_delay=16, error=error) == 7


def test_exponential_backoff_remains_capped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(retry.random, "uniform", lambda _low, _high: 1.2)
    error = RuntimeError("temporary failure")

    assert retry._backoff_delay(2, base_delay=1, max_delay=16, error=error) == 2.4
    assert retry._backoff_delay(10, base_delay=1, max_delay=16, error=error) == 16


def test_call_with_backoff_honors_provider_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    sleep = Mock()
    monkeypatch.setattr(retry.time, "sleep", sleep)
    operation = Mock(side_effect=[header_error({AZURE_RETRY_HEADERS[0]: "120"}), "ok"])

    assert retry.call_with_backoff(
        "Azure Cost Management", operation, is_retryable=retry.is_azure_retryable, max_delay=16
    ) == "ok"
    sleep.assert_called_once_with(120)
    assert operation.call_count == 2


def test_call_with_backoff_success_does_not_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    sleep = Mock()
    monkeypatch.setattr(retry.time, "sleep", sleep)

    assert retry.call_with_backoff("test", lambda: "ok", is_retryable=lambda _error: True) == "ok"
    sleep.assert_not_called()


@pytest.mark.parametrize("retryable, attempts", [(False, 1), (True, 3)])
def test_call_with_backoff_preserves_failure_limits(
    monkeypatch: pytest.MonkeyPatch, retryable: bool, attempts: int
) -> None:
    sleep = Mock()
    monkeypatch.setattr(retry.time, "sleep", sleep)
    error = RuntimeError("failure")
    operation = Mock(side_effect=error)

    with pytest.raises(RuntimeError) as raised:
        retry.call_with_backoff(
            "test", operation, is_retryable=lambda _error: retryable, max_attempts=3
        )

    assert raised.value is error
    assert operation.call_count == attempts
    assert sleep.call_count == attempts - 1
