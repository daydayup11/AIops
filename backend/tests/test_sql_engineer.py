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


def _make_plan():
    from models.schemas import AnalysisPlan, TaskPlan
    return TaskPlan(
        analysis_plan=AnalysisPlan(
            goal="找高流量IP",
            approach="统计各IP的总流量",
            expected_findings=["Top10高流量IP"],
            analysis_dimensions=["IP流量排行"],
            viz_intent="展示Top10 IP流量柱状图，按流量降序排列",
        ),
        clarification_needed=False,
    )


def test_sql_engineer_returns_py_script():
    from agents.sql_engineer import run_sql_engineer
    from models.schemas import PyScript

    script_code = "import os\nprint('hello')\n"
    result = run_sql_engineer(_make_plan(), llm=_fake_llm(script_code))
    assert isinstance(result, PyScript)
    assert "import" in result.script_code


def test_sql_engineer_with_issues_includes_feedback():
    from agents.sql_engineer import run_sql_engineer

    script_code = "import clickhouse_driver\n# fixed\nprint('ok')\n"
    issues = ["缺少LIMIT子句", "全表扫描风险"]
    result = run_sql_engineer(_make_plan(), issues=issues, llm=_fake_llm(script_code))
    assert result is not None


def test_sql_engineer_handles_llm_failure():
    from agents.sql_engineer import run_sql_engineer

    class ErrorLLM:
        def invoke(self, _):
            raise RuntimeError("LLM down")

    result = run_sql_engineer(_make_plan(), llm=ErrorLLM())
    assert result is None
