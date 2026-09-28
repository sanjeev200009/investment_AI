"""Per-client request limits for the endpoints that cost money or guard secrets.

Keyed on the bearer token when present (one user across devices shares a token
per session, which is close enough) and on the client IP otherwise, so the
unauthenticated /auth endpoints are covered too.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

# ponytail: in-process sliding window. Each web worker counts separately, so the
# effective limit is N_workers x max. Move to Redis (INCR + EXPIRE) if the API
# runs more than a couple of workers.
_hits: dict[str, deque[float]] = defaultdict(deque)
_lock = threading.Lock()


def _client_key(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer ") and len(auth) > 20:
        return "t:" + auth[-32:]
    fwd = request.headers.get("x-forwarded-for", "")
    ip = fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "?")
    return "ip:" + ip


def check(key: str, max_hits: int, window_s: float, now: float | None = None) -> bool:
    """Record a hit for ``key``; return False if it exceeds the limit."""
    now = time.monotonic() if now is None else now
    with _lock:
        q = _hits[key]
        while q and q[0] <= now - window_s:
            q.popleft()
        if len(q) >= max_hits:
            return False
        q.append(now)
        return True


def limit(bucket: str, max_hits: int, window_s: float):
    """FastAPI dependency: at most ``max_hits`` calls per ``window_s`` seconds."""

    def dependency(request: Request) -> None:
        if not check(f"{bucket}|{_client_key(request)}", max_hits, window_s):
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please wait a minute and try again.",
                headers={"Retry-After": str(int(window_s))},
            )

    return dependency
