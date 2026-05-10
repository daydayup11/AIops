# Pipeline 重设计实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 pipeline 前加需求澄清 Agent，让 planner 输出可视化蓝图，visualizer 按蓝图确定性执行，pipeline 末尾加 summarizer 节点生成针对用户问题的结构化分析报告，并通过 SSE 推送规划卡片和摘要。

**Architecture:** 新增 `node_clarifier` 节点作为 pipeline 入口，多轮追问直到需求明确；planner 输出扩展 `viz_blueprint` 字段；visualizer 不再调 LLM，按蓝图渲染；新增 `node_summarizer` 节点在所有图表后生成结构化报告。前端新增 `ClarifyMessage`、`PlanCard`、`SummaryReport` 三个组件。

**Tech Stack:** Python/FastAPI/LangGraph（后端），React/TypeScript/Tailwind（前端），LangChain OpenAI，Pydantic v2

---

## 文件变更清单

| 文件 | 操作 | 职责 |
|------|------|------|
| `backend/models/schemas.py` | 修改 | 新增 `VizBlueprint`、`SummaryReport`，扩展 `TaskPlan`，扩展 `WSMessage` |
| `backend/agents/clarifier.py` | 新增 | 需求澄清 Agent，判断需求明确性，生成追问+选项 |
| `backend/agents/planner.py` | 修改 | prompt 增加 viz_blueprint 输出，解析新 schema |
| `backend/agents/visualizer.py` | 修改 | 按蓝图执行，不调 LLM，保留兜底逻辑 |
| `backend/agents/summarizer.py` | 新增 | 针对用户问题汇总图表生成结构化报告 |
| `backend/graph/pipeline.py` | 修改 | 新增 clarifier/summarizer 节点，扩展 State，新增路由 |
| `backend/api/chat.py` | 修改 | 新增 plan/summary/clarify（带 options）SSE 推送 |
| `backend/tests/test_clarifier.py` | 新增 | clarifier 单元测试 |
| `backend/tests/test_planner.py` | 修改 | 更新测试以覆盖 viz_blueprint |
| `backend/tests/test_visualizer.py` | 新增 | visualizer 按蓝图执行的单元测试 |
| `backend/tests/test_summarizer.py` | 新增 | summarizer 单元测试 |
| `frontend/src/types.ts` | 修改 | 新增 `plan`、`summary` 消息类型及相关接口 |
| `frontend/src/hooks/useWebSocket.ts` | 修改 | 处理 `plan`、`summary` 新消息类型 |
| `frontend/src/components/ClarifyMessage.tsx` | 新增 | 渲染问题+选项按钮+自由输入 |
| `frontend/src/components/PlanCard.tsx` | 新增 | 渲染规划蓝图卡片 |
| `frontend/src/components/SummaryReport.tsx` | 新增 | 渲染结构化分析报告 |
| `frontend/src/components/ChatPanel.tsx` | 修改 | 集成三个新组件 |

---

## Task 1: 扩展 schemas

**Files:**
- Modify: `backend/models/schemas.py`

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/test_schemas.py`：

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

def test_viz_blueprint_fields():
    from models.schemas import VizBlueprint
    bp = VizBlueprint(
        task_id="t1",
        chart_type="bar",
        title="Top10流量",
        x_field="appid",
        y_field="total_bytes",
        insight_hint="应用ID 5 流量最高",
    )
    assert bp.task_id == "t1"
    assert bp.chart_type == "bar"

def test_task_plan_with_blueprint():
    from models.schemas import TaskPlan, SubTask, VizBlueprint
    plan = TaskPlan(
        tasks=[SubTask(id="t1", description="查流量", tables=["sessions"], time_range_hours=24)],
        viz_blueprint=[VizBlueprint(
            task_id="t1", chart_type="bar", title="流量排行",
            x_field="appid", y_field="total_bytes", insight_hint="头部效应明显",
        )],
    )
    assert len(plan.viz_blueprint) == 1
    assert plan.viz_blueprint[0].task_id == "t1"

def test_summary_report_fields():
    from models.schemas import SummaryReport
    report = SummaryReport(
        title="校园网分析报告",
        key_points=["应用5流量最高", "高峰在22点"],
        conclusion="过去24小时应用5主导流量。",
    )
    assert len(report.key_points) == 2
```

- [ ] **Step 2: 运行确认失败**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/backend
python -m pytest tests/test_schemas.py -v
```

预期：`ImportError: cannot import name 'VizBlueprint'`

- [ ] **Step 3: 修改 schemas.py**

```python
# backend/models/schemas.py
from pydantic import BaseModel, Field
from typing import Any, Literal, Optional
from datetime import datetime


class WSIncoming(BaseModel):
    session_id: str
    message: str


class WSMessage(BaseModel):
    type: Literal["clarify", "progress", "result", "plan", "summary", "error", "done"]
    content: Any
    render: Optional[Literal["echarts", "html", "table", "text"]] = None
    elapsed: Optional[float] = None


class SubTask(BaseModel):
    id: str
    description: str
    tables: list[str]
    time_range_hours: int = 24


class VizBlueprint(BaseModel):
    task_id: str
    chart_type: str          # bar / line / pie / scatter / heatmap
    title: str
    x_field: str
    y_field: str
    insight_hint: str        # planner 预期洞察方向，传给 summarizer


class TaskPlan(BaseModel):
    tasks: list[SubTask]
    viz_blueprint: list[VizBlueprint] = Field(default_factory=list)
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


class SummaryReport(BaseModel):
    title: str
    key_points: list[str]    # 3-5 条核心要点
    conclusion: str          # 针对用户问题的结论段落


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

