import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _fake_llm(content: str):
    class FakeLLM:
        def invoke(self, messages):
            class Resp:
                pass
            r = Resp()
            r.content = content
            return r
    return FakeLLM()


def test_planner_returns_analysis_plan():
    from agents.planner import run_planner
    from models.schemas import TaskPlan, AnalysisPlan

    payload = '{"analysis_plan":{"goal":"找异常主机","approach":"流量特征分析","expected_findings":["高流量IP"],"analysis_dimensions":["IP流量排行"],"viz_intent":"展示Top10 IP流量柱状图"},"clarification_needed":false,"clarification_question":null,"estimated_seconds":10}'
    result = run_planner("分析异常主机", conversation_history=[], llm=_fake_llm(payload))
    assert isinstance(result, TaskPlan)
    assert isinstance(result.analysis_plan, AnalysisPlan)
    assert result.analysis_plan.viz_intent != ""
    assert not result.clarification_needed


def test_planner_returns_clarification():
    from agents.planner import run_planner

    payload = '{"analysis_plan":null,"clarification_needed":true,"clarification_question":"请问您想分析哪个时间段？","estimated_seconds":0}'
    result = run_planner("分析一下", conversation_history=[], llm=_fake_llm(payload))
    assert result.clarification_needed is True
    assert result.clarification_question is not None


def test_planner_handles_invalid_json():
    from agents.planner import run_planner

    result = run_planner("分析流量", conversation_history=[], llm=_fake_llm("这不是JSON"))
    assert result.clarification_needed is True
    assert result.clarification_question is not None


def test_planner_no_tasks_field():
    from agents.planner import run_planner
    from models.schemas import TaskPlan

    payload = '{"analysis_plan":{"goal":"g","approach":"a","expected_findings":[],"analysis_dimensions":[],"viz_intent":"bar chart"},"clarification_needed":false,"clarification_question":null,"estimated_seconds":5}'
    result = run_planner("流量排行", conversation_history=[], llm=_fake_llm(payload))
    assert "tasks" not in TaskPlan.model_fields
    assert "viz_blueprint" not in TaskPlan.model_fields
