# Intent Router Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an intent router node to the LangGraph pipeline that classifies user questions into `data_analysis`, `knowledge_qa`, `chitchat`, or `unknown`, rewrites the query, and dispatches to the appropriate handler.

**Architecture:** A new `intent_router` node becomes the pipeline entry point, replacing the direct `clarifier` entry. It outputs `intent` + `rewritten_query` into `PipelineState`. Conditional edges dispatch to: existing `clarifier` (data_analysis/unknown), new `node_knowledge_agent` (knowledge_qa), or new `node_chitchat_agent` (chitchat). The `knowledge_agent` retrieves context from `docs/*.md` files via keyword matching and answers with LLM. The `chitchat_agent` replies directly with LLM.

**Tech Stack:** Python 3.12, LangGraph, LangChain OpenAI, FastAPI, pytest

---

## File Map

| Operation | File | Responsibility |
|---|---|---|
| Create | `backend/agents/intent_router.py` | LLM intent classification + query rewrite |
| Create | `backend/agents/knowledge_agent.py` | docs/ retrieval + LLM answer generation |
| Create | `backend/agents/chitchat_agent.py` | Direct LLM chitchat reply |
| Modify | `backend/graph/pipeline.py` | Add new state fields, nodes, routing |
| Modify | `backend/api/chat.py` | Handle knowledge/chitchat answers in WS loop |
| Create | `backend/tests/test_intent_router.py` | Tests for intent_router |
| Create | `backend/tests/test_knowledge_agent.py` | Tests for knowledge_agent |
| Create | `backend/tests/test_chitchat_agent.py` | Tests for chitchat_agent |
| Create | `backend/tests/test_pipeline_routing.py` | Integration tests for new routing |

---

## Task 1: intent_router agent

**Files:**
- Create: `backend/agents/intent_router.py`
- Create: `backend/tests/test_intent_router.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_intent_router.py`:

```python
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


def test_unknown_falls_back_to_data_analysis():
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/backend
python -m pytest tests/test_intent_router.py -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError` or `ImportError` for `agents.intent_router`.

- [ ] **Step 3: Implement intent_router**

Create `backend/agents/intent_router.py`:

```python
import json
import logging
from langchain_openai import ChatOpenAI
from config import settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """你是校园网流量分析助手的意图识别专家。
判断用户的提问属于哪种类型，并将问题改写为标准化表达。

意图分类标准：
- data_analysis：需要查数据库、统计数据、排行榜、趋势分析、异常检测等
- knowledge_qa：询问系统本身、数据来源、字段含义、功能说明、使用帮助等
- chitchat：问候语、闲聊、与数据分析完全无关的随意对话
- unknown：无法归入以上任何类别

改写规则：
- 将口语化、模糊的问题改写为简洁、标准化的表达
- 保持原意不变，不添加推断内容
- 例：「top10会话数量的用户」→「查询会话数量最多的前10个用户」
- 例：「你的账号数据哪里来的」→「系统的账号数据来源是什么」
- 例：「你好」→「你好」

返回严格JSON（不要Markdown代码块）：
{"intent": "data_analysis|knowledge_qa|chitchat|unknown", "rewritten_query": "改写后的问题", "confidence": 0.0-1.0}
"""


def _build_llm() -> ChatOpenAI:
    cfg = settings["llm"]
    return ChatOpenAI(
        base_url=cfg["base_url"],
        api_key=cfg["api_key"],
        model=cfg["model"],
        temperature=0.0,
    )


def run_intent_router(user_message: str, conversation_history: list, llm=None) -> dict:
    llm = llm or _build_llm()
    messages = [{"role": "system", "content": _SYSTEM_PROMPT}]
    messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_message})

    logger.info("intent_router: LLM call  input=%r  history=%d", user_message[:80], len(conversation_history))
    try:
        response = llm.invoke(messages)
    except Exception:
        logger.error("intent_router: LLM call failed", exc_info=True)
        return {"intent": "data_analysis", "rewritten_query": user_message, "confidence": 0.0}

    logger.debug("intent_router: raw response %r", response.content[:200])
    try:
        result = json.loads(response.content)
        assert result.get("intent") in ("data_analysis", "knowledge_qa", "chitchat", "unknown")
        assert isinstance(result.get("rewritten_query"), str)
        assert isinstance(result.get("confidence"), (int, float))
        logger.info("intent_router: intent=%s  confidence=%.2f  rewritten=%r",
                    result["intent"], result["confidence"], result["rewritten_query"][:60])
        return result
    except Exception:
        logger.warning("intent_router: parse failed, fallback to data_analysis", exc_info=True)
        return {"intent": "data_analysis", "rewritten_query": user_message, "confidence": 0.0}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/backend
python -m pytest tests/test_intent_router.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/agents/intent_router.py backend/tests/test_intent_router.py
git commit -m "feat: add intent_router agent with LLM classification and query rewrite"
```

