import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Point to a temp DB so tests don't touch the real one
import db.sqlite as db_module
import tempfile, pathlib

@pytest.fixture(autouse=True)
def tmp_db(monkeypatch, tmp_path):
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(db_module, "_DB_PATH", db_path)
    db_module.init_db()
    yield

def test_save_message_with_image_data():
    sid = db_module.create_session("test")
    db_module.save_message(sid, "assistant", "image", "[图表]", image_data="base64abc")
    msgs = db_module.get_session_messages(sid)
    assert len(msgs) == 1
    assert msgs[0]["content"] == "[图表]"
    assert "image_data" not in msgs[0]  # get_session_messages excludes image_data

def test_get_message_image_returns_data():
    sid = db_module.create_session("test")
    db_module.save_message(sid, "assistant", "image", "[图表]", image_data="base64abc")
    msgs = db_module.get_session_messages(sid)
    msg_id = msgs[0]["id"]
    result = db_module.get_message_image(msg_id)
    assert result == "base64abc"

def test_get_message_image_returns_none_for_text():
    sid = db_module.create_session("test")
    db_module.save_message(sid, "user", "text", "hello")
    msgs = db_module.get_session_messages(sid)
    result = db_module.get_message_image(msgs[0]["id"])
    assert result is None

def test_delete_session_removes_messages():
    sid = db_module.create_session("test")
    db_module.save_message(sid, "user", "text", "hi")
    db_module.delete_session(sid)
    assert db_module.get_session_messages(sid) == []
    sessions = db_module.get_sessions()
    assert all(s["id"] != sid for s in sessions)

def test_rename_session():
    sid = db_module.create_session("旧标题")
    db_module.rename_session(sid, "新标题")
    sessions = db_module.get_sessions()
    match = next(s for s in sessions if s["id"] == sid)
    assert match["title"] == "新标题"
