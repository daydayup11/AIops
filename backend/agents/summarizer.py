import json
import logging
import time
from typing import Optional
from langchain_openai import ChatOpenAI
from models.schemas import SummaryReport, AnalysisPlan
from config import settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """你是数据分析报告专家。你会收到：
1. 用户的原始问题
2. 分析方案（规划阶段制定的目标、思路、预期发现）
3. 各查询任务的实际数据结果摘要

你的任务是：对照分析方案，结合实际数据，生成一份有深度的分析报告。

返回严格JSON（不要Markdown代码块）：
{
  "title": "报告标题（10字以内）",
  "key_points": ["要点1", "要点2", "要点3"],
  "conclusion": "结论段落（3-4句话：先直接回答用户问题，再说明数据依据，最后给出行动建议）"
}

规则：
- key_points 3-5条，每条一句话，需对照预期发现说明是否验证、有何差异
- conclusion 必须直接回答用户问题，并给出可操作的建议
- 若某个分析维度数据为空或查询失败，需在报告中说明该维度未能覆盖
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


def _format_insight(index: int, item: dict) -> str:
    hint = item.get("insight_hint", "")
    # New script-based pipeline: item has "charts" (number of images produced)
    if "charts" in item:
        charts = item["charts"]
        status = f"已生成 {charts} 张图表" if charts > 0 else "脚本执行完成但未生成图表"
        return f"- 分析{index + 1}：{hint}，{status}"
    # Legacy row-based pipeline: item has "rows"
    rows = item.get("rows", 0)
    status = f"有效数据 {rows} 行" if rows > 0 else "无数据或查询失败"
    return f"- 维度{index + 1}（{item.get('task_id', '')}）：{hint}，{status}"


def run_summarizer(
    user_message: str,
    insights: list,
    analysis_plan: Optional[AnalysisPlan] = None,
    data_summary: Optional[str] = None,
    llm=None,
) -> SummaryReport:
    llm = llm or _build_llm()

    plan_text = ""
    if analysis_plan:
        dims = "、".join(analysis_plan.analysis_dimensions)
        findings = "\n".join(f"  - {f}" for f in analysis_plan.expected_findings)
        plan_text = f"""
分析方案：
- 目标：{analysis_plan.goal}
- 思路：{analysis_plan.approach}
- 分析维度：{dims}
- 预期发现：
{findings}
"""

    insights_text = "\n".join(
        _format_insight(i, item) for i, item in enumerate(insights)
    )

    data_text = f"\n\n实际图表数据（JSON）：\n{data_summary}" if data_summary else ""
    user_content = f"用户问题：{user_message}\n{plan_text}\n实际查询结果：\n{insights_text}{data_text}"
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
