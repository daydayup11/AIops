import json
import logging
import time
import pandas as pd
from pathlib import Path
from langchain_openai import ChatOpenAI
from models.schemas import VizSpec
from config import settings

logger = logging.getLogger(__name__)

_RENDERS_DIR = Path(__file__).parent.parent.parent / "data" / "renders"
_RENDERS_DIR.mkdir(parents=True, exist_ok=True)

_SYSTEM_PROMPT = """你是数据可视化专家。根据DataFrame的结构和任务描述，决定最佳可视化方案。

返回严格JSON（不要Markdown代码块）：
{
  "render_type": "echarts",
  "chart_type": "bar",
  "title": "图表标题",
  "x_field": "列名",
  "y_field": "列名",
  "series_field": null,
  "insight": "一句话洞察"
}

render_type 规则：
- echarts：单图，简单数据（柱状图/折线图/饼图）
- html：多图联动、地图、复杂看板

chart_type 可选：bar, line, pie, scatter, heatmap
"""


def _build_llm() -> ChatOpenAI:
    cfg = settings["llm"]
    return ChatOpenAI(
        base_url=cfg["base_url"],
        api_key=cfg["api_key"],
        model=cfg["model"],
        temperature=cfg["temperature"],
    )


def _df_summary(df: pd.DataFrame) -> str:
    return f"columns: {list(df.columns)}, dtypes: {df.dtypes.to_dict()}, shape: {df.shape}, head:\n{df.head(3).to_string()}"


def _build_echarts_option(spec: VizSpec, df: pd.DataFrame) -> dict:
    x_data = df[spec.x_field].astype(str).tolist() if spec.x_field and spec.x_field in df.columns else []
    y_data = df[spec.y_field].tolist() if spec.y_field and spec.y_field in df.columns else []

    if spec.chart_type == "pie":
        series_data = []
        if spec.x_field and spec.y_field:
            series_data = [{"name": str(row[spec.x_field]), "value": row[spec.y_field]} for _, row in df.iterrows()]
        return {
            "title": {"text": spec.title},
            "tooltip": {"trigger": "item"},
            "series": [{"type": "pie", "data": series_data, "radius": "60%"}],
        }

    return {
        "title": {"text": spec.title, "subtext": spec.insight},
        "tooltip": {},
        "xAxis": {"type": "category", "data": x_data},
        "yAxis": {"type": "value"},
        "series": [{"type": spec.chart_type or "bar", "data": y_data}],
    }


def _build_html(spec: VizSpec, df: pd.DataFrame, session_id: str, message_id: str) -> str:
    table_html = df.to_html(index=False, classes="table", max_rows=200)
    echarts_option = json.dumps(_build_echarts_option(spec, df), ensure_ascii=False)
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>{spec.title}</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<style>body{{font-family:sans-serif;padding:20px}} .table{{border-collapse:collapse;width:100%}} .table th,.table td{{border:1px solid #ddd;padding:8px}}</style>
</head><body>
<h2>{spec.title}</h2>
<p>{spec.insight}</p>
<div id="chart" style="width:100%;height:400px"></div>
{table_html}
<script>
var chart = echarts.init(document.getElementById('chart'));
chart.setOption({echarts_option});
</script>
</body></html>"""
    path = _RENDERS_DIR / session_id / f"{message_id}.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return str(path)


def run_visualizer(
    results: dict,
    blueprints: list,
    session_id: str,
    message_id: str,
    llm=None,
) -> list:
    llm_instance = None  # 懒加载，仅在需要时初始化
    blueprint_map = {bp.task_id: bp for bp in blueprints}
    outputs = []

    logger.info("visualizer: start  tasks=%d  blueprints=%d", len(results), len(blueprints))
    for task_id, result in results.items():
        if result["status"] != "success":
            logger.warning("visualizer: skip task=%s  status=%s", task_id, result["status"])
            outputs.append({
                "render": "text",
                "content": f"⚠️ {result['description']} 获取失败：{result.get('error', '未知错误')}"
            })
            continue

        df: pd.DataFrame = result["df"]
        if df.empty:
            outputs.append({"render": "text", "content": f"📭 {result['description']}：无数据"})
            continue

        blueprint = blueprint_map.get(task_id)
        if blueprint:
            logger.info("visualizer: task=%s  using blueprint  chart=%s", task_id, blueprint.chart_type)
            spec = VizSpec(
                render_type="echarts",
                chart_type=blueprint.chart_type,
                title=blueprint.title,
                x_field=blueprint.x_field,
                y_field=blueprint.y_field,
                insight=blueprint.insight_hint,
            )
            option = _build_echarts_option(spec, df)
            outputs.append({"render": "echarts", "content": option, "insight": blueprint.insight_hint})
        else:
            logger.info("visualizer: task=%s  no blueprint, falling back to LLM", task_id)
            if llm_instance is None:
                llm_instance = llm or _build_llm()
            summary = _df_summary(df)
            messages = [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": f"任务：{result['description']}\n数据结构：{summary}"},
            ]
            t0 = time.perf_counter()
            response = llm_instance.invoke(messages)
            logger.info("visualizer: task=%s  LLM fallback done %.2fs", task_id, time.perf_counter() - t0)
            try:
                spec = VizSpec(**json.loads(response.content))
            except Exception:
                spec = VizSpec(
                    render_type="echarts",
                    chart_type="bar",
                    title=result["description"],
                    x_field=df.columns[0] if len(df.columns) > 0 else None,
                    y_field=df.columns[1] if len(df.columns) > 1 else None,
                    insight="",
                )
            if spec.render_type == "html":
                path = _build_html(spec, df, session_id, f"{message_id}_{task_id}")
                outputs.append({"render": "html", "content": path, "title": spec.title})
            else:
                option = _build_echarts_option(spec, df)
                outputs.append({"render": "echarts", "content": option, "insight": spec.insight})

    logger.info("visualizer: done  outputs=%d", len(outputs))
    return outputs
