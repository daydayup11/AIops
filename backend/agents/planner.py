import json
import logging
from langchain_openai import ChatOpenAI
from models.schemas import TaskPlan
from db.schema import TABLE_SCHEMA
from config import settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = f"""你是校园网流量分析助手的任务规划器。
根据用户的自然语言问题，分解成可并行执行的数据查询子任务，并为每个子任务指定可视化蓝图。

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
  "viz_blueprint": [
    {{
      "task_id": "t1",
      "chart_type": "bar",
      "title": "图表标题",
      "x_field": "列名",
      "y_field": "列名",
      "insight_hint": "预期揭示的规律，一句话"
    }}
  ],
  "clarification_needed": false,
  "clarification_question": null,
  "estimated_seconds": 10
}}

规则：
- viz_blueprint 与 tasks 一一对应，task_id 必须匹配
- 不允许两个蓝图的 chart_type+x_field+y_field 完全相同（避免重复图表）
- chart_type 可选：bar, line, pie, scatter, heatmap
- 如果问题不清楚（缺少时间范围或分析维度），设 clarification_needed=true，viz_blueprint 可为空数组
- 最多5轮澄清，之后必须给出任务
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

    logger.info("planner: LLM call start  model=%s  history_turns=%d  input=%r",
                settings["llm"]["model"], len(conversation_history), user_message[:100])
    import time
    t0 = time.perf_counter()
    try:
        response = llm.invoke(messages)
    except Exception:
        logger.error("planner: LLM call failed (%.2fs)", time.perf_counter() - t0, exc_info=True)
        return TaskPlan(
            tasks=[],
            clarification_needed=True,
            clarification_question="抱歉，我没有理解您的问题，请重新描述一下您想分析什么？",
        )
    logger.info("planner: LLM call done  %.2fs  tokens=%s", time.perf_counter() - t0,
                getattr(response, "response_metadata", {}).get("token_usage", "?"))
    logger.debug("planner: raw response  %s", response.content[:500])
    try:
        data = json.loads(response.content)
        plan = TaskPlan(**data)
        if plan.clarification_needed:
            logger.info("planner: clarification_needed  question=%r", plan.clarification_question)
        else:
            for t in plan.tasks:
                logger.info("planner: task  id=%s  tables=%s  hours=%s  desc=%r",
                            t.id, t.tables, t.time_range_hours, t.description)
            for bp in plan.viz_blueprint:
                logger.info("planner: blueprint  task_id=%s  chart=%s  x=%s  y=%s",
                            bp.task_id, bp.chart_type, bp.x_field, bp.y_field)
        return plan
    except Exception:
        logger.warning("planner: JSON parse failed, falling back to clarification", exc_info=True)
        return TaskPlan(
            tasks=[],
            clarification_needed=True,
            clarification_question="抱歉，我没有理解您的问题，请重新描述一下您想分析什么？",
        )
