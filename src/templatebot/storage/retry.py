"""Retry helper for outbound HTTP calls.

httpx's own transport-level retries only cover connection errors, so they
never re-issue a request that got as far as the server and then timed out
waiting for the response. `retry_async` sits *above* the transport, wrapping
a call that has already been through ``raise_for_status``, so read timeouts
and retryable status codes are both covered.

Retries are opted into per call site rather than configured globally: a
non-idempotent ``POST`` must never inherit them implicitly.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx
from structlog.stdlib import BoundLogger

__all__ = [
    "BASE_BACKOFF",
    "DEFAULT_POLICY",
    "JITTER",
    "MAX_ATTEMPTS",
    "MAX_BACKOFF",
    "RetryPolicy",
    "retry_async",
]

MAX_ATTEMPTS = 3
"""Total number of attempts, including the first one, before giving up."""

BASE_BACKOFF = 0.5
"""Delay, in seconds, before the first retry."""

MAX_BACKOFF = 8.0
"""Cap, in seconds, on the exponentially-growing delay between retries."""

JITTER = 0.25
"""Fraction by which each delay is randomly scaled up or down.

Jitter keeps a burst of concurrent callers from retrying in lockstep after a
shared upstream hiccup.
"""


@dataclass(frozen=True, slots=True, kw_only=True)
class RetryPolicy:
    """How many times to retry a transient failure, and how long to wait."""

    max_attempts: int = MAX_ATTEMPTS
    """Total attempts, including the first, before the error is re-raised."""

    base_backoff: float = BASE_BACKOFF
    """Delay, in seconds, before the first retry."""

    max_backoff: float = MAX_BACKOFF
    """Cap, in seconds, on the exponential delay."""

    jitter: float = JITTER
    """Fraction by which each delay is randomly scaled up or down."""


DEFAULT_POLICY = RetryPolicy()
"""The policy used when a call site does not supply one of its own."""


async def retry_async[T](
    func: Callable[[], Awaitable[T]],
    *,
    policy: RetryPolicy = DEFAULT_POLICY,
    logger: BoundLogger,
) -> T:
    """Call an awaitable, retrying it if it fails transiently.

    Parameters
    ----------
    func
        A zero-argument callable returning an awaitable. It is called afresh
        for each attempt, so it must be a factory (a coroutine function or a
        closure), not a single already-created coroutine object.
    policy
        How many attempts to make and how long to wait between them. Defaults
        to `DEFAULT_POLICY`.
    logger
        Logger for the per-retry log lines. Bind any call-site context (the
        API method, for instance) before passing it in.

    Returns
    -------
    T
        Whatever ``func`` returned on its successful attempt.

    Raises
    ------
    Exception
        Whatever ``func`` raised, either immediately if the failure is not
        transient or after the final attempt if it is.

    Notes
    -----
    A failure is transient if it is an `httpx.TransportError` (connection
    failures and timeouts) or an `httpx.HTTPStatusError` carrying a 5xx or
    429 status. Everything else — a 4xx that is the caller's own fault, or
    any non-HTTP exception — propagates on the first attempt, because
    retrying it would only repeat the same failure.
    """
    attempt = 0
    while True:
        attempt += 1
        try:
            return await func()
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            if not _is_transient(exc):
                raise
            if attempt >= policy.max_attempts:
                logger.warning(
                    "http_retry_exhausted",
                    attempts=attempt,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
                raise
            delay = _compute_delay(exc, attempt=attempt, policy=policy)
            logger.warning(
                "http_retry",
                attempt=attempt,
                max_attempts=policy.max_attempts,
                delay=delay,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            await _sleep(delay)


async def _sleep(delay: float) -> None:
    """Wait between retry attempts.

    Wrapping `asyncio.sleep` gives tests a seam they can patch to assert on
    the delays without actually waiting for them.
    """
    await asyncio.sleep(delay)


def _is_transient(exc: httpx.TransportError | httpx.HTTPStatusError) -> bool:
    """Report whether a failure is worth retrying."""
    if isinstance(exc, httpx.TransportError):
        return True
    status = exc.response.status_code
    return (
        status >= httpx.codes.INTERNAL_SERVER_ERROR
        or status == httpx.codes.TOO_MANY_REQUESTS
    )


def _compute_delay(
    exc: httpx.TransportError | httpx.HTTPStatusError,
    *,
    attempt: int,
    policy: RetryPolicy,
) -> float:
    """Compute how long to wait before the next attempt.

    The delay grows exponentially from `RetryPolicy.base_backoff`, is capped
    at `RetryPolicy.max_backoff`, and is then randomly scaled by up to
    `RetryPolicy.jitter` in either direction. A ``Retry-After`` header raises
    the floor: the server's own instruction is always honored in full, even
    when it exceeds the cap.
    """
    backoff = min(policy.base_backoff * 2 ** (attempt - 1), policy.max_backoff)
    delay = backoff * random.uniform(  # noqa: S311
        1 - policy.jitter, 1 + policy.jitter
    )
    retry_after = _parse_retry_after(exc)
    if retry_after is not None:
        delay = max(delay, retry_after)
    return delay


def _parse_retry_after(
    exc: httpx.TransportError | httpx.HTTPStatusError,
) -> float | None:
    """Extract the ``Retry-After`` delay, in seconds, from a failure.

    Returns `None` when the failure carries no usable ``Retry-After`` header.
    Both header forms are accepted: a delay in seconds, and an HTTP date.
    """
    if not isinstance(exc, httpx.HTTPStatusError):
        return None
    value = exc.response.headers.get("Retry-After")
    if value is None:
        return None
    try:
        return max(float(value), 0.0)
    except ValueError:
        pass
    try:
        retry_at = parsedate_to_datetime(value)
    except TypeError, ValueError:
        return None
    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=UTC)
    return max((retry_at - datetime.now(tz=UTC)).total_seconds(), 0.0)
