from fastapi import APIRouter
from db.sqlite import get_sessions, get_session_messages

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/sessions")
def list_sessions():
    return get_sessions()


@router.get("/sessions/{session_id}")
def get_session(session_id: str):
    return get_session_messages(session_id)
