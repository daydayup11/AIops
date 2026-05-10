import json
import logging
import time
from langchain_openai import ChatOpenAI
from models.schemas import SummaryReport
from config import settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """你是数据分析报告专家。根据用户的原始问题和各图表的洞察，生成一份结构化分析报告。

返回严格JSON（不要Markdown代码块）：
{
  "title": "报告标题（10字以内）",
  "key_points": ["要点1", "要点2", "要点3"],
  "conclusion": "针对用户问题的结论段落（2-3句话，直接回答用户问题）"
}

规则：
- key_points 3-5条，每条一句话，聚焦数据发现
- conclusion 必须直接回答用户的原始问题
- 使用中文
"""


def _build_llm() -> ChatOpenAI:
    cfg = settings["llm"]
    return ChatOpenAI(
        base_url=cfg["base_url"],
        api_key=cfg["api_key"],
        model=cfg["model"],
        temperature=cfg["temperature"],
    )


def run_summarizer(user_message: str, insights: list, llm=None) -> SummaryReport:
    llm = llm or _build_llm()
    insights_text = "\n".join(
        f"- 图表{i+1}（{item.get('task_id','')}）：{item.get('insight_hint','')}，数据行数={item.get('rows',0)}"
        for i, item in enumerate(insights)
    )
    user_content = f"用户问题：{user_message}\n\n各图表洞察：\n{insights_text}"
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    logger.info("summarizer: LLM call start  input=%r  insights=%d", user_message[:80], len(insights))
    t0 = time.perf_counter()
    try:
        response = llm.invoke(messages)
    except Exception:
        logger.error("summarizer: LLM call failed", exc_info=True)
        return SummaryReport(title="分析完成", key_points=[], conclusion="数据已查询完成，请查看上方图表。")

    logger.info("summarizer: done %.2fs", time.perf_counter() - t0)
    try:
        data = json.loads(response.content)
        report = SummaryReport(**data)
        logger.info("summarizer: report title=%r  points=%d", report.title, len(report.key_points))
        return report
    except Exception:
        logger.warning("summarizer: parse failed, using fallback", exc_info=True)
        return SummaryReport(
            title="分析报告",
            key_points=[item.get("insight_hint", "") for item in insights if item.get("insight_hint")],
            conclusion=f"针对「{user_message}」的分析已完成，请参考上方图表。",
        )
