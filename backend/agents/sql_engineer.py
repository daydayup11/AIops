import logging
import time
from typing import Optional
from langchain_openai import ChatOpenAI
from models.schemas import TaskPlan, PyScript
from db.schema import TABLE_SCHEMA
from config import settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = f"""你是校园网流量分析的Python脚本生成专家。

{TABLE_SCHEMA}

你的任务：根据分析方案，生成一个完整的Python脚本。

## 脚本要求

1. **数据库连接与查询**：通过环境变量获取参数，使用以下固定模板执行查询并转换为DataFrame：
   ```python
   import os
   import pandas as pd
   from clickhouse_driver import Client
   client = Client(
       host=os.environ['CH_HOST'],
       port=int(os.environ['CH_PORT']),
       user=os.environ['CH_USER'],
       password=os.environ['CH_PASSWORD'],
       database=os.environ['CH_DATABASE'],
   )

   # 【重要】execute返回 (rows, columns) 元组，必须按此方式转换DataFrame：
   rows, columns = client.execute("SELECT ...", with_column_types=True)
   df = pd.DataFrame(rows, columns=[col[0] for col in columns])
   ```
   **严禁**写成 `df = client.execute(...)` 或 `df[0]`/`df[1]` 的访问方式，否则DataFrame无法正确构建。

2. **SQL规则**（违反会导致查询失败）：
   - 只用SELECT，必须带时间条件（sessions/npm用start，其余用collect_time）
   - 大表（sessions/npm/dns/url）必须加LIMIT
   - 禁止大表相互JOIN
   - 使用ClickHouse语法（now(), INTERVAL 1 DAY等）

3. **图片输出**：
   ```python
   output_dir = os.environ['OUTPUT_DIR']
   plt.savefig(os.path.join(output_dir, '01_图表名.png'), dpi=100, bbox_inches='tight')
   plt.close()
   ```
   - 文件名用数字前缀排序（01_, 02_）
   - 只能写入 OUTPUT_DIR，不能写其他路径
   - 使用matplotlib/seaborn，设置中文字体：`plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']`

4. **错误处理**：每个查询用try/except，失败时打印错误并继续下一个图

5. **数据摘要输出**（可选，失败时静默跳过）：
   每个图表的plt.savefig之前，将关键数据追加到_summary["charts"]；所有图表完成后写入一次：
   ```python
   import json as _json
   _summary = {{"charts": []}}
   # 在每个图表块中，plt.savefig 之前：
   # _summary["charts"].append({{
   #     "title": "图表标题",
   #     "key_findings": ["关键发现1（中文）", "关键发现2"],  # 2-5条最重要发现
   #     "data": df.head(20).to_dict(orient="records")  # 最多20行原始数据
   # }})
   try:
       with open(os.path.join(output_dir, 'data_summary.json'), 'w', encoding='utf-8') as _f:
           _json.dump(_summary, _f, ensure_ascii=False, default=str)
   except Exception:
       pass
   ```
   - key_findings 用中文自然语言描述该图最重要的2-5条发现（如"BiliBili流量最高：45.2GB"）
   - data 只取前20行，避免文件过大
   - 写入用try/except包裹，失败静默跳过，不影响图表输出

6. **超时意识**：
   - 查询大表时带时间窗口，避免全表扫描
   - 复杂聚合用LIMIT控制结果集
   - 整个脚本须在60秒内完成

## 输出

直接输出Python脚本代码，不要任何说明文字，不要Markdown代码块。
"""

_RETRY_SUFFIX = """

## 上次代码审查发现的问题，请修复：

{issues}

请生成修复后的完整脚本。
"""


def _build_llm() -> ChatOpenAI:
    cfg = settings["llm"]
    return ChatOpenAI(
        base_url=cfg["base_url"],
        api_key=cfg["api_key"],
        model=cfg["model"],
        temperature=cfg["temperature"],
    )


def run_sql_engineer(
    task_plan: TaskPlan,
    issues: Optional[list[str]] = None,
    llm=None,
) -> Optional[PyScript]:
    llm = llm or _build_llm()
    ap = task_plan.analysis_plan
    if ap is None:
        logger.error("sql_engineer: analysis_plan is None, cannot generate script")
        return None

    user_content = f"""分析目标：{ap.goal}
分析思路：{ap.approach}
分析维度：{', '.join(ap.analysis_dimensions)}
预期发现：{', '.join(ap.expected_findings)}
可视化意图：{ap.viz_intent}"""

    if issues:
        user_content += _RETRY_SUFFIX.format(issues='\n'.join(f'- {i}' for i in issues))

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    logger.info("sql_engineer: LLM call start  retry_issues=%d", len(issues) if issues else 0)
    t0 = time.perf_counter()
    try:
        response = llm.invoke(messages)
    except Exception:
        logger.error("sql_engineer: LLM call failed (%.2fs)", time.perf_counter() - t0, exc_info=True)
        return None
    elapsed = time.perf_counter() - t0
    logger.info("sql_engineer: done %.2fs  script_len=%d", elapsed, len(response.content))

    script_code = response.content.strip()
    # Strip markdown code fences if LLM adds them despite instructions
    if script_code.startswith("```"):
        lines = script_code.split('\n')
        end_idx = next(
            (i for i in range(len(lines) - 1, 0, -1) if lines[i].strip() == "```"),
            None,
        )
        script_code = '\n'.join(lines[1:end_idx] if end_idx is not None else lines[1:])

    description = ap.goal
    return PyScript(script_code=script_code, description=description)