---

## Task 2: knowledge_agent

**Files:**
- Create: `backend/agents/knowledge_agent.py`
- Create: `backend/tests/test_knowledge_agent.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_knowledge_agent.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/backend
python -m pytest tests/test_knowledge_agent.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError` for `agents.knowledge_agent`.

- [ ] **Step 3: Implement knowledge_agent**

Create `backend/agents/knowledge_agent.py`:

```python
import json
import logging
import os
from pathlib import Path
from langchain_openai import ChatOpenAI
from config import settings

logger = logging.getLogger(__name__)

_DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "docs")

_SYSTEM_PROMPT = """你是校园网流量分析助手的知识问答专家。
根据提供的文档内容回答用户关于系统、数据来源、字段含义等问题。

如果问题过于模糊，追问一次以明确方向（最多追问一次）。
如果文档中没有相关内容，基于系统背景知识回答并注明"未找到相关文档"。

系统背景：这是一个校园网流量智能分析助手，数据来自ClickHouse数据库（logdb），
包含会话记录、应用日志、安全事件、认证用户等约60张核心表。

返回严格JSON（不要Markdown代码块）：
- 可以回答：{"action": "answer", "answer": "回答内容"}
- 需要追问：{"action": "ask", "question": "追问问题", "options": ["选项1", "选项2", "选项3"]}
"""


def search_docs(query: str, docs_dir: str = _DOCS_DIR) -> list[str]:
    """Keyword search across all .md files in docs_dir. Returns matching paragraphs."""
    keywords = [kw.strip() for kw in query.replace("，", " ").replace("、", " ").split() if len(kw.strip()) >= 2]
    if not keywords:
        return []

    results = []
    docs_path = Path(docs_dir)
    for md_file in sorted(docs_path.rglob("*.md")):
        try:
            text = md_file.read_text(encoding="utf-8")
        except Exception:
            continue
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        for para in paragraphs:
            if any(kw in para for kw in keywords):
                results.append(para[:500])
                if len(results) >= 5:
                    return results
    return results


def run_knowledge_agent(
    query: str,
    conversation_history: list,
    docs_context: list[str] | None = None,
    llm=None,
) -> dict:
    llm = llm or _build_llm()

    if docs_context is None:
        docs_context = search_docs(query)
        logger.info("knowledge_agent: retrieved %d doc paragraphs for query=%r", len(docs_context), query[:60])

    context_text = "\n\n---\n\n".join(docs_context) if docs_context else "（未检索到相关文档）"
    user_content = f"【参考文档】\n{context_text}\n\n【用户问题】\n{query}"

    messages = [{"role": "system", "content": _SYSTEM_PROMPT}]
    messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_content})

    logger.info("knowledge_agent: LLM call  query=%r  context_len=%d", query[:60], len(context_text))
    try:
        response = llm.invoke(messages)
    except Exception:
        logger.error("knowledge_agent: LLM call failed", exc_info=True)
        return {"action": "answer", "answer": "抱歉，知识查询服务暂时不可用，请稍后再试。"}

    logger.debug("knowledge_agent: raw response %r", response.content[:200])
    try:
        result = json.loads(response.content)
        assert result.get("action") in ("answer", "ask")
        logger.info("knowledge_agent: action=%s", result["action"])
        return result
    except Exception:
        logger.warning("knowledge_agent: parse failed, return raw", exc_info=True)
        return {"action": "answer", "answer": response.content.strip()}


def _build_llm() -> ChatOpenAI:
    cfg = settings["llm"]
    return ChatOpenAI(
        base_url=cfg["base_url"],
        api_key=cfg["api_key"],
        model=cfg["model"],
        temperature=cfg["temperature"],
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/backend
python -m pytest tests/test_knowledge_agent.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/agents/knowledge_agent.py backend/tests/test_knowledge_agent.py
git commit -m "feat: add knowledge_agent with docs/ keyword search and LLM answer"
```

