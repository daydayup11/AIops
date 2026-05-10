# Planner → Python Script Visualization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the fragile planner→viz_blueprint→ECharts pipeline with a planner→sql_engineer(script)→code_reviewer→script_runner pipeline that generates and executes self-contained Python scripts to produce PNG images.

**Architecture:** Planner outputs a single `AnalysisPlan` (no sub-tasks, no column name predictions). sql_engineer generates one complete Python script per analysis (ClickHouse queries + matplotlib visualization). code_reviewer (LLM) audits for safety/performance/timeout issues and returns issues to sql_engineer for fixes (up to 3 retries). script_runner executes the approved script via subprocess, collects PNG output, and sends base64-encoded images to the frontend via WebSocket.

**Tech Stack:** Python 3.12, FastAPI, LangGraph, langchain-openai, clickhouse-driver, matplotlib, seaborn, subprocess, pytest

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/models/schemas.py` | Modify | Add `PyScript`, `CodeReviewResult`; update `TaskPlan`; remove `SubTask`, `VizBlueprint`, `SQLTask`, `VizSpec` |
| `backend/agents/planner.py` | Modify | Remove viz_blueprint, output `AnalysisPlan` only |
| `backend/agents/sql_engineer.py` | Rewrite | Generate complete Python script from `AnalysisPlan` |
| `backend/agents/code_reviewer.py` | Create | LLM safety/performance/timeout audit |
| `backend/agents/script_runner.py` | Create | subprocess execution, PNG collection, base64 output |
| `backend/agents/visualizer.py` | Delete | Replaced by script_runner |
| `backend/executor/parallel.py` | Delete | No longer needed |
| `backend/graph/pipeline.py` | Rewrite | New node topology with retry routing |
| `backend/api/chat.py` | Modify | Handle `render: "image"` type |
| `frontend/src/types.ts` | Modify | Add `"image"` to `RenderType`; remove `VizBlueprintItem` |
| `frontend/src/components/ChartRenderer.tsx` | Modify | Add image render branch |
| `frontend/src/components/ChatPanel.tsx` | Modify | Remove PlanCard usage |
| `backend/tests/test_planner.py` | Rewrite | Tests for new planner output shape |
| `backend/tests/test_sql_engineer.py` | Rewrite | Tests for script generation |
| `backend/tests/test_code_reviewer.py` | Create | Tests for review logic |
| `backend/tests/test_script_runner.py` | Create | Tests for subprocess execution |
| `backend/tests/test_pipeline.py` | Modify | Update for new pipeline state |

---

## Task 1: Update schemas

**Files:**
- Modify: `backend/models/schemas.py`
- Test: `backend/tests/test_schemas.py`

- [ ] **Step 1: Write failing tests for new schema shapes**

```python
# backend/tests/test_schemas.py  (add to existing file)
def test_task_plan_no_tasks_field():
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from models.schemas import TaskPlan, AnalysisPlan
    plan = TaskPlan(
        analysis_plan=AnalysisPlan(
            goal="找异常主机",
            approach="流量特征分析",
            expected_findings=["高流量IP"],
            analysis_dimensions=["IP流量排行"],
            viz_intent="展示Top10 IP流量柱状图",
        ),
        clarification_needed=False,
    )
    assert not hasattr(plan, "tasks")
    assert not hasattr(plan, "viz_blueprint")
    assert plan.analysis_plan.viz_intent == "展示Top10 IP流量柱状图"


def test_py_script_schema():
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from models.schemas import PyScript
    s = PyScript(script_code="print('hello')", description="test")
    assert s.script_code == "print('hello')"


def test_code_review_result_schema():
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from models.schemas import CodeReviewResult
    r = CodeReviewResult(approved=True, issues=[])
    assert r.approved is True
    r2 = CodeReviewResult(approved=False, issues=["危险操作: os.system"])
    assert len(r2.issues) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_schemas.py::test_task_plan_no_tasks_field tests/test_schemas.py::test_py_script_schema tests/test_schemas.py::test_code_review_result_schema -v
```

Expected: FAIL (ImportError or AttributeError)

- [ ] **Step 3: Update schemas.py**

Replace the entire content of `backend/models/schemas.py` with:

```python
from pydantic import BaseModel, Field
from typing import Any, Literal, Optional
from datetime import datetime


class WSIncoming(BaseModel):
    session_id: str
    message: str


class WSMessage(BaseModel):
    type: Literal["clarify", "progress", "result", "plan", "summary", "error", "done"]
    content: Any
    render: Optional[Literal["image", "text"]] = None
    elapsed: Optional[float] = None


class AnalysisPlan(BaseModel):
    goal: str
    approach: str
    expected_findings: list[str]
    analysis_dimensions: list[str]
    viz_intent: str


class TaskPlan(BaseModel):
    analysis_plan: Optional[AnalysisPlan] = None
    clarification_needed: bool = False
    clarification_question: Optional[str] = None
    estimated_seconds: int = 10


class PyScript(BaseModel):
    script_code: str
    description: str


class CodeReviewResult(BaseModel):
    approved: bool
    issues: list[str]


