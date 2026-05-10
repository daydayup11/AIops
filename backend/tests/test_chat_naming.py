import asyncio
import json
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import db.sqlite as db_module

@pytest.fixture(autouse=True)
def tmp_db(monkeypatch, tmp_path):
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(db_module, "_DB_PATH", db_path)
    db_module.init_db()
    yield

@pytest.mark.asyncio
async def test_generate_session_title_sends_ws_message(monkeypatch):
    from api.chat import generate_and_push_title

    sent = []

    async def fake_send(payload):
        sent.append(payload)

    sid = db_module.create_session("新对话")

    # Mock LLM to return a fixed title
    class FakeLLM:
        def invoke(self, messages):
            class R:
                content = "流量分析"
            return R()

    monkeypatch.setattr("api.chat._get_llm", lambda: FakeLLM())

    await generate_and_push_title(sid, "查一下今天的流量分布", fake_send)

    # Title was saved to DB
    sessions = db_module.get_sessions()
    match = next(s for s in sessions if s["id"] == sid)
    assert match["title"] == "流量分析"

    # session_title message was pushed
    assert any(m.get("type") == "session_title" for m in sent)
    title_msg = next(m for m in sent if m.get("type") == "session_title")
    assert title_msg["session_id"] == sid
    assert title_msg["title"] == "流量分析"

@pytest.mark.asyncio
async def test_generate_session_title_silent_on_llm_failure(monkeypatch):
    from api.chat import generate_and_push_title

    sent = []

    async def fake_send(payload):
        sent.append(payload)

    sid = db_module.create_session("新对话")

    class FailingLLM:
        def invoke(self, messages):
            raise RuntimeError("LLM failed")

    monkeypatch.setattr("api.chat._get_llm", lambda: FailingLLM())

    # Should not raise
    await generate_and_push_title(sid, "some question", fake_send)

    # Title unchanged
    sessions = db_module.get_sessions()
    match = next(s for s in sessions if s["id"] == sid)
    assert match["title"] == "新对话"

    # No session_title message pushed
    assert not any(m.get("type") == "session_title" for m in sent)
