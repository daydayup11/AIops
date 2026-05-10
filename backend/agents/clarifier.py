import json
import logging
from langchain_openai import ChatOpenAI
from config import settings

logger = logging.getLogger(__name__)

_FORCE_CONTINUE_KEYWORDS = {"开始分析", "就这样", "直接查", "不用问了", "跳过", "直接分析"}

_SYSTEM_PROMPT = """你是校园网流量分析助手的需求澄清专家。
判断用户的问题是否已经足够明确，可以直接开始分析。

明确的需求应包含：
1. 时间范围（如"过去24小时"、"最近一周"）
2. 分析维度（如"按应用"、"按用户"、"按时段"）
3. 分析目标（如"排行"、"趋势"、"异常"）

返回严格JSON（不要Markdown代码块）：
- 需求明确：{"action": "continue"}
- 需求不明确：{"action": "ask", "question": "一个具体追问", "options": ["选项1", "选项2", "选项3"]}

规则：
- options 提供 2-4 个，覆盖最常见选择
- 每次只问一个问题，不堆叠问题
- 如果已经追问过，且用户给出了任何回答，倾向于 continue
"""


def _build_llm() -> ChatOpenAI:
    cfg = settings["llm"]
    return ChatOpenAI(
        base_url=cfg["base_url"],
        api_key=cfg["api_key"],
        model=cfg["model"],
        temperature=cfg["temperature"],
    )


def run_clarifier(user_message: str, conversation_history: list, llm=None) -> dict:
    for kw in _FORCE_CONTINUE_KEYWORDS:
        if kw in user_message:
            logger.info("clarifier: force continue by keyword %r", kw)
            return {"action": "continue"}

    llm = llm or _build_llm()
    messages = [{"role": "system", "content": _SYSTEM_PROMPT}]
    messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_message})

    logger.info("clarifier: LLM call start  input=%r  history=%d", user_message[:80], len(conversation_history))
    try:
        response = llm.invoke(messages)
    except Exception:
        logger.error("clarifier: LLM call failed", exc_info=True)
        return {
            "action": "ask",
            "question": "您想分析什么内容？请描述时间范围和分析目标。",
            "options": ["最近24小时流量排行", "最近一周趋势", "实时异常检测"],
        }

    logger.debug("clarifier: raw response %r", response.content[:200])
    try:
        result = json.loads(response.content)
        assert result.get("action") in ("continue", "ask")
        logger.info("clarifier: action=%s", result["action"])
        return result
    except Exception:
        logger.warning("clarifier: parse failed, fallback to ask", exc_info=True)
        return {
            "action": "ask",
            "question": "请问您具体想分析什么？",
            "options": ["过去24小时Top应用流量", "用户流量趋势", "网络异常检测", "时段流量分布"],
        }
