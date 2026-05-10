import logging
import time
from typing import Any, Optional
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END

from models.schemas import TaskPlan, SQLTask
from agents.planner import run_planner
from agents.sql_engineer import run_sql_engineer
from agents.visualizer import run_visualizer
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
    error: Optional[str]
    progress_cb: Optional[Any]


def node_planner(state: PipelineState) -> dict:
    logger.debug("Entering node: planner")
    start = time.perf_counter()
    plan = run_planner(state["user_message"], state["conversation_history"])
    logger.debug("Exiting node: planner (%.2fs)", time.perf_counter() - start)
    return {
        "task_plan": plan,
        "clarification_needed": plan.clarification_needed,
        "clarification_question": plan.clarification_question,
    }


def node_sql_engineer(state: PipelineState) -> dict:
    logger.debug("Entering node: sql_engineer")
    start = time.perf_counter()
    sql_tasks = run_sql_engineer(state["task_plan"].tasks)
    logger.debug("Exiting node: sql_engineer (%.2fs)", time.perf_counter() - start)
    return {"sql_tasks": sql_tasks}


def node_executor(state: PipelineState) -> dict:
    logger.debug("Entering node: executor")
    start = time.perf_counter()
    executor = ParallelExecutor()
    results = executor.run(state["sql_tasks"], progress_cb=state.get("progress_cb"))
    logger.debug("Exiting node: executor (%.2fs)", time.perf_counter() - start)
    return {"execution_results": results}


def node_visualizer(state: PipelineState) -> dict:
    import uuid
    logger.debug("Entering node: visualizer")
    start = time.perf_counter()
    outputs = run_visualizer(
        state["execution_results"],
        session_id=state["session_id"],
        message_id=str(uuid.uuid4()),
    )
    logger.debug("Exiting node: visualizer (%.2fs)", time.perf_counter() - start)
    return {"viz_outputs": outputs}


def route_after_planner(state: PipelineState) -> str:
    if state["clarification_needed"]:
        return "end_clarify"
    return "sql_engineer"


def build_pipeline():
    graph = StateGraph(PipelineState)
    graph.add_node("planner", node_planner)
    graph.add_node("sql_engineer", node_sql_engineer)
    graph.add_node("executor", node_executor)
    graph.add_node("visualizer", node_visualizer)

    graph.set_entry_point("planner")
    graph.add_conditional_edges("planner", route_after_planner, {
        "end_clarify": END,
        "sql_engineer": "sql_engineer",
    })
    graph.add_edge("sql_engineer", "executor")
    graph.add_edge("executor", "visualizer")
    graph.add_edge("visualizer", END)

    return graph.compile()