- [ ] **Step 4: 运行确认通过**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/backend
python -m pytest tests/test_schemas.py -v
```

预期：3 tests PASSED

- [ ] **Step 5: 提交**

```bash
git add backend/models/schemas.py backend/tests/test_schemas.py
git commit -m "feat: add VizBlueprint and SummaryReport schemas, extend TaskPlan"
```

---

## Task 2: 新增需求澄清 Agent

**Files:**
- Create: `backend/agents/clarifier.py`
- Create: `backend/tests/test_clarifier.py`

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/test_clarifier.py`：

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_clarifier_returns_continue_when_clear():
    from agents.clarifier import run_clarifier

    class FakeLLM:
        def invoke(self, messages):
            class Resp:
                content = '{"action":"continue"}'
            return Resp()

    result = run_clarifier("分析过去24小时Top10应用流量排行", [], llm=FakeLLM())
    assert result["action"] == "continue"


def test_clarifier_returns_ask_when_vague():
    from agents.clarifier import run_clarifier

    class FakeLLM:
        def invoke(self, messages):
            class Resp:
                content = '{"action":"ask","question":"您想分析哪个时间范围？","options":["最近1小时","最近24小时","最近7天"]}'
            return Resp()

    result = run_clarifier("分析一下流量", [], llm=FakeLLM())
    assert result["action"] == "ask"
    assert "question" in result
    assert len(result["options"]) == 3


def test_clarifier_force_continue_on_keyword():
    from agents.clarifier import run_clarifier

    # 即使 LLM 返回 ask，关键词也应强制 continue
    class FakeLLM:
        def invoke(self, messages):
            class Resp:
                content = '{"action":"ask","question":"时间范围？","options":[]}'
            return Resp()

    result = run_clarifier("开始分析", [], llm=FakeLLM())
    assert result["action"] == "continue"


def test_clarifier_handles_invalid_json():
    from agents.clarifier import run_clarifier

    class FakeLLM:
        def invoke(self, messages):
            class Resp:
                content = "不是JSON"
            return Resp()

    result = run_clarifier("帮我看看网络", [], llm=FakeLLM())
    assert result["action"] == "ask"
    assert "question" in result
```

- [ ] **Step 2: 运行确认失败**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/backend
python -m pytest tests/test_clarifier.py -v
```

预期：`ImportError: cannot import name 'run_clarifier'`

- [ ] **Step 3: 实现 clarifier.py**

```python
# backend/agents/clarifier.py
import json
import logging
from langchain_openai import ChatOpenAI
from config import settings

logger = logging.getLogger(__name__)

_FORCE_CONTINUE_KEYWORDS = {"开始分析", "就这样", "直接查", "不用问了", "跳过", "直接分析"}

_SYSTEM_PROMPT = """你是校园网流量分析助手的需求澄清专家。
判断用户的问题是否已经足够明确，可以直接开始分析。

明确的需求应包含：
1. 时间范围（如"过去24小时"、"最近一周"）
2. 分析维度（如"按应用"、"按用户"、"按时段"）
3. 分析目标（如"排行"、"趋势"、"异常"）

返回严格JSON（不要Markdown代码块）：
- 需求明确：{"action": "continue"}
- 需求不明确：{"action": "ask", "question": "一个具体追问", "options": ["选项1", "选项2", "选项3"]}

规则：
- options 提供 2-4 个，覆盖最常见选择
- 每次只问一个问题，不堆叠问题
- 如果已经追问过，且用户给出了任何回答，倾向于 continue
"""


def _build_llm() -> ChatOpenAI:
    cfg = settings["llm"]
    return ChatOpenAI(
        base_url=cfg["base_url"],
        api_key=cfg["api_key"],
        model=cfg["model"],
        temperature=cfg["temperature"],
    )


def run_clarifier(user_message: str, conversation_history: list, llm=None) -> dict:
    # 强制跳过关键词检查
    for kw in _FORCE_CONTINUE_KEYWORDS:
        if kw in user_message:
            logger.info("clarifier: force continue by keyword %r", kw)
            return {"action": "continue"}

    llm = llm or _build_llm()
    messages = [{"role": "system", "content": _SYSTEM_PROMPT}]
    messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_message})

    logger.info("clarifier: LLM call start  input=%r  history=%d", user_message[:80], len(conversation_history))
    try:
        response = llm.invoke(messages)
    except Exception:
        logger.error("clarifier: LLM call failed", exc_info=True)
        return {
            "action": "ask",
            "question": "您想分析什么内容？请描述时间范围和分析目标。",
            "options": ["最近24小时流量排行", "最近一周趋势", "实时异常检测"],
        }

    logger.debug("clarifier: raw response %r", response.content[:200])
    try:
        result = json.loads(response.content)
        assert result.get("action") in ("continue", "ask")
        logger.info("clarifier: action=%s", result["action"])
        return result
    except Exception:
        logger.warning("clarifier: parse failed, fallback to ask", exc_info=True)
        return {
            "action": "ask",
            "question": "请问您具体想分析什么？",
            "options": ["过去24小时Top应用流量", "用户流量趋势", "网络异常检测", "时段流量分布"],
        }
```

- [ ] **Step 4: 运行确认通过**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/backend
python -m pytest tests/test_clarifier.py -v
```

预期：4 tests PASSED

- [ ] **Step 5: 提交**

```bash
git add backend/agents/clarifier.py backend/tests/test_clarifier.py
git commit -m "feat: add clarifier agent with force-continue keyword support"
```

---

## Task 3: 更新 planner 输出 viz_blueprint

**Files:**
- Modify: `backend/agents/planner.py`
- Modify: `backend/tests/test_planner.py`

- [ ] **Step 1: 更新 test_planner.py 添加 viz_blueprint 测试**

在 `backend/tests/test_planner.py` 末尾追加：

```python
def test_planner_returns_viz_blueprint():
    from agents.planner import run_planner
    from models.schemas import TaskPlan

    class FakeLLM:
        def invoke(self, messages):
            class Resp:
                content = '{"tasks":[{"id":"t1","description":"Top10应用流量","tables":["sessions"],"time_range_hours":24}],"viz_blueprint":[{"task_id":"t1","chart_type":"bar","title":"Top10应用流量排行","x_field":"appid","y_field":"total_bytes","insight_hint":"头部效应明显"}],"clarification_needed":false,"clarification_question":null,"estimated_seconds":5}'
            return Resp()

    result = run_planner("过去24小时Top10应用流量", conversation_history=[], llm=FakeLLM())
    assert isinstance(result, TaskPlan)
    assert len(result.viz_blueprint) == 1
    assert result.viz_blueprint[0].chart_type == "bar"
    assert result.viz_blueprint[0].x_field == "appid"