---

## Task 3: chitchat_agent

**Files:**
- Create: `backend/agents/chitchat_agent.py`
- Create: `backend/tests/test_chitchat_agent.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_chitchat_agent.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/backend
python -m pytest tests/test_chitchat_agent.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError` for `agents.chitchat_agent`.

- [ ] **Step 3: Implement chitchat_agent**

Create `backend/agents/chitchat_agent.py`:

```python
import logging
from langchain_openai import ChatOpenAI
from config import settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """你是校园网流量智能分析助手。
当用户进行日常问候或闲聊时，友好简洁地回应。
保持专业但亲切的风格，适时引导用户进行数据分析。
回复控制在2-3句话以内。"""


def _build_llm() -> ChatOpenAI:
    cfg = settings["llm"]
    return ChatOpenAI(
        base_url=cfg["base_url"],
        api_key=cfg["api_key"],
        model=cfg["model"],
        temperature=0.7,
    )


def run_chitchat_agent(user_message: str, conversation_history: list, llm=None) -> str:
    llm = llm or _build_llm()
    messages = [{"role": "system", "content": _SYSTEM_PROMPT}]
    messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_message})

    logger.info("chitchat_agent: LLM call  input=%r", user_message[:60])
    try:
        response = llm.invoke(messages)
        answer = response.content.strip()
        logger.info("chitchat_agent: done  answer_len=%d", len(answer))
        return answer
    except Exception:
        logger.error("chitchat_agent: LLM call failed", exc_info=True)
        return "你好！我是校园网流量分析助手，有什么可以帮你分析的吗？"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/backend
python -m pytest tests/test_chitchat_agent.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/agents/chitchat_agent.py backend/tests/test_chitchat_agent.py
git commit -m "feat: add chitchat_agent for direct LLM reply"
```

---

## Task 4: pipeline.py — new state fields + nodes + routing

**Files:**
- Modify: `backend/graph/pipeline.py`
- Create: `backend/tests/test_pipeline_routing.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_pipeline_routing.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/backend
python -m pytest tests/test_pipeline_routing.py -v 2>&1 | head -30
```

Expected: failures due to missing fields in `PipelineState` and missing functions.

- [ ] **Step 3: Update PipelineState and add new nodes/routing**

In `backend/graph/pipeline.py`, make the following changes:

**3a. Add new fields to `PipelineState`** (after `error: Optional[str]`):

```python
    intent: Optional[str]
    rewritten_query: Optional[str]
    intent_confidence: float
    knowledge_answer: Optional[str]
    chitchat_answer: Optional[str]
```

**3b. Add new imports** at top of file (after existing imports):

```python
from agents.intent_router import run_intent_router
from agents.knowledge_agent import run_knowledge_agent, search_docs
from agents.chitchat_agent import run_chitchat_agent
```

**3c. Add three new node functions** (add after `node_clarifier`):

