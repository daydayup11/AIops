import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_routes_data_analysis():
    from agents.intent_router import run_intent_router

    class FakeLLM:
        def invoke(self, messages):
            class Resp:
                content = '{"intent":"data_analysis","rewritten_query":"查询会话数量最多的前10个用户","confidence":0.95}'
            return Resp()

    result = run_intent_router("top10会话数量的用户", [], llm=FakeLLM())
    assert result["intent"] == "data_analysis"
    assert result["rewritten_query"] == "查询会话数量最多的前10个用户"
    assert result["confidence"] == 0.95


def test_routes_knowledge_qa():
    from agents.intent_router import run_intent_router

    class FakeLLM:
        def invoke(self, messages):
            class Resp:
                content = '{"intent":"knowledge_qa","rewritten_query":"系统的账号数据来源是什么","confidence":0.9}'
            return Resp()

    result = run_intent_router("你的账号数据哪里来的", [], llm=FakeLLM())
    assert result["intent"] == "knowledge_qa"


def test_routes_chitchat():
    from agents.intent_router import run_intent_router

    class FakeLLM:
        def invoke(self, messages):
            class Resp:
                content = '{"intent":"chitchat","rewritten_query":"你好","confidence":0.99}'
            return Resp()

    result = run_intent_router("你好", [], llm=FakeLLM())
    assert result["intent"] == "chitchat"


def test_unknown_intent_passes_through():
    from agents.intent_router import run_intent_router

    class FakeLLM:
        def invoke(self, messages):
            class Resp:
                content = '{"intent":"unknown","rewritten_query":"帮我分析一下","confidence":0.3}'
            return Resp()

    result = run_intent_router("随便看看", [], llm=FakeLLM())
    assert result["intent"] == "unknown"


def test_handles_invalid_json():
    from agents.intent_router import run_intent_router

    class FakeLLM:
        def invoke(self, messages):
            class Resp:
                content = "不是JSON"
            return Resp()

    result = run_intent_router("分析一下", [], llm=FakeLLM())
    assert result["intent"] == "data_analysis"
    assert "rewritten_query" in result
    assert "confidence" in result


def test_includes_conversation_history():
    from agents.intent_router import run_intent_router

    captured = {}

    class FakeLLM:
        def invoke(self, messages):
            captured["messages"] = messages

            class Resp:
                content = '{"intent":"data_analysis","rewritten_query":"查流量","confidence":0.8}'
            return Resp()

    history = [{"role": "user", "content": "你好"}, {"role": "assistant", "content": "你好！"}]
    run_intent_router("查流量", history, llm=FakeLLM())
    assert any(m["role"] == "user" and m["content"] == "你好" for m in captured["messages"])