def test_planner_no_duplicate_blueprints():
    from agents.planner import run_planner

    class FakeLLM:
        def invoke(self, messages):
            class Resp:
                # 两个不同维度的蓝图
                content = '{"tasks":[{"id":"t1","description":"流量排行","tables":["sessions"],"time_range_hours":24},{"id":"t2","description":"时段分布","tables":["sessions"],"time_range_hours":24}],"viz_blueprint":[{"task_id":"t1","chart_type":"bar","title":"Top10应用","x_field":"appid","y_field":"total_bytes","insight_hint":"头部效应"},{"task_id":"t2","chart_type":"line","title":"时段流量","x_field":"hour","y_field":"bytes","insight_hint":"高峰时段"}],"clarification_needed":false,"clarification_question":null,"estimated_seconds":8}'
            return Resp()

    result = run_planner("流量排行和时段分布", conversation_history=[], llm=FakeLLM())
    combos = [(bp.chart_type, bp.x_field, bp.y_field) for bp in result.viz_blueprint]
    assert len(combos) == len(set(combos)), "viz_blueprint 不应有重复图表"
```

- [ ] **Step 2: 运行确认失败**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/backend
python -m pytest tests/test_planner.py::test_planner_returns_viz_blueprint -v
```

预期：FAILED（`viz_blueprint` 字段为空列表）

- [ ] **Step 3: 更新 planner.py 的 prompt 和解析**

将 `backend/agents/planner.py` 中的 `_SYSTEM_PROMPT` 替换为：

```python
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
```

- [ ] **Step 4: 运行确认通过**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/backend
python -m pytest tests/test_planner.py -v
```

预期：5 tests PASSED（原有 3 个 + 新增 2 个）

- [ ] **Step 5: 提交**

```bash
git add backend/agents/planner.py backend/tests/test_planner.py
git commit -m "feat: planner now outputs viz_blueprint alongside tasks"
```

---

## Task 4: 改造 visualizer 按蓝图执行

**Files:**
- Modify: `backend/agents/visualizer.py`
- Create: `backend/tests/test_visualizer.py`

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/test_visualizer.py`：

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pandas as pd


def _make_result(df, description="测试任务"):
    return {"status": "success", "df": df, "description": description}


def test_visualizer_uses_blueprint_no_llm():
    from agents.visualizer import run_visualizer
    from models.schemas import VizBlueprint

    df = pd.DataFrame({"appid": [5, 878, 613], "total_bytes": [1e12, 8e11, 7e11]})
    results = {"t1": _make_result(df, "Top10应用流量")}
    blueprints = [VizBlueprint(
        task_id="t1", chart_type="bar", title="Top10应用流量排行",
        x_field="appid", y_field="total_bytes", insight_hint="头部效应明显",
    )]

    llm_called = []
    class FakeLLM:
        def invoke(self, messages):
            llm_called.append(True)
            class Resp:
                content = '{}'
            return Resp()

    outputs = run_visualizer(results, blueprints=blueprints, session_id="s1", message_id="m1", llm=FakeLLM())
    assert len(llm_called) == 0, "有蓝图时不应调用 LLM"
    assert len(outputs) == 1
    assert outputs[0]["render"] == "echarts"
    assert outputs[0]["insight"] == "头部效应明显"


def test_visualizer_fallback_to_llm_when_no_blueprint():
    from agents.visualizer import run_visualizer

    df = pd.DataFrame({"appid": [5, 878], "total_bytes": [1e12, 8e11]})
    results = {"t1": _make_result(df)}
    blueprints = []  # 没有蓝图，应降级调 LLM

    llm_called = []
    class FakeLLM:
        def invoke(self, messages):
            llm_called.append(True)
            class Resp:
                content = '{"render_type":"echarts","chart_type":"bar","title":"流量","x_field":"appid","y_field":"total_bytes","insight":"头部效应"}'
            return Resp()

    outputs = run_visualizer(results, blueprints=blueprints, session_id="s1", message_id="m1", llm=FakeLLM())
    assert len(llm_called) == 1, "没有蓝图时应降级调用 LLM"
    assert len(outputs) == 1


def test_visualizer_skips_failed_task():
    from agents.visualizer import run_visualizer
    from models.schemas import VizBlueprint

    results = {"t1": {"status": "error", "error": "超时", "description": "查询失败"}}
    blueprints = [VizBlueprint(
        task_id="t1", chart_type="bar", title="X",
        x_field="a", y_field="b", insight_hint="",
    )]
    outputs = run_visualizer(results, blueprints=blueprints, session_id="s1", message_id="m1")
    assert outputs[0]["render"] == "text"
    assert "失败" in outputs[0]["content"]
```

- [ ] **Step 2: 运行确认失败**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/backend
python -m pytest tests/test_visualizer.py -v
```

预期：FAILED（`run_visualizer` 签名不匹配）

- [ ] **Step 3: 修改 visualizer.py**

将 `run_visualizer` 函数签名和实现替换为：

```python
def run_visualizer(
    results: dict,
    blueprints: list,          # list[VizBlueprint]，可为空（降级到 LLM）
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
            # 按蓝图确定性执行，不调 LLM
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
            # 兜底：降级到 LLM 推断
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
```

