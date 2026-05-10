import json
import logging
from langchain_openai import ChatOpenAI
from models.schemas import TaskPlan
from db.schema import TABLE_SCHEMA
from config import settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = f"""你是校园网流量智能分析助手的规划大脑。你的职责是：深度理解用户的分析意图，制定完整的分析方案。

{TABLE_SCHEMA}

## 工作流程

**第一步：推理分析目标**
思考用户真正想知道什么，不只是字面意思。

**第二步：制定分析方案**
确定分析维度和策略，例如：从流量特征、端口特征、应用特征、时序特征等多个角度交叉验证。

**第三步：规划可视化意图**
用自然语言描述希望生成的图表，不需要指定列名或图表类型，只描述"想看什么"。

---

返回严格JSON格式（不要Markdown代码块）：
{{
  "analysis_plan": {{
    "goal": "用户真实分析目标（1-2句话）",
    "approach": "分析思路（2-3句话）",
    "expected_findings": ["预期发现1", "预期发现2"],
    "analysis_dimensions": ["维度1", "维度2"],
    "viz_intent": "可视化意图描述（自然语言，描述想展示什么，不要指定列名或图表类型）"
  }},
  "clarification_needed": false,
  "clarification_question": null,
  "estimated_seconds": 10
}}

## 约束规则

- 如果问题缺少关键信息（时间范围或分析维度），设 clarification_needed=true
- 最多澄清5轮，之后必须强制给出分析方案
- analysis_plan.viz_intent 只描述意图，例如："展示各IP的外发流量排名，突出Top10异常值；同时展示时序趋势"
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

    import time
    logger.info("planner: LLM call start  model=%s  history=%d  input=%r",
                settings["llm"]["model"], len(conversation_history), user_message[:100])
    t0 = time.perf_counter()
    try:
        response = llm.invoke(messages)
    except Exception:
        logger.error("planner: LLM call failed (%.2fs)", time.perf_counter() - t0, exc_info=True)
        return TaskPlan(
            clarification_needed=True,
            clarification_question="抱歉，我没有理解您的问题，请重新描述一下您想分析什么？",
        )
    logger.info("planner: LLM call done  %.2fs", time.perf_counter() - t0)
    try:
        data = json.loads(response.content)
        plan = TaskPlan(**data)
        if plan.clarification_needed:
            logger.info("planner: clarification_needed  question=%r", plan.clarification_question)
        else:
            ap = plan.analysis_plan
            logger.info("planner: plan  goal=%r  dims=%s  viz_intent=%r",
                        ap.goal if ap else None,
                        ap.analysis_dimensions if ap else [],
                        (ap.viz_intent[:80] if ap else None))
        return plan
    except Exception:
        logger.warning("planner: JSON parse failed, falling back to clarification", exc_info=True)
        return TaskPlan(
            clarification_needed=True,
            clarification_question="抱歉，我没有理解您的问题，请重新描述一下您想分析什么？",
        )
