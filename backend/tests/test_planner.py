import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_planner_returns_task_plan():
    from agents.planner import run_planner
    from models.schemas import TaskPlan

    class FakeLLM:
        def invoke(self, messages):
            class Resp:
                content = '{"tasks":[{"id":"t1","description":"统计昨天总流量","tables":["iplog"],"time_range_hours":24}],"clarification_needed":false,"clarification_question":null,"estimated_seconds":5}'
            return Resp()

    result = run_planner("分析昨天的总流量", conversation_history=[], llm=FakeLLM())
    assert isinstance(result, TaskPlan)
    assert len(result.tasks) == 1
    assert result.tasks[0].id == "t1"


def test_planner_returns_clarification():
    from agents.planner import run_planner
    from models.schemas import TaskPlan

    class FakeLLM:
        def invoke(self, messages):
            class Resp:
                content = '{"tasks":[],"clarification_needed":true,"clarification_question":"请问您想分析哪个时间段？","estimated_seconds":0}'
            return Resp()

    result = run_planner("分析一下", conversation_history=[], llm=FakeLLM())
    assert result.clarification_needed is True
    assert "时间段" in result.clarification_question


def test_planner_handles_invalid_json():
    from agents.planner import run_planner
    from models.schemas import TaskPlan

    class FakeLLM:
        def invoke(self, messages):
            class Resp:
                content = "这不是JSON"
            return Resp()

    result = run_planner("分析流量", conversation_history=[], llm=FakeLLM())
    assert result.clarification_needed is True
    assert result.clarification_question is not None
