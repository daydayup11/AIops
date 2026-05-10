import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_pipeline_state_schema():
    from graph.pipeline import PipelineState
    state = PipelineState(
        session_id="test-123",
        user_message="分析流量",
        conversation_history=[],
        task_plan=None,
        sql_tasks=[],
        execution_results={},
        viz_outputs=[],
        clarification_needed=False,
        clarification_question=None,
        error=None,
        progress_cb=None,
    )
    assert state["session_id"] == "test-123"


def test_pipeline_graph_compiles():
    from graph.pipeline import build_pipeline
    graph = build_pipeline()
    assert graph is not None


def test_pipeline_routes_to_clarify():
    from graph.pipeline import route_after_planner, PipelineState
    state = PipelineState(
        session_id="s1",
        user_message="分析",
        conversation_history=[],
        task_plan=None,
        sql_tasks=[],
        execution_results={},
        viz_outputs=[],
        clarification_needed=True,
        clarification_question="请说明时间范围",
        error=None,
        progress_cb=None,
    )
    assert route_after_planner(state) == "end_clarify"


def test_pipeline_routes_to_sql_engineer():
    from graph.pipeline import route_after_planner, PipelineState
    state = PipelineState(
        session_id="s1",
        user_message="分析昨天流量",
        conversation_history=[],
        task_plan=None,
        sql_tasks=[],
        execution_results={},
        viz_outputs=[],
        clarification_needed=False,
        clarification_question=None,
        error=None,
        progress_cb=None,
    )
    assert route_after_planner(state) == "sql_engineer"
