import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import db.sqlite as db_module
from fastapi.testclient import TestClient

@pytest.fixture(autouse=True)
def tmp_db(monkeypatch, tmp_path):
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(db_module, "_DB_PATH", db_path)
    db_module.init_db()
    yield

@pytest.fixture
def client(tmp_db):
    # Import app after monkeypatching DB path
    from main import app
    return TestClient(app)

def test_get_sessions_empty(client):
    r = client.get("/api/v1/sessions")
    assert r.status_code == 200
    assert r.json() == []

def test_get_sessions_returns_list(client):
    sid = db_module.create_session("hello")
    r = client.get("/api/v1/sessions")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["id"] == sid
    assert data[0]["title"] == "hello"

def test_get_session_messages(client):
    sid = db_module.create_session("s1")
    db_module.save_message(sid, "user", "text", "hi")
    r = client.get(f"/api/v1/sessions/{sid}/messages")
    assert r.status_code == 200
    msgs = r.json()
    assert len(msgs) == 1
    assert msgs[0]["content"] == "hi"
    assert "image_data" not in msgs[0]

def test_get_session_messages_unknown_session_returns_empty(client):
    r = client.get("/api/v1/sessions/nonexistent/messages")
    assert r.status_code == 200
    assert r.json() == []

def test_get_message_image(client):
    sid = db_module.create_session("s1")
    db_module.save_message(sid, "assistant", "image", "[图表]", image_data="b64data")
    msgs = db_module.get_session_messages(sid)
    msg_id = msgs[0]["id"]
    r = client.get(f"/api/v1/sessions/{sid}/messages/{msg_id}/image")
    assert r.status_code == 200
    assert r.json()["image_data"] == "b64data"

def test_get_message_image_not_found(client):
    sid = db_module.create_session("s1")
    r = client.get(f"/api/v1/sessions/{sid}/messages/999/image")
    assert r.status_code == 404

def test_delete_session(client):
    sid = db_module.create_session("del")
    r = client.delete(f"/api/v1/sessions/{sid}")
    assert r.status_code == 204
    assert db_module.get_session_messages(sid) == []

def test_delete_session_not_found(client):
    r = client.delete("/api/v1/sessions/nonexistent")
    assert r.status_code == 404

def test_patch_session_title(client):
    sid = db_module.create_session("old")
    r = client.patch(f"/api/v1/sessions/{sid}", json={"title": "new"})
    assert r.status_code == 200
    assert r.json()["title"] == "new"

def test_patch_session_not_found(client):
    r = client.patch("/api/v1/sessions/nonexistent", json={"title": "x"})
    assert r.status_code == 404

def test_get_message_image_wrong_session(client):
    sid1 = db_module.create_session("s1")
    sid2 = db_module.create_session("s2")
    db_module.save_message(sid1, "assistant", "image", "[图表]", image_data="b64data")
    msgs = db_module.get_session_messages(sid1)
    msg_id = msgs[0]["id"]
    # Access msg_id from sid1 via sid2's URL — should 404
    r = client.get(f"/api/v1/sessions/{sid2}/messages/{msg_id}/image")
    assert r.status_code == 404
