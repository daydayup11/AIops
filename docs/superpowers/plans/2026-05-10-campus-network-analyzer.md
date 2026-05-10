# 校园网流量分析助手 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个基于自然语言的校园网流量分析助手，LangGraph 三 Agent 流水线驱动，ClickHouse 数据后端，React 前端展示图表。

**Architecture:** FastAPI 后端 + React 前端分离部署。后端通过 LangGraph 编排 Planner → SQL Engineer → Visualizer 三个 Agent，SQL 结果不经 LLM 直接由 Python 渲染为 ECharts JSON 或 HTML，前端通过 WebSocket 实时接收进度和结果。

**Tech Stack:** Python 3.9+, FastAPI, LangGraph, langchain-openai, clickhouse-driver, pandas, SQLite, React 18, TypeScript, ECharts, Tailwind CSS, Vite

---

## 文件结构总览

**后端新建文件：**
- `backend/main.py` — FastAPI 入口，挂载路由，初始化数据库
- `backend/config.py` — 加载 `config/settings.yaml`，暴露全局 `settings` 对象
- `backend/models/schemas.py` — Pydantic 模型：`WSMessage`, `TaskPlan`, `SQLTask`, `VizPlan`, `ChatMessage`
- `backend/db/clickhouse.py` — ClickHouse 连接池，`execute_query(sql) -> pd.DataFrame`
- `backend/db/sqlite.py` — SQLite 初始化，`save_message()`, `get_session_messages()`
- `backend/db/schema.py` — 表结构字符串常量，供 LLM System Prompt 使用
- `backend/executor/parallel.py` — `ParallelExecutor`: 并行运行 SQL 列表，WebSocket 推送进度，降级重试
- `backend/agents/planner.py` — Planner Agent 节点函数，LLM 意图识别 + 澄清 + 任务分解
- `backend/agents/sql_engineer.py` — SQL Engineer Agent 节点函数，LLM 生成 SQL + Python 安全校验和优化
- `backend/agents/visualizer.py` — Visualizer Agent 节点函数，LLM 决定可视化方案 + Python 生成 ECharts JSON 或 HTML
- `backend/graph/pipeline.py` — LangGraph StateGraph 定义，连接三个 Agent 节点
- `backend/api/chat.py` — WebSocket `/api/v1/chat` 端点
- `backend/api/health.py` — GET `/api/v1/health`, `/api/v1/sessions`, `/api/v1/sessions/{id}`
- `config/settings.yaml` — 所有可配置参数

**前端新建文件：**
- `frontend/src/types.ts` — 前端 TypeScript 类型定义
- `frontend/src/hooks/useWebSocket.ts` — WebSocket 连接 hook，处理消息流
- `frontend/src/components/SessionSidebar.tsx` — 历史对话列表
- `frontend/src/components/ProgressBar.tsx` — 任务进度条
- `frontend/src/components/ChartRenderer.tsx` — ECharts/iframe 渲染器
- `frontend/src/components/ChatPanel.tsx` — 对话消息流（主工作区）
- `frontend/src/components/InputBar.tsx` — 输入框 + 发送按钮
- `frontend/src/App.tsx` — 根组件，布局组装

**测试文件：**
- `backend/tests/test_config.py`
- `backend/tests/test_clickhouse.py`
- `backend/tests/test_sql_safety.py`
- `backend/tests/test_parallel_executor.py`
- `backend/tests/test_planner.py`
- `backend/tests/test_pipeline.py`

---

## Task 1: 项目脚手架和配置

**Files:**
- Create: `config/settings.yaml`
- Create: `backend/config.py`
- Create: `backend/tests/test_config.py`
- Create: `requirements.txt`

- [ ] **Step 1: 安装后端依赖**

```bash
cd /Users/daiyutong/PycharmProjects/AIops
source .venv/bin/activate
pip install fastapi uvicorn[standard] langgraph langchain-openai \
    clickhouse-driver pandas pyyaml cachetools aiosqlite \
    pytest pytest-asyncio
pip freeze > requirements.txt
```

- [ ] **Step 2: 创建配置文件**

创建 `config/settings.yaml`：

```yaml
clickhouse:
  host: "10.161.111.100"
  port: 9000
  user: "sesslog"
  password: "1"
  database: "logdb"
  connect_timeout: 30
  query_timeout: 30
  max_connections: 10

llm:
  base_url: "http://localhost:11434/v1"
  api_key: "ollama"
  model: "qwen2.5:72b"
  temperature: 0.1

server:
  host: "0.0.0.0"
  port: 8000

executor:
  max_workers: 5
  retry_time_shrink: 0.5

cache:
  ttl_seconds: 300
```

- [ ] **Step 3: 写失败测试**

创建 `backend/tests/test_config.py`：

```python
import pytest
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

def test_settings_loads_clickhouse():
    from config import settings
    assert settings["clickhouse"]["host"] == "10.161.111.100"
    assert settings["clickhouse"]["port"] == 9000

def test_settings_loads_llm():
    from config import settings
    assert "base_url" in settings["llm"]
    assert "model" in settings["llm"]

def test_settings_loads_executor():
    from config import settings
    assert settings["executor"]["max_workers"] == 5
```

- [ ] **Step 4: 运行测试确认失败**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/backend
python -m pytest tests/test_config.py -v
```

期望：`ModuleNotFoundError: No module named 'config'`

- [ ] **Step 5: 实现 config.py**

创建 `backend/config.py`：

```python
import yaml
import os

_config_path = os.path.join(os.path.dirname(__file__), "..", "config", "settings.yaml")

with open(_config_path, "r", encoding="utf-8") as f:
    settings = yaml.safe_load(f)
```

- [ ] **Step 6: 运行测试确认通过**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/backend
python -m pytest tests/test_config.py -v
```