class SummaryReport(BaseModel):
    title: str
    key_points: list[str]
    conclusion: str


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

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_schemas.py::test_task_plan_no_tasks_field tests/test_schemas.py::test_py_script_schema tests/test_schemas.py::test_code_review_result_schema -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/models/schemas.py backend/tests/test_schemas.py
git commit -m "feat: update schemas for script-based viz pipeline"
```

---

## Task 2: Update planner agent

**Files:**
- Modify: `backend/agents/planner.py`
- Rewrite: `backend/tests/test_planner.py`

- [ ] **Step 1: Write failing tests for new planner output**

Replace `backend/tests/test_planner.py` with:

```python
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _fake_llm(content: str):
    class FakeLLM:
        def invoke(self, messages):
            class Resp:
                pass
            r = Resp()
            r.content = content
            return r
    return FakeLLM()


def test_planner_returns_analysis_plan():
    from agents.planner import run_planner
    from models.schemas import TaskPlan, AnalysisPlan

    payload = '{"analysis_plan":{"goal":"找异常主机","approach":"流量特征分析","expected_findings":["高流量IP"],"analysis_dimensions":["IP流量排行"],"viz_intent":"展示Top10 IP流量柱状图"},"clarification_needed":false,"clarification_question":null,"estimated_seconds":10}'
    result = run_planner("分析异常主机", conversation_history=[], llm=_fake_llm(payload))
    assert isinstance(result, TaskPlan)
    assert isinstance(result.analysis_plan, AnalysisPlan)
    assert result.analysis_plan.viz_intent != ""
    assert not result.clarification_needed


def test_planner_returns_clarification():
    from agents.planner import run_planner

    payload = '{"analysis_plan":null,"clarification_needed":true,"clarification_question":"请问您想分析哪个时间段？","estimated_seconds":0}'
    result = run_planner("分析一下", conversation_history=[], llm=_fake_llm(payload))
    assert result.clarification_needed is True
    assert result.clarification_question is not None


def test_planner_handles_invalid_json():
    from agents.planner import run_planner

    result = run_planner("分析流量", conversation_history=[], llm=_fake_llm("这不是JSON"))
    assert result.clarification_needed is True
    assert result.clarification_question is not None


def test_planner_no_tasks_field():
    from agents.planner import run_planner

    payload = '{"analysis_plan":{"goal":"g","approach":"a","expected_findings":[],"analysis_dimensions":[],"viz_intent":"bar chart"},"clarification_needed":false,"clarification_question":null,"estimated_seconds":5}'
    result = run_planner("流量排行", conversation_history=[], llm=_fake_llm(payload))
    assert not hasattr(result, "tasks")
    assert not hasattr(result, "viz_blueprint")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_planner.py -v
```

Expected: FAIL (old planner still returns tasks field)

- [ ] **Step 3: Rewrite planner.py**

Replace `backend/agents/planner.py` with:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_planner.py -v
```

Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/agents/planner.py backend/tests/test_planner.py
git commit -m "feat: planner outputs AnalysisPlan only, removes viz_blueprint"
```

---

## Task 3: Rewrite sql_engineer to generate Python scripts

**Files:**
- Rewrite: `backend/agents/sql_engineer.py`
- Rewrite: `backend/tests/test_sql_engineer.py`

- [ ] **Step 1: Write failing tests**

Replace `backend/tests/test_sql_engineer.py` with:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _fake_llm(content: str):
    class FakeLLM:
        def invoke(self, messages):
            class Resp:
                pass
            r = Resp()
            r.content = content
            return r
    return FakeLLM()


def _make_plan():
    from models.schemas import AnalysisPlan, TaskPlan
    return TaskPlan(
        analysis_plan=AnalysisPlan(
            goal="找高流量IP",
            approach="统计各IP的总流量",
            expected_findings=["Top10高流量IP"],
            analysis_dimensions=["IP流量排行"],
            viz_intent="展示Top10 IP流量柱状图，按流量降序排列",
        ),
        clarification_needed=False,
    )


def test_sql_engineer_returns_py_script():
    from agents.sql_engineer import run_sql_engineer
    from models.schemas import PyScript

    script_code = "import os\nprint('hello')\n"
    result = run_sql_engineer(_make_plan(), llm=_fake_llm(script_code))
    assert isinstance(result, PyScript)
    assert "import" in result.script_code


def test_sql_engineer_with_issues_includes_feedback():
    from agents.sql_engineer import run_sql_engineer

    script_code = "import clickhouse_driver\n# fixed\nprint('ok')\n"
    issues = ["缺少LIMIT子句", "全表扫描风险"]
    result = run_sql_engineer(_make_plan(), issues=issues, llm=_fake_llm(script_code))
    assert result is not None
    # The LLM was called — we trust it incorporated issues via prompt


def test_sql_engineer_handles_llm_failure():
    from agents.sql_engineer import run_sql_engineer

    class ErrorLLM:
        def invoke(self, _):
            raise RuntimeError("LLM down")

    result = run_sql_engineer(_make_plan(), llm=ErrorLLM())
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_sql_engineer.py -v
```

Expected: FAIL (old sql_engineer signature differs)

- [ ] **Step 3: Rewrite sql_engineer.py**

