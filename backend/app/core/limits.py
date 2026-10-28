from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from fastapi import Request
from fastapi.responses import JSONResponse

_requests: dict[str, deque[float]] = defaultdict(deque)
_lock = Lock()
WINDOW_SECONDS = 60


async def rate_limit(request: Request, call_next):
    path = request.url.path
    if not path.startswith("/api/v1/"):
        return await call_next(request)
    if path.endswith("/auth/login") or path.endswith("/auth/register"):
        limit = 8
    elif path.endswith("/diagnosis/predict") or path.endswith("/risk/predict") or path.endswith("/weather/refresh"):
        limit = 12
    else:
        return await call_next(request)

    client = request.client.host if request.client else "unknown"
    key = f"{client}:{path}"
    now = monotonic()
    with _lock:
        timestamps = _requests[key]
        while timestamps and now - timestamps[0] >= WINDOW_SECONDS:
            timestamps.popleft()
        if len(timestamps) >= limit:
            return JSONResponse(status_code=429, content={"detail": "Too many requests. Please wait before trying again."})
        timestamps.append(now)
        if len(_requests) > 10_000:
            expired_keys = [item for item, values in _requests.items() if not values or now - values[-1] >= WINDOW_SECONDS]
            for item in expired_keys:
                _requests.pop(item, None)
    return await call_next(request)