期望：3 个测试全部 PASS

- [ ] **Step 7: Commit**

```bash
git add config/settings.yaml backend/config.py backend/tests/test_config.py requirements.txt
git commit -m "feat: project scaffold with config loading"
```

---

## Task 2: Pydantic 数据模型

**Files:**
- Create: `backend/models/__init__.py`
- Create: `backend/models/schemas.py`

- [ ] **Step 1: 创建 models 目录**

```bash
mkdir -p /Users/daiyutong/PycharmProjects/AIops/backend/models
touch /Users/daiyutong/PycharmProjects/AIops/backend/models/__init__.py
```

- [ ] **Step 2: 创建 schemas.py**

创建 `backend/models/schemas.py`：

```python
from pydantic import BaseModel, Field
from typing import Any, Literal, Optional
from datetime import datetime


class WSIncoming(BaseModel):
    session_id: str
    message: str


class WSMessage(BaseModel):
    type: Literal["clarify", "progress", "result", "error", "done"]
    content: Any
    render: Optional[Literal["echarts", "html", "table", "text"]] = None
    elapsed: Optional[float] = None


class SubTask(BaseModel):
    id: str
    description: str
    tables: list[str]
    time_range_hours: int = 24


class TaskPlan(BaseModel):
    tasks: list[SubTask]
    clarification_needed: bool = False
    clarification_question: Optional[str] = None
    estimated_seconds: int = 10


class SQLTask(BaseModel):
    task_id: str
    sql: str
    description: str


class VizSpec(BaseModel):
    render_type: Literal["echarts", "html"]
    chart_type: Optional[str] = None
    title: str
    x_field: Optional[str] = None
    y_field: Optional[str] = None
    series_field: Optional[str] = None
    insight: str = ""


class ChatMessage(BaseModel):
    id: int
    session_id: str
    role: Literal["user", "assistant"]
    type: str
    content: str
    created_at: datetime


class Session(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 3: 验证模型可正确实例化**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/backend
python -c "
from models.schemas import WSMessage, TaskPlan, SubTask, SQLTask, VizSpec
msg = WSMessage(type='progress', content='2/3 完成', elapsed=5.2)
plan = TaskPlan(tasks=[SubTask(id='t1', description='流量统计', tables=['iplog'])])
print('schemas OK:', msg.type, plan.tasks[0].id)
"
```

期望输出：`schemas OK: progress t1`

- [ ] **Step 4: Commit**

```bash
git add backend/models/
git commit -m "feat: add pydantic schemas"
```

---

## Task 3: ClickHouse 连接层

**Files:**
- Create: `backend/db/__init__.py`
- Create: `backend/db/clickhouse.py`
- Create: `backend/tests/test_clickhouse.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_clickhouse.py`：

```python
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_execute_returns_dataframe():
    from db.clickhouse import execute_query
    import pandas as pd
    df = execute_query("SELECT 1 AS val")
    assert isinstance(df, pd.DataFrame)
    assert df.iloc[0]["val"] == 1


def test_execute_rejects_non_select():
    from db.clickhouse import execute_query, SQLSecurityError
    with pytest.raises(SQLSecurityError):
        execute_query("DROP TABLE sessions")


def test_execute_rejects_insert():
    from db.clickhouse import execute_query, SQLSecurityError
    with pytest.raises(SQLSecurityError):
        execute_query("INSERT INTO sessions VALUES (1)")
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/backend
python -m pytest tests/test_clickhouse.py -v
```

期望：`ModuleNotFoundError`

- [ ] **Step 3: 实现 clickhouse.py**

创建 `backend/db/__init__.py`（空文件），创建 `backend/db/clickhouse.py`：

```python
import re
import pandas as pd
from clickhouse_driver import Client
from config import settings

_cfg = settings["clickhouse"]

_client = Client(
    host=_cfg["host"],
    port=_cfg["port"],
    user=_cfg["user"],
    password=_cfg["password"],
    database=_cfg["database"],
    connect_timeout=_cfg["connect_timeout"],
)

_FORBIDDEN = re.compile(
    r"^\s*(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|RENAME|ATTACH|DETACH)",
    re.IGNORECASE,
)


class SQLSecurityError(Exception):
    pass


def execute_query(sql: str, timeout: int | None = None) -> pd.DataFrame:
    if _FORBIDDEN.match(sql):
        raise SQLSecurityError(f"拒绝执行非SELECT语句: {sql[:60]}")
    t = timeout or _cfg.get("query_timeout", 30)
    rows, columns = _client.execute(
        sql,
        with_column_types=True,
        settings={"max_execution_time": t},
    )
    col_names = [c[0] for c in columns]
    return pd.DataFrame(rows, columns=col_names)
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/backend
python -m pytest tests/test_clickhouse.py -v
```

期望：3 个测试全部 PASS（需能访问 10.161.111.100:9000，否则连接测试会跳过）

- [ ] **Step 5: Commit**

```bash
git add backend/db/ backend/tests/test_clickhouse.py
git commit -m "feat: clickhouse query layer with SQL security guard"
```

---

## Task 4: SQLite 对话存储

**Files:**
- Create: `backend/db/sqlite.py`

- [ ] **Step 1: 实现 sqlite.py**

创建 `backend/db/sqlite.py`：

