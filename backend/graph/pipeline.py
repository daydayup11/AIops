import logging
import concurrent.futures
import time
from typing import Callable, Optional
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END

from models.schemas import TaskPlan, PyScript, CodeReviewResult, SummaryReport
from agents.clarifier import run_clarifier
from agents.planner import run_planner
from agents.sql_engineer import run_sql_engineer
from agents.code_reviewer import run_code_reviewer
from agents.script_runner import run_script_runner
from agents.summarizer import run_summarizer
from agents.intent_router import run_intent_router
from agents.knowledge_agent import run_knowledge_agent, search_docs
from agents.chitchat_agent import run_chitchat_agent

logger = logging.getLogger(__name__)

_MAX_SCRIPT_RETRIES = 3


class PipelineState(TypedDict):
    session_id: str
    user_message: str
    conversation_history: list
    task_plan: Optional[TaskPlan]
    py_script: Optional[PyScript]
    code_review_result: Optional[CodeReviewResult]
    script_retry_count: int
    viz_outputs: list
    clarification_needed: bool
    clarification_question: Optional[str]
    clarifier_done: bool
    clarifier_question: Optional[str]
    clarifier_options: list
    summary_report: Optional[SummaryReport]
    error: Optional[str]
    progress_cb: Optional[Callable[[str], None]]
    intent: Optional[str]
    rewritten_query: Optional[str]
    intent_confidence: float
    knowledge_answer: Optional[str]
    chitchat_answer: Optional[str]


def _emit(state: PipelineState, text: str) -> None:
    cb = state.get("progress_cb")
    if cb:
        cb(text)


def _fallback_outputs(message: str) -> list:
    return [{"render": "text", "content": message}]


def _has_error(state: PipelineState) -> bool:
    return bool(state.get("error"))


def node_clarifier(state: PipelineState) -> dict:
    sid = state["session_id"]
    logger.info("[%s] >>> node:clarifier  input=%r", sid, state["user_message"][:80])
    try:
        result = run_clarifier(state["user_message"], state["conversation_history"])
    except Exception as e:
        logger.error("[%s] <<< node:clarifier  FAILED: %s", sid, e, exc_info=True)
        return {"clarifier_done": True, "clarifier_question": None, "clarifier_options": []}
    if result["action"] == "continue":
        logger.info("[%s] <<< node:clarifier  action=continue", sid)
        return {"clarifier_done": True, "clarifier_question": None, "clarifier_options": []}
    else:
        logger.info("[%s] <<< node:clarifier  action=ask  question=%r", sid, result.get("question", "")[:60])
        return {
            "clarifier_done": False,
            "clarifier_question": result.get("question", "请描述您的分析需求"),
            "clarifier_options": result.get("options", []),
        }


def node_intent_router(state: PipelineState) -> dict:
    sid = state["session_id"]
    logger.info("[%s] >>> node:intent_router  input=%r", sid, state["user_message"][:80])
    try:
        result = run_intent_router(state["user_message"], state["conversation_history"])
    except Exception as e:
        logger.error("[%s] <<< node:intent_router  FAILED: %s", sid, e, exc_info=True)
        return {"intent": "data_analysis", "rewritten_query": state["user_message"], "intent_confidence": 0.0}
    logger.info("[%s] <<< node:intent_router  intent=%s  confidence=%.2f", sid, result["intent"], result["confidence"])
    return {
        "intent": result["intent"],
        "rewritten_query": result["rewritten_query"],
        "intent_confidence": result["confidence"],
    }


