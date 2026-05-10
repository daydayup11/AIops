# Intent Router 设计文档

**日期**：2026-05-10  
**状态**：待实现

## 背景

现有系统对所有用户提问统一走 `clarifier → planner → sql_engineer → ...` 的 LangGraph 流水线。  
用户提问实际上分为多种类型（数据分析、知识问答、闲聊），统一走 SQL 分析流水线会导致不必要的 LLM 调用和错误的处理逻辑。

## 目标

在现有流水线入口前加入意图路由器（intent router），由 LLM 判断用户提问类型，分发到对应的处理流程。

---

## 意图分类

| 意图 | 标签 | 说明 | 兜底行为 |
|---|---|---|---|
| 数据分析 | `data_analysis` | 查数据库、统计、排行、趋势、异常检测 | — |
| 知识问答 | `knowledge_qa` | 询问系统本身、数据来源、字段含义、使用说明 | — |
| 闲聊 | `chitchat` | 问候、闲聊、与数据无关的随意对话 | — |
| 未知 | `unknown` | 无法判断 | 走 data_analysis |

---

## 整体架构

```
[user message]
      ↓
 intent_router          ← LLM 判断意图 + 改写问题
      ↓ (按 intent 分支)
 ┌──────────┬──────────┬──────────────┐
 ↓          ↓          ↓              ↓
data       knowledge  chitchat      unknown
analysis   _qa                    (→ data_analysis)
 ↓          ↓          ↓
clarifier  knowledge  chitchat
(现有)     _agent     _agent
 ↓
(现有流水线不变)
```

---

## intent_router Agent

**文件**：`backend/agents/intent_router.py`

### 输出格式（严格 JSON）

```json
{
  "intent": "data_analysis" | "knowledge_qa" | "chitchat" | "unknown",
  "rewritten_query": "改写后的标准化问题",
  "confidence": 0.0-1.0
}
```

### 改写规则

- 把口语化、模糊的问题标准化，但不改变原意
- 例：「top10会话数量的用户」→「查询会话数量最多的前10个用户」
- 例：「你的账号数据哪里来的」→「系统的账号数据来源是什么」
- 下游各节点优先使用 `rewritten_query` 而非原始 `user_message`

---

## knowledge_agent

**文件**：`backend/agents/knowledge_agent.py`

### 处理流程

1. **检索**：扫描 `docs/` 下所有 `.md` 文件，关键词匹配（当前阶段字符串匹配，后续升级为 RAG），取最相关段落作为 context
2. **澄清**（内置）：问题过于模糊时追问一次，明确后再检索
3. **生成**：LLM 基于 context + `rewritten_query` 生成回答；检索结果为空时基于 system prompt 背景知识回答并注明"未找到相关文档"

### 扩展路径

当前：docs/ md 文件关键词检索 → 后续：向量库 RAG

---

## chitchat_agent

**文件**：`backend/agents/chitchat_agent.py`

- 直接 LLM 回复，system prompt 定义角色（校园网流量分析助手）
- 保持友好简洁，不做澄清追问
- 输出通过现有 `result` 消息类型推送前端

---

## pipeline.py 改动

### 新增字段（PipelineState）

```python
intent: Optional[str]           # "data_analysis" | "knowledge_qa" | "chitchat" | "unknown"
rewritten_query: Optional[str]  # 改写后的问题，下游优先使用
intent_confidence: float
knowledge_answer: Optional[str]
chitchat_answer: Optional[str]
```

### 新节点与路由

```python
graph.set_entry_point("intent_router")   # 原 entry_point 为 "clarifier"

def route_after_intent_router(state) -> str:
    intent = state.get("intent", "unknown")
    if intent == "knowledge_qa":
        return "knowledge_agent"
    elif intent == "chitchat":
        return "chitchat_agent"
    else:  # data_analysis + unknown
        return "clarifier"
```

### 现有节点

`clarifier` 及其后续节点**完全不变**，仅将入口从 `set_entry_point` 改为由 `intent_router` 路由进入。

---

## chat.py 改动

几乎不变：
- `result_state` 中新增 `knowledge_answer` / `chitchat_answer` 字段的推送逻辑
- 两者均通过现有 `{"type": "result", "render": "text", "content": ...}` 格式推送
- **前端零改动**

---

## 文件变更清单

| 操作 | 文件 |
|---|---|
| 新增 | `backend/agents/intent_router.py` |
| 新增 | `backend/agents/knowledge_agent.py` |
| 新增 | `backend/agents/chitchat_agent.py` |
| 修改 | `backend/graph/pipeline.py` |
| 修改 | `backend/api/chat.py`（少量） |

---

## 不在本次范围内

- RAG 向量库（当前用关键词检索）
- D 类意图（待定义）
- 前端意图标签展示
