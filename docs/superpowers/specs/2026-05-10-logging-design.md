# Logging System Design

Date: 2026-05-10

## Overview

Add structured logging to the AIops backend using Python's standard `logging` module. A single `backend/logger.py` module centralizes configuration. All other modules obtain loggers via `logging.getLogger(__name__)`. `main.py` calls `setup_logging()` once at startup.

Goals:
- Console: human-readable plaintext for development
- File: JSON per line for production troubleshooting
- Level controlled by `LOG_LEVEL` environment variable

## Architecture

### New file: `backend/logger.py`

Exports one function: `setup_logging()`. Called once in `main.py` before the app starts.

Responsibilities:
1. Read `LOG_LEVEL` env var (default: `INFO`)
2. Read `LOG_FILE` env var (default: `logs/app.json`; empty string disables file logging)
3. Configure root logger with two handlers:
   - `StreamHandler` → plaintext formatter → stdout
   - `RotatingFileHandler` → JSON formatter → `LOG_FILE` (10MB max, 5 backups)

### New directory: `backend/logs/`

Created at runtime. Added to `.gitignore`.

### Modified files

| File | Change |
|---|---|
| `main.py` | Call `setup_logging()` at module top |
| `api/chat.py` | Add logger; log connect/disconnect/messages/errors |
| `graph/pipeline.py` | Add logger; log node entry/exit with timing |
| `agents/planner.py` | Add logger; log LLM output and parse failures |
| `agents/sql_engineer.py` | Add logger; log generated SQL count and parse failures |
| `executor/parallel.py` | Add logger; log task start/completion/timing |
| `db/clickhouse.py` | Add logger; log SQL, timing, row count, security blocks |

## Log Content by Module

### `api/chat.py`
| Level | Event |
|---|---|
| `INFO` | WebSocket connected (client address) |
| `INFO` | WebSocket disconnected |
| `INFO` | Message received (session_id, message length) |
| `INFO` | Response sent (session_id, type) |
| `ERROR` | Unexpected exception (non-WebSocketDisconnect) |

### `graph/pipeline.py`
| Level | Event |
|---|---|
| `DEBUG` | Node entered (node name) |
| `DEBUG` | Node exited (node name, elapsed ms) |
| `INFO` | Clarification triggered (question content) |
| `ERROR` | Node raised exception |

### `agents/planner.py`
| Level | Event |
|---|---|
| `INFO` | Task plan generated (task count) |
| `DEBUG` | Raw LLM response content |
| `WARNING` | JSON parse failed, returning clarification fallback |
| `ERROR` | LLM call raised exception |

### `agents/sql_engineer.py`
| Level | Event |
|---|---|
| `INFO` | SQL tasks generated (count) |
| `DEBUG` | Raw LLM response content |
| `WARNING` | JSON parse failed, returning empty list |
| `ERROR` | LLM call raised exception |

### `executor/parallel.py`
| Level | Event |
|---|---|
| `INFO` | Starting parallel execution (N tasks, max_workers) |
| `INFO` | All tasks complete (elapsed ms) |
| `DEBUG` | Single task complete (task_id, status, elapsed ms, row count if success) |
| `ERROR` | Single task failed (task_id, error message) |

### `db/clickhouse.py`
| Level | Event |
|---|---|
| `DEBUG` | Executing SQL (first 200 chars) |
| `DEBUG` | Query complete (elapsed ms, row count) |
| `WARNING` | SQL security block (SQLSecurityError, first 60 chars of SQL) |
| `ERROR` | ClickHouse driver exception |

## Log Formats

### Console (plaintext)

```
%(asctime)s %(levelname)-8s %(name)-20s %(message)s
```

Example:
```
2026-05-10 14:23:01 INFO     agents.planner       生成任务数: 2
2026-05-10 14:23:02 DEBUG    db.clickhouse        SQL执行耗时: 1.23s, 返回行数: 4821
2026-05-10 14:23:02 ERROR    api.chat             WebSocket异常: Connection reset
```

### File (JSON, one object per line)

Fields: `ts`, `level`, `logger`, `msg`

Example:
```json
{"ts": "2026-05-10T14:23:01", "level": "INFO", "logger": "agents.planner", "msg": "生成任务数: 2"}
```

## Configuration

| Env Var | Default | Description |
|---|---|---|
| `LOG_LEVEL` | `INFO` | One of `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `LOG_FILE` | `logs/app.json` | Path to JSON log file; set to empty string to disable |

## File Rotation

`RotatingFileHandler` with:
- `maxBytes`: 10 MB
- `backupCount`: 5 (files: `app.json.1` through `app.json.5`)

## `.gitignore` Addition

```
backend/logs/
```

## Out of Scope

- Per-module log level control (not needed given standard 4-level approach)
- External log aggregation (ELK, Loki) — file JSON format makes future integration straightforward
- `session_id` context propagation across all log lines (can be added later with `structlog` if needed)
