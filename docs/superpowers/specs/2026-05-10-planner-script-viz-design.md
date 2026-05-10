# Design: Planner → Python Script Visualization

**Date:** 2026-05-10  
**Status:** Approved

## Problem

The current `planner → visualizer` chain is fragile:

1. Planner must predict SQL result column names in `viz_blueprint` — LLM frequently gets these wrong.
2. Visualizer only supports 5 chart types (bar/line/pie/scatter/heatmap) via ECharts JSON construction.
3. Field name mismatches between blueprint and actual query results cause silent render failures.

## Solution

Replace the SQL + ECharts JSON pipeline with a Python script execution pipeline. Planner focuses on analysis strategy; sql_engineer generates a complete self-contained Python script (SQL + matplotlib visualization); code_reviewer audits and sends issues back to sql_engineer for fixes; script_runner executes the approved script and streams image results to the frontend.

## New Pipeline Topology

```
clarifier → planner → sql_engineer → code_reviewer → script_runner → summarizer
                              ↑              |
                              └── issues ────┘ (up to 3 retries)
```

Nodes removed: `executor`, `visualizer`

## Node Responsibilities

### planner
- Outputs a single `AnalysisPlan` describing the full analysis strategy.
- Does NOT split into sub-tasks. Does NOT specify column names or chart types.
- Fields: `goal`, `approach`, `expected_findings: list[str]`, `analysis_dimensions: list[str]`, `viz_intent` (natural language description of what visualizations to produce).
- Retains `clarification_needed` / `clarification_question` for the clarification flow.

### sql_engineer
- Receives `AnalysisPlan` (and optionally `code_review_issues` on retry).
- Generates a single complete Python script (`PyScript`) that:
  - Reads ClickHouse connection params from environment variables (`CH_HOST`, `CH_PORT`, `CH_DATABASE`, `CH_USER`, `CH_PASSWORD`).
  - Executes all necessary SQL queries against ClickHouse.
  - Produces all visualizations using matplotlib/seaborn.
  - Saves output images to the directory specified by the `OUTPUT_DIR` environment variable.
  - Decides independently how many images to produce and whether to use subplots or separate files.
- On retry: incorporates `code_review_issues` to fix the previous script.
- Images must be named with a numeric prefix for ordering (e.g., `01_traffic.png`, `02_anomaly.png`).

### code_reviewer
- LLM audits the generated script for:
  - **Safety**: dangerous operations (`os.system`, `subprocess`, file writes outside `OUTPUT_DIR`, network calls other than ClickHouse, `DROP`/`DELETE` SQL).
  - **Performance**: large table cross-JOINs, unbounded full-table scans, missing `LIMIT` on large tables.
  - **Timeout risk**: queries or computations likely to exceed the execution time budget.
- Outputs `CodeReviewResult`:
  - `approved: bool`
  - `issues: list[str]` — specific problems found (empty when approved)
- Does NOT rewrite the script itself.
- If `approved=False`, pipeline routes back to sql_engineer with issues.
- Maximum 3 retries. If still not approved after 3 attempts, pipeline returns an error message to the user.

### script_runner
- Executes the approved script via `subprocess` with:
  - Environment variables: `CH_HOST`, `CH_PORT`, `CH_DATABASE`, `CH_USER`, `CH_PASSWORD`, `OUTPUT_DIR` (a fresh temp directory per execution).
  - Timeout: 60 seconds. If exceeded, kill process and return timeout error.
- After execution, scans `OUTPUT_DIR` for all PNG files, sorts by filename.
- Base64-encodes each PNG and sends via WebSocket as `{"type": "result", "render": "image", "content": "<base64>"}`.
- One WebSocket message per image.

### summarizer
- Unchanged. Receives execution metadata (image count, analysis plan) and produces the summary report.

## Schema Changes

### New schemas (backend/models/schemas.py)

```python
class AnalysisPlan(BaseModel):
    goal: str
    approach: str
    expected_findings: list[str]
    analysis_dimensions: list[str]
    viz_intent: str  # natural language, e.g. "show top IPs by outbound traffic, highlight anomalies"

class TaskPlan(BaseModel):
    analysis_plan: Optional[AnalysisPlan] = None
    clarification_needed: bool = False
    clarification_question: Optional[str] = None
    estimated_seconds: int = 10
    # tasks, viz_blueprint fields removed

class PyScript(BaseModel):
    script_code: str
    description: str

class CodeReviewResult(BaseModel):
    approved: bool
    issues: list[str]  # empty when approved

# WSMessage.render gains new literal value: "image"
```

### Removed schemas
- `SubTask`
- `VizBlueprint`
- `SQLTask`
- `VizSpec`

## PipelineState Changes

```python
class PipelineState(TypedDict):
    # unchanged
    session_id: str
    user_message: str
    conversation_history: list
    clarification_needed: bool
    clarification_question: Optional[str]
    clarifier_done: bool
    clarifier_question: Optional[str]
    clarifier_options: list
    summary_report: Optional[SummaryReport]
    error: Optional[str]
    progress_cb: Optional[Callable]
    plan_cb: Optional[Callable]

    # changed
    task_plan: Optional[TaskPlan]         # now only holds AnalysisPlan + clarification fields
    py_script: Optional[PyScript]         # replaces sql_tasks
    code_review_result: Optional[CodeReviewResult]  # new
    script_retry_count: int               # new, max 3
    viz_outputs: list                     # same key, content changes to image render type

    # removed
    # sql_tasks
    # execution_results
```

## WebSocket Protocol Change

New render type on the frontend:

```json
{"type": "result", "render": "image", "content": "<base64 PNG string>"}
```

Frontend renders as: `<img src="data:image/png;base64,{content}">`

Existing render types (`echarts`, `html`, `text`) are removed from active use but the frontend can keep backward compatibility if needed.

## File Changes Summary

| File | Action |
|------|--------|
| `backend/agents/planner.py` | Remove viz_blueprint from prompt and output schema |
| `backend/agents/sql_engineer.py` | Rewrite: generate Python script instead of SQL string |
| `backend/agents/code_reviewer.py` | New file |
| `backend/agents/script_runner.py` | New file (replaces visualizer.py) |
| `backend/agents/visualizer.py` | Delete |
| `backend/executor/parallel.py` | Delete (or keep if used elsewhere) |
| `backend/graph/pipeline.py` | Rewire nodes, add retry routing |
| `backend/models/schemas.py` | Add PyScript, CodeReviewResult; remove SubTask, VizBlueprint, SQLTask, VizSpec |
| `backend/api/chat.py` | Handle new `render: "image"` type |
| `frontend/` | Add image render support in chat message component |

## Environment Variables for Script Execution

The script_runner injects these into the subprocess environment:

- `CH_HOST`, `CH_PORT`, `CH_DATABASE`, `CH_USER`, `CH_PASSWORD` — from `config/settings.yaml`
- `OUTPUT_DIR` — fresh temp directory created per execution (e.g., `/tmp/renders/<uuid>/`)

## Error Handling

| Scenario | Behavior |
|----------|----------|
| code_reviewer rejects, retry < 3 | Route back to sql_engineer with issues |
| code_reviewer rejects, retry = 3 | Return error message to user |
| script_runner timeout (>60s) | Kill subprocess, return timeout error |
| script produces no PNG files | Return "no output" error |
| script raises exception | Capture stderr, return error with detail |
