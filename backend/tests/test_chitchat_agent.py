import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_chitchat_returns_answer():
    from agents.chitchat_agent import run_chitchat_agent

    class FakeLLM:
        def invoke(self, messages):
            class Resp:
                content = "你好！我是校园网流量分析助手，有什么可以帮助你的？"
            return Resp()

    result = run_chitchat_agent("你好", [], llm=FakeLLM())
    assert isinstance(result, str)
    assert len(result) > 0


def test_chitchat_includes_conversation_history():
    from agents.chitchat_agent import run_chitchat_agent

    captured = {}

    class FakeLLM:
        def invoke(self, messages):
            captured["messages"] = messages

            class Resp:
                content = "好的！"
            return Resp()

    history = [{"role": "user", "content": "你好"}, {"role": "assistant", "content": "你好！"}]
    run_chitchat_agent("再见", history, llm=FakeLLM())
    roles = [m["role"] for m in captured["messages"]]
    assert "system" in roles
    assert captured["messages"].count({"role": "user", "content": "你好"}) == 1


def test_chitchat_handles_llm_failure():
    from agents.chitchat_agent import run_chitchat_agent

    class FakeLLM:
        def invoke(self, messages):
            raise RuntimeError("LLM unavailable")

    result = run_chitchat_agent("你好", [], llm=FakeLLM())
    assert isinstance(result, str)
    assert len(result) > 0
