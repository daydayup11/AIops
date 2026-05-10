# 校园网流量分析助手：基于 LangGraph 的自然语言数据分析系统

> 技术分享 · 2026-05-11

---

## 一、背景与问题

### 数据规模

我们的校园网网关设备持续采集网络流量数据，写入 ClickHouse 数据库 `logdb`：

| 表 | 数据量 | 内容 |
|----|--------|------|
| `sessions` | **364 亿条** | TCP/UDP/ICMP 会话五元组 + 流量 |
| `npm` | **375 亿条** | 延迟、重传等性能指标 |
| `dns` | **34 亿条** | DNS 查询日志 |
| `url` | **26 亿条** | HTTP/HTTPS 访问日志 |
| `iplog` | **10 亿条** | 按 IP 聚合的流量统计 |
| `event` | **1.9 亿条** | QQ / 微信等应用登录事件 |

日均处理约 **100 TB** 流量，在线终端 **7～11 万**个。

### 真实痛点

传统分析方式需要：

1. 了解 ClickHouse SQL 语法
2. 熟悉 8 张核心表的字段定义
3. 知道如何避免对百亿条记录全表扫描
4. 手动绘制图表

结果是：**只有少数运维同学能做分析**，普通用户、老师、管理人员无法自助获取数据洞察。

### 目标

> 让任何人用一句自然语言提问，系统自动完成 SQL 生成、查询执行、结果可视化，并给出文字摘要。

---

## 二、系统架构

### 总体分层

```
用户浏览器
  │  自然语言输入
  │  WebSocket（流式进度推送）
  ▼
FastAPI 后端
  │
  ▼
LangGraph Pipeline（多 Agent 流水线）
  │
  ├─── ClickHouse（logdb，流量数据）
  └─── SQLite（对话历史）
```

前端使用 **React + ECharts**，通过 WebSocket 接收实时进度和图表数据。

### Pipeline 全貌

每条用户消息进入 Pipeline 后，首先由 `intent_router` 判断意图，分三条路径处理：

```
用户消息
    │
    ▼
intent_router（意图分类）
    ├── data_analysis ──► clarifier ──► planner ──► sql_engineer ──► code_reviewer ──► script_runner ──► summarizer
    ├── knowledge_qa  ──► knowledge_agent（检索 docs/ 文档回答）
    └── chitchat      ──► chitchat_agent（直接 LLM 回复）
```

### 为什么用 LangGraph

- **条件路由**：根据意图、审查结果、重试次数动态决定下一步节点，用普通函数调用难以清晰表达
- **状态机清晰**：所有中间状态（`TaskPlan`、`PyScript`、`CodeReviewResult` 等）统一存在 `PipelineState`，每个节点只读自己需要的字段
- **重试循环**：`sql_engineer → code_reviewer → sql_engineer` 最多循环 3 次，在图结构里自然表达，无需手写循环逻辑

---

## 三、核心 Agent 设计

### 3.1 intent_router — 意图路由

**输入**：用户消息 + 对话历史  
**输出**：`intent`（`data_analysis` / `knowledge_qa` / `chitchat`）+ `rewritten_query`（改写后的规范化问题）

LLM 同时完成两件事：分类意图、改写问题（补全上下文、消歧义），后续 Agent 统一使用 `rewritten_query`。

---

### 3.2 clarifier — 意图澄清

**输入**：用户消息 + 对话历史  
**输出**：`continue`（直接放行）或 `ask`（反问用户）

当问题过于模糊时（如"分析一下流量"），返回一个澄清问题和选项，最多澄清 2 轮后强制执行。

---

### 3.3 planner — 任务规划

**输入**：规范化问题 + 对话历史  
**输出**：`TaskPlan`

```python
class AnalysisPlan(BaseModel):
    goal: str                    # "分析昨天各出口线路流量分布"
    subtasks: List[SubTask]      # 每个子任务含 sql_goal、table_hint、viz_intent
    viz_intent: str              # 最终可视化意图描述
```