```python
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

_DB_PATH = Path(__file__).parent.parent.parent / "data" / "aiops.db"
_DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id          TEXT PRIMARY KEY,
                title       TEXT,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS messages (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  TEXT NOT NULL,
                role        TEXT NOT NULL,
                type        TEXT NOT NULL,
                content     TEXT NOT NULL,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );
        """)


def create_session(title: str = "新对话") -> str:
    sid = str(uuid.uuid4())
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO sessions (id, title) VALUES (?, ?)", (sid, title)
        )
    return sid


def save_message(session_id: str, role: str, msg_type: str, content: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO messages (session_id, role, type, content) VALUES (?, ?, ?, ?)",
            (session_id, role, msg_type, content),
        )
        conn.execute(
            "UPDATE sessions SET updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (session_id,),
        )


def get_sessions() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT 50"
        ).fetchall()
    return [dict(r) for r in rows]


def get_session_messages(session_id: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM messages WHERE session_id=? ORDER BY id",
            (session_id,),
        ).fetchall()
    return [dict(r) for r in rows]
```

- [ ] **Step 2: 验证 SQLite 初始化和读写**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/backend
python -c "
from db.sqlite import init_db, create_session, save_message, get_sessions
init_db()
sid = create_session('测试对话')
save_message(sid, 'user', 'text', '分析昨天的流量')
save_message(sid, 'assistant', 'echarts', '{\"title\":\"流量统计\"}')
sessions = get_sessions()
print('sessions:', len(sessions), sessions[0]['title'])
"
```

期望输出：`sessions: 1 测试对话`

- [ ] **Step 3: Commit**

```bash
git add backend/db/sqlite.py
git commit -m "feat: sqlite session and message storage"
```

---

## Task 5: 表结构定义（LLM Context）

**Files:**
- Create: `backend/db/schema.py`

- [ ] **Step 1: 创建 schema.py**

创建 `backend/db/schema.py`：

```python
TABLE_SCHEMA = """
## 可用数据表（ClickHouse logdb）

### sessions — 网络会话记录（最核心，364亿条）
字段：dev_id(UInt16), start(DateTime), end(DateTime), protocol(UInt8, 6=TCP/17=UDP/1=ICMP),
src_ipv4(IPv4), dst_ipv4(IPv4), src_port(UInt16), dst_port(UInt16),
up_bytes(UInt64), down_bytes(UInt64), up_pkts(UInt32), down_pkts(UInt32),
ret_up_pkts(UInt32), ret_down_pkts(UInt32),
wan_name(String), appid(UInt32), domain_name(String), account(String),
src_ISP(String), dst_ISP(String), dst_pos_country(String), dst_pos_province(String),
malc_hit(UInt8), direction(UInt8)
注意：查询必须带 start 时间条件，时间范围>7天需按天分片

### npm — 网络性能监控（375亿条）
字段：start(DateTime), end(DateTime), src_ipv4(IPv4), dst_ipv4(IPv4),
clntdelay(UInt32,μs), svrdelay(UInt32,μs), appdelay(UInt32,μs),
ret_up_pkts(UInt32), ret_down_pkts(UInt32), wan_name(String), malc_hit(UInt8)
注意：查询必须带 start 时间条件

### dns — DNS查询日志（34亿条）
字段：collect_time(DateTime), src_ipv4(IPv4), src_mac(String),
dst_ipv4(IPv4), domain_name(String), account(String)
注意：查询必须带 collect_time 时间条件

### url — HTTP/HTTPS访问日志（26亿条）
字段：collect_time(DateTime), type(String), uri(String), domain_name(String),
src_ipv4(IPv4), dst_ipv4(IPv4), appid(UInt32), account(String)
注意：查询必须带 collect_time 时间条件

### iplog — IP流量汇总（10亿条，按IP聚合，60s间隔）
字段：collect_time(DateTime), interval(UInt32), ipv4(IPv4),
up_bytes(UInt64), down_bytes(UInt64), flowcnt(UInt32), appid(UInt32), account(String)

### wanlog — WAN出口流量统计（119万条，60s间隔）
字段：collect_time(DateTime), interval(UInt32), wan_name(String),
wan_id(UInt32), wan_type(UInt8), in_bps(UInt64), out_bps(UInt64)

### applog — 应用流量汇总（3330万条）
字段：collect_time(DateTime), interval(UInt32), appid(UInt32),
up_bytes(UInt64), down_bytes(UInt64), flowcnt(UInt32)

### event — 应用事件（1.9亿条）
字段：type(String, qqlogin3/weixin3/pop3login3), collect_time(DateTime),
account(String), src_ipv4(IPv4), src_mac(String), app_account(String)

### usrauth — 用户认证记录（14万条）
字段：collect_time(DateTime), account(String), src_ipv4(IPv4),
src_mac(String), logtype(String, login/logoff)

## SQL规则
1. 所有查询必须包含时间条件（sessions/npm用start，其余用collect_time）
2. 只允许SELECT语句
3. 大表（sessions/npm/dns/url）建议加 LIMIT 10000
4. 时间范围超过7天时，建议按天分片查询
"""
```

- [ ] **Step 2: 验证可导入**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/backend
python -c "from db.schema import TABLE_SCHEMA; print(len(TABLE_SCHEMA), 'chars')"
```

期望输出：字符数 > 100

- [ ] **Step 3: Commit**

```bash
git add backend/db/schema.py
git commit -m "feat: table schema definitions for LLM context"
```

---

## Task 6: 并行执行层

**Files:**
- Create: `backend/executor/__init__.py`
- Create: `backend/executor/parallel.py`
- Create: `backend/tests/test_parallel_executor.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_parallel_executor.py`：

