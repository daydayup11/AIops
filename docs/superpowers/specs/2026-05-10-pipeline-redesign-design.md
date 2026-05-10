# Pipeline 重设计：需求澄清 + 可视化蓝图 + 综合分析

**日期：** 2026-05-10  
**状态：** 已确认

---

## 背景与问题

当前 pipeline 存在以下问题：
1. planner 拆分多个独立子任务，每个任务各自可视化，导致返回重复/近似的图表
2. visualizer 每次调 LLM 推断图表类型，不稳定且浪费资源
3. 没有综合分析文本，用户拿到图表后缺乏针对性结论
4. planner 自带的 clarification 逻辑简单，无法引导用户完善需求，也不支持选项式交互

---

## 目标

1. 在 planner 前增加**需求澄清 Agent**，通过选项+自由输入引导用户明确需求
2. planner 输出**可视化蓝图**，一次性决定展示几张图、每张图的类型和字段
3. visualizer 按蓝图确定性执行，不再调 LLM
4. pipeline 末尾增加 **summarizer 节点**，针对用户原始问题生成结构化分析报告
5. 规划结果通过 SSE 推送给前端（文字概要 + 结构化卡片）

---

## 整体架构

### 新 Pipeline 节点顺序

```
用户消息
  └→ node_clarifier（新）
       ├→ [需要追问] → 推送 type:"clarify" 消息 → END（等待用户回复）
       └→ [需求明确 / 用户强制跳过] → node_planner
                                          └→ node_sql_engineer
                                               └→ node_executor
                                                    └→ node_visualizer（改：按蓝图执行）
                                                         └→ node_summarizer（新）
                                                              └→ END
```

### 多轮对话机制

clarifier 复用现有 `conversation_history` 机制：
- clarifier 追问 → 推 `type:"clarify"` → pipeline END
- 用户回复 → WebSocket 收到新消息 → 重新 invoke pipeline → 从 clarifier 开始
- 直到 clarifier 判断需求明确或用户发送强制跳过关键词（"开始分析"、"就这样"、"直接查"等）

---

## 数据结构变更

### 新增 `VizBlueprint`

```python
class VizBlueprint(BaseModel):
    task_id: str          # 绑定哪个子任务的查询结果
    chart_type: str       # bar / line / pie / scatter / heatmap
    title: str            # 图表标题
    x_field: str          # X 轴字段名
    y_field: str          # Y 轴字段名
    insight_hint: str     # planner 预期的洞察方向，传给 summarizer
```

### 扩展 `TaskPlan`

```python
class TaskPlan(BaseModel):
    tasks: list[SubTask]
    viz_blueprint: list[VizBlueprint]   # 新增，与 tasks 一一对应
    clarification_needed: bool
    clarification_question: Optional[str]
    estimated_seconds: int
```

### 新增 `SummaryReport`

```python
class SummaryReport(BaseModel):
    title: str            # 报告标题
    key_points: list[str] # 3-5 条核心要点
    conclusion: str       # 针对用户问题的结论段落
```

### `PipelineState` 新增字段

```python
class PipelineState(TypedDict):
    # 现有字段不变 ...
    clarifier_done: bool           # clarifier 是否已放行
    summary_report: Optional[SummaryReport]  # summarizer 输出
```

---

## 各节点详细设计

### node_clarifier（新）

**职责：** 判断用户需求是否明确，不明确则追问。

**行为逻辑：**
1. 检查用户消息是否包含强制跳过关键词 → 是则设 `clarifier_done=True`，进入 planner
2. 调 LLM 判断当前 conversation_history 中需求是否明确（时间范围、分析维度、目标）
3. 明确 → 设 `clarifier_done=True`，进入 planner
4. 不明确 → LLM 生成一个追问问题 + 2-4 个选项，推送 `type:"clarify"`，pipeline END

**LLM prompt 原则：**
- 每次只问一个问题
- 优先引导补全：时间范围、分析维度（按应用/用户/时段）、目标（排行/趋势/异常）
- 需求明确时内部输出 `{"action": "continue"}` 信号
- 不明确时输出 `{"action": "ask", "question": "...", "options": ["...", "..."]}`

