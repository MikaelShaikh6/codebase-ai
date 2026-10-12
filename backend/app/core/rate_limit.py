from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
from time import monotonic
from typing import Callable

from fastapi import HTTPException, Request, status


_requests: dict[str, deque[float]] = defaultdict(deque)
_lock = Lock()


def rate_limit(name: str, *, max_requests: int, window_seconds: int) -> Callable:
    def dependency(request: Request) -> None:
        client = request.client.host if request.client else "unknown"
        key = f"{name}:{client}"
        now = monotonic()
        cutoff = now - window_seconds

        with _lock:
            timestamps = _requests[key]
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()
            if len(timestamps) >= max_requests:
                retry_after = max(1, int(timestamps[0] + window_seconds - now))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please try again later.",
                    headers={"Retry-After": str(retry_after)},
                )
            timestamps.append(now)

    return dependency


def clear_rate_limits() -> None:
    with _lock:
        _requests.clear()