```python
def node_intent_router(state: PipelineState) -> dict:
    sid = state["session_id"]
    logger.info("[%s] >>> node:intent_router  input=%r", sid, state["user_message"][:80])
    try:
        result = run_intent_router(state["user_message"], state["conversation_history"])
    except Exception as e:
        logger.error("[%s] <<< node:intent_router  FAILED: %s", sid, e, exc_info=True)
        return {"intent": "data_analysis", "rewritten_query": state["user_message"], "intent_confidence": 0.0}
    logger.info("[%s] <<< node:intent_router  intent=%s  confidence=%.2f", sid, result["intent"], result["confidence"])
    return {
        "intent": result["intent"],
        "rewritten_query": result["rewritten_query"],
        "intent_confidence": result["confidence"],
    }


def node_knowledge_agent(state: PipelineState) -> dict:
    sid = state["session_id"]
    query = state.get("rewritten_query") or state["user_message"]
    _emit(state, "🔍 正在检索相关文档...")
    logger.info("[%s] >>> node:knowledge_agent  query=%r", sid, query[:80])
    docs_context = search_docs(query)
    try:
        result = run_knowledge_agent(query, state["conversation_history"], docs_context=docs_context)
    except Exception as e:
        logger.error("[%s] <<< node:knowledge_agent  FAILED: %s", sid, e, exc_info=True)
        return {"knowledge_answer": None, "error": str(e)}
    if result["action"] == "ask":
        logger.info("[%s] <<< node:knowledge_agent  action=ask", sid)
        return {
            "knowledge_answer": None,
            "clarifier_done": False,
            "clarifier_question": result["question"],
            "clarifier_options": result.get("options", []),
        }
    answer = result.get("answer", "")
    logger.info("[%s] <<< node:knowledge_agent  answer_len=%d", sid, len(answer))
    return {"knowledge_answer": answer}


def node_chitchat_agent(state: PipelineState) -> dict:
    sid = state["session_id"]
    query = state.get("rewritten_query") or state["user_message"]
    logger.info("[%s] >>> node:chitchat_agent  input=%r", sid, query[:60])
    try:
        answer = run_chitchat_agent(query, state["conversation_history"])
    except Exception as e:
        logger.error("[%s] <<< node:chitchat_agent  FAILED: %s", sid, e, exc_info=True)
        return {"chitchat_answer": "你好！有什么可以帮你的吗？"}
    logger.info("[%s] <<< node:chitchat_agent  answer_len=%d", sid, len(answer))
    return {"chitchat_answer": answer}
```

**3d. Add routing function** (add after `route_after_clarifier`):

```python
def route_after_intent_router(state: PipelineState) -> str:
    intent = state.get("intent", "unknown")
    if intent == "knowledge_qa":
        return "knowledge_agent"
    elif intent == "chitchat":
        return "chitchat_agent"
    else:
        return "clarifier"
```

**3e. Add routing function for knowledge_agent** (add after `route_after_intent_router`):

```python
def route_after_knowledge_agent(state: PipelineState) -> str:
    if not state.get("clarifier_done", True) and state.get("clarifier_question"):
        return "end_clarify"
    return "end"
```

**3f. Update `build_pipeline()`** — replace `graph.set_entry_point("clarifier")` and add new nodes/edges:

```python
def build_pipeline():
    graph = StateGraph(PipelineState)
    graph.add_node("intent_router", node_intent_router)
    graph.add_node("clarifier", node_clarifier)
    graph.add_node("planner", node_planner)
    graph.add_node("sql_engineer", node_sql_engineer)
    graph.add_node("increment_retry", node_increment_retry)
    graph.add_node("code_reviewer", node_code_reviewer)
    graph.add_node("script_runner", node_script_runner)
    graph.add_node("summarizer", node_summarizer)
    graph.add_node("knowledge_agent", node_knowledge_agent)
    graph.add_node("chitchat_agent", node_chitchat_agent)

    graph.set_entry_point("intent_router")
    graph.add_conditional_edges("intent_router", route_after_intent_router, {
        "clarifier": "clarifier",
        "knowledge_agent": "knowledge_agent",
        "chitchat_agent": "chitchat_agent",
    })
    graph.add_conditional_edges("clarifier", route_after_clarifier, {
        "end_clarify": END,
        "planner": "planner",
    })
    graph.add_conditional_edges("planner", route_after_planner, {
        "end": END,
        "end_clarify": END,
        "sql_engineer": "sql_engineer",
    })
    graph.add_conditional_edges("sql_engineer", route_after_sql_engineer, {
        "end": END,
        "code_reviewer": "code_reviewer",
    })
    graph.add_conditional_edges("code_reviewer", route_after_code_reviewer, {
        "end": END,
        "sql_engineer": "increment_retry",
        "script_runner": "script_runner",
    })
    graph.add_edge("increment_retry", "sql_engineer")
    graph.add_conditional_edges("script_runner", route_after_script_runner, {
        "end": END,
        "summarizer": "summarizer",
    })
    graph.add_edge("summarizer", END)
    graph.add_conditional_edges("knowledge_agent", route_after_knowledge_agent, {
        "end_clarify": END,
        "end": END,
    })
    graph.add_edge("chitchat_agent", END)

    return graph.compile()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/backend
python -m pytest tests/test_pipeline_routing.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 5: Run full existing test suite to verify no regressions**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/backend
python -m pytest tests/ -v --ignore=tests/test_clickhouse.py 2>&1 | tail -20
```

