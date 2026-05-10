# 校园网流量分析助手 设计文档

**日期**：2026-05-10  
**项目**：AIops  
**数据库**：ClickHouse `logdb`（10.161.111.100:9000）

---

## 一、项目概述

校园网流量分析助手，用户通过自然语言提问，系统自动分析 ClickHouse 中的校园网流量数据，以图表或 HTML 可视化形式返回结果。同时提供 Web 界面（面向网络管理员和学校管理层）。

**核心特性：**
- 自然语言驱动，意图识别模式（不直接 Text-to-SQL）
- LangGraph 三 Agent 流水线编排
- 并行 SQL 执行 + 实时进度推送
- SQL 结果不经过 LLM，避免超长上下文
- 支持 ECharts 图表和 HTML 可视化两种展示形式

---

## 二、整体架构

```
┌─────────────────────────────────────────────────────┐
│                   前端 (React)                       │
│  对话界面 | 图表看板 | 报表展示                        │
└──────────────────┬──────────────────────────────────┘
                   │ WebSocket
┌──────────────────▼──────────────────────────────────┐
│               后端 (FastAPI)                         │
│                                                      │
│  ┌─────────────────────────────────────────────┐    │
│  │         LangGraph 三 Agent 流水线             │    │
│  │  Planner → SQL Engineer → Visualizer        │    │
│  └─────────────────────────────────────────────┘    │
│                                                      │
│  ┌──────────────────────────────────────────────┐   │
│  │      并行执行层（ThreadPoolExecutor）           │   │
│  │      ClickHouse 连接池 + 查询结果缓存           │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
                   │
        ┌──────────▼──────────┐    ┌─────────────┐
        │   ClickHouse DB     │    │  SQLite DB  │
        │   logdb             │    │  对话历史    │
        └─────────────────────┘    └─────────────┘
```

---

## 三、LangGraph 三 Agent 流水线

### 完整流程

```
用户提问
    │
    ▼
┌──────────────────────────────────────────────────────┐
│           Agent 1: Planner（方案设计）                  │
│  clarify → 分解子任务 → 确定数据表和维度                 │
│  LLM输入：用户问题 + 表结构定义                          │
│  LLM输出：任务列表 + 每个任务的数据需求                   │
└──────────────────────┬───────────────────────────────┘
                       │ 任务列表
                       ▼
┌──────────────────────────────────────────────────────┐
│           Agent 2: SQL Engineer（SQL生成+优化）          │
│  LLM输入：任务描述 + 表字段定义                          │
│  LLM输出：参数化 SQL 模板                               │
│  Python执行：时间分片 / LIMIT保护 / 强制时间条件优化      │
│  支持两类SQL：预定义分析模板 + LLM直接生成任意SELECT       │
│  安全边界：只允许SELECT，拦截DDL/DML，强制时间条件         │
│  并行执行：ThreadPool → DataFrame列表                   │
│  WebSocket：实时进度推送                                │
│  降级：超时缩窗口重试 → 部分结果 + 说明                   │
└──────────────────────┬───────────────────────────────┘
                       │ DataFrame列表（全量，不过LLM）
                       ▼
┌──────────────────────────────────────────────────────┐
│           Agent 3: Visualizer（可视化）                  │
│  LLM输入：DataFrame结构(columns+dtypes) + 任务描述      │
│  LLM输出：可视化方案（图表类型 + 字段映射 + 洞察标注）     │
│  Python执行：DataFrame → 图表                          │
│                                                      │
│  ECharts JSON 模式：单图/简单图表，前端直接渲染           │
│  HTML 可视化模式：多图联动/复杂看板，iframe 嵌入展示      │
└──────────────────────────────────────────────────────┘
```

### Agent 节点说明

| Agent | LLM 输入 | LLM 输出 | 备注 |
|-------|----------|----------|------|
| Planner | 用户问题 + 表结构 | 任务列表 + 澄清问题 | 最多 2 轮澄清 |
| SQL Engineer | 任务描述 + 表字段 | SQL 语句 + 预估耗时 | Python 做优化和执行 |
| Visualizer | DataFrame 结构 + 任务描述 | 可视化方案 JSON | Python 做实际渲染 |

### SQL 优化策略

| 风险场景 | 优化手段 |
|----------|----------|
| 时间范围 > 7天 的 sessions 查询 | 按天分片，并行执行后聚合 |
| 无时间条件的查询 | 强制注入 `WHERE start >= now()-interval 1 day` |
| 复杂 JOIN | 改写为子查询或分步查询 |
| 结果集过大 | 自动加 `LIMIT 10000`，告知用户已截断 |

### 失败降级策略

- 子任务超时（默认 30s）→ 缩小时间窗口至 50% 重试一次
- 重试仍失败 → 返回已成功的部分结果，标注"XX 数据获取失败"
- 全部失败 → 返回错误说明 + 建议缩小查询范围

---

## 四、后端项目结构

