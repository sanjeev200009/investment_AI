"""Evaluation-plan logging: recommendation snapshots (E5), lesson views (E7)
and chat answer timing (E6). Offline; the snapshot test uses in-memory SQLite."""

import json
import logging
from datetime import date
from types import SimpleNamespace as NS

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.dependencies import get_current_user, get_db
from app.models.evaluation import RecommendationSnapshot
from app.routers import chat, learn
from app.services import recommendations
from tests.test_chat_stream import FakeSession


def test_snapshot_saves_top_picks_per_category_and_reruns_cleanly(monkeypatch):
    engine = create_engine("sqlite://")
    RecommendationSnapshot.__table__.create(engine)
    db = sessionmaker(bind=engine)()

    def fake_build(db, limit, risk_category):
        items = [{"symbol": f"{risk_category}{i}", "score": 90 - i, "price": 10.0 + i}
                 for i in range(12)]
        return {"items": items[:limit]}

    monkeypatch.setattr(recommendations, "build_recommendations", fake_build)
    day = date(2026, 9, 28)
    expected = len(recommendations.RISK_WEIGHTS) * recommendations.SNAPSHOT_SIZE

    assert recommendations.snapshot_recommendations(db, day) == expected
    assert recommendations.snapshot_recommendations(db, day) == expected  # same day again
    rows = db.query(RecommendationSnapshot).all()
    assert len(rows) == expected
    top = min((r for r in rows if r.risk_category == "Low"), key=lambda r: r.rank)
    assert (top.rank, top.symbol, top.model_version) == (1, "Low0", recommendations.MODEL_VERSION)


class RecordingDB:
    def __init__(self, fail=False):
        self.added, self.fail = [], fail

    def add(self, obj):
        if self.fail:
            raise RuntimeError("db down")
        self.added.append(obj)

    def commit(self):
        pass

    def rollback(self):
        pass


def _learn_client(db):
    app = FastAPI()
    app.include_router(learn.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: NS(user_id="u-1")
    return TestClient(app)


def test_opening_a_lesson_is_recorded():
    db = RecordingDB()
    r = _learn_client(db).get("/learn/lessons/diversification")
    assert r.status_code == 200
    assert [(v.user_id, v.lesson_id) for v in db.added] == [("u-1", "diversification")]


def test_lesson_still_shows_when_the_view_cannot_be_saved():
    r = _learn_client(RecordingDB(fail=True)).get("/learn/lessons/diversification")
    assert r.status_code == 200 and r.json()["id"] == "diversification"


def test_chat_stream_logs_answer_timing(monkeypatch, caplog):
    async def fake_stream_agent(user_message, session_id, db, user):
        yield f"data: {json.dumps({'type': 'tool_start', 'tool': 'x'})}\n\n"
        yield f"data: {json.dumps({'type': 'token', 'content': 'ok'})}\n\n"
        yield f"data: {json.dumps({'type': 'done', 'message_id': 1})}\n\n"

    monkeypatch.setattr(chat, "SessionLocal", lambda: FakeSession("stream"))
    monkeypatch.setattr(chat, "stream_agent", fake_stream_agent)
    app = FastAPI()
    app.include_router(chat.router)
    app.dependency_overrides[get_db] = lambda: FakeSession("request")
    app.dependency_overrides[get_current_user] = lambda: NS(user_id="u-1")

    with caplog.at_level(logging.INFO, logger=chat.logger.name), TestClient(app) as client:
        client.post("/chat/stream", json={"message": "hello", "session_id": 7})

    line = next(r.getMessage() for r in caplog.records if "chat_timing" in r.getMessage())
    assert "first_token_ms=" in line and "first_token_ms=None" not in line and "total_ms=" in line