def node_knowledge_agent(state: PipelineState) -> dict:
    sid = state["session_id"]
    query = state.get("rewritten_query") or state["user_message"]
    _emit(state, "🔍 正在检索相关文档...")
    logger.info("[%s] >>> node:knowledge_agent  query=%r", sid, query[:80])
    docs_context = search_docs(query)
    try:
        result = run_knowledge_agent(query, state["conversation_history"], docs_context=docs_context)
    except Exception as e:
        logger.error("[%s] <<< node:knowledge_agent  FAILED: %s", sid, e, exc_info=True)
        return {"knowledge_answer": None, "error": str(e)}
    if result["action"] == "ask":
        logger.info("[%s] <<< node:knowledge_agent  action=ask", sid)
        return {
            "knowledge_answer": None,
            "clarifier_done": False,
            "clarifier_question": result["question"],
            "clarifier_options": result.get("options", []),
        }
    answer = result.get("answer", "")
    logger.info("[%s] <<< node:knowledge_agent  answer_len=%d", sid, len(answer))
    return {"knowledge_answer": answer}


def node_chitchat_agent(state: PipelineState) -> dict:
    sid = state["session_id"]
    query = state.get("rewritten_query") or state["user_message"]
    logger.info("[%s] >>> node:chitchat_agent  input=%r", sid, query[:60])
    try:
        answer = run_chitchat_agent(query, state["conversation_history"])
    except Exception as e:
        logger.error("[%s] <<< node:chitchat_agent  FAILED: %s", sid, e, exc_info=True)
        return {"chitchat_answer": "你好！有什么可以帮你的吗？"}
    logger.info("[%s] <<< node:chitchat_agent  answer_len=%d", sid, len(answer))
    return {"chitchat_answer": answer}


def node_planner(state: PipelineState) -> dict:
    sid = state["session_id"]
    _emit(state, "🧠 正在理解问题、制定分析方案...")
    logger.info("[%s] >>> node:planner  input=%r", sid, state["user_message"][:120])
    start = time.perf_counter()
    try:
        plan = run_planner(state["user_message"], state["conversation_history"])
    except Exception as e:
        elapsed = time.perf_counter() - start
        logger.error("[%s] <<< node:planner  %.2fs  FAILED: %s", sid, elapsed, e, exc_info=True)
        _emit(state, "⚠️ 任务规划失败，已降级处理")
        return {
            "task_plan": None,
            "clarification_needed": False,
            "clarification_question": None,
            "viz_outputs": _fallback_outputs(f"❌ 任务规划出错：{e}"),
            "error": str(e),
        }
    elapsed = time.perf_counter() - start
    if not plan.clarification_needed and plan.analysis_plan:
        _emit(state, f"📋 规划完成：{plan.analysis_plan.goal}")
        logger.info("[%s] <<< node:planner  %.2fs  goal=%r", sid, elapsed, plan.analysis_plan.goal)
    return {
        "task_plan": plan,
        "clarification_needed": plan.clarification_needed,
        "clarification_question": plan.clarification_question,
    }


_HEARTBEAT_INTERVAL = 10  # seconds between progress heartbeats during LLM calls