Planner 负责把自然语言问题分解为若干个**有明确 SQL 目标的子任务**，后续 SQL Engineer 逐个生成脚本。

---

### 3.4 sql_engineer — 脚本生成

**输入**：`TaskPlan`（+ 可选的 Code Review 问题列表）  
**输出**：`PyScript`（一段可执行的 Python 脚本）

生成的脚本内含：
- ClickHouse 查询（已注入时间条件和 LIMIT）
- matplotlib / pandas 处理逻辑
- 图表输出代码

安全规则在提示词中强制要求，Code Reviewer 再做一次静态校验。

---

### 3.5 code_reviewer — 代码审查

**输入**：生成的 Python 脚本  
**输出**：`CodeReviewResult`（`approved: bool` + `issues: List[str]`）

检查项包括：
- 是否包含非 SELECT 语句
- 是否有全表扫描风险（缺少时间过滤）
- 脚本逻辑是否存在明显错误

若不通过，返回问题列表，`sql_engineer` 根据问题重新生成，**最多重试 3 次**。

```
sql_engineer ──► code_reviewer
      ▲               │ 不通过（retry < 3）
      └───────────────┘
```

---

### 3.6 script_runner — 脚本执行

**输入**：审查通过的 `PyScript`  
**输出**：`viz_outputs`（图表列表）

在进程内安全执行脚本，捕获三种输出类型：

| render 类型 | 内容 | 前端处理 |
|-------------|------|----------|
| `echarts` | ECharts JSON 配置 | 直接渲染图表 |
| `image` | matplotlib PNG（base64）| `<img>` 标签展示 |
| `html` | 完整 HTML 看板 | `<iframe>` 嵌入 |
| `json` | 原始数据 | 传给 Summarizer |

---

### 3.7 summarizer — 报告生成

**输入**：用户原始问题 + 图表元数据 + 原始数据摘要  
**输出**：`SummaryReport`（`key_points: List[str]` + `conclusion: str`）

根据图表结果用 LLM 生成 2-4 条关键洞察，以自然语言展示在图表下方。

---

### 3.8 knowledge_agent + chitchat_agent

| Agent | 触发条件 | 实现方式 |
|-------|----------|----------|
| `knowledge_agent` | 问"这个系统怎么用"/"sessions 表有哪些字段" | 关键词检索 `docs/` 目录 → LLM 组织回答 |
| `chitchat_agent` | 问好、闲聊、无关话题 | 直接调用 LLM，保持友好对话 |

---

## 四、数据安全与性能

### SQL 安全三道防线

| 防线 | 机制 |
|------|------|
| 提示词约束 | 要求 LLM 只生成 SELECT，强制加时间过滤 |
| Code Reviewer | 静态检查，发现问题打回重试 |
| 数据库层 | ClickHouse 连接用只读账号，后端拦截非 SELECT |

大表（`sessions`/`npm`/`dns`/`url`）查询自动追加 `LIMIT 10000`，防止百亿条扫描。

### 并行执行

多个子任务 SQL 通过 `ThreadPoolExecutor` 并行执行，每个查询独立计时，超时自动缩小时间窗口重试（`retry_time_shrink: 0.5`）。

### WebSocket 流式推送

```
后端                          前端
  │── {"type":"progress","content":"🧠 正在规划..."} ──►
  │── {"type":"progress","content":"⚙️ 生成脚本..."} ──►
  │── {"type":"progress","content":"✅ 审查通过"}    ──►
  │── {"type":"result","render":"echarts","content":{...}} ──►
  │── {"type":"result","render":"image","content":"base64..."} ──►
  └── {"type":"done","content":"分析完成"}           ──►
```

用户全程看到进度更新，不会面对空白等待。

---

## 五、效果展示

### 典型交互示例

**用户输入：**
> 分析昨天各出口线路的流量分布，按线路名称做柱状图