- [ ] **Step 4: 运行确认通过**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/backend
python -m pytest tests/test_visualizer.py -v
```

预期：3 tests PASSED

- [ ] **Step 5: 提交**

```bash
git add backend/agents/visualizer.py backend/tests/test_visualizer.py
git commit -m "feat: visualizer uses viz_blueprint directly, LLM only as fallback"
```

---

## Task 5: 新增 summarizer Agent

**Files:**
- Create: `backend/agents/summarizer.py`
- Create: `backend/tests/test_summarizer.py`

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/test_summarizer.py`：

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_summarizer_returns_report():
    from agents.summarizer import run_summarizer
    from models.schemas import SummaryReport

    class FakeLLM:
        def invoke(self, messages):
            class Resp:
                content = '{"title":"校园网流量分析报告","key_points":["应用5流量最高，占35%","高峰集中在20-23点"],"conclusion":"过去24小时应用5主导流量，建议关注带宽分配。"}'
            return Resp()

    insights = [{"task_id": "t1", "insight_hint": "头部效应明显", "rows": 10}]
    report = run_summarizer(
        user_message="过去24小时Top10应用流量排行",
        insights=insights,
        llm=FakeLLM(),
    )
    assert isinstance(report, SummaryReport)
    assert len(report.key_points) == 2
    assert "应用5" in report.conclusion


def test_summarizer_handles_invalid_json():
    from agents.summarizer import run_summarizer
    from models.schemas import SummaryReport

    class FakeLLM:
        def invoke(self, messages):
            class Resp:
                content = "不是JSON"
            return Resp()

    report = run_summarizer("查流量", insights=[], llm=FakeLLM())
    assert isinstance(report, SummaryReport)
    assert report.title != ""
```

- [ ] **Step 2: 运行确认失败**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/backend
python -m pytest tests/test_summarizer.py -v
```

预期：`ImportError: cannot import name 'run_summarizer'`

- [ ] **Step 3: 实现 summarizer.py**

```python
# backend/agents/summarizer.py
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
```

- [ ] **Step 4: 运行确认通过**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/backend
python -m pytest tests/test_summarizer.py -v
```

预期：2 tests PASSED

- [ ] **Step 5: 提交**

```bash
git add backend/agents/summarizer.py backend/tests/test_summarizer.py
git commit -m "feat: add summarizer agent for structured analysis reports"
```

---

## Task 6: 更新 pipeline（新增节点 + 扩展 State）

**Files:**
- Modify: `backend/graph/pipeline.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_pipeline.py` 末尾追加（先读现有文件内容，追加不覆盖）：

```python
def test_pipeline_has_clarifier_node():
    from graph.pipeline import build_pipeline
    pipeline = build_pipeline()
    # LangGraph compiled graph 的节点名称在 graph.nodes 里
    node_names = set(pipeline.graph.nodes.keys())
    assert "clarifier" in node_names, f"缺少 clarifier 节点，现有节点: {node_names}"
    assert "summarizer" in node_names, f"缺少 summarizer 节点，现有节点: {node_names}"
```

- [ ] **Step 2: 运行确认失败**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/backend
python -m pytest tests/test_pipeline.py::test_pipeline_has_clarifier_node -v
```

预期：FAILED

- [ ] **Step 3: 重写 pipeline.py**

