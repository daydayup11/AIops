import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_clarifier_returns_continue_when_clear():
    from agents.clarifier import run_clarifier

    class FakeLLM:
        def invoke(self, messages):
            class Resp:
                content = '{"action":"continue"}'
            return Resp()

    result = run_clarifier("分析过去24小时Top10应用流量排行", [], llm=FakeLLM())
    assert result["action"] == "continue"


def test_clarifier_returns_ask_when_vague():
    from agents.clarifier import run_clarifier

    class FakeLLM:
        def invoke(self, messages):
            class Resp:
                content = '{"action":"ask","question":"您想分析哪个时间范围？","options":["最近1小时","最近24小时","最近7天"]}'
            return Resp()

    result = run_clarifier("分析一下流量", [], llm=FakeLLM())
    assert result["action"] == "ask"
    assert "question" in result
    assert len(result["options"]) == 3


def test_clarifier_force_continue_on_keyword():
    from agents.clarifier import run_clarifier

    class FakeLLM:
        def invoke(self, messages):
            class Resp:
                content = '{"action":"ask","question":"时间范围？","options":[]}'
            return Resp()

    result = run_clarifier("开始分析", [], llm=FakeLLM())
    assert result["action"] == "continue"


def test_clarifier_handles_invalid_json():
    from agents.clarifier import run_clarifier

    class FakeLLM:
        def invoke(self, messages):
            class Resp:
                content = "不是JSON"
            return Resp()

    result = run_clarifier("帮我看看网络", [], llm=FakeLLM())
    assert result["action"] == "ask"
    assert "question" in result