```python
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from models.schemas import SQLTask


def test_parallel_executor_runs_multiple_tasks():
    from executor.parallel import ParallelExecutor

    tasks = [
        SQLTask(task_id="t1", sql="SELECT 1 AS v", description="test1"),
        SQLTask(task_id="t2", sql="SELECT 2 AS v", description="test2"),
    ]
    executor = ParallelExecutor(max_workers=2)
    results = executor.run(tasks)
    assert len(results) == 2
    assert results["t1"]["status"] == "success"
    assert results["t2"]["status"] == "success"


def test_parallel_executor_handles_failure():
    from executor.parallel import ParallelExecutor

    tasks = [
        SQLTask(task_id="bad", sql="SELECT * FROM nonexistent_table_xyz", description="bad"),
    ]
    executor = ParallelExecutor(max_workers=1)
    results = executor.run(tasks)
    assert results["bad"]["status"] == "error"
    assert "error" in results["bad"]


def test_parallel_executor_rejects_non_select():
    from executor.parallel import ParallelExecutor
    from db.clickhouse import SQLSecurityError

    tasks = [
        SQLTask(task_id="evil", sql="DROP TABLE sessions", description="evil"),
    ]
    executor = ParallelExecutor(max_workers=1)
    results = executor.run(tasks)
    assert results["evil"]["status"] == "error"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/backend
python -m pytest tests/test_parallel_executor.py -v
```

期望：`ModuleNotFoundError`

- [ ] **Step 3: 实现 parallel.py**

创建 `backend/executor/__init__.py`（空），创建 `backend/executor/parallel.py`：

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Any
import pandas as pd

from models.schemas import SQLTask
from db.clickhouse import execute_query, SQLSecurityError
from config import settings


class ParallelExecutor:
    def __init__(self, max_workers: int | None = None):
        self.max_workers = max_workers or settings["executor"]["max_workers"]
        self.retry_shrink = settings["executor"]["retry_time_shrink"]

    def _run_one(self, task: SQLTask, progress_cb: Callable | None = None) -> dict:
        try:
            df = execute_query(task.sql)
            if progress_cb:
                progress_cb(task.task_id, "success")
            return {"task_id": task.task_id, "status": "success", "df": df, "description": task.description}
        except SQLSecurityError as e:
            if progress_cb:
                progress_cb(task.task_id, "error")
            return {"task_id": task.task_id, "status": "error", "error": str(e), "description": task.description}
        except Exception as e:
            if progress_cb:
                progress_cb(task.task_id, "error")
            return {"task_id": task.task_id, "status": "error", "error": str(e), "description": task.description}

    def run(
        self,
        tasks: list[SQLTask],
        progress_cb: Callable[[str, str], None] | None = None,
    ) -> dict[str, dict]:
        results = {}
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {pool.submit(self._run_one, t, progress_cb): t for t in tasks}
            for future in as_completed(futures):
                result = future.result()
                results[result["task_id"]] = result
        return results
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/backend
python -m pytest tests/test_parallel_executor.py -v
```

期望：3 个测试全部 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/executor/ backend/tests/test_parallel_executor.py
git commit -m "feat: parallel SQL executor with error handling"
```

---

## Task 7: Planner Agent

**Files:**
- Create: `backend/agents/__init__.py`
- Create: `backend/agents/planner.py`
- Create: `backend/tests/test_planner.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_planner.py`：

```python
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_planner_returns_task_plan(monkeypatch):
    from agents.planner import run_planner
    from models.schemas import TaskPlan

    class FakeLLM:
        def invoke(self, messages):
            class Resp:
                content = '{"tasks":[{"id":"t1","description":"统计昨天总流量","tables":["iplog"],"time_range_hours":24}],"clarification_needed":false,"clarification_question":null,"estimated_seconds":5}'
            return Resp()

    result = run_planner("分析昨天的总流量", conversation_history=[], llm=FakeLLM())
    assert isinstance(result, TaskPlan)
    assert len(result.tasks) == 1
    assert result.tasks[0].id == "t1"


def test_planner_returns_clarification(monkeypatch):
    from agents.planner import run_planner
    from models.schemas import TaskPlan

    class FakeLLM:
        def invoke(self, messages):
            class Resp:
                content = '{"tasks":[],"clarification_needed":true,"clarification_question":"请问您想分析哪个时间段？","estimated_seconds":0}'
            return Resp()

    result = run_planner("分析一下", conversation_history=[], llm=FakeLLM())
    assert result.clarification_needed is True
    assert "时间段" in result.clarification_question
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/backend
python -m pytest tests/test_planner.py -v
```

期望：`ModuleNotFoundError`

- [ ] **Step 3: 实现 planner.py**

创建 `backend/agents/__init__.py`（空），创建 `backend/agents/planner.py`：

```python
import json
from langchain_openai import ChatOpenAI
from models.schemas import TaskPlan
from db.schema import TABLE_SCHEMA
from config import settings

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
    conversation_history: list[dict],
    llm=None,
) -> TaskPlan:
    llm = llm or _build_llm()
    messages = [{"role": "system", "content": _SYSTEM_PROMPT}]
    messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_message})

    response = llm.invoke(messages)
    try:
        data = json.loads(response.content)
        return TaskPlan(**data)
    except (json.JSONDecodeError, Exception) as e:
        return TaskPlan(
            tasks=[],
            clarification_needed=True,
            clarification_question="抱歉，我没有理解您的问题，请重新描述一下您想分析什么？",
        )
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/backend
python -m pytest tests/test_planner.py -v
```

期望：2 个测试全部 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/agents/ backend/tests/test_planner.py
git commit -m "feat: planner agent with intent recognition"
```

---

## Task 8: SQL Engineer Agent

**Files:**
- Create: `backend/agents/sql_engineer.py`
- Create: `backend/tests/test_sql_safety.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_sql_safety.py`：

```python
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_sql_engineer_returns_sql_tasks(monkeypatch):
    from agents.sql_engineer import run_sql_engineer
    from models.schemas import SubTask, SQLTask

    class FakeLLM:
        def invoke(self, messages):
            class Resp:
                content = '[{"task_id":"t1","sql":"SELECT ipv4, sum(up_bytes+down_bytes) as total FROM iplog WHERE collect_time >= now()-INTERVAL 1 DAY GROUP BY ipv4 ORDER BY total DESC LIMIT 100","description":"IP流量Top100"}]'
            return Resp()

    tasks = [SubTask(id="t1", description="统计昨天各IP流量", tables=["iplog"], time_range_hours=24)]
    result = run_sql_engineer(tasks, llm=FakeLLM())
    assert len(result) == 1
    assert result[0].task_id == "t1"
    assert "SELECT" in result[0].sql.upper()


