import logging
import time
import uuid
from typing import Callable, Optional
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END

from models.schemas import TaskPlan, SummaryReport
from agents.clarifier import run_clarifier
from agents.planner import run_planner
from agents.sql_engineer import run_sql_engineer
from agents.visualizer import run_visualizer
from agents.summarizer import run_summarizer
from executor.parallel import ParallelExecutor

logger = logging.getLogger(__name__)


class PipelineState(TypedDict):
    session_id: str
    user_message: str
    conversation_history: list
    task_plan: Optional[TaskPlan]
    sql_tasks: list
    execution_results: dict
    viz_outputs: list
    clarification_needed: bool
    clarification_question: Optional[str]
    clarifier_done: bool
    clarifier_question: Optional[str]
    clarifier_options: list
    summary_report: Optional[SummaryReport]
    error: Optional[str]
    progress_cb: Optional[Callable[[str], None]]
    plan_cb: Optional[Callable[[list], None]]


def _emit(state: PipelineState, text: str) -> None:
    cb = state.get("progress_cb")
    if cb:
        cb(text)


def _emit_plan(state: PipelineState, blueprint: list) -> None:
    cb = state.get("plan_cb")
    if cb:
        cb(blueprint)


def node_clarifier(state: PipelineState) -> dict:
    sid = state["session_id"]
    logger.info("[%s] >>> node:clarifier  input=%r", sid, state["user_message"][:80])
    result = run_clarifier(state["user_message"], state["conversation_history"])
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


def node_planner(state: PipelineState) -> dict:
    sid = state["session_id"]
    _emit(state, "🧠 正在理解问题、规划查询任务...")
    logger.info("[%s] >>> node:planner  input=%r", sid, state["user_message"][:120])
    start = time.perf_counter()
    plan = run_planner(state["user_message"], state["conversation_history"])
    elapsed = time.perf_counter() - start
    if not plan.clarification_needed:
        chart_types = [bp.chart_type for bp in plan.viz_blueprint]
        titles = [bp.title for bp in plan.viz_blueprint]
        summary = "、".join(f"{ct}图({t})" for ct, t in zip(chart_types, titles))
        _emit(state, f"📋 规划完成：共 {len(plan.tasks)} 个查询，将展示 {summary}")
        _emit_plan(state, [bp.model_dump() for bp in plan.viz_blueprint])
        logger.info("[%s] <<< node:planner  %.2fs  tasks=%s", sid, elapsed, [t.id for t in plan.tasks])
    return {
        "task_plan": plan,
        "clarification_needed": plan.clarification_needed,
        "clarification_question": plan.clarification_question,
    }


def node_sql_engineer(state: PipelineState) -> dict:
    sid = state["session_id"]
    n = len(state["task_plan"].tasks)
    _emit(state, f"⚙️ 正在生成 {n} 条查询 SQL...")
    logger.info("[%s] >>> node:sql_engineer  tasks=%s", sid, [t.id for t in state["task_plan"].tasks])
    start = time.perf_counter()
    sql_tasks = run_sql_engineer(state["task_plan"].tasks)
    elapsed = time.perf_counter() - start
    _emit(state, f"✅ SQL 生成完成，准备执行 {len(sql_tasks)} 条查询")
    logger.info("[%s] <<< node:sql_engineer  %.2fs  sql_tasks=%d", sid, elapsed, len(sql_tasks))
    return {"sql_tasks": sql_tasks}


def node_executor(state: PipelineState) -> dict:
    sid = state["session_id"]
    n = len(state["sql_tasks"])
    _emit(state, f"🔍 正在并行执行 {n} 条查询...")
    logger.info("[%s] >>> node:executor  sql_tasks=%s", sid, [t.task_id for t in state["sql_tasks"]])
    start = time.perf_counter()

    def task_progress_cb(task_id: str, status: str) -> None:
        icon = "✅" if status == "success" else "❌"
        _emit(state, f"{icon} 查询 {task_id} {status}")

    executor = ParallelExecutor()
    results = executor.run(state["sql_tasks"], progress_cb=task_progress_cb)
    elapsed = time.perf_counter() - start
    ok = sum(1 for r in results.values() if r["status"] == "success")
    fail = len(results) - ok
    _emit(state, f"📊 查询完成：{ok} 成功{'，' + str(fail) + ' 失败' if fail else ''}")
    logger.info("[%s] <<< node:executor  %.2fs  ok=%d fail=%d", sid, elapsed, ok, fail)
    return {"execution_results": results}


def node_visualizer(state: PipelineState) -> dict:
    sid = state["session_id"]
    n = len(state["execution_results"])
    _emit(state, f"🎨 正在生成 {n} 个图表...")
    logger.info("[%s] >>> node:visualizer  results=%d", sid, n)
    start = time.perf_counter()
    blueprints = state["task_plan"].viz_blueprint if state["task_plan"] else []
    outputs = run_visualizer(
        state["execution_results"],
        blueprints=blueprints,
        session_id=sid,
        message_id=str(uuid.uuid4()),
    )
    elapsed = time.perf_counter() - start
    logger.info("[%s] <<< node:visualizer  %.2fs  outputs=%d", sid, elapsed, len(outputs))
    return {"viz_outputs": outputs}


def node_summarizer(state: PipelineState) -> dict:
    sid = state["session_id"]
    _emit(state, "📝 正在生成分析报告...")
    logger.info("[%s] >>> node:summarizer", sid)
    start = time.perf_counter()
    blueprints = state["task_plan"].viz_blueprint if state["task_plan"] else []
    insights = [
        {
            "task_id": bp.task_id,
            "insight_hint": bp.insight_hint,
            "rows": len(state["execution_results"].get(bp.task_id, {}).get("df", [])),
        }
        for bp in blueprints
    ]
    report = run_summarizer(state["user_message"], insights)
    elapsed = time.perf_counter() - start
    logger.info("[%s] <<< node:summarizer  %.2fs  points=%d", sid, elapsed, len(report.key_points))
    return {"summary_report": report}


def route_after_clarifier(state: PipelineState) -> str:
    return "planner" if state["clarifier_done"] else "end_clarify"


def route_after_planner(state: PipelineState) -> str:
    return "end_clarify" if state["clarification_needed"] else "sql_engineer"


def build_pipeline():
    graph = StateGraph(PipelineState)
    graph.add_node("clarifier", node_clarifier)
    graph.add_node("planner", node_planner)
    graph.add_node("sql_engineer", node_sql_engineer)
    graph.add_node("executor", node_executor)
    graph.add_node("visualizer", node_visualizer)
    graph.add_node("summarizer", node_summarizer)

    graph.set_entry_point("clarifier")
    graph.add_conditional_edges("clarifier", route_after_clarifier, {
        "end_clarify": END,
        "planner": "planner",
    })
    graph.add_conditional_edges("planner", route_after_planner, {
        "end_clarify": END,
        "sql_engineer": "sql_engineer",
    })
    graph.add_edge("sql_engineer", "executor")
    graph.add_edge("executor", "visualizer")
    graph.add_edge("visualizer", "summarizer")
    graph.add_edge("summarizer", END)

    return graph.compile()
