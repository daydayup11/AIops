# 校园网流量分析助手

基于自然语言的校园网流量分析系统。用户通过对话描述分析需求，系统自动查询 ClickHouse 数据库并以图表形式返回结果。

## 功能特性

- **自然语言驱动**：直接用中文描述想分析的内容，无需手写 SQL
- **智能澄清**：意图不明确时自动提问，最多 2 轮确认后执行
- **三 Agent 流水线**：Planner（方案设计）→ SQL Engineer（SQL 生成优化）→ Visualizer（可视化渲染）
- **并行查询**：多个子任务并行执行，实时 WebSocket 推送进度
- **双模式可视化**：简单图表直接渲染为 ECharts，复杂看板生成可交互 HTML
- **SQL 安全防护**：拦截所有非 SELECT 语句，强制时间条件防止全表扫描
- **对话历史**：SQLite 持久化对话记录，支持切换历史会话

## 技术架构

```
前端 (React + ECharts)
        │ WebSocket
后端 (FastAPI)
        │
LangGraph Pipeline
  ├── Planner Agent      ← LLM 理解意图，分解子任务
  ├── SQL Engineer Agent ← LLM 生成 SQL，Python 做安全优化
  └── Visualizer Agent   ← LLM 决定图表类型，Python 渲染
        │
ThreadPoolExecutor（并行 SQL 执行）
        │
ClickHouse (logdb) + SQLite (对话历史)
```

## 数据源

连接校园网网关设备采集的 ClickHouse 数据库，主要包含：

| 表 | 内容 | 数据量 |
|----|------|--------|
| `sessions` | 网络会话五元组及流量 | 364 亿条 |
| `npm` | 网络性能（延迟/重传） | 375 亿条 |
| `dns` | DNS 查询日志 | 34 亿条 |
| `url` | HTTP/HTTPS 访问日志 | 26 亿条 |
| `iplog` | 按 IP 聚合的流量统计 | 10 亿条 |
| `wanlog` | WAN 出口带宽统计 | 119 万条 |
| `applog` | 应用流量汇总 | 3330 万条 |
| `event` | 应用登录事件（QQ/微信等） | 1.9 亿条 |
| `usrauth` | 用户认证记录 | 14 万条 |

## 快速开始

### 环境要求

- Python 3.9+
- Node.js 18+
- 可访问 ClickHouse 实例
- 兼容 OpenAI 格式的 LLM 服务（本地 ollama 或远程 API）

### 后端

```bash
# 安装依赖
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 编辑配置
vim ../config/settings.yaml

# 启动服务
uvicorn main:app --reload --port 8000
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173

### 配置文件

编辑 `config/settings.yaml`：

```yaml
clickhouse:
  host: "10.161.111.100"   # ClickHouse 地址
  port: 9000
  user: "sesslog"
  password: "your_password"
  database: "logdb"
  connect_timeout: 30
  query_timeout: 30        # 单条 SQL 超时秒数
  max_connections: 10

llm:
  base_url: "http://localhost:11434/v1"  # LLM API 地址（兼容 OpenAI 格式）
  api_key: "ollama"
  model: "qwen2.5:72b"                   # 模型名称
  temperature: 0.1

server:
  host: "0.0.0.0"
  port: 8000

executor:
  max_workers: 5           # 并行 SQL 最大线程数
  retry_time_shrink: 0.5   # 超时重试时缩小时间窗口比例

cache:
  ttl_seconds: 300         # 查询结果缓存时间
```

## 项目结构

```
AIops/
├── backend/
│   ├── main.py               # FastAPI 入口
│   ├── config.py             # 配置加载
│   ├── agents/
│   │   ├── planner.py        # Planner Agent：意图识别 + 任务分解
│   │   ├── sql_engineer.py   # SQL Engineer Agent：SQL 生成 + 安全优化
│   │   └── visualizer.py     # Visualizer Agent：图表/HTML 渲染
│   ├── graph/
│   │   └── pipeline.py       # LangGraph 流水线定义
│   ├── db/
│   │   ├── clickhouse.py     # ClickHouse 查询层（含 SQL 安全校验）
│   │   ├── sqlite.py         # 对话历史存储
│   │   └── schema.py         # 表结构描述（供 LLM 参考）
│   ├── executor/
│   │   └── parallel.py       # 并行 SQL 执行 + 降级处理
│   ├── api/
│   │   ├── chat.py           # WebSocket /api/v1/chat
│   │   └── health.py         # GET /api/v1/health|sessions
│   └── models/
│       └── schemas.py        # Pydantic 数据模型
├── frontend/
│   └── src/
│       ├── App.tsx
│       ├── types.ts
│       ├── hooks/
│       │   └── useWebSocket.ts
│       └── components/
│           ├── ChatPanel.tsx
│           ├── ChartRenderer.tsx
│           ├── ProgressBar.tsx
│           ├── InputBar.tsx
│           └── SessionSidebar.tsx
├── config/
│   └── settings.yaml
└── data/
    ├── aiops.db             # SQLite 对话历史
    └── renders/             # HTML 可视化文件
```

## API 接口

### WebSocket 对话

```
WS /api/v1/chat

发送：{"session_id": "uuid", "message": "分析昨天各出口线路的流量分布"}

接收（流式）：
{"type": "progress", "content": "正在分析您的问题..."}
{"type": "clarify",  "content": "请问需要哪个时间粒度？小时/天"}
{"type": "progress", "content": "2/3 完成 (66%)"}
{"type": "result",   "content": {...}, "render": "echarts"}
{"type": "result",   "content": "<html>...", "render": "html"}
{"type": "done",     "content": "分析完成"}
```

### REST 接口

```
GET /api/v1/health              # 健康检查
GET /api/v1/sessions            # 历史对话列表
GET /api/v1/sessions/{id}       # 指定会话的消息记录
```

## 运行测试

```bash
cd backend
python -m pytest tests/ -v
```

19 个单元测试，覆盖配置加载、SQL 安全校验、并行执行、Agent 逻辑、LangGraph 流水线。连接 ClickHouse 的测试在网络不可达时自动跳过。

## SQL 安全机制

- 只允许 `SELECT` 语句，拦截 `INSERT/UPDATE/DELETE/DROP/CREATE/ALTER` 等
- 所有查询强制注入时间条件（防止全表扫描数百亿条记录）
- 大表（sessions/npm/dns/url）自动添加 `LIMIT 10000`
- 时间范围超过 7 天的查询建议按天分片执行
