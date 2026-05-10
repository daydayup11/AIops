import json
import logging
import re
from langchain_openai import ChatOpenAI
from models.schemas import SubTask, SQLTask
from db.schema import TABLE_SCHEMA
from config import settings

logger = logging.getLogger(__name__)

_BIG_TABLES = {"sessions", "npm", "dns", "url"}
_TIME_FIELDS = {
    "sessions": "start",
    "npm": "start",
    "dns": "collect_time",
    "url": "collect_time",
    "iplog": "collect_time",
    "wanlog": "collect_time",
    "applog": "collect_time",
    "event": "collect_time",
    "usrauth": "collect_time",
}

_SYSTEM_PROMPT = f"""你是SQL生成专家，为校园网ClickHouse数据库生成查询SQL。

{TABLE_SCHEMA}

返回严格JSON数组（不要Markdown代码块）：
[{{"task_id":"t1","sql":"SELECT ...","description":"说明"}}]

规则：
1. 只生成SELECT语句
2. 必须包含时间条件（sessions/npm用start，其余用collect_time）
3. 大表加LIMIT 10000
4. 使用ClickHouse语法（now(), INTERVAL 1 DAY, toDate()等）
"""


def ensure_time_condition(sql: str, primary_table: str) -> str:
    time_field = _TIME_FIELDS.get(primary_table, "collect_time")
    if re.search(r'\b(start|collect_time)\b', sql, re.IGNORECASE):
        return sql
    where_match = re.search(r'\bWHERE\b', sql, re.IGNORECASE)
    if where_match:
        pos = where_match.end()
        return sql[:pos] + f" {time_field} >= now()-INTERVAL 1 DAY AND" + sql[pos:]
    from_match = re.search(r'\bGROUP BY\b|\bORDER BY\b|\bLIMIT\b', sql, re.IGNORECASE)
    if from_match:
        pos = from_match.start()
        return sql[:pos] + f" WHERE {time_field} >= now()-INTERVAL 1 DAY " + sql[pos:]
    return sql + f" WHERE {time_field} >= now()-INTERVAL 1 DAY"


def ensure_limit(sql: str, limit: int = 10000) -> str:
    if re.search(r'\bLIMIT\b', sql, re.IGNORECASE):
        return sql
    return sql.rstrip(";") + f" LIMIT {limit}"


def optimize_sql(sql: str, tables: list) -> str:
    primary = tables[0] if tables else "sessions"
    sql = ensure_time_condition(sql, primary)
    if any(t in _BIG_TABLES for t in tables):
        sql = ensure_limit(sql)
    return sql


def _build_llm() -> ChatOpenAI:
    cfg = settings["llm"]
    return ChatOpenAI(
        base_url=cfg["base_url"],
        api_key=cfg["api_key"],
        model=cfg["model"],
        temperature=cfg["temperature"],
    )


def run_sql_engineer(tasks: list, llm=None) -> list:
    llm = llm or _build_llm()
    task_desc = "\n".join(
        f"- id={t.id}: {t.description}，涉及表：{', '.join(t.tables)}, 时间范围：{t.time_range_hours}小时"
        for t in tasks
    )
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": f"为以下子任务生成SQL：\n{task_desc}"},
    ]
    try:
        response = llm.invoke(messages)
    except Exception:
        logger.error("LLM call failed in sql_engineer", exc_info=True)
        return []

    logger.debug("SQL engineer raw LLM response: %s", response.content[:500])
    try:
        data = json.loads(response.content)
        result = []
        task_map = {t.id: t for t in tasks}
        for item in data:
            matched_task = task_map.get(item["task_id"], tasks[0])
            sql = optimize_sql(item["sql"], matched_task.tables)
            result.append(SQLTask(task_id=item["task_id"], sql=sql, description=item["description"]))
        logger.info("SQL tasks generated: %d", len(result))
        return result
    except Exception:
        logger.warning("SQL engineer JSON parse failed, returning empty list", exc_info=True)
        return []
