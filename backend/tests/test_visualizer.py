import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pandas as pd


def _make_result(df, description="测试任务"):
    return {"status": "success", "df": df, "description": description}


def test_visualizer_uses_blueprint_no_llm():
    from agents.visualizer import run_visualizer
    from models.schemas import VizBlueprint

    df = pd.DataFrame({"appid": [5, 878, 613], "total_bytes": [1e12, 8e11, 7e11]})
    results = {"t1": _make_result(df, "Top10应用流量")}
    blueprints = [VizBlueprint(
        task_id="t1", chart_type="bar", title="Top10应用流量排行",
        x_field="appid", y_field="total_bytes", insight_hint="头部效应明显",
    )]

    llm_called = []
    class FakeLLM:
        def invoke(self, messages):
            llm_called.append(True)
            class Resp:
                content = '{}'
            return Resp()

    outputs = run_visualizer(results, blueprints=blueprints, session_id="s1", message_id="m1", llm=FakeLLM())
    assert len(llm_called) == 0, "有蓝图时不应调用 LLM"
    assert len(outputs) == 1
    assert outputs[0]["render"] == "echarts"
    assert outputs[0]["insight"] == "头部效应明显"


def test_visualizer_fallback_to_llm_when_no_blueprint():
    from agents.visualizer import run_visualizer

    df = pd.DataFrame({"appid": [5, 878], "total_bytes": [1e12, 8e11]})
    results = {"t1": _make_result(df)}
    blueprints = []  # 没有蓝图，应降级调 LLM

    llm_called = []
    class FakeLLM:
        def invoke(self, messages):
            llm_called.append(True)
            class Resp:
                content = '{"render_type":"echarts","chart_type":"bar","title":"流量","x_field":"appid","y_field":"total_bytes","insight":"头部效应"}'
            return Resp()

    outputs = run_visualizer(results, blueprints=blueprints, session_id="s1", message_id="m1", llm=FakeLLM())
    assert len(llm_called) == 1, "没有蓝图时应降级调用 LLM"
    assert len(outputs) == 1


def test_visualizer_skips_failed_task():
    from agents.visualizer import run_visualizer
    from models.schemas import VizBlueprint

    results = {"t1": {"status": "error", "error": "超时", "description": "查询失败"}}
    blueprints = [VizBlueprint(
        task_id="t1", chart_type="bar", title="X",
        x_field="a", y_field="b", insight_hint="",
    )]
    outputs = run_visualizer(results, blueprints=blueprints, session_id="s1", message_id="m1")
    assert outputs[0]["render"] == "text"
    assert "失败" in outputs[0]["content"]