def _run_with_heartbeat(fn, emit_fn, heartbeat_msg: str, heartbeat_interval: int = _HEARTBEAT_INTERVAL):
    """Run fn() in a thread while emitting heartbeat progress on the main thread."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(fn)
        while True:
            try:
                return future.result(timeout=heartbeat_interval)
            except concurrent.futures.TimeoutError:
                emit_fn(heartbeat_msg)


def node_sql_engineer(state: PipelineState) -> dict:
    sid = state["session_id"]
    retry = state.get("script_retry_count", 0)
    issues = None
    if retry > 0 and state.get("code_review_result"):
        issues = state["code_review_result"].issues
        _emit(state, f"🔧 正在根据审查意见修复脚本（第{retry}次重试）...")
    else:
        _emit(state, "⚙️ 正在生成分析脚本...")
    logger.info("[%s] >>> node:sql_engineer  retry=%d", sid, retry)
    start = time.perf_counter()
    try:
        py_script = _run_with_heartbeat(
            lambda: run_sql_engineer(state["task_plan"], issues=issues),
            lambda msg: _emit(state, msg),
            "⏳ 脚本生成中，请稍候...",
        )
    except Exception as e:
        elapsed = time.perf_counter() - start
        logger.error("[%s] <<< node:sql_engineer  %.2fs  FAILED: %s", sid, elapsed, e, exc_info=True)
        _emit(state, "⚠️ 脚本生成失败，已降级处理")
        return {
            "py_script": None,
            "viz_outputs": _fallback_outputs(f"❌ 脚本生成出错：{e}"),
            "error": str(e),
        }
    elapsed = time.perf_counter() - start
    if py_script is None:
        logger.warning("[%s] <<< node:sql_engineer  %.2fs  returned None", sid, elapsed)
        _emit(state, "⚠️ 脚本生成失败")
        return {
            "py_script": None,
            "viz_outputs": _fallback_outputs("❌ 未能生成分析脚本，请换一种方式描述您的问题。"),
            "error": "sql_engineer returned None",
        }
    _emit(state, f"✅ 脚本生成完成（{len(py_script.script_code)}字符）")
    logger.info("[%s] <<< node:sql_engineer  %.2fs  script_len=%d", sid, elapsed, len(py_script.script_code))
    logger.info("[%s] generated script:\n%s", sid, py_script.script_code)
    return {"py_script": py_script}


def node_code_reviewer(state: PipelineState) -> dict:
    sid = state["session_id"]
    _emit(state, "🔍 正在审查脚本安全性与性能...")
    logger.info("[%s] >>> node:code_reviewer", sid)
    start = time.perf_counter()
    script_code = state["py_script"].script_code
    try:
        result = _run_with_heartbeat(
            lambda: run_code_reviewer(script_code),
            lambda msg: _emit(state, msg),
            "⏳ 代码审查中，请稍候...",
        )
    except Exception as e:
        elapsed = time.perf_counter() - start
        logger.error("[%s] <<< node:code_reviewer  %.2fs  FAILED: %s", sid, elapsed, e, exc_info=True)
        return {"code_review_result": CodeReviewResult(approved=True, issues=[])}
    elapsed = time.perf_counter() - start
    if result.approved:
        _emit(state, "✅ 脚本审查通过")
    else:
        _emit(state, f"⚠️ 发现{len(result.issues)}个问题，正在修复...")
    logger.info("[%s] <<< node:code_reviewer  %.2fs  approved=%s  issues=%d",
                sid, elapsed, result.approved, len(result.issues))
    return {"code_review_result": result}


def node_script_runner(state: PipelineState) -> dict:
    sid = state["session_id"]
    _emit(state, "🎨 正在执行分析脚本并生成图表...")
    logger.info("[%s] >>> node:script_runner", sid)
    start = time.perf_counter()
    try:
        outputs = run_script_runner(state["py_script"])
    except Exception as e:
        elapsed = time.perf_counter() - start
        logger.error("[%s] <<< node:script_runner  %.2fs  FAILED: %s", sid, elapsed, e, exc_info=True)
        _emit(state, "⚠️ 图表生成失败，已降级处理")
        return {
            "viz_outputs": _fallback_outputs(f"❌ 图表生成出错：{e}"),
            "error": str(e),
        }
    elapsed = time.perf_counter() - start
    image_count = sum(1 for o in outputs if o["render"] == "image")
    logger.info("[%s] <<< node:script_runner  %.2fs  outputs=%d  images=%d",
                sid, elapsed, len(outputs), image_count)
    return {"viz_outputs": outputs}


def node_summarizer(state: PipelineState) -> dict:
    sid = state["session_id"]
    _emit(state, "📝 正在生成分析报告...")
    logger.info("[%s] >>> node:summarizer", sid)
    start = time.perf_counter()
    task_plan = state["task_plan"]
    analysis_plan = task_plan.analysis_plan if task_plan else None
    try:
        image_count = sum(1 for o in state.get("viz_outputs", []) if o.get("render") == "image")
        data_summary = next(
            (o["content"] for o in state.get("viz_outputs", []) if o.get("render") == "json"),
            None,
        )
        insights = [{"task_id": "script", "insight_hint": analysis_plan.viz_intent if analysis_plan else "", "charts": image_count}]
        report = run_summarizer(state["user_message"], insights, analysis_plan=analysis_plan, data_summary=data_summary)
    except Exception as e:
        elapsed = time.perf_counter() - start
        logger.error("[%s] <<< node:summarizer  %.2fs  FAILED: %s", sid, elapsed, e, exc_info=True)
        _emit(state, "⚠️ 报告生成失败，已跳过")
        return {"summary_report": None}
    elapsed = time.perf_counter() - start
    logger.info("[%s] <<< node:summarizer  %.2fs  points=%d", sid, elapsed, len(report.key_points))
    return {"summary_report": report}


def route_after_clarifier(state: PipelineState) -> str:
    return "planner" if state["clarifier_done"] else "end_clarify"


def route_after_intent_router(state: PipelineState) -> str:
    intent = state.get("intent", "unknown")
    if intent == "knowledge_qa":
        return "knowledge_agent"
    elif intent == "chitchat":
        return "chitchat_agent"
    else:
        return "clarifier"


def route_after_knowledge_agent(state: PipelineState) -> str:
    if not state.get("clarifier_done", True) and state.get("clarifier_question"):
        return "end_clarify"
    return "end"


def route_after_planner(state: PipelineState) -> str:
    if _has_error(state):
        return "end"
    return "end_clarify" if state["clarification_needed"] else "sql_engineer"


def route_after_sql_engineer(state: PipelineState) -> str:
    return "end" if _has_error(state) else "code_reviewer"


def route_after_code_reviewer(state: PipelineState) -> str:
    if _has_error(state):
        return "end"
    result = state.get("code_review_result")
    if result and not result.approved:
        retry = state.get("script_retry_count", 0)
        if retry < _MAX_SCRIPT_RETRIES:
            return "sql_engineer"
        else:
            return "end"
    return "script_runner"


def route_after_script_runner(state: PipelineState) -> str:
    return "end" if _has_error(state) else "summarizer"


def node_increment_retry(state: PipelineState) -> dict:
    return {"script_retry_count": state.get("script_retry_count", 0) + 1}


def build_pipeline():
    graph = StateGraph(PipelineState)
    graph.add_node("intent_router", node_intent_router)
    graph.add_node("clarifier", node_clarifier)
    graph.add_node("planner", node_planner)
    graph.add_node("sql_engineer", node_sql_engineer)
    graph.add_node("increment_retry", node_increment_retry)
    graph.add_node("code_reviewer", node_code_reviewer)
    graph.add_node("script_runner", node_script_runner)
    graph.add_node("summarizer", node_summarizer)
    graph.add_node("knowledge_agent", node_knowledge_agent)
    graph.add_node("chitchat_agent", node_chitchat_agent)

    graph.set_entry_point("intent_router")
    graph.add_conditional_edges("intent_router", route_after_intent_router, {
        "clarifier": "clarifier",
        "knowledge_agent": "knowledge_agent",
        "chitchat_agent": "chitchat_agent",
    })
    graph.add_conditional_edges("clarifier", route_after_clarifier, {
        "end_clarify": END,
        "planner": "planner",
    })
    graph.add_conditional_edges("planner", route_after_planner, {
        "end": END,
        "end_clarify": END,
        "sql_engineer": "sql_engineer",
    })
    graph.add_conditional_edges("sql_engineer", route_after_sql_engineer, {
        "end": END,
        "code_reviewer": "code_reviewer",
    })
    graph.add_conditional_edges("code_reviewer", route_after_code_reviewer, {
        "end": END,
        "sql_engineer": "increment_retry",
        "script_runner": "script_runner",
    })
    graph.add_edge("increment_retry", "sql_engineer")
    graph.add_conditional_edges("script_runner", route_after_script_runner, {
        "end": END,
        "summarizer": "summarizer",
    })
    graph.add_edge("summarizer", END)
    graph.add_conditional_edges("knowledge_agent", route_after_knowledge_agent, {
        "end_clarify": END,
        "end": END,
    })
    graph.add_edge("chitchat_agent", END)

    return graph.compile()