Expected: all previously passing tests still PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/graph/pipeline.py backend/tests/test_pipeline_routing.py
git commit -m "feat: wire intent_router, knowledge_agent, chitchat_agent into pipeline"
```

---

## Task 5: chat.py — handle knowledge/chitchat answers in WebSocket loop

**Files:**
- Modify: `backend/api/chat.py`

- [ ] **Step 1: Update PipelineState initialization in chat.py**

In `backend/api/chat.py`, find the `PipelineState(...)` constructor call and add the five new fields:

```python
            state = PipelineState(
                session_id=session_id,
                user_message=message,
                conversation_history=conversation_history.copy(),
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
                progress_cb=progress_cb,
                intent=None,
                rewritten_query=None,
                intent_confidence=0.0,
                knowledge_answer=None,
                chitchat_answer=None,
            )
```

- [ ] **Step 2: Add knowledge/chitchat answer handling after the pipeline result**

In `backend/api/chat.py`, find the comment `# clarifier 追问` and add new handling blocks **before** it:

```python
            # knowledge_qa 澄清追问
            if result_state.get("intent") == "knowledge_qa" and not result_state.get("clarifier_done", True) and result_state.get("clarifier_question"):
                q = result_state["clarifier_question"]
                options = result_state.get("clarifier_options", [])
                payload = {"type": "clarify", "question": q, "options": options, "allow_free_input": True}
                await _send(ws, payload)
                save_message(session_id, "assistant", "text", q)
                conversation_history.append({"role": "assistant", "content": q})
                logger.info("[%s] knowledge clarification sent", session_id)
                await _send(ws, {"type": "done", "content": ""})
                continue

            # knowledge_qa 回答
            knowledge_answer = result_state.get("knowledge_answer")
            if knowledge_answer:
                save_message(session_id, "assistant", "text", knowledge_answer)
                await _send(ws, {"type": "result", "render": "text", "content": knowledge_answer})
                conversation_history.append({"role": "assistant", "content": knowledge_answer})
                logger.info("[%s] knowledge answer sent  len=%d", session_id, len(knowledge_answer))
                await _send(ws, {"type": "done", "content": ""})
                continue

            # chitchat 回答
            chitchat_answer = result_state.get("chitchat_answer")
            if chitchat_answer:
                save_message(session_id, "assistant", "text", chitchat_answer)
                await _send(ws, {"type": "result", "render": "text", "content": chitchat_answer})
                conversation_history.append({"role": "assistant", "content": chitchat_answer})
                logger.info("[%s] chitchat answer sent  len=%d", session_id, len(chitchat_answer))
                await _send(ws, {"type": "done", "content": ""})
                continue
```

- [ ] **Step 3: Run full test suite**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/backend
python -m pytest tests/ -v --ignore=tests/test_clickhouse.py 2>&1 | tail -20
```

Expected: all tests PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/api/chat.py
git commit -m "feat: handle knowledge_answer and chitchat_answer in WebSocket handler"
```

---

## Task 6: smoke test end-to-end

**Files:**
- No new files — manual verification

- [ ] **Step 1: Start the backend**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/backend
uvicorn main:app --reload --port 8000
```

- [ ] **Step 2: Verify health endpoint responds**

```bash
curl http://localhost:8000/api/v1/health
```

Expected: `{"status": "ok"}` or similar.

- [ ] **Step 3: Run all tests one final time**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/backend
python -m pytest tests/ -v --ignore=tests/test_clickhouse.py
```

Expected: all tests PASS, no regressions.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "chore: intent router feature complete — all tests passing"
```
