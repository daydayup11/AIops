import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_summarizer_returns_report():
    from agents.summarizer import run_summarizer
    from models.schemas import SummaryReport

    class FakeLLM:
        def invoke(self, messages):
            class Resp:
                content = '{"title":"校园网流量分析报告","key_points":["应用5流量最高，占35%","高峰集中在20-23点"],"conclusion":"过去24小时应用5主导流量，建议关注带宽分配。"}'
            return Resp()

    insights = [{"task_id": "t1", "insight_hint": "头部效应明显", "rows": 10}]
    report = run_summarizer(
        user_message="过去24小时Top10应用流量排行",
        insights=insights,
        llm=FakeLLM(),
    )
    assert isinstance(report, SummaryReport)
    assert len(report.key_points) == 2
    assert "应用5" in report.conclusion


def test_summarizer_handles_invalid_json():
    from agents.summarizer import run_summarizer
    from models.schemas import SummaryReport

    class FakeLLM:
        def invoke(self, messages):
            class Resp:
                content = "不是JSON"
            return Resp()

    report = run_summarizer("查流量", insights=[], llm=FakeLLM())
    assert isinstance(report, SummaryReport)
    assert report.title != ""
