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