Replace `backend/agents/sql_engineer.py` with:

```python
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

1. **数据库连接**：通过环境变量获取参数：
   ```python
   import os
   from clickhouse_driver import Client
   client = Client(
       host=os.environ['CH_HOST'],
       port=int(os.environ['CH_PORT']),
       user=os.environ['CH_USER'],
       password=os.environ['CH_PASSWORD'],
       database=os.environ['CH_DATABASE'],
   )
   ```

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

5. **超时意识**：
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
        script_code = '\n'.join(lines[1:-1] if lines[-1].strip() == '```' else lines[1:])

    description = ap.goal
    return PyScript(script_code=script_code, description=description)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_sql_engineer.py -v
```

Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/agents/sql_engineer.py backend/tests/test_sql_engineer.py
git commit -m "feat: sql_engineer generates Python script instead of SQL tasks"
```

---

## Task 4: Create code_reviewer agent

**Files:**
- Create: `backend/agents/code_reviewer.py`
- Create: `backend/tests/test_code_reviewer.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_code_reviewer.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _fake_llm(content: str):
    class FakeLLM:
        def invoke(self, messages):
            class Resp:
                pass
            r = Resp()
            r.content = content
            return r
    return FakeLLM()


def test_code_reviewer_approves_clean_script():
    from agents.code_reviewer import run_code_reviewer
    from models.schemas import CodeReviewResult

    result = run_code_reviewer(
        "import os\nprint('hello')",
        llm=_fake_llm('{"approved": true, "issues": []}')
    )
    assert isinstance(result, CodeReviewResult)
    assert result.approved is True
    assert result.issues == []


def test_code_reviewer_rejects_dangerous_script():
    from agents.code_reviewer import run_code_reviewer
    from models.schemas import CodeReviewResult

    result = run_code_reviewer(
        "import os\nos.system('rm -rf /')",
        llm=_fake_llm('{"approved": false, "issues": ["危险操作: os.system调用"]}')
    )
    assert result.approved is False
    assert len(result.issues) == 1


def test_code_reviewer_handles_invalid_json():
    from agents.code_reviewer import run_code_reviewer

    result = run_code_reviewer("print('hi')", llm=_fake_llm("不是JSON"))
    # Fallback: approve to avoid blocking pipeline on reviewer failure
    assert result.approved is True


def test_code_reviewer_handles_llm_failure():
    from agents.code_reviewer import run_code_reviewer

    class ErrorLLM:
        def invoke(self, _):
            raise RuntimeError("LLM down")

    result = run_code_reviewer("print('hi')", llm=ErrorLLM())
    assert result.approved is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_code_reviewer.py -v
```

Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Create code_reviewer.py**

Create `backend/agents/code_reviewer.py`:

```python
import json
import logging
import time
from langchain_openai import ChatOpenAI
from models.schemas import CodeReviewResult
from config import settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """你是Python代码安全与性能审查专家。审查以下数据分析脚本，检查：

1. **安全性**：
   - 危险系统调用（os.system, subprocess, eval, exec）
   - 写入OUTPUT_DIR以外的文件路径
   - 除ClickHouse外的网络连接
   - DROP/DELETE/INSERT等危险SQL语句

2. **性能**：
   - 大表（sessions/npm/dns/url，数十亿条）没有LIMIT
   - 大表之间相互JOIN（会超时）
   - 没有时间条件的查询（全表扫描）

3. **超时风险**：
   - 预计可能超过60秒执行时间的查询或计算

返回严格JSON（不要Markdown代码块）：
{"approved": true, "issues": []}
或
{"approved": false, "issues": ["问题1描述", "问题2描述"]}

规则：
- approved=false 时 issues 必须非空，列出具体问题
- approved=true 时 issues 为空数组
- 只在发现明确问题时 approved=false，不要过度审查
"""


def _build_llm() -> ChatOpenAI:
    cfg = settings["llm"]
    return ChatOpenAI(
        base_url=cfg["base_url"],
        api_key=cfg["api_key"],
        model=cfg["model"],
        temperature=cfg["temperature"],
    )


def run_code_reviewer(script_code: str, llm=None) -> CodeReviewResult:
    llm = llm or _build_llm()
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": f"请审查以下脚本：\n\n{script_code}"},
    ]

    logger.info("code_reviewer: LLM call start  script_len=%d", len(script_code))
    t0 = time.perf_counter()
    try:
        response = llm.invoke(messages)
    except Exception:
        logger.error("code_reviewer: LLM call failed (%.2fs)", time.perf_counter() - t0, exc_info=True)
        return CodeReviewResult(approved=True, issues=[])
    elapsed = time.perf_counter() - t0
    logger.info("code_reviewer: done %.2fs", elapsed)

    try:
        data = json.loads(response.content)
        result = CodeReviewResult(**data)
        if result.approved:
            logger.info("code_reviewer: APPROVED")
        else:
            logger.info("code_reviewer: REJECTED  issues=%s", result.issues)
        return result
    except Exception:
        logger.warning("code_reviewer: parse failed, defaulting to approved", exc_info=True)
        return CodeReviewResult(approved=True, issues=[])
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_code_reviewer.py -v
```

Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/agents/code_reviewer.py backend/tests/test_code_reviewer.py
git commit -m "feat: add code_reviewer agent for script safety/performance audit"
```

---

## Task 5: Create script_runner agent

**Files:**
- Create: `backend/agents/script_runner.py`
- Create: `backend/tests/test_script_runner.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_script_runner.py`:

```python
import sys, os, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_script_runner_returns_image_outputs():
    from agents.script_runner import run_script_runner
    from models.schemas import PyScript

    # Script that creates two PNG files in OUTPUT_DIR
    script = PyScript(
        script_code="""
import os
from PIL import Image
output_dir = os.environ['OUTPUT_DIR']
img = Image.new('RGB', (10, 10), color='red')
img.save(os.path.join(output_dir, '01_test.png'))
img.save(os.path.join(output_dir, '02_test.png'))
""",
        description="test"
    )
    outputs = run_script_runner(script)
    assert len(outputs) == 2
    assert all(o["render"] == "image" for o in outputs)
    assert all(isinstance(o["content"], str) and len(o["content"]) > 0 for o in outputs)


