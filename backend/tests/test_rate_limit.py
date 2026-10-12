import pytest
from fastapi import HTTPException, Request

from app.core.rate_limit import clear_rate_limits, rate_limit


def request_for(host: str = "127.0.0.1") -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
            "client": (host, 1234),
            "query_string": b"",
            "scheme": "http",
            "server": ("testserver", 80),
        }
    )


def test_rate_limit_rejects_after_configured_count() -> None:
    clear_rate_limits()
    dependency = rate_limit("test", max_requests=2, window_seconds=60)

    dependency(request_for())
    dependency(request_for())
    with pytest.raises(HTTPException) as error:
        dependency(request_for())

    assert error.value.status_code == 429
    assert error.value.headers["Retry-After"]


def test_rate_limits_are_separated_by_client() -> None:
    clear_rate_limits()
    dependency = rate_limit("test", max_requests=1, window_seconds=60)

    dependency(request_for("127.0.0.1"))
    dependency(request_for("127.0.0.2"))
