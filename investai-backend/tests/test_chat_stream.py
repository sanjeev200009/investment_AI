"""POST /chat/stream must not use the request's DB session inside the stream.

On FastAPI 0.106-0.117 (this project pins 0.111) a yield-dependency's cleanup
runs before a StreamingResponse body is iterated, so the session from get_db is
already closed when the generator starts. The route therefore opens its own
session for the stream. This test drives the real route through TestClient and
fails if the generator ever touches the request session.
"""

import json
from types import SimpleNamespace as NS

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies import get_current_user, get_db
from app.routers import chat


class FakeSession:
    def __init__(self, name):
        self.name = name
        self.closed = False

    def close(self):
        self.closed = True

    def rollback(self):
        pass

    def get(self, model, pk):
        return NS(user_id=pk, owner_session=self)

    def query(self, *a):
        return self

    def filter(self, *a):
        return self

    def first(self):
        return NS(session_id=7)


def test_stream_uses_its_own_open_session(monkeypatch):
    request_db = FakeSession("request")
    stream_db = FakeSession("stream")
    seen = {}

    def fake_get_db():
        try:
            yield request_db
        finally:
            request_db.close()

    async def fake_stream_agent(user_message, session_id, db, user):
        seen["db"] = db
        seen["db_closed_at_start"] = db.closed
        seen["request_closed_at_start"] = request_db.closed
        seen["user_session"] = user.owner_session
        yield f"data: {json.dumps({'type': 'token', 'content': 'ok'})}\n\n"
        yield f"data: {json.dumps({'type': 'done', 'message_id': 1})}\n\n"

    monkeypatch.setattr(chat, "SessionLocal", lambda: stream_db)
    monkeypatch.setattr(chat, "stream_agent", fake_stream_agent)

    app = FastAPI()
    app.include_router(chat.router)
    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = lambda: NS(user_id="u-1")

    with TestClient(app) as client:
        r = client.post("/chat/stream", json={"message": "hello", "session_id": 7})

    assert r.status_code == 200
    assert '"type": "done"' in r.text
    assert seen["db"] is stream_db and seen["user_session"] is stream_db
    assert seen["db_closed_at_start"] is False
    assert stream_db.closed is True   # released when the stream ends


def test_stream_error_is_generic(monkeypatch):
    async def boom(**kw):
        raise RuntimeError("psycopg2 secret-ish internals")
        yield  # pragma: no cover

    monkeypatch.setattr(chat, "SessionLocal", lambda: FakeSession("stream"))
    monkeypatch.setattr(chat, "stream_agent", boom)
    app = FastAPI()
    app.include_router(chat.router)
    app.dependency_overrides[get_db] = lambda: FakeSession("request")
    app.dependency_overrides[get_current_user] = lambda: NS(user_id="u-1")

    with TestClient(app) as client:
        r = client.post("/chat/stream", json={"message": "hello", "session_id": 7})
    assert "psycopg2" not in r.text
    assert '"type": "error"' in r.text


def test_message_length_is_capped():
    app = FastAPI()
    app.include_router(chat.router)
    app.dependency_overrides[get_db] = lambda: FakeSession("request")
    app.dependency_overrides[get_current_user] = lambda: NS(user_id="u-1")
    with TestClient(app) as client:
        r = client.post("/chat/stream", json={"message": "x" * 2001})
    assert r.status_code == 422