```
AIops/
├── backend/
│   ├── main.py                    # FastAPI 入口
│   ├── config.py                  # 统一配置加载
│   ├── agents/
│   │   ├── planner.py             # Agent 1: 方案设计
│   │   ├── sql_engineer.py        # Agent 2: SQL生成+优化
│   │   └── visualizer.py          # Agent 3: 可视化
│   ├── graph/
│   │   └── pipeline.py            # LangGraph 图定义和节点编排
│   ├── db/
│   │   ├── clickhouse.py          # ClickHouse 连接池+查询执行
│   │   └── schema.py              # 表结构定义（供LLM参考）
│   ├── executor/
│   │   └── parallel.py            # ThreadPool并行执行+降级逻辑
│   ├── api/
│   │   ├── chat.py                # WebSocket /api/v1/chat
│   │   └── health.py              # GET /api/v1/health
│   └── models/
│       └── schemas.py             # Pydantic 请求/响应模型
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ChatPanel.tsx      # 对话消息流
│   │   │   ├── ChartRenderer.tsx  # ECharts/iframe 渲染
│   │   │   ├── ProgressBar.tsx    # 任务进度
│   │   │   └── SessionSidebar.tsx # 历史对话列表
│   │   └── App.tsx
│   └── package.json
├── config/
│   └── settings.yaml              # 外部配置文件
├── data/
│   ├── aiops.db                   # SQLite 数据库
│   └── renders/                   # HTML 可视化文件
│       └── {session_id}/
│           └── {message_id}.html
└── docs/
    └── campus_network_data_summary.md
```

---

## 五、配置文件

`config/settings.yaml`：

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
  base_url: "http://..."
  api_key: "..."
  model: "..."
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

---

## 六、API 接口

### WebSocket 对话接口

```
WS /api/v1/chat

客户端发送：
{
  "session_id": "uuid",
  "message": "分析昨天各出口线路的流量分布"
}

服务端推送（流式）：
{"type": "clarify",  "content": "请问需要哪个时间粒度？小时/天"}
{"type": "progress", "content": "预计15秒，共3个子任务"}
{"type": "progress", "content": "2/3 完成 (66%)", "elapsed": 8}
{"type": "result",   "content": {...}, "render": "echarts"}
{"type": "result",   "content": "<html>...</html>", "render": "html"}
{"type": "error",    "content": "wan_quality查询超时，已返回部分结果"}
```

### 基础接口

```
GET /api/v1/health            # 健康检查
GET /api/v1/sessions          # 历史对话列表
GET /api/v1/sessions/{id}     # 对话历史记录
```

---

## 七、存储方案

| 数据 | 存储 | 说明 |
|------|------|------|
| 对话历史 | SQLite | 持久化，结构化 |
| LangGraph 状态 | SQLite Checkpointer | LangGraph 内置 |
| SQL 查询结果缓存 | 内存（cachetools） | TTL 5分钟 |
| HTML 可视化文件 | 本地文件系统 | `data/renders/` |
| 配置 | settings.yaml | 启动加载 |

### SQLite 表结构

```sql
CREATE TABLE sessions (
    id          TEXT PRIMARY KEY,
    title       TEXT,
    created_at  DATETIME,
    updated_at  DATETIME
);

CREATE TABLE messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT,
    role        TEXT,      -- user / assistant
    type        TEXT,      -- text / echarts / html / progress / error
    content     TEXT,
    created_at  DATETIME,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);
```

---

## 八、前端设计

**技术栈：** React 18 + TypeScript + ECharts + Tailwind CSS + Vite

**布局：**

```
┌─────────────────────────────────────────────────────┐
│  校园网流量分析助手                          [设置⚙]  │
├─────────────────┬───────────────────────────────────┤
│  历史对话列表    │         主工作区                   │
│                 │                                   │
│  ○ 昨日流量分析  │  对话消息流                        │
│  ○ 出口质量对比  │  （文本/澄清选项/进度条/图表混合）    │
│  ○ Top用户查询  │                                   │
│                 │  ████████░░░░ 66% 2/3任务          │
│                 │                                   │
│                 │  ┌─────────────────────┐          │
│                 │  │  ECharts / HTML      │          │
│                 │  └─────────────────────┘          │
│                 │                                   │
│                 │  ┌───────────────┐  [发送↑]        │
│                 │  │  输入分析问题  │                 │
│                 │  └───────────────┘                │
└─────────────────┴───────────────────────────────────┘
```

**核心组件：**

| 组件 | 职责 |
|------|------|
| `ChatPanel` | 对话消息流，支持文本/澄清/进度/图表混合展示 |
| `ProgressBar` | 实时任务进度，显示预计时间和完成数 |
| `ChartRenderer` | 根据 render 类型选择 ECharts 或 iframe HTML |
| `SessionSidebar` | 历史对话列表，支持切换 |

---

## 九、数据源参考

核心表：`sessions`（364亿条）、`npm`（375亿条）、`dns`（34亿条）、`url`（26亿条）、`iplog`（10亿条）、`wanlog`、`usrauth`、`applog`、`event`

详见：`docs/campus_network_data_summary.md`
