from pydantic import BaseModel, Field
from typing import Any, Literal, Optional
from datetime import datetime


class WSIncoming(BaseModel):
    session_id: str
    message: str


class WSMessage(BaseModel):
    type: Literal["clarify", "progress", "result", "error", "done"]
    content: Any
    render: Optional[Literal["echarts", "html", "table", "text"]] = None
    elapsed: Optional[float] = None


class SubTask(BaseModel):
    id: str
    description: str
    tables: list[str]
    time_range_hours: int = 24


class TaskPlan(BaseModel):
    tasks: list[SubTask]
    clarification_needed: bool = False
    clarification_question: Optional[str] = None
    estimated_seconds: int = 10


class SQLTask(BaseModel):
    task_id: str
    sql: str
    description: str


class VizSpec(BaseModel):
    render_type: Literal["echarts", "html"]
    chart_type: Optional[str] = None
    title: str
    x_field: Optional[str] = None
    y_field: Optional[str] = None
    series_field: Optional[str] = None
    insight: str = ""


class ChatMessage(BaseModel):
    id: int
    session_id: str
    role: Literal["user", "assistant"]
    type: str
    content: str
    created_at: datetime


class Session(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