```python
# backend/graph/pipeline.py
import logging
import time
import uuid
from typing import Any, Callable, Optional
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END

from models.schemas import TaskPlan, SummaryReport
from agents.clarifier import run_clarifier
from agents.planner import run_planner
from agents.sql_engineer import run_sql_engineer
from agents.visualizer import run_visualizer
from agents.summarizer import run_summarizer
from executor.parallel import ParallelExecutor

logger = logging.getLogger(__name__)


class PipelineState(TypedDict):
    session_id: str
    user_message: str
    conversation_history: list
    task_plan: Optional[TaskPlan]
    sql_tasks: list
    execution_results: dict
    viz_outputs: list
    clarification_needed: bool
    clarification_question: Optional[str]
    clarifier_done: bool
    clarifier_question: Optional[str]          # 澄清追问文字
    clarifier_options: list                    # 澄清选项列表
    summary_report: Optional[SummaryReport]
    error: Optional[str]
    progress_cb: Optional[Callable[[str], None]]
    plan_cb: Optional[Callable[[list], None]]  # 推送 plan 卡片


def _emit(state: PipelineState, text: str) -> None:
    cb = state.get("progress_cb")
    if cb:
        cb(text)


def _emit_plan(state: PipelineState, blueprint: list) -> None:
    cb = state.get("plan_cb")
    if cb:
        cb(blueprint)


def node_clarifier(state: PipelineState) -> dict:
    sid = state["session_id"]
    logger.info("[%s] >>> node:clarifier  input=%r", sid, state["user_message"][:80])
    result = run_clarifier(state["user_message"], state["conversation_history"])
    if result["action"] == "continue":
        logger.info("[%s] <<< node:clarifier  action=continue", sid)
        return {"clarifier_done": True, "clarifier_question": None, "clarifier_options": []}
    else:
        logger.info("[%s] <<< node:clarifier  action=ask  question=%r", sid, result.get("question", "")[:60])
        return {
            "clarifier_done": False,
            "clarifier_question": result.get("question", "请描述您的分析需求"),
            "clarifier_options": result.get("options", []),
        }


def node_planner(state: PipelineState) -> dict:
    sid = state["session_id"]
    _emit(state, "🧠 正在理解问题、规划查询任务...")
    logger.info("[%s] >>> node:planner  input=%r", sid, state["user_message"][:120])
    start = time.perf_counter()
    plan = run_planner(state["user_message"], state["conversation_history"])
    elapsed = time.perf_counter() - start
    if not plan.clarification_needed:
        task_ids = [t.id for t in plan.tasks]
        chart_types = [bp.chart_type for bp in plan.viz_blueprint]
        titles = [bp.title for bp in plan.viz_blueprint]
        summary = "、".join(f"{ct}图({t})" for ct, t in zip(chart_types, titles))
        _emit(state, f"📋 规划完成：共 {len(plan.tasks)} 个查询，将展示 {summary}")
        _emit_plan(state, [bp.model_dump() for bp in plan.viz_blueprint])
        logger.info("[%s] <<< node:planner  %.2fs  tasks=%s", sid, elapsed, task_ids)
    return {
        "task_plan": plan,
        "clarification_needed": plan.clarification_needed,
        "clarification_question": plan.clarification_question,
    }


def node_sql_engineer(state: PipelineState) -> dict:
    sid = state["session_id"]
    n = len(state["task_plan"].tasks)
    _emit(state, f"⚙️ 正在生成 {n} 条查询 SQL...")
    logger.info("[%s] >>> node:sql_engineer  tasks=%s", sid, [t.id for t in state["task_plan"].tasks])
    start = time.perf_counter()
    sql_tasks = run_sql_engineer(state["task_plan"].tasks)
    elapsed = time.perf_counter() - start
    _emit(state, f"✅ SQL 生成完成，准备执行 {len(sql_tasks)} 条查询")
    logger.info("[%s] <<< node:sql_engineer  %.2fs  sql_tasks=%d", sid, elapsed, len(sql_tasks))
    return {"sql_tasks": sql_tasks}


def node_executor(state: PipelineState) -> dict:
    sid = state["session_id"]
    n = len(state["sql_tasks"])
    _emit(state, f"🔍 正在并行执行 {n} 条查询...")
    logger.info("[%s] >>> node:executor  sql_tasks=%s", sid, [t.task_id for t in state["sql_tasks"]])
    start = time.perf_counter()

    def task_progress_cb(task_id: str, status: str) -> None:
        icon = "✅" if status == "success" else "❌"
        _emit(state, f"{icon} 查询 {task_id} {status}")

    executor = ParallelExecutor()
    results = executor.run(state["sql_tasks"], progress_cb=task_progress_cb)
    elapsed = time.perf_counter() - start
    ok = sum(1 for r in results.values() if r["status"] == "success")
    fail = len(results) - ok
    _emit(state, f"📊 查询完成：{ok} 成功{'，' + str(fail) + ' 失败' if fail else ''}")
    logger.info("[%s] <<< node:executor  %.2fs  ok=%d fail=%d", sid, elapsed, ok, fail)
    return {"execution_results": results}


def node_visualizer(state: PipelineState) -> dict:
    sid = state["session_id"]
    n = len(state["execution_results"])
    _emit(state, f"🎨 正在生成 {n} 个图表...")
    logger.info("[%s] >>> node:visualizer  results=%d", sid, n)
    start = time.perf_counter()
    blueprints = state["task_plan"].viz_blueprint if state["task_plan"] else []
    outputs = run_visualizer(
        state["execution_results"],
        blueprints=blueprints,
        session_id=sid,
        message_id=str(uuid.uuid4()),
    )
    elapsed = time.perf_counter() - start
    logger.info("[%s] <<< node:visualizer  %.2fs  outputs=%d", sid, elapsed, len(outputs))
    return {"viz_outputs": outputs}


def node_summarizer(state: PipelineState) -> dict:
    sid = state["session_id"]
    _emit(state, "📝 正在生成分析报告...")
    logger.info("[%s] >>> node:summarizer", sid)
    start = time.perf_counter()
    blueprints = state["task_plan"].viz_blueprint if state["task_plan"] else []
    insights = [
        {"task_id": bp.task_id, "insight_hint": bp.insight_hint, "rows": len(state["execution_results"].get(bp.task_id, {}).get("df", []))}
        for bp in blueprints
    ]
    report = run_summarizer(state["user_message"], insights)
    elapsed = time.perf_counter() - start
    logger.info("[%s] <<< node:summarizer  %.2fs  points=%d", sid, elapsed, len(report.key_points))
    return {"summary_report": report}


def route_after_clarifier(state: PipelineState) -> str:
    return "planner" if state["clarifier_done"] else "end_clarify"


def route_after_planner(state: PipelineState) -> str:
    if state["clarification_needed"]:
        return "end_clarify"
    return "sql_engineer"


def build_pipeline():
    graph = StateGraph(PipelineState)
    graph.add_node("clarifier", node_clarifier)
    graph.add_node("planner", node_planner)
    graph.add_node("sql_engineer", node_sql_engineer)
    graph.add_node("executor", node_executor)
    graph.add_node("visualizer", node_visualizer)
    graph.add_node("summarizer", node_summarizer)

    graph.set_entry_point("clarifier")
    graph.add_conditional_edges("clarifier", route_after_clarifier, {
        "end_clarify": END,
        "planner": "planner",
    })
    graph.add_conditional_edges("planner", route_after_planner, {
        "end_clarify": END,
        "sql_engineer": "sql_engineer",
    })
    graph.add_edge("sql_engineer", "executor")
    graph.add_edge("executor", "visualizer")
    graph.add_edge("visualizer", "summarizer")
    graph.add_edge("summarizer", END)

    return graph.compile()
```

- [ ] **Step 4: 运行确认通过**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/backend
python -m pytest tests/test_pipeline.py -v
```

预期：所有 tests PASSED

- [ ] **Step 5: 提交**

```bash
git add backend/graph/pipeline.py
git commit -m "feat: add clarifier and summarizer nodes to pipeline, extend PipelineState"
```

---

## Task 7: 更新 chat.py 推送新消息类型

**Files:**
- Modify: `backend/api/chat.py`

- [ ] **Step 1: 直接修改 chat.py**

将整个 `websocket_chat` 函数中的 `state = PipelineState(...)` 构建和结果处理部分替换：

```python
# backend/api/chat.py
import asyncio
import json
import logging
from functools import partial
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from db.sqlite import create_session, save_message
from graph.pipeline import build_pipeline, PipelineState

