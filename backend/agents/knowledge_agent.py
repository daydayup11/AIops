import json
import logging
import os
from pathlib import Path
from typing import List, Optional
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


def _build_llm() -> ChatOpenAI:
    cfg = settings["llm"]
    return ChatOpenAI(
        base_url=cfg["base_url"],
        api_key=cfg["api_key"],
        model=cfg["model"],
        temperature=cfg["temperature"],
    )


def run_knowledge_agent(
    query: str,
    conversation_history: list,
    docs_context: Optional[List[str]] = None,
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
        if result.get("action") not in ("answer", "ask"):
            raise ValueError(f"invalid action: {result.get('action')!r}")
        logger.info("knowledge_agent: action=%s", result["action"])
        return result
    except Exception:
        logger.warning("knowledge_agent: parse failed, return raw", exc_info=True)
        return {"action": "answer", "answer": response.content.strip()}
