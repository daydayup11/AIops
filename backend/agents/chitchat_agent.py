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
        temperature=0.7,  # higher temperature for more natural chitchat responses
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