logger = logging.getLogger(__name__)
router = APIRouter()
_pipeline = None


def get_pipeline():
    global _pipeline
    if _pipeline is None:
        _pipeline = build_pipeline()
    return _pipeline


async def _send(ws: WebSocket, payload: dict) -> None:
    await ws.send_text(json.dumps(payload, ensure_ascii=False))


@router.websocket("/chat")
async def websocket_chat(ws: WebSocket):
    await ws.accept()
    client = ws.client
    logger.info("WebSocket connected: %s:%s", client.host if client else "?", client.port if client else "?")
    conversation_history = []

    try:
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)
            session_id = data.get("session_id") or create_session()
            message = data["message"]
            logger.info("[%s] message received  len=%d", session_id, len(message))

            save_message(session_id, "user", "text", message)
            conversation_history.append({"role": "user", "content": message})

            loop = asyncio.get_event_loop()

            def progress_cb(text: str) -> None:
                logger.info("[%s] progress: %s", session_id, text)
                asyncio.run_coroutine_threadsafe(
                    _send(ws, {"type": "progress", "content": text}),
                    loop,
                )

            def plan_cb(blueprint: list) -> None:
                logger.info("[%s] plan: %d items", session_id, len(blueprint))
                asyncio.run_coroutine_threadsafe(
                    _send(ws, {"type": "plan", "content": blueprint}),
                    loop,
                )

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
                clarifier_done=False,
                clarifier_question=None,
                clarifier_options=[],
                summary_report=None,
                error=None,
                progress_cb=progress_cb,
                plan_cb=plan_cb,
            )

            logger.info("[%s] pipeline start", session_id)
            try:
                result_state = await loop.run_in_executor(
                    None, partial(get_pipeline().invoke, state)
                )
            except Exception as e:
                logger.error("[%s] pipeline failed: %s", session_id, e, exc_info=True)
                await _send(ws, {"type": "error", "content": str(e)})
                await _send(ws, {"type": "done", "content": ""})
                continue

            # clarifier 追问
            if not result_state.get("clarifier_done", True) and result_state.get("clarifier_question"):
                q = result_state["clarifier_question"]
                options = result_state.get("clarifier_options", [])
                payload = {"type": "clarify", "question": q, "options": options, "allow_free_input": True}
                await _send(ws, payload)
                save_message(session_id, "assistant", "text", q)
                conversation_history.append({"role": "assistant", "content": q})
                logger.info("[%s] clarifier ask sent  question=%r  options=%s", session_id, q[:60], options)
                await _send(ws, {"type": "done", "content": ""})
                continue

            # planner 澄清（兜底，不应常走）
            if result_state["clarification_needed"]:
                q = result_state["clarification_question"]
                await _send(ws, {"type": "clarify", "question": q, "options": [], "allow_free_input": True})
                save_message(session_id, "assistant", "text", q)
                conversation_history.append({"role": "assistant", "content": q})
                logger.info("[%s] planner clarification sent", session_id)
                await _send(ws, {"type": "done", "content": ""})
                continue

            # 图表结果
            for i, output in enumerate(result_state["viz_outputs"]):
                render = output["render"]
                content = output["content"]
                if render == "html":
                    html_content = open(content, encoding="utf-8").read() if isinstance(content, str) else content
                    save_message(session_id, "assistant", "html", html_content)
                    await _send(ws, {"type": "result", "render": "html", "content": html_content})
                    logger.info("[%s] sent output[%d] html", session_id, i)
                elif render == "echarts":
                    save_message(session_id, "assistant", "echarts", json.dumps(content, ensure_ascii=False))
                    await _send(ws, {"type": "result", "render": "echarts", "content": content})
                    logger.info("[%s] sent output[%d] echarts", session_id, i)
                else:
                    save_message(session_id, "assistant", "text", str(content))
                    await _send(ws, {"type": "result", "render": "text", "content": content})

            # 综合报告
            report = result_state.get("summary_report")
            if report:
                report_payload = report.model_dump()
                save_message(session_id, "assistant", "text", report.conclusion)
                await _send(ws, {"type": "summary", "content": report_payload})
                logger.info("[%s] summary sent  title=%r  points=%d", session_id, report.title, len(report.key_points))

            logger.info("[%s] pipeline done  outputs=%d", session_id, len(result_state["viz_outputs"]))
            await _send(ws, {"type": "done", "content": "分析完成"})

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: %s:%s", client.host if client else "?", client.port if client else "?")
    except Exception:
        logger.error("Unexpected WebSocket error", exc_info=True)
        raise
```

- [ ] **Step 2: 运行所有后端测试确认不回归**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/backend
python -m pytest tests/ -v
```

预期：全部 PASSED

- [ ] **Step 3: 提交**

```bash
git add backend/api/chat.py
git commit -m "feat: push plan/summary/clarify-with-options via websocket"
```

---

## Task 8: 前端类型和 useWebSocket 更新

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/hooks/useWebSocket.ts`

- [ ] **Step 1: 更新 types.ts**

```typescript
// frontend/src/types.ts
export type MessageType = "clarify" | "progress" | "result" | "plan" | "summary" | "error" | "done" | "user";
export type RenderType = "echarts" | "html" | "table" | "text";

export interface WSMessage {
  type: MessageType;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  content?: any;
  render?: RenderType;
  elapsed?: number;
  // clarify 专用字段
  question?: string;
  options?: string[];
  allow_free_input?: boolean;
}

export interface ChatMessage {
  id: string;
  type: MessageType;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  content: any;
  render?: RenderType;
  timestamp: number;
  // clarify 专用
  question?: string;
  options?: string[];
}