def test_sql_engineer_injects_time_condition():
    from agents.sql_engineer import ensure_time_condition
    sql_without_time = "SELECT count(*) FROM sessions"
    result = ensure_time_condition(sql_without_time, "sessions")
    assert "start" in result.lower()


def test_sql_engineer_adds_limit():
    from agents.sql_engineer import ensure_limit
    sql = "SELECT * FROM sessions WHERE start >= now()-INTERVAL 1 DAY"
    result = ensure_limit(sql)
    assert "LIMIT" in result.upper()
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/backend
python -m pytest tests/test_sql_safety.py -v
```

期望：`ModuleNotFoundError`

- [ ] **Step 3: 实现 sql_engineer.py**

创建 `backend/agents/sql_engineer.py`：

```python
import json
import re
from langchain_openai import ChatOpenAI
from models.schemas import SubTask, SQLTask
from db.schema import TABLE_SCHEMA
from config import settings

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


def optimize_sql(sql: str, tables: list[str]) -> str:
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


def run_sql_engineer(tasks: list[SubTask], llm=None) -> list[SQLTask]:
    llm = llm or _build_llm()
    task_desc = "\n".join(
        f"- id={t.id}: {t.description}，涉及表：{', '.join(t.tables)}, 时间范围：{t.time_range_hours}小时"
        for t in tasks
    )
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": f"为以下子任务生成SQL：\n{task_desc}"},
    ]
    response = llm.invoke(messages)
    try:
        data = json.loads(response.content)
        result = []
        task_map = {t.id: t for t in tasks}
        for item in data:
            sql = optimize_sql(item["sql"], task_map.get(item["task_id"], tasks[0]).tables)
            result.append(SQLTask(task_id=item["task_id"], sql=sql, description=item["description"]))
        return result
    except Exception:
        return []
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/backend
python -m pytest tests/test_sql_safety.py -v
```

期望：3 个测试全部 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/agents/sql_engineer.py backend/tests/test_sql_safety.py
git commit -m "feat: sql engineer agent with safety optimization"
```

---

## Task 9: Visualizer Agent

**Files:**
- Create: `backend/agents/visualizer.py`

- [ ] **Step 1: 实现 visualizer.py**

创建 `backend/agents/visualizer.py`：

```python
import json
import re
import hashlib
import pandas as pd
from pathlib import Path
from langchain_openai import ChatOpenAI
from models.schemas import VizSpec
from config import settings

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
        if spec.x_field and spec.y_field:
            series_data = [{"name": str(row[spec.x_field]), "value": row[spec.y_field]} for _, row in df.iterrows()]
        else:
            series_data = []
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
chart.setOption({json.dumps(_build_echarts_option(spec, df), ensure_ascii=False)});
</script>
</body></html>"""
    path = _RENDERS_DIR / session_id / f"{message_id}.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return str(path)


def run_visualizer(
    results: dict[str, dict],
    session_id: str,
    message_id: str,
    llm=None,
) -> list[dict]:
    llm = llm or _build_llm()
    outputs = []

    for task_id, result in results.items():
        if result["status"] != "success":
            outputs.append({"render": "text", "content": f"⚠️ {result['description']} 获取失败：{result.get('error', '未知错误')}"})
            continue

        df: pd.DataFrame = result["df"]
        if df.empty:
            outputs.append({"render": "text", "content": f"📭 {result['description']}：无数据"})
            continue

        summary = _df_summary(df)
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"任务：{result['description']}\n数据结构：{summary}"},
        ]
        response = llm.invoke(messages)
        try:
            spec = VizSpec(**json.loads(response.content))
        except Exception:
            spec = VizSpec(render_type="echarts", chart_type="bar", title=result["description"],
                           x_field=df.columns[0] if len(df.columns) > 0 else None,
                           y_field=df.columns[1] if len(df.columns) > 1 else None,
                           insight="")

        if spec.render_type == "html":
            path = _build_html(spec, df, session_id, f"{message_id}_{task_id}")
            outputs.append({"render": "html", "content": path, "title": spec.title})
        else:
            option = _build_echarts_option(spec, df)
            outputs.append({"render": "echarts", "content": option, "insight": spec.insight})

    return outputs
```

- [ ] **Step 2: 验证可导入**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/backend
python -c "from agents.visualizer import run_visualizer; print('visualizer OK')"
```

期望：`visualizer OK`

- [ ] **Step 3: Commit**

```bash
git add backend/agents/visualizer.py
git commit -m "feat: visualizer agent with echarts and html rendering"
```

---

## Task 10: LangGraph Pipeline

**Files:**
- Create: `backend/graph/__init__.py`
- Create: `backend/graph/pipeline.py`
- Create: `backend/tests/test_pipeline.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_pipeline.py`：

```python
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_pipeline_state_schema():
    from graph.pipeline import PipelineState
    state = PipelineState(
        session_id="test-123",
        user_message="分析流量",
        conversation_history=[],
        task_plan=None,
        sql_tasks=[],
        execution_results={},
        viz_outputs=[],
        clarification_needed=False,
        clarification_question=None,
        error=None,
    )
    assert state["session_id"] == "test-123"


