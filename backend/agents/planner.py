import json
import logging
from langchain_openai import ChatOpenAI
from models.schemas import TaskPlan
from db.schema import TABLE_SCHEMA
from config import settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = f"""你是校园网流量分析助手的任务规划器。
根据用户的自然语言问题，分解成可并行执行的数据查询子任务。

{TABLE_SCHEMA}

你必须返回严格的JSON格式（不要Markdown代码块）：
{{
  "tasks": [
    {{
      "id": "t1",
      "description": "任务描述",
      "tables": ["表名"],
      "time_range_hours": 24
    }}
  ],
  "clarification_needed": false,
  "clarification_question": null,
  "estimated_seconds": 10
}}

规则：
- 如果问题不清楚（缺少时间范围或分析维度），设 clarification_needed=true
- 最多2轮澄清，之后必须给出任务
- 每个子任务只查询1-2张表
- estimated_seconds 根据表大小和时间范围估算（sessions/npm大表单天约5s）
"""


def _build_llm() -> ChatOpenAI:
    cfg = settings["llm"]
    return ChatOpenAI(
        base_url=cfg["base_url"],
        api_key=cfg["api_key"],
        model=cfg["model"],
        temperature=cfg["temperature"],
    )


def run_planner(
    user_message: str,
    conversation_history: list,
    llm=None,
) -> TaskPlan:
    llm = llm or _build_llm()
    messages = [{"role": "system", "content": _SYSTEM_PROMPT}]
    messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_message})

    try:
        response = llm.invoke(messages)
    except Exception:
        logger.error("LLM call failed in planner", exc_info=True)
        return TaskPlan(
            tasks=[],
            clarification_needed=True,
            clarification_question="抱歉，我没有理解您的问题，请重新描述一下您想分析什么？",
        )

    logger.debug("Planner raw LLM response: %s", response.content[:500])
    try:
        data = json.loads(response.content)
        plan = TaskPlan(**data)
        if plan.clarification_needed:
            logger.info("Clarification requested: %s", plan.clarification_question)
        else:
            logger.info("Task plan generated: %d tasks", len(plan.tasks))
        return plan
    except Exception:
        logger.warning("Planner JSON parse failed, returning clarification fallback", exc_info=True)
        return TaskPlan(
            tasks=[],
            clarification_needed=True,
            clarification_question="抱歉，我没有理解您的问题，请重新描述一下您想分析什么？",
        )
