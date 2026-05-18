import logging
import random
import re
import time
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

_RETRYABLE_HTTP_STATUS_CODES = {408, 429, 500, 502, 503, 504}
_AWS_RETRYABLE_CODES = {
    "bandwidthlimitexceeded",
    "ec2throttledexception",
    "priorrequestnotcomplete",
    "provisionedthroughputexceededexception",
    "requestlimitexceeded",
    "requestthrottled",
    "slowdown",
    "throttling",
    "throttledexception",
    "throttlingexception",
    "throttlinginvocationexception",
    "toomanyrequestsexception",
    "transactioninprogressexception",
}
_RETRY_DELAY_PATTERNS = (
    re.compile(r"retry[_ -]?after[:= ]+(\d+)", re.IGNORECASE),
    re.compile(r"retry_delay.*?seconds[:= ]+(\d+)", re.IGNORECASE | re.DOTALL),
)


def _exception_tuple(*classes: Any) -> tuple[type[BaseException], ...]:
    return tuple(cls for cls in classes if isinstance(cls, type) and issubclass(cls, BaseException))


def _status_code(error: Exception) -> int | None:
    response = getattr(error, "response", None)
    if response is not None:
        status_code = getattr(response, "status_code", None)
        if isinstance(status_code, int):
            return status_code
        resp = getattr(error, "resp", None)
        status = getattr(resp, "status", None)
        if isinstance(status, int):
            return status

    status_code = getattr(error, "status_code", None)
    return status_code if isinstance(status_code, int) else None


def _retry_after_seconds(error: Exception) -> float | None:
    response = getattr(error, "response", None)
    headers = getattr(response, "headers", None)
    if headers:
        retry_after = headers.get("Retry-After") or headers.get("retry-after")
        if retry_after:
            try:
                return max(float(retry_after), 0.0)
            except (TypeError, ValueError):
                pass

    for candidate in (getattr(error, "retry_after", None), getattr(error, "retry_after_seconds", None)):
        if candidate is None:
            continue
        try:
            return max(float(candidate), 0.0)
        except (TypeError, ValueError):
            continue

    message = str(error or "")
    for pattern in _RETRY_DELAY_PATTERNS:
        match = pattern.search(message)
        if not match:
            continue
        try:
            return max(float(match.group(1)), 0.0)
        except (TypeError, ValueError):
            continue

    return None


def _backoff_delay(
    attempt: int,
    *,
    base_delay: float,
    max_delay: float,
    error: Exception,
) -> float:
    explicit_delay = _retry_after_seconds(error)
    if explicit_delay is not None:
        return min(explicit_delay, max_delay)

    exponential = min(base_delay * (2 ** (attempt - 1)), max_delay)
    return min(exponential * random.uniform(0.8, 1.2), max_delay)


def call_with_backoff(
    operation_name: str,
    func: Callable[[], T],
    *,
    is_retryable: Callable[[Exception], bool],
    max_attempts: int = 4,
    base_delay: float = 1.0,
    max_delay: float = 16.0,
) -> T:
    for attempt in range(1, max_attempts + 1):
        try:
            return func()
        except Exception as error:
            should_retry = attempt < max_attempts and is_retryable(error)
            if not should_retry:
                raise

            delay = _backoff_delay(
                attempt,
                base_delay=base_delay,
                max_delay=max_delay,
                error=error,
            )
            logger.warning(
                "%s failed with a retryable error on attempt %s/%s. Retrying in %.2fs: %s",
                operation_name,
                attempt,
                max_attempts,
                delay,
                error,
            )
            time.sleep(delay)

    raise RuntimeError(f"{operation_name} exhausted retry attempts")


def build_aws_retry_config(
    *,
    region_name: str,
    connect_timeout: int = 5,
    read_timeout: int = 15,
    max_attempts: int = 8,
) -> Any:
    from botocore.config import Config

    return Config(
        retries={"max_attempts": max_attempts, "mode": "adaptive"},
        connect_timeout=connect_timeout,
        read_timeout=read_timeout,
        region_name=region_name,
    )


def is_httpx_retryable(error: Exception) -> bool:
    try:
        import httpx
    except Exception:
        return False

    request_error_types = _exception_tuple(getattr(httpx, "RequestError", None))
    if request_error_types and isinstance(error, request_error_types):
        return True

    http_status_error_types = _exception_tuple(getattr(httpx, "HTTPStatusError", None))
    if http_status_error_types and isinstance(error, http_status_error_types):
        status_code = _status_code(error)
        return status_code in _RETRYABLE_HTTP_STATUS_CODES

    return False


def is_aws_retryable(error: Exception) -> bool:
    try:
        from botocore.exceptions import (
            ClientError,
            ConnectionClosedError,
            EndpointConnectionError,
            ReadTimeoutError,
        )
    except Exception:
        ClientError = None
        ConnectionClosedError = None
        EndpointConnectionError = None
        ReadTimeoutError = None

    transport_errors = _exception_tuple(ConnectionClosedError, EndpointConnectionError, ReadTimeoutError)
    if transport_errors and isinstance(error, transport_errors):
        return True

    client_error_types = _exception_tuple(ClientError)
    if client_error_types and isinstance(error, client_error_types):
        code = str(getattr(error, "response", {}).get("Error", {}).get("Code", "") or "").strip().lower()
        if code in _AWS_RETRYABLE_CODES or code.startswith("throttl"):
            return True

    return False


def is_azure_retryable(error: Exception) -> bool:
    try:
        from azure.core.exceptions import HttpResponseError, ServiceRequestError, ServiceResponseError
    except Exception:
        HttpResponseError = None
        ServiceRequestError = None
        ServiceResponseError = None

    transport_errors = _exception_tuple(ServiceRequestError, ServiceResponseError)
    if transport_errors and isinstance(error, transport_errors):
        return True

    response_error_types = _exception_tuple(HttpResponseError)
    if response_error_types and isinstance(error, response_error_types):
        status_code = _status_code(error)
        if status_code in _RETRYABLE_HTTP_STATUS_CODES:
            return True

    message = str(error or "").lower()
    return any(token in message for token in ("too many requests", "throttl", "rate limit", "temporarily unavailable"))


def is_gcp_retryable(error: Exception) -> bool:
    try:
        from google.api_core.exceptions import (
            DeadlineExceeded,
            InternalServerError,
            ResourceExhausted,
            ServiceUnavailable,
            TooManyRequests,
        )
    except Exception:
        DeadlineExceeded = None
        InternalServerError = None
        ResourceExhausted = None
        ServiceUnavailable = None
        TooManyRequests = None

    try:
        from googleapiclient.errors import HttpError
    except Exception:
        HttpError = None

    api_core_errors = _exception_tuple(
        DeadlineExceeded,
        InternalServerError,
        ResourceExhausted,
        ServiceUnavailable,
        TooManyRequests,
    )
    if api_core_errors and isinstance(error, api_core_errors):
        return True

    http_error_types = _exception_tuple(HttpError)
    if http_error_types and isinstance(error, http_error_types):
        status_code = _status_code(error)
        if status_code in _RETRYABLE_HTTP_STATUS_CODES:
            return True

    message = str(error or "").lower()
    return any(token in message for token in ("too many requests", "rate limit", "quota", "resource exhausted", "temporarily unavailable"))