def test_pipeline_graph_compiles():
    from graph.pipeline import build_pipeline
    graph = build_pipeline()
    assert graph is not None
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/backend
python -m pytest tests/test_pipeline.py -v
```

期望：`ModuleNotFoundError`

- [ ] **Step 3: 实现 pipeline.py**

创建 `backend/graph/__init__.py`（空），创建 `backend/graph/pipeline.py`：

```python
from typing import Any, Optional
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END

from models.schemas import TaskPlan, SQLTask
from agents.planner import run_planner
from agents.sql_engineer import run_sql_engineer
from agents.visualizer import run_visualizer
from executor.parallel import ParallelExecutor


class PipelineState(TypedDict):
    session_id: str
    user_message: str
    conversation_history: list[dict]
    task_plan: Optional[TaskPlan]
    sql_tasks: list[SQLTask]
    execution_results: dict[str, Any]
    viz_outputs: list[dict]
    clarification_needed: bool
    clarification_question: Optional[str]
    error: Optional[str]
    progress_cb: Optional[Any]


def node_planner(state: PipelineState) -> PipelineState:
    plan = run_planner(state["user_message"], state["conversation_history"])
    return {
        **state,
        "task_plan": plan,
        "clarification_needed": plan.clarification_needed,
        "clarification_question": plan.clarification_question,
    }


def node_sql_engineer(state: PipelineState) -> PipelineState:
    plan = state["task_plan"]
    sql_tasks = run_sql_engineer(plan.tasks)
    return {**state, "sql_tasks": sql_tasks}


def node_executor(state: PipelineState) -> PipelineState:
    executor = ParallelExecutor()
    results = executor.run(state["sql_tasks"], progress_cb=state.get("progress_cb"))
    return {**state, "execution_results": results}


def node_visualizer(state: PipelineState) -> PipelineState:
    import uuid
    outputs = run_visualizer(
        state["execution_results"],
        session_id=state["session_id"],
        message_id=str(uuid.uuid4()),
    )
    return {**state, "viz_outputs": outputs}


def route_after_planner(state: PipelineState) -> str:
    if state["clarification_needed"]:
        return "end_clarify"
    return "sql_engineer"


def build_pipeline():
    graph = StateGraph(PipelineState)
    graph.add_node("planner", node_planner)
    graph.add_node("sql_engineer", node_sql_engineer)
    graph.add_node("executor", node_executor)
    graph.add_node("visualizer", node_visualizer)

    graph.set_entry_point("planner")
    graph.add_conditional_edges("planner", route_after_planner, {
        "end_clarify": END,
        "sql_engineer": "sql_engineer",
    })
    graph.add_edge("sql_engineer", "executor")
    graph.add_edge("executor", "visualizer")
    graph.add_edge("visualizer", END)

    return graph.compile()
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/backend
python -m pytest tests/test_pipeline.py -v
```

期望：2 个测试全部 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/graph/ backend/tests/test_pipeline.py
git commit -m "feat: langgraph pipeline connecting three agents"
```

---

## Task 11: FastAPI 后端入口和 WebSocket 接口

**Files:**
- Create: `backend/api/__init__.py`
- Create: `backend/api/chat.py`
- Create: `backend/api/health.py`
- Create: `backend/main.py`

- [ ] **Step 1: 实现 health.py**

创建 `backend/api/__init__.py`（空），创建 `backend/api/health.py`：

```python
from fastapi import APIRouter
from db.sqlite import get_sessions, get_session_messages

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/sessions")
def list_sessions():
    return get_sessions()


@router.get("/sessions/{session_id}")
def get_session(session_id: str):
    return get_session_messages(session_id)
```

- [ ] **Step 2: 实现 chat.py**

创建 `backend/api/chat.py`：

```python
import json
import uuid
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from db.sqlite import init_db, create_session, save_message
from graph.pipeline import build_pipeline, PipelineState

router = APIRouter()
_pipeline = None


def get_pipeline():
    global _pipeline
    if _pipeline is None:
        _pipeline = build_pipeline()
    return _pipeline


@router.websocket("/chat")
async def websocket_chat(ws: WebSocket):
    await ws.accept()
    conversation_history = []

    try:
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)
            session_id = data.get("session_id") or create_session()
            message = data["message"]

            save_message(session_id, "user", "text", message)
            conversation_history.append({"role": "user", "content": message})

            async def progress_cb(task_id: str, status: str):
                await ws.send_text(json.dumps({
                    "type": "progress",
                    "content": f"任务 {task_id} {status}",
                }))

            def sync_progress_cb(task_id: str, status: str):
                import asyncio
                pass

            state = PipelineState(
                session_id=session_id,
                user_message=message,
                conversation_history=conversation_history.copy(),
                task_plan=None,
                sql_tasks=[],
                execution_results={},
                viz_outputs=[],
                clarification_needed=False,
                clarification_question=None,
                error=None,
                progress_cb=sync_progress_cb,
            )

            await ws.send_text(json.dumps({"type": "progress", "content": "正在分析您的问题..."}))
            result_state = get_pipeline().invoke(state)

            if result_state["clarification_needed"]:
                q = result_state["clarification_question"]
                await ws.send_text(json.dumps({"type": "clarify", "content": q}))
                save_message(session_id, "assistant", "text", q)
                conversation_history.append({"role": "assistant", "content": q})
                continue

            for output in result_state["viz_outputs"]:
                render = output["render"]
                content = output["content"]
                if render == "html":
                    html_content = open(content, encoding="utf-8").read() if isinstance(content, str) else content
                    save_message(session_id, "assistant", "html", html_content)
                    await ws.send_text(json.dumps({"type": "result", "render": "html", "content": html_content}))
                elif render == "echarts":
                    payload = json.dumps(content, ensure_ascii=False)
                    save_message(session_id, "assistant", "echarts", payload)
                    await ws.send_text(json.dumps({"type": "result", "render": "echarts", "content": content}))
                else:
                    save_message(session_id, "assistant", "text", str(content))
                    await ws.send_text(json.dumps({"type": "result", "render": "text", "content": content}))

            await ws.send_text(json.dumps({"type": "done", "content": "分析完成"}))

    except WebSocketDisconnect:
        pass
```