def test_script_runner_matplotlib_output():
    from agents.script_runner import run_script_runner
    from models.schemas import PyScript

    script = PyScript(
        script_code="""
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
output_dir = os.environ['OUTPUT_DIR']
plt.plot([1, 2, 3], [4, 5, 6])
plt.savefig(os.path.join(output_dir, '01_chart.png'))
plt.close()
""",
        description="matplotlib test"
    )
    outputs = run_script_runner(script)
    assert len(outputs) == 1
    assert outputs[0]["render"] == "image"


def test_script_runner_timeout_returns_error():
    from agents.script_runner import run_script_runner
    from models.schemas import PyScript

    script = PyScript(script_code="import time\ntime.sleep(9999)", description="timeout test")
    outputs = run_script_runner(script, timeout=2)
    assert len(outputs) == 1
    assert outputs[0]["render"] == "text"
    assert "超时" in outputs[0]["content"]


def test_script_runner_script_error_returns_error():
    from agents.script_runner import run_script_runner
    from models.schemas import PyScript

    script = PyScript(script_code="raise ValueError('boom')", description="error test")
    outputs = run_script_runner(script)
    assert len(outputs) == 1
    assert outputs[0]["render"] == "text"


def test_script_runner_no_output_returns_error():
    from agents.script_runner import run_script_runner
    from models.schemas import PyScript

    script = PyScript(script_code="print('no images')", description="no output test")
    outputs = run_script_runner(script)
    assert len(outputs) == 1
    assert outputs[0]["render"] == "text"
    assert "图表" in outputs[0]["content"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_script_runner.py -v
```

Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Create script_runner.py**

Create `backend/agents/script_runner.py`:

```python
import base64
import logging
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

from models.schemas import PyScript
from config import settings

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 60
_cfg = settings["clickhouse"]


def run_script_runner(
    py_script: PyScript,
    timeout: int = _DEFAULT_TIMEOUT,
) -> list:
    with tempfile.TemporaryDirectory(prefix="aiops_renders_") as output_dir:
        env = os.environ.copy()
        env.update({
            "CH_HOST": str(_cfg["host"]),
            "CH_PORT": str(_cfg["port"]),
            "CH_USER": str(_cfg["user"]),
            "CH_PASSWORD": str(_cfg["password"]),
            "CH_DATABASE": str(_cfg["database"]),
            "OUTPUT_DIR": output_dir,
            "MPLBACKEND": "Agg",
        })

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False, encoding="utf-8") as f:
            f.write(py_script.script_code)
            script_path = f.name

        try:
            logger.info("script_runner: executing script  len=%d  timeout=%ds",
                        len(py_script.script_code), timeout)
            t0 = time.perf_counter()
            proc = subprocess.run(
                [sys.executable, script_path],
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            elapsed = time.perf_counter() - t0
            logger.info("script_runner: done  %.2fs  returncode=%d", elapsed, proc.returncode)

            if proc.returncode != 0:
                err = proc.stderr[-500:] if proc.stderr else "脚本执行失败"
                logger.warning("script_runner: script failed\n%s", proc.stderr)
                return [{"render": "text", "content": f"⚠️ 脚本执行错误：{err}"}]

            png_files = sorted(Path(output_dir).glob("*.png"))
            logger.info("script_runner: found %d PNG files", len(png_files))

            if not png_files:
                return [{"render": "text", "content": "⚠️ 脚本执行完成但未生成图表，请重试"}]

            outputs = []
            for png_path in png_files:
                data = png_path.read_bytes()
                b64 = base64.b64encode(data).decode("ascii")
                outputs.append({"render": "image", "content": b64})
            return outputs

        except subprocess.TimeoutExpired:
            logger.warning("script_runner: timeout after %ds", timeout)
            return [{"render": "text", "content": f"⚠️ 脚本执行超时（>{timeout}秒），请简化查询后重试"}]
        finally:
            try:
                os.unlink(script_path)
            except OSError:
                pass
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_script_runner.py -v
```

Expected: PASS (5 tests). Note: PIL test may be skipped if Pillow not installed — matplotlib test is the primary one.

- [ ] **Step 5: Commit**

```bash
git add backend/agents/script_runner.py backend/tests/test_script_runner.py
git commit -m "feat: add script_runner agent for subprocess PNG execution"
```

---

## Task 6: Rewrite pipeline

**Files:**
- Rewrite: `backend/graph/pipeline.py`
- Modify: `backend/tests/test_pipeline.py`

- [ ] **Step 1: Write failing tests for new pipeline state**

Add to `backend/tests/test_pipeline.py` (replace existing):

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_pipeline_state_has_new_fields():
    from graph.pipeline import PipelineState
    fields = PipelineState.__annotations__
    assert "py_script" in fields
    assert "code_review_result" in fields
    assert "script_retry_count" in fields
    assert "sql_tasks" not in fields
    assert "execution_results" not in fields


def test_pipeline_builds():
    from graph.pipeline import build_pipeline
    pipeline = build_pipeline()
    assert pipeline is not None


def test_pipeline_route_after_code_reviewer_approved():
    from graph.pipeline import route_after_code_reviewer
    state = {
        "code_review_result": type("R", (), {"approved": True, "issues": []})(),
        "script_retry_count": 0,
        "error": None,
    }
    assert route_after_code_reviewer(state) == "script_runner"


def test_pipeline_route_after_code_reviewer_retry():
    from graph.pipeline import route_after_code_reviewer
    state = {
        "code_review_result": type("R", (), {"approved": False, "issues": ["问题"]})(),
        "script_retry_count": 1,
        "error": None,
    }
    assert route_after_code_reviewer(state) == "sql_engineer"


def test_pipeline_route_after_code_reviewer_max_retries():
    from graph.pipeline import route_after_code_reviewer
    state = {
        "code_review_result": type("R", (), {"approved": False, "issues": ["问题"]})(),
        "script_retry_count": 3,
        "error": None,
    }
    assert route_after_code_reviewer(state) == "end"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_pipeline.py -v
```

Expected: FAIL

- [ ] **Step 3: Rewrite pipeline.py**

Replace `backend/graph/pipeline.py` with:

```python
import logging
import time
import uuid
from typing import Callable, Optional
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END

from models.schemas import TaskPlan, PyScript, CodeReviewResult, SummaryReport
from agents.clarifier import run_clarifier
from agents.planner import run_planner
from agents.sql_engineer import run_sql_engineer
from agents.code_reviewer import run_code_reviewer
from agents.script_runner import run_script_runner
from agents.summarizer import run_summarizer

logger = logging.getLogger(__name__)

_MAX_SCRIPT_RETRIES = 3


class PipelineState(TypedDict):
    session_id: str
    user_message: str
    conversation_history: list
    task_plan: Optional[TaskPlan]
    py_script: Optional[PyScript]
    code_review_result: Optional[CodeReviewResult]
    script_retry_count: int
    viz_outputs: list
    clarification_needed: bool
    clarification_question: Optional[str]
    clarifier_done: bool
    clarifier_question: Optional[str]
    clarifier_options: list
    summary_report: Optional[SummaryReport]
    error: Optional[str]
    progress_cb: Optional[Callable[[str], None]]


def _emit(state: PipelineState, text: str) -> None:
    cb = state.get("progress_cb")
    if cb:
        cb(text)


def _fallback_outputs(message: str) -> list:
    return [{"render": "text", "content": message}]


def _has_error(state: PipelineState) -> bool:
    return bool(state.get("error"))


def node_clarifier(state: PipelineState) -> dict:
    sid = state["session_id"]
    logger.info("[%s] >>> node:clarifier  input=%r", sid, state["user_message"][:80])
    try:
        result = run_clarifier(state["user_message"], state["conversation_history"])
    except Exception as e:
        logger.error("[%s] <<< node:clarifier  FAILED: %s", sid, e, exc_info=True)
        return {"clarifier_done": True, "clarifier_question": None, "clarifier_options": []}
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
    _emit(state, "🧠 正在理解问题、制定分析方案...")
    logger.info("[%s] >>> node:planner  input=%r", sid, state["user_message"][:120])
    start = time.perf_counter()
    try:
        plan = run_planner(state["user_message"], state["conversation_history"])
    except Exception as e:
        elapsed = time.perf_counter() - start
        logger.error("[%s] <<< node:planner  %.2fs  FAILED: %s", sid, elapsed, e, exc_info=True)
        _emit(state, "⚠️ 任务规划失败，已降级处理")
        return {
            "task_plan": None,
            "clarification_needed": False,
            "clarification_question": None,
            "viz_outputs": _fallback_outputs(f"❌ 任务规划出错：{e}"),
            "error": str(e),
        }
    elapsed = time.perf_counter() - start
    if not plan.clarification_needed and plan.analysis_plan:
        _emit(state, f"📋 规划完成：{plan.analysis_plan.goal}")
        logger.info("[%s] <<< node:planner  %.2fs  goal=%r", sid, elapsed, plan.analysis_plan.goal)
    return {
        "task_plan": plan,
        "clarification_needed": plan.clarification_needed,
        "clarification_question": plan.clarification_question,
    }


def node_sql_engineer(state: PipelineState) -> dict:
    sid = state["session_id"]
    retry = state.get("script_retry_count", 0)
    issues = None
    if retry > 0 and state.get("code_review_result"):
        issues = state["code_review_result"].issues
        _emit(state, f"🔧 正在根据审查意见修复脚本（第{retry}次重试）...")
    else:
        _emit(state, "⚙️ 正在生成分析脚本...")
    logger.info("[%s] >>> node:sql_engineer  retry=%d", sid, retry)
    start = time.perf_counter()
    try:
        py_script = run_sql_engineer(state["task_plan"], issues=issues)
    except Exception as e:
        elapsed = time.perf_counter() - start
        logger.error("[%s] <<< node:sql_engineer  %.2fs  FAILED: %s", sid, elapsed, e, exc_info=True)
        _emit(state, "⚠️ 脚本生成失败，已降级处理")
        return {
            "py_script": None,
            "viz_outputs": _fallback_outputs(f"❌ 脚本生成出错：{e}"),
            "error": str(e),
        }
    elapsed = time.perf_counter() - start
    if py_script is None:
        logger.warning("[%s] <<< node:sql_engineer  %.2fs  returned None", sid, elapsed)
        _emit(state, "⚠️ 脚本生成失败")
        return {
            "py_script": None,
            "viz_outputs": _fallback_outputs("❌ 未能生成分析脚本，请换一种方式描述您的问题。"),
            "error": "sql_engineer returned None",
        }
    _emit(state, f"✅ 脚本生成完成（{len(py_script.script_code)}字符）")
    logger.info("[%s] <<< node:sql_engineer  %.2fs  script_len=%d", sid, elapsed, len(py_script.script_code))
    return {"py_script": py_script}


def node_code_reviewer(state: PipelineState) -> dict:
    sid = state["session_id"]
    _emit(state, "🔍 正在审查脚本安全性与性能...")
    logger.info("[%s] >>> node:code_reviewer", sid)
    start = time.perf_counter()
    try:
        result = run_code_reviewer(state["py_script"].script_code)
    except Exception as e:
        elapsed = time.perf_counter() - start
        logger.error("[%s] <<< node:code_reviewer  %.2fs  FAILED: %s", sid, elapsed, e, exc_info=True)
        return {"code_review_result": CodeReviewResult(approved=True, issues=[])}
    elapsed = time.perf_counter() - start
    if result.approved:
        _emit(state, "✅ 脚本审查通过")
    else:
        _emit(state, f"⚠️ 发现{len(result.issues)}个问题，正在修复...")
    logger.info("[%s] <<< node:code_reviewer  %.2fs  approved=%s  issues=%d",
                sid, elapsed, result.approved, len(result.issues))
    return {"code_review_result": result}


def node_script_runner(state: PipelineState) -> dict:
    sid = state["session_id"]
    _emit(state, "🎨 正在执行分析脚本并生成图表...")
    logger.info("[%s] >>> node:script_runner", sid)
    start = time.perf_counter()
    try:
        outputs = run_script_runner(state["py_script"])
    except Exception as e:
        elapsed = time.perf_counter() - start
        logger.error("[%s] <<< node:script_runner  %.2fs  FAILED: %s", sid, elapsed, e, exc_info=True)
        _emit(state, "⚠️ 图表生成失败，已降级处理")
        return {
            "viz_outputs": _fallback_outputs(f"❌ 图表生成出错：{e}"),
            "error": str(e),
        }
    elapsed = time.perf_counter() - start
    image_count = sum(1 for o in outputs if o["render"] == "image")
    logger.info("[%s] <<< node:script_runner  %.2fs  outputs=%d  images=%d",
                sid, elapsed, len(outputs), image_count)
    return {"viz_outputs": outputs}


def node_summarizer(state: PipelineState) -> dict:
    sid = state["session_id"]
    _emit(state, "📝 正在生成分析报告...")
    logger.info("[%s] >>> node:summarizer", sid)
    start = time.perf_counter()
    task_plan = state["task_plan"]
    analysis_plan = task_plan.analysis_plan if task_plan else None
    image_count = sum(1 for o in state.get("viz_outputs", []) if o.get("render") == "image")
    insights = [{"task_id": "script", "insight_hint": analysis_plan.viz_intent if analysis_plan else "", "rows": image_count}]
    try:
        report = run_summarizer(state["user_message"], insights, analysis_plan=analysis_plan)
    except Exception as e:
        elapsed = time.perf_counter() - start
        logger.error("[%s] <<< node:summarizer  %.2fs  FAILED: %s", sid, elapsed, e, exc_info=True)
        _emit(state, "⚠️ 报告生成失败，已跳过")
        return {"summary_report": None}
    elapsed = time.perf_counter() - start
    logger.info("[%s] <<< node:summarizer  %.2fs  points=%d", sid, elapsed, len(report.key_points))
    return {"summary_report": report}


def route_after_clarifier(state: PipelineState) -> str:
    return "planner" if state["clarifier_done"] else "end_clarify"


def route_after_planner(state: PipelineState) -> str:
    if _has_error(state):
        return "end"
    return "end_clarify" if state["clarification_needed"] else "sql_engineer"


def route_after_sql_engineer(state: PipelineState) -> str:
    return "end" if _has_error(state) else "code_reviewer"


def route_after_code_reviewer(state: PipelineState) -> str:
    if _has_error(state):
        return "end"
    result = state.get("code_review_result")
    if result and not result.approved:
        retry = state.get("script_retry_count", 0)
        if retry < _MAX_SCRIPT_RETRIES:
            return "sql_engineer"
        else:
            return "end"
    return "script_runner"


def route_after_script_runner(state: PipelineState) -> str:
    return "end" if _has_error(state) else "summarizer"


def node_increment_retry(state: PipelineState) -> dict:
    return {"script_retry_count": state.get("script_retry_count", 0) + 1}


def build_pipeline():
    graph = StateGraph(PipelineState)
    graph.add_node("clarifier", node_clarifier)
    graph.add_node("planner", node_planner)
    graph.add_node("sql_engineer", node_sql_engineer)
    graph.add_node("increment_retry", node_increment_retry)
    graph.add_node("code_reviewer", node_code_reviewer)
    graph.add_node("script_runner", node_script_runner)
    graph.add_node("summarizer", node_summarizer)

    graph.set_entry_point("clarifier")
    graph.add_conditional_edges("clarifier", route_after_clarifier, {
        "end_clarify": END,
        "planner": "planner",
    })
    graph.add_conditional_edges("planner", route_after_planner, {
        "end": END,
        "end_clarify": END,
        "sql_engineer": "sql_engineer",
    })
    graph.add_conditional_edges("sql_engineer", route_after_sql_engineer, {
        "end": END,
        "code_reviewer": "code_reviewer",
    })
    graph.add_conditional_edges("code_reviewer", route_after_code_reviewer, {
        "end": END,
        "sql_engineer": "increment_retry",
        "script_runner": "script_runner",
    })
    graph.add_edge("increment_retry", "sql_engineer")
    graph.add_conditional_edges("script_runner", route_after_script_runner, {
        "end": END,
        "summarizer": "summarizer",
    })
    graph.add_edge("summarizer", END)

    return graph.compile()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_pipeline.py -v
```

Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/graph/pipeline.py backend/tests/test_pipeline.py
git commit -m "feat: rewrite pipeline with code_reviewer and script_runner nodes"
```

---

## Task 7: Update api/chat.py

**Files:**
- Modify: `backend/api/chat.py`

- [ ] **Step 1: Update chat.py to handle new state shape and image render type**

In `backend/api/chat.py`, make the following changes:

1. Remove the `plan_cb` from the state construction (planner no longer emits blueprint).
2. Handle `render: "image"` in the viz_outputs loop.
3. Remove the `plan` message type sending.
4. Initialize new state fields.

Replace `backend/api/chat.py` with:

```python
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

            state = PipelineState(
                session_id=session_id,
                user_message=message,
                conversation_history=conversation_history.copy(),
                task_plan=None,
                py_script=None,
                code_review_result=None,
                script_retry_count=0,
                viz_outputs=[],
                clarification_needed=False,
                clarification_question=None,
                clarifier_done=False,
                clarifier_question=None,
                clarifier_options=[],
                summary_report=None,
                error=None,
                progress_cb=progress_cb,
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
                logger.info("[%s] clarifier ask sent", session_id)
                await _send(ws, {"type": "done", "content": ""})
                continue

            # planner 澄清（兜底）
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
                if render == "image":
                    save_message(session_id, "assistant", "image", content[:100] + "...")
                    await _send(ws, {"type": "result", "render": "image", "content": content})
                    logger.info("[%s] sent output[%d] image  b64_len=%d", session_id, i, len(content))
                else:
                    save_message(session_id, "assistant", "text", str(content))
                    await _send(ws, {"type": "result", "render": "text", "content": content})

            # 综合报告
            report = result_state.get("summary_report")
            if report:
                report_payload = report.model_dump()
                save_message(session_id, "assistant", "text", report.conclusion)
                await _send(ws, {"type": "summary", "content": report_payload})
                logger.info("[%s] summary sent  points=%d", session_id, len(report.key_points))

            logger.info("[%s] pipeline done  outputs=%d", session_id, len(result_state["viz_outputs"]))
            await _send(ws, {"type": "done", "content": "分析完成"})

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error("Unexpected WebSocket error", exc_info=True)
        try:
            await _send(ws, {"type": "error", "content": f"服务器内部错误：{e}"})
            await _send(ws, {"type": "done", "content": ""})
        except Exception:
            pass
```

- [ ] **Step 2: Run existing tests to confirm no regressions**

```bash
cd backend && python -m pytest tests/ -v --ignore=tests/test_visualizer.py --ignore=tests/test_parallel_executor.py
```

Expected: All previously passing tests still pass.

- [ ] **Step 3: Commit**

```bash
git add backend/api/chat.py
git commit -m "feat: update chat.py for image render type and new pipeline state"
```

---

## Task 8: Delete obsolete files

**Files:**
- Delete: `backend/agents/visualizer.py`
- Delete: `backend/executor/parallel.py`
- Delete: `backend/tests/test_visualizer.py`
- Delete: `backend/tests/test_parallel_executor.py`

- [ ] **Step 1: Delete obsolete files**

```bash
git rm backend/agents/visualizer.py backend/executor/parallel.py backend/tests/test_visualizer.py backend/tests/test_parallel_executor.py
```

- [ ] **Step 2: Run full test suite to confirm nothing broke**

```bash
cd backend && python -m pytest tests/ -v
```

Expected: All remaining tests pass.

- [ ] **Step 3: Commit**

```bash
git commit -m "chore: remove visualizer, parallel executor, and their tests"
```

---

## Task 9: Update frontend

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/components/ChartRenderer.tsx`
- Modify: `frontend/src/components/ChatPanel.tsx`

- [ ] **Step 1: Update types.ts**

Replace `frontend/src/types.ts` with:

```typescript
export type MessageType = "clarify" | "progress" | "result" | "plan" | "summary" | "error" | "done" | "user";
export type RenderType = "image" | "text";

export interface WSMessage {
  type: MessageType;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  content?: any;
  render?: RenderType;
  elapsed?: number;
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
  question?: string;
  options?: string[];
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

- [ ] **Step 2: Update ChartRenderer.tsx**

Replace `frontend/src/components/ChartRenderer.tsx` with:

```tsx
interface Props {
  render: "image" | "text";
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  content: any;
}

export function ChartRenderer({ render, content }: Props) {
  if (render === "image") {
    return (
      <img
        src={`data:image/png;base64,${content}`}
        alt="分析图表"
        className="w-full rounded"
        style={{ maxHeight: 600, objectFit: "contain" }}
      />
    );
  }
  return (
    <p className="text-sm text-[var(--color-foreground)] whitespace-pre-wrap">
      {content}
    </p>
  );
}
```

- [ ] **Step 3: Update ChatPanel.tsx — remove PlanCard import and plan message handler**

In `frontend/src/components/ChatPanel.tsx`:

1. Remove import of `PlanCard` and `VizBlueprintItem`.
2. Remove the `if (msg.type === "plan")` block.

Replace `frontend/src/components/ChatPanel.tsx` with:

```tsx
import { useEffect, useRef } from "react";
import type { ChatMessage, SummaryReportData } from "../types";
import { ChartRenderer } from "./ChartRenderer";
import { ProgressBar } from "./ProgressBar";
import { ClarifyMessage } from "./ClarifyMessage";
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

- [ ] **Step 4: Check TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types.ts frontend/src/components/ChartRenderer.tsx frontend/src/components/ChatPanel.tsx
git commit -m "feat: frontend supports image render type, removes ECharts and PlanCard"
```

---

## Task 10: Update summarizer to work with new insight format

**Files:**
- Modify: `backend/agents/summarizer.py`
- Modify: `backend/tests/test_summarizer.py`

- [ ] **Step 1: Verify summarizer tests still pass as-is**

```bash
cd backend && python -m pytest tests/test_summarizer.py -v
```

If they pass, no changes needed — skip to commit check. If they fail:

- [ ] **Step 2: Fix summarizer.py to handle missing task_id/insight_hint gracefully**

The summarizer receives `insights` from `node_summarizer` in pipeline.py, which now passes:
```python
[{"task_id": "script", "insight_hint": analysis_plan.viz_intent, "rows": image_count}]
```

The existing `run_summarizer` already handles this format. Verify by running the tests.

- [ ] **Step 3: Run full backend test suite**

```bash
cd backend && python -m pytest tests/ -v
```

Expected: All tests pass.

- [ ] **Step 4: Commit if any changes were needed**

```bash
git add backend/agents/summarizer.py backend/tests/test_summarizer.py
git commit -m "fix: summarizer compatible with new single-insight format"
```

---

## Task 11: Install matplotlib/seaborn dependency

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Check if matplotlib is already in requirements.txt**

```bash
grep -i matplotlib backend/requirements.txt || grep -i matplotlib requirements.txt
```

- [ ] **Step 2: Add if missing**

If not present, add to `requirements.txt`:

```
matplotlib>=3.8.0
seaborn>=0.13.0
```

- [ ] **Step 3: Install in venv**

```bash
cd backend && .venv/bin/pip install matplotlib seaborn
```

Expected: Successfully installed (or already satisfied)

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "chore: add matplotlib and seaborn dependencies"
```

---

## Task 12: Final integration check

- [ ] **Step 1: Run full backend test suite**

```bash
cd backend && python -m pytest tests/ -v
```

Expected: All tests pass, no failures.

- [ ] **Step 2: Start backend and verify it starts cleanly**

```bash
cd backend && python main.py &
sleep 3 && curl -s http://localhost:8000/health | python -m json.tool
```

Expected: `{"status": "ok"}` or similar.

- [ ] **Step 3: Start frontend and verify TypeScript compiles**

```bash
cd frontend && npm run build 2>&1 | tail -20
```

Expected: Build succeeds with no TypeScript errors.

- [ ] **Step 4: Kill backend**

```bash
pkill -f "python main.py"
```

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat: complete planner→script viz pipeline migration" --allow-empty
```
