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


def test_planner_returns_viz_blueprint():
    from agents.planner import run_planner
    from models.schemas import TaskPlan

    class FakeLLM:
        def invoke(self, messages):
            class Resp:
                content = '{"tasks":[{"id":"t1","description":"Top10应用流量","tables":["sessions"],"time_range_hours":24}],"viz_blueprint":[{"task_id":"t1","chart_type":"bar","title":"Top10应用流量排行","x_field":"appid","y_field":"total_bytes","insight_hint":"头部效应明显"}],"clarification_needed":false,"clarification_question":null,"estimated_seconds":5}'
            return Resp()

    result = run_planner("过去24小时Top10应用流量", conversation_history=[], llm=FakeLLM())
    assert isinstance(result, TaskPlan)
    assert len(result.viz_blueprint) == 1
    assert result.viz_blueprint[0].chart_type == "bar"
    assert result.viz_blueprint[0].x_field == "appid"


def test_planner_no_duplicate_blueprints():
    from agents.planner import run_planner

    class FakeLLM:
        def invoke(self, messages):
            class Resp:
                content = '{"tasks":[{"id":"t1","description":"流量排行","tables":["sessions"],"time_range_hours":24},{"id":"t2","description":"时段分布","tables":["sessions"],"time_range_hours":24}],"viz_blueprint":[{"task_id":"t1","chart_type":"bar","title":"Top10应用","x_field":"appid","y_field":"total_bytes","insight_hint":"头部效应"},{"task_id":"t2","chart_type":"line","title":"时段流量","x_field":"hour","y_field":"bytes","insight_hint":"高峰时段"}],"clarification_needed":false,"clarification_question":null,"estimated_seconds":8}'
            return Resp()

    result = run_planner("流量排行和时段分布", conversation_history=[], llm=FakeLLM())
    combos = [(bp.chart_type, bp.x_field, bp.y_field) for bp in result.viz_blueprint]
    assert len(combos) == len(set(combos)), "viz_blueprint 不应有重复图表"
