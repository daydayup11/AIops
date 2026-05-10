from pydantic import BaseModel, Field
from typing import Any, Literal, Optional
from datetime import datetime


class WSIncoming(BaseModel):
    session_id: str
    message: str


class WSMessage(BaseModel):
    type: Literal["clarify", "progress", "result", "plan", "summary", "error", "done"]
    content: Any
    render: Optional[Literal["image", "text"]] = None
    elapsed: Optional[float] = None


class AnalysisPlan(BaseModel):
    goal: str
    approach: str
    expected_findings: list[str]
    analysis_dimensions: list[str]
    viz_intent: str


class TaskPlan(BaseModel):
    analysis_plan: Optional[AnalysisPlan] = None
    clarification_needed: bool = False
    clarification_question: Optional[str] = None
    estimated_seconds: int = 10


class PyScript(BaseModel):
    script_code: str
    description: str


class CodeReviewResult(BaseModel):
    approved: bool
    issues: list[str]


class SummaryReport(BaseModel):
    title: str
    key_points: list[str]
    conclusion: str


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