**系统处理流程：**
1. `intent_router` → `data_analysis`，改写为"统计昨日各 wan_name 的总 up_bytes+down_bytes，生成柱状图"
2. `planner` → 规划 1 个子任务：查 `sessions` 表按 `wan_name` 聚合流量
3. `sql_engineer` → 生成 Python 脚本（含时间过滤、GROUP BY wan_name）
4. `code_reviewer` → 审查通过
5. `script_runner` → 执行，输出 ECharts 柱状图
6. `summarizer` → "教育网-万兆流量占比最高（约 35%），移动-代拨系列合计约 20%"

**系统输出：** ECharts 交互柱状图 + 3 条关键洞察文字

---

### 意图识别演示

| 用户输入 | 识别意图 | 处理路径 |
|----------|----------|----------|
| "分析昨天各出口流量" | `data_analysis` | 完整 Pipeline |
| "sessions 表有哪些字段" | `knowledge_qa` | knowledge_agent |
| "你好，你是什么系统" | `chitchat` | chitchat_agent |
| "帮我看看最近有没有异常流量" | `data_analysis` | 完整 Pipeline + clarifier 追问 |

---

### 澄清机制演示

**用户输入：** "分析一下流量"

**系统返回：**
> 您想分析哪个维度的流量？
> - A. 按出口线路（wan_name）统计
> - B. 按应用类型（appid）统计
> - C. 按地理目标（dst_pos_country）统计
> - D. 按时间趋势（小时级）统计

意图不清晰时主动澄清，而不是乱猜一个 SQL 执行。

---

## 六、技术选型总结

| 组件 | 技术 | 理由 |
|------|------|------|
| Pipeline 编排 | LangGraph | 条件路由、状态机、重试循环表达清晰 |
| 后端框架 | FastAPI + WebSocket | 异步支持好，流式推送天然适配 |
| 前端图表 | ECharts | 交互性强，JSON 配置易于 LLM 生成 |
| 对话历史 | SQLite | 轻量，无需额外依赖 |
| 数据库 | ClickHouse | 列式存储，百亿条聚合查询秒级响应 |
| LLM | Qwen2.5:72B（本地 Ollama）| 兼容 OpenAI 格式，可换任意模型 |

---

## 七、项目结构

```
AIops/
├── backend/
│   ├── agents/
│   │   ├── intent_router.py   # 意图分类 + 问题改写
│   │   ├── clarifier.py       # 澄清追问
│   │   ├── planner.py         # 任务分解
│   │   ├── sql_engineer.py    # 脚本生成
│   │   ├── code_reviewer.py   # 安全审查
│   │   ├── script_runner.py   # 脚本执行
│   │   ├── summarizer.py      # 报告生成
│   │   ├── knowledge_agent.py # 文档问答
│   │   └── chitchat_agent.py  # 闲聊回复
│   ├── graph/
│   │   └── pipeline.py        # LangGraph 流水线
│   ├── db/
│   │   ├── clickhouse.py      # 查询层（含安全校验）
│   │   └── sqlite.py          # 对话历史
│   └── api/
│       └── chat.py            # WebSocket 接口
└── frontend/
    └── src/components/
        ├── ChatPanel.tsx
        ├── ChartRenderer.tsx  # ECharts / image / HTML 三模式
        └── SessionSidebar.tsx # 历史会话切换
```

---

## 八、测试覆盖

19 个单元测试，覆盖：

- 配置加载
- SQL 安全校验（非 SELECT 拦截、时间条件注入）
- 并行执行逻辑
- 各 Agent 核心逻辑（intent_router、planner、sql_engineer 等）
- LangGraph 流水线路由（data_analysis / knowledge_qa / chitchat 三条路径）
- 对话历史 API

连接 ClickHouse 的集成测试在网络不可达时自动跳过，不影响 CI。

---

*项目地址：`/Users/daiyutong/PycharmProjects/AIops`*