**强制跳过关键词：** "开始分析"、"就这样"、"直接查"、"不用问了"、"跳过"

---

### node_planner（改）

**新增职责：** 在原有任务拆分基础上，输出 `viz_blueprint`。

**prompt 新增要求：**
- 为每个子任务指定一个 `VizBlueprint`
- `task_id` 与 `tasks` 中的 id 一一对应
- 不允许出现两个完全相同 `chart_type + x_field + y_field` 的蓝图（避免重复图表）
- `insight_hint` 用一句话描述该图预期揭示的规律

**planner 完成后 SSE 推送两条消息：**
```json
{"type": "progress", "content": "📋 规划完成：共 2 个查询，将展示流量排行柱状图 + 时段折线图"}
{"type": "plan", "content": [
  {"task_id": "t1", "chart_type": "bar", "title": "Top10应用流量排行", "x_field": "appid", "y_field": "total_bytes"},
  {"task_id": "t2", "chart_type": "line", "title": "24小时流量时段分布", "x_field": "hour", "y_field": "bytes"}
]}
```

---

### node_visualizer（改）

**变化：** 不再调 LLM，直接从 `task_plan.viz_blueprint` 中查找对应蓝图，按蓝图调用 `_build_echarts_option`。

**逻辑：**
```
for task_id, result in execution_results:
    blueprint = viz_blueprint_map[task_id]
    option = _build_echarts_option(blueprint, result["df"])
    outputs.append({"render": "echarts", "content": option, "insight": blueprint.insight_hint})
```

找不到蓝图时降级为现有 LLM 推断逻辑（兜底）。

---

### node_summarizer（新）

**职责：** 针对用户原始问题，汇总所有图表数据生成结构化分析报告。

**输入：**
- `user_message`（用户原始问题）
- `viz_outputs`（所有图表的 insight_hint + 数据摘要）
- `task_plan.viz_blueprint`（各图预期洞察方向）

**输出：** `SummaryReport`，通过 SSE 推送：
```json
{"type": "summary", "content": {
  "title": "校园网流量分析报告",
  "key_points": ["应用ID 5 流量最高，占总流量 35%", "流量高峰集中在 20:00-23:00", "..."],
  "conclusion": "针对您的问题「过去24小时流量排行」：..."
}}
```

**位置：** 在所有 `result` 消息之后、`done` 消息之前发送。

---

## 前端变更

### 新增消息类型处理

| 消息类型 | 前端行为 |
|---------|---------|
| `type: "clarify"` | 渲染问题文字 + 选项按钮组（可点击）+ 支持自由输入；用户点击或发送后按钮自动禁用 |
| `type: "plan"` | 渲染规划卡片，展示每个子任务标题和图表类型（待执行状态） |
| `type: "summary"` | 渲染结构化报告：标题 + 要点列表 + 结论段落，位于所有图表之后 |

### 现有消息类型不变

`progress`、`result`（echarts/html/text）、`done`、`error` 保持原样。

### 消息渲染顺序

```
[clarify 问答（0~N 轮）]
[progress: 规划中...]
[plan: 规划卡片]
[progress: SQL 生成...]
[progress: 查询执行...]
[result: 图表 1]
[result: 图表 2]
[summary: 综合报告]
[done]
```

---

## 文件变更清单

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `backend/models/schemas.py` | 修改 | 新增 `VizBlueprint`、`SummaryReport`，扩展 `TaskPlan` |
| `backend/agents/clarifier.py` | 新增 | 需求澄清 Agent |
| `backend/agents/planner.py` | 修改 | prompt 增加 viz_blueprint 输出要求 |
| `backend/agents/visualizer.py` | 修改 | 按蓝图执行，去掉 LLM 调用，保留兜底 |
| `backend/agents/summarizer.py` | 新增 | 综合分析报告生成 |
| `backend/graph/pipeline.py` | 修改 | 新增 clarifier/summarizer 节点，扩展 State |
| `backend/api/chat.py` | 修改 | 新增 plan/summary/clarify SSE 消息推送 |
| `frontend/src/hooks/useWebSocket.ts` | 修改 | 新增消息类型处理 |
| `frontend/src/components/` | 新增 | ClarifyMessage、PlanCard、SummaryReport 组件 |
