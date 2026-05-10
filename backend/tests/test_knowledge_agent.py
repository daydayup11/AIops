import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "docs")


def test_search_docs_finds_relevant_content(tmp_path):
    from agents.knowledge_agent import search_docs

    doc = tmp_path / "test.md"
    doc.write_text("# 数据来源\n校园网数据来自ClickHouse数据库，包含会话记录。", encoding="utf-8")

    results = search_docs("数据来源", docs_dir=str(tmp_path))
    assert len(results) > 0
    assert any("ClickHouse" in r for r in results)


def test_search_docs_returns_empty_for_no_match(tmp_path):
    from agents.knowledge_agent import search_docs

    doc = tmp_path / "test.md"
    doc.write_text("# 数据来源\n校园网数据来自ClickHouse。", encoding="utf-8")

    results = search_docs("完全不存在的关键词xyz", docs_dir=str(tmp_path))
    assert results == []


def test_run_knowledge_agent_with_context():
    from agents.knowledge_agent import run_knowledge_agent

    class FakeLLM:
        def invoke(self, messages):
            class Resp:
                content = '{"action":"answer","answer":"数据来自ClickHouse数据库。"}'
            return Resp()

    result = run_knowledge_agent(
        "系统的账号数据来源是什么",
        [],
        docs_context=["# 数据来源\n校园网数据来自ClickHouse数据库。"],
        llm=FakeLLM(),
    )
    assert result["action"] == "answer"
    assert "ClickHouse" in result["answer"]


def test_run_knowledge_agent_asks_when_vague():
    from agents.knowledge_agent import run_knowledge_agent

    class FakeLLM:
        def invoke(self, messages):
            class Resp:
                content = '{"action":"ask","question":"您想了解哪方面的信息？","options":["数据来源","字段说明","使用方法"]}'
            return Resp()

    result = run_knowledge_agent("告诉我关于数据的事", [], docs_context=[], llm=FakeLLM())
    assert result["action"] == "ask"
    assert "question" in result
    assert len(result["options"]) == 3


def test_run_knowledge_agent_no_docs_found():
    from agents.knowledge_agent import run_knowledge_agent

    class FakeLLM:
        def invoke(self, messages):
            class Resp:
                content = '{"action":"answer","answer":"未找到相关文档，根据系统知识：这是校园网分析系统。"}'
            return Resp()

    result = run_knowledge_agent("没有文档覆盖的问题", [], docs_context=[], llm=FakeLLM())
    assert result["action"] == "answer"
    assert "answer" in result