export interface VizBlueprintItem {
  task_id: string;
  chart_type: string;
  title: string;
  x_field: string;
  y_field: string;
  insight_hint: string;
}

export interface SummaryReportData {
  title: string;
  key_points: string[];
  conclusion: string;
}

export interface Session {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}
```

- [ ] **Step 2: 更新 useWebSocket.ts 处理新消息类型**

```typescript
// frontend/src/hooks/useWebSocket.ts
import { useCallback, useEffect, useRef, useState } from "react";
import type { ChatMessage, WSMessage } from "../types";
import { v4 as uuidv4 } from "uuid";

const WS_URL = "ws://localhost:8000/api/v1/chat";
const PROGRESS_BUBBLE_ID = "__progress__";

export function useWebSocket(sessionId: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [connected, setConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let cancelled = false;
    const ws = new WebSocket(WS_URL);

    ws.onopen = () => {
      if (cancelled) { ws.close(); return; }
      wsRef.current = ws;
      setConnected(true);
    };
    ws.onclose = () => {
      if (!cancelled) setConnected(false);
    };
    ws.onmessage = (event) => {
      if (cancelled) return;
      const msg: WSMessage = JSON.parse(event.data);

      if (msg.type === "done") {
        setMessages((prev) => prev.filter((m) => m.id !== PROGRESS_BUBBLE_ID));
        setIsLoading(false);
        return;
      }

      if (msg.type === "progress") {
        setMessages((prev) => {
          const exists = prev.some((m) => m.id === PROGRESS_BUBBLE_ID);
          const bubble: ChatMessage = {
            id: PROGRESS_BUBBLE_ID,
            type: "progress",
            content: msg.content,
            timestamp: Date.now(),
          };
          return exists
            ? prev.map((m) => (m.id === PROGRESS_BUBBLE_ID ? bubble : m))
            : [...prev, bubble];
        });
        return;
      }

      if (msg.type === "clarify") {
        setMessages((prev) => prev.filter((m) => m.id !== PROGRESS_BUBBLE_ID));
        setIsLoading(false);
        setMessages((prev) => [
          ...prev,
          {
            id: uuidv4(),
            type: "clarify",
            content: msg.question ?? msg.content,
            question: msg.question,
            options: msg.options ?? [],
            timestamp: Date.now(),
          },
        ]);
        return;
      }

      if (msg.type === "error") {
        setMessages((prev) => prev.filter((m) => m.id !== PROGRESS_BUBBLE_ID));
        setIsLoading(false);
      }

      // plan / summary / result — 通用处理
      setMessages((prev) => [
        ...prev,
        {
          id: uuidv4(),
          type: msg.type,
          content: msg.content,
          render: msg.render,
          timestamp: Date.now(),
        },
      ]);
    };

    return () => {
      cancelled = true;
      ws.onopen = null;
      ws.onclose = null;
      ws.onmessage = null;
      ws.close();
    };
  }, [sessionId]);

  const sendMessage = useCallback(
    (text: string) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
      setIsLoading(true);
      // 禁用所有 clarify 消息的选项按钮
      setMessages((prev) =>
        prev.map((m) =>
          m.type === "clarify" ? { ...m, options: [] } : m
        )
      );
      setMessages((prev) => [
        ...prev,
        { id: uuidv4(), type: "user", content: text, timestamp: Date.now() },
      ]);
      wsRef.current.send(
        JSON.stringify({ session_id: sessionId, message: text })
      );
    },
    [sessionId]
  );

  return { messages, connected, isLoading, sendMessage };
}
```

- [ ] **Step 3: 运行 TypeScript 类型检查**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/frontend
npx tsc --noEmit
```

预期：无类型错误

- [ ] **Step 4: 提交**

```bash
git add frontend/src/types.ts frontend/src/hooks/useWebSocket.ts
git commit -m "feat: add plan/summary/clarify-options types and websocket handling"
```

---

## Task 9: 新增前端组件

**Files:**
- Create: `frontend/src/components/ClarifyMessage.tsx`
- Create: `frontend/src/components/PlanCard.tsx`
- Create: `frontend/src/components/SummaryReport.tsx`

- [ ] **Step 1: 新建 ClarifyMessage.tsx**

```tsx
// frontend/src/components/ClarifyMessage.tsx
interface Props {
  question: string;
  options: string[];
  onSelect: (text: string) => void;
}

export function ClarifyMessage({ question, options, onSelect }: Props) {
  return (
    <div className="flex justify-start">
      <div className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-2xl rounded-bl-sm px-4 py-3 max-w-lg shadow-sm">
        <p className="text-sm text-[var(--color-foreground)] leading-relaxed mb-2">{question}</p>
        {options.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {options.map((opt) => (
              <button
                key={opt}
                onClick={() => onSelect(opt)}
                disabled={options.length === 0}
                className="text-xs px-3 py-1.5 rounded-full border border-[var(--color-primary)] text-[var(--color-primary)] hover:bg-[var(--color-primary)] hover:text-[var(--color-primary-foreground)] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {opt}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 新建 PlanCard.tsx**

```tsx
// frontend/src/components/PlanCard.tsx
import type { VizBlueprintItem } from "../types";

const CHART_ICON: Record<string, string> = {
  bar: "📊",
  line: "📈",
  pie: "🥧",
  scatter: "✦",
  heatmap: "🗺",
};

interface Props {
  items: VizBlueprintItem[];
}