- [ ] **Step 3: 实现 main.py**

创建 `backend/main.py`：

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from db.sqlite import init_db
from api.chat import router as chat_router
from api.health import router as health_router

app = FastAPI(title="校园网流量分析助手")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()

app.include_router(health_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
```

- [ ] **Step 4: 启动后端验证**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/backend
uvicorn main:app --reload --port 8000
```

访问 `http://localhost:8000/api/v1/health` 期望返回：`{"status":"ok"}`

- [ ] **Step 5: Commit**

```bash
git add backend/api/ backend/main.py
git commit -m "feat: fastapi server with websocket chat endpoint"
```

---

## Task 12: React 前端脚手架

**Files:**
- Create: `frontend/` (Vite React TS 项目)

- [ ] **Step 1: 初始化前端项目**

```bash
cd /Users/daiyutong/PycharmProjects/AIops
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install echarts echarts-for-react
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
```

- [ ] **Step 2: 配置 Tailwind**

编辑 `frontend/tailwind.config.js`：

```js
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: { extend: {} },
  plugins: [],
}
```

编辑 `frontend/src/index.css`，替换为：

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

- [ ] **Step 3: 创建类型定义**

创建 `frontend/src/types.ts`：

```typescript
export type MessageType = "clarify" | "progress" | "result" | "error" | "done" | "user";
export type RenderType = "echarts" | "html" | "table" | "text";

export interface WSMessage {
  type: MessageType;
  content: any;
  render?: RenderType;
  elapsed?: number;
}

export interface ChatMessage {
  id: string;
  type: MessageType;
  content: any;
  render?: RenderType;
  timestamp: number;
}

export interface Session {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/
git commit -m "feat: react frontend scaffold with tailwind and echarts"
```

---

## Task 13: WebSocket Hook

**Files:**
- Create: `frontend/src/hooks/useWebSocket.ts`

- [ ] **Step 1: 实现 useWebSocket.ts**

创建 `frontend/src/hooks/useWebSocket.ts`：

```typescript
import { useCallback, useEffect, useRef, useState } from "react";
import { ChatMessage, WSMessage } from "../types";
import { v4 as uuidv4 } from "uuid";

const WS_URL = "ws://localhost:8000/api/v1/chat";

export function useWebSocket(sessionId: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [connected, setConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);

    ws.onmessage = (event) => {
      const msg: WSMessage = JSON.parse(event.data);
      if (msg.type === "done") {
        setIsLoading(false);
        return;
      }
      setMessages((prev) => [
        ...prev,
        { id: uuidv4(), type: msg.type, content: msg.content, render: msg.render, timestamp: Date.now() },
      ]);
    };

    return () => ws.close();
  }, [sessionId]);

  const sendMessage = useCallback(
    (text: string) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
      setIsLoading(true);
      setMessages((prev) => [
        ...prev,
        { id: uuidv4(), type: "user", content: text, timestamp: Date.now() },
      ]);
      wsRef.current.send(JSON.stringify({ session_id: sessionId, message: text }));
    },
    [sessionId]
  );

  return { messages, connected, isLoading, sendMessage };
}
```

安装 uuid：

```bash
cd /Users/daiyutong/PycharmProjects/AIops/frontend
npm install uuid @types/uuid
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/hooks/
git commit -m "feat: websocket hook for real-time chat"
```

---

## Task 14: 前端组件

**Files:**
- Create: `frontend/src/components/ProgressBar.tsx`
- Create: `frontend/src/components/ChartRenderer.tsx`
- Create: `frontend/src/components/ChatPanel.tsx`
- Create: `frontend/src/components/SessionSidebar.tsx`
- Create: `frontend/src/components/InputBar.tsx`

- [ ] **Step 1: 实现 ProgressBar.tsx**

创建 `frontend/src/components/ProgressBar.tsx`：

```typescript
interface Props {
  content: string;
}

export function ProgressBar({ content }: Props) {
  return (
    <div className="flex items-center gap-2 text-sm text-gray-500 py-1">
      <div className="animate-spin w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full" />
      <span>{content}</span>
    </div>
  );
}
```

- [ ] **Step 2: 实现 ChartRenderer.tsx**

创建 `frontend/src/components/ChartRenderer.tsx`：

```typescript
import ReactECharts from "echarts-for-react";

interface Props {
  render: "echarts" | "html" | "text";
  content: any;
  insight?: string;
}

export function ChartRenderer({ render, content, insight }: Props) {
  if (render === "echarts") {
    return (
      <div className="w-full">
        {insight && <p className="text-sm text-gray-600 mb-2">{insight}</p>}
        <ReactECharts option={content} style={{ height: 350 }} />
      </div>
    );
  }
  if (render === "html") {
    return (
      <iframe
        srcDoc={content}
        className="w-full border rounded"
        style={{ height: 500 }}
        sandbox="allow-scripts"
      />
    );
  }
  return <p className="text-sm text-gray-700 whitespace-pre-wrap">{content}</p>;
}
```

- [ ] **Step 3: 实现 ChatPanel.tsx**

创建 `frontend/src/components/ChatPanel.tsx`：

```typescript
import { ChatMessage } from "../types";
import { ChartRenderer } from "./ChartRenderer";
import { ProgressBar } from "./ProgressBar";

interface Props {
  messages: ChatMessage[];
}

export function ChatPanel({ messages }: Props) {
  return (
    <div className="flex flex-col gap-3 p-4 overflow-y-auto flex-1">
      {messages.map((msg) => {
        if (msg.type === "user") {
          return (
            <div key={msg.id} className="self-end bg-blue-500 text-white rounded-lg px-4 py-2 max-w-lg">
              {msg.content}
            </div>
          );
        }
        if (msg.type === "progress") {
          return <ProgressBar key={msg.id} content={msg.content} />;
        }
        if (msg.type === "clarify") {
          return (
            <div key={msg.id} className="self-start bg-gray-100 rounded-lg px-4 py-2 max-w-lg text-gray-800">
              {msg.content}
            </div>
          );
        }
        if (msg.type === "result") {
          return (
            <div key={msg.id} className="w-full bg-white border rounded-lg p-4 shadow-sm">
              <ChartRenderer render={msg.render!} content={msg.content} />
            </div>
          );
        }
        if (msg.type === "error") {
          return (
            <div key={msg.id} className="text-red-500 text-sm px-4 py-2 bg-red-50 rounded">
              {msg.content}
            </div>
          );
        }
        return null;
      })}
    </div>
  );
}
```

- [ ] **Step 4: 实现 InputBar.tsx**

创建 `frontend/src/components/InputBar.tsx`：

```typescript
import { useState, KeyboardEvent } from "react";

interface Props {
  onSend: (text: string) => void;
  disabled?: boolean;
}

export function InputBar({ onSend, disabled }: Props) {
  const [value, setValue] = useState("");

  const handleSend = () => {
    if (!value.trim()) return;
    onSend(value.trim());
    setValue("");
  };

  const handleKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex gap-2 p-4 border-t bg-white">
      <input
        className="flex-1 border rounded-lg px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-300"
        placeholder="输入分析问题，例如：分析昨天各出口线路的流量分布"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKey}
        disabled={disabled}
      />
      <button
        className="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded-lg text-sm disabled:opacity-50"
        onClick={handleSend}
        disabled={disabled || !value.trim()}
      >
        发送
      </button>
    </div>
  );
}
```

- [ ] **Step 5: 实现 SessionSidebar.tsx**

创建 `frontend/src/components/SessionSidebar.tsx`：

```typescript
import { Session } from "../types";

interface Props {
  sessions: Session[];
  activeId: string;
  onSelect: (id: string) => void;
  onNew: () => void;
}

export function SessionSidebar({ sessions, activeId, onSelect, onNew }: Props) {
  return (
    <div className="w-56 border-r bg-gray-50 flex flex-col">
      <div className="p-3 border-b">
        <button
          className="w-full bg-blue-500 hover:bg-blue-600 text-white text-sm py-2 rounded-lg"
          onClick={onNew}
        >
          + 新对话
        </button>
      </div>
      <div className="flex-1 overflow-y-auto">
        {sessions.map((s) => (
          <div
            key={s.id}
            className={`px-3 py-2 text-sm cursor-pointer hover:bg-gray-100 truncate ${s.id === activeId ? "bg-blue-50 text-blue-600 font-medium" : "text-gray-700"}`}
            onClick={() => onSelect(s.id)}
          >
            {s.title}
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/
git commit -m "feat: chat UI components (panel, chart, progress, input, sidebar)"
```

---

## Task 15: App 根组件组装

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: 实现 App.tsx**

替换 `frontend/src/App.tsx`：

```typescript
import { useState, useEffect } from "react";
import { v4 as uuidv4 } from "uuid";
import { SessionSidebar } from "./components/SessionSidebar";
import { ChatPanel } from "./components/ChatPanel";
import { InputBar } from "./components/InputBar";
import { useWebSocket } from "./hooks/useWebSocket";
import { Session } from "./types";

export default function App() {
  const [sessionId, setSessionId] = useState(() => uuidv4());
  const [sessions, setSessions] = useState<Session[]>([]);
  const { messages, isLoading, sendMessage } = useWebSocket(sessionId);

  useEffect(() => {
    fetch("http://localhost:8000/api/v1/sessions")
      .then((r) => r.json())
      .then(setSessions)
      .catch(() => {});
  }, [sessionId]);

  const handleNew = () => setSessionId(uuidv4());

  return (
    <div className="flex flex-col h-screen bg-white">
      <header className="flex items-center justify-between px-6 py-3 border-b bg-white shadow-sm">
        <h1 className="text-lg font-semibold text-gray-800">校园网流量分析助手</h1>
      </header>
      <div className="flex flex-1 overflow-hidden">
        <SessionSidebar
          sessions={sessions}
          activeId={sessionId}
          onSelect={setSessionId}
          onNew={handleNew}
        />
        <div className="flex flex-col flex-1 overflow-hidden">
          <ChatPanel messages={messages} />
          <InputBar onSend={sendMessage} disabled={isLoading} />
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 启动前端验证**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/frontend
npm run dev
```

在浏览器访问 `http://localhost:5173`，确认页面正常加载，侧边栏和输入框可见。

- [ ] **Step 3: 端到端测试**

确保后端也在运行（Task 11 步骤4），在前端输入：
```
分析今天WAN出口的带宽使用情况
```

确认：
1. 进度消息出现
2. 若需澄清，澄清问题显示
3. 图表或HTML结果正常渲染

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat: assemble root app component with full layout"
```

---

## Task 16: 运行所有测试并验收

- [ ] **Step 1: 运行所有后端测试**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/backend
python -m pytest tests/ -v
```

期望：全部 PASS（连接 ClickHouse 的测试需访问 10.161.111.100:9000）

- [ ] **Step 2: 前端构建验证**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/frontend
npm run build
```

期望：`dist/` 目录生成，无构建错误

- [ ] **Step 3: 最终 commit**

```bash
git add -A
git commit -m "feat: complete campus network traffic analyzer v1"
```
