import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _make_state(**kwargs):
    from graph.pipeline import PipelineState
    defaults = dict(
        session_id="test",
        user_message="你好",
        conversation_history=[],
        task_plan=None,
        py_script=None,
        code_review_result=None,
        script_retry_count=0,
        viz_outputs=[],
        clarification_needed=False,
        clarification_question=None,
        clarifier_done=False,
        clarifier_question=None,
        clarifier_options=[],
        summary_report=None,
        error=None,
        progress_cb=None,
        intent=None,
        rewritten_query=None,
        intent_confidence=0.0,
        knowledge_answer=None,
        chitchat_answer=None,
    )
    defaults.update(kwargs)
    return defaults


def test_route_after_intent_router_data_analysis():
    from graph.pipeline import route_after_intent_router
    state = _make_state(intent="data_analysis")
    assert route_after_intent_router(state) == "clarifier"


def test_route_after_intent_router_unknown():
    from graph.pipeline import route_after_intent_router
    state = _make_state(intent="unknown")
    assert route_after_intent_router(state) == "clarifier"


def test_route_after_intent_router_knowledge_qa():
    from graph.pipeline import route_after_intent_router
    state = _make_state(intent="knowledge_qa")
    assert route_after_intent_router(state) == "knowledge_agent"


def test_route_after_intent_router_chitchat():
    from graph.pipeline import route_after_intent_router
    state = _make_state(intent="chitchat")
    assert route_after_intent_router(state) == "chitchat_agent"


def test_node_intent_router_populates_state():
    from graph.pipeline import node_intent_router

    class FakeLLM:
        def invoke(self, messages):
            class Resp:
                content = '{"intent":"data_analysis","rewritten_query":"查询Top10用户","confidence":0.9}'
            return Resp()

    import agents.intent_router as ir
    orig = ir._build_llm
    ir._build_llm = lambda: FakeLLM()
    try:
        state = _make_state(user_message="top10用户")
        result = node_intent_router(state)
        assert result["intent"] == "data_analysis"
        assert result["rewritten_query"] == "查询Top10用户"
        assert result["intent_confidence"] == 0.9
    finally:
        ir._build_llm = orig


def test_node_knowledge_agent_populates_state():
    from graph.pipeline import node_knowledge_agent

    import agents.knowledge_agent as ka
    orig = ka._build_llm

    class FakeLLM:
        def invoke(self, messages):
            class Resp:
                content = '{"action":"answer","answer":"数据来自ClickHouse。"}'
            return Resp()

    ka._build_llm = lambda: FakeLLM()
    try:
        state = _make_state(
            user_message="数据从哪来",
            rewritten_query="系统的数据来源是什么",
        )
        result = node_knowledge_agent(state)
        assert result["knowledge_answer"] == "数据来自ClickHouse。"
    finally:
        ka._build_llm = orig


def test_node_chitchat_agent_populates_state():
    from graph.pipeline import node_chitchat_agent

    import agents.chitchat_agent as ca
    orig = ca._build_llm

    class FakeLLM:
        def invoke(self, messages):
            class Resp:
                content = "你好！有什么可以帮你的？"
            return Resp()

    ca._build_llm = lambda: FakeLLM()
    try:
        state = _make_state(user_message="你好", rewritten_query="你好")
        result = node_chitchat_agent(state)
        assert result["chitchat_answer"] == "你好！有什么可以帮你的？"
    finally:
        ca._build_llm = orig