export function PlanCard({ items }: Props) {
  return (
    <div className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl px-4 py-3 shadow-sm max-w-lg">
      <p className="text-xs text-[var(--color-muted-foreground)] mb-2 font-medium">📋 分析规划</p>
      <ul className="space-y-1.5">
        {items.map((item) => (
          <li key={item.task_id} className="flex items-center gap-2 text-sm text-[var(--color-foreground)]">
            <span>{CHART_ICON[item.chart_type] ?? "📉"}</span>
            <span className="font-medium">{item.title}</span>
            <span className="text-xs text-[var(--color-muted-foreground)]">({item.chart_type})</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 3: 新建 SummaryReport.tsx**

```tsx
// frontend/src/components/SummaryReport.tsx
import type { SummaryReportData } from "../types";

interface Props {
  report: SummaryReportData;
}

export function SummaryReport({ report }: Props) {
  return (
    <div className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl px-5 py-4 shadow-sm">
      <h3 className="text-sm font-semibold text-[var(--color-foreground)] mb-3">📝 {report.title}</h3>
      {report.key_points.length > 0 && (
        <ul className="space-y-1 mb-3">
          {report.key_points.map((point, i) => (
            <li key={i} className="flex items-start gap-2 text-sm text-[var(--color-foreground)]">
              <span className="text-[var(--color-primary)] mt-0.5">•</span>
              <span>{point}</span>
            </li>
          ))}
        </ul>
      )}
      <p className="text-sm text-[var(--color-muted-foreground)] leading-relaxed border-t border-[var(--color-border)] pt-3">
        {report.conclusion}
      </p>
    </div>
  );
}
```

- [ ] **Step 4: 运行类型检查**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/frontend
npx tsc --noEmit
```

预期：无错误

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/ClarifyMessage.tsx frontend/src/components/PlanCard.tsx frontend/src/components/SummaryReport.tsx
git commit -m "feat: add ClarifyMessage, PlanCard, SummaryReport components"
```

---

## Task 10: 更新 ChatPanel 集成新组件

**Files:**
- Modify: `frontend/src/components/ChatPanel.tsx`

- [ ] **Step 1: 重写 ChatPanel.tsx**

```tsx
// frontend/src/components/ChatPanel.tsx
import { useEffect, useRef } from "react";
import type { ChatMessage, VizBlueprintItem, SummaryReportData } from "../types";
import { ChartRenderer } from "./ChartRenderer";
import { ProgressBar } from "./ProgressBar";
import { ClarifyMessage } from "./ClarifyMessage";
import { PlanCard } from "./PlanCard";
import { SummaryReport } from "./SummaryReport";

interface Props {
  messages: ChatMessage[];
  onSend: (text: string) => void;
}

export function ChatPanel({ messages, onSend }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="flex flex-col gap-4 p-5 overflow-y-auto flex-1 bg-[var(--color-background)]">
      {messages.map((msg) => {
        if (msg.type === "user") {
          return (
            <div key={msg.id} className="flex justify-end">
              <div className="bg-[var(--color-primary)] text-[var(--color-primary-foreground)] rounded-2xl rounded-br-sm px-4 py-2.5 max-w-lg text-sm leading-relaxed shadow-sm">
                {msg.content}
              </div>
            </div>
          );
        }
        if (msg.type === "progress") {
          return <ProgressBar key={msg.id} content={msg.content} />;
        }
        if (msg.type === "clarify") {
          return (
            <ClarifyMessage
              key={msg.id}
              question={msg.question ?? msg.content}
              options={msg.options ?? []}
              onSelect={onSend}
            />
          );
        }
        if (msg.type === "plan") {
          return (
            <div key={msg.id} className="flex justify-start">
              <PlanCard items={msg.content as VizBlueprintItem[]} />
            </div>
          );
        }
        if (msg.type === "result") {
          return (
            <div
              key={msg.id}
              className="w-full bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl p-5 shadow-md"
            >
              <ChartRenderer render={msg.render!} content={msg.content} />
            </div>
          );
        }
        if (msg.type === "summary") {
          return (
            <div key={msg.id} className="w-full">
              <SummaryReport report={msg.content as SummaryReportData} />
            </div>
          );
        }
        if (msg.type === "error") {
          return (
            <div
              key={msg.id}
              className="text-[var(--color-destructive)] text-sm px-4 py-2.5 bg-[var(--color-destructive)]/10 border border-[var(--color-destructive)]/20 rounded-lg"
            >
              {msg.content}
            </div>
          );
        }
        return null;
      })}
      <div ref={bottomRef} />
    </div>
  );
}
```

- [ ] **Step 2: 找到 ChatPanel 的调用处，传入 onSend prop**

```bash
grep -rn "ChatPanel" /Users/daiyutong/PycharmProjects/AIops/frontend/src/
```

找到调用处（通常在 `App.tsx`），确认传入 `onSend={sendMessage}`。

- [ ] **Step 3: 运行类型检查**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/frontend
npx tsc --noEmit
```

预期：无类型错误

- [ ] **Step 4: 提交**

```bash
git add frontend/src/components/ChatPanel.tsx
git commit -m "feat: integrate ClarifyMessage, PlanCard, SummaryReport into ChatPanel"
```

---

## Task 11: 端到端验证

- [ ] **Step 1: 启动后端**

```bash
cd /Users/daiyutong/PycharmProjects/AIops
python backend/main.py
```

- [ ] **Step 2: 启动前端**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/frontend
npm run dev
```

- [ ] **Step 3: 验证需求澄清流程**

打开浏览器，发送模糊消息："帮我分析一下"

预期：
- 返回 `clarify` 消息，显示追问+选项按钮
- 点击选项按钮后，按钮禁用，发送选项文字

- [ ] **Step 4: 验证完整分析流程**

发送具体消息："过去24小时Top10应用流量排行"

预期顺序：
1. progress 消息（规划中）
2. plan 卡片（展示规划蓝图）
3. progress 消息（SQL 生成 / 查询执行）
4. result 图表（非重复）
5. summary 报告（标题 + 要点 + 结论）

- [ ] **Step 5: 验证强制跳过**

发送："开始分析"

预期：不触发澄清，直接进入规划。

- [ ] **Step 6: 运行全部后端测试**

```bash
cd /Users/daiyutong/PycharmProjects/AIops/backend
python -m pytest tests/ -v
```

预期：全部 PASSED
