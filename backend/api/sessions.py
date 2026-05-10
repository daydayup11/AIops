from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel
from db.sqlite import (
    get_sessions,
    get_session_messages,
    get_message_image,
    delete_session,
    rename_session,
)

router = APIRouter()


class PatchSessionBody(BaseModel):
    title: str


@router.get("/sessions")
def list_sessions():
    return get_sessions()


@router.get("/sessions/{session_id}/messages")
def list_messages(session_id: str):
    sessions = get_sessions()
    if not any(s["id"] == session_id for s in sessions):
        raise HTTPException(status_code=404, detail="Session not found")
    return get_session_messages(session_id)


@router.get("/sessions/{session_id}/messages/{msg_id}/image")
def get_image(session_id: str, msg_id: int):
    data = get_message_image(msg_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Image not found")
    return {"image_data": data}


@router.delete("/sessions/{session_id}", status_code=204)
def remove_session(session_id: str):
    sessions = get_sessions()
    if not any(s["id"] == session_id for s in sessions):
        raise HTTPException(status_code=404, detail="Session not found")
    delete_session(session_id)
    return Response(status_code=204)


@router.patch("/sessions/{session_id}")
def update_session(session_id: str, body: PatchSessionBody):
    sessions = get_sessions()
    if not any(s["id"] == session_id for s in sessions):
        raise HTTPException(status_code=404, detail="Session not found")
    rename_session(session_id, body.title)
    updated = next(s for s in get_sessions() if s["id"] == session_id)
    return updated
