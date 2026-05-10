# Deploy Script Design

Date: 2026-05-10

## Overview

A single `start.sh` at the project root that starts both frontend and backend with one command. Designed for humans unfamiliar with the project ("傻瓜脚本"): colored output, clear error messages, clean shutdown.

## Usage

```bash
./start.sh        # development mode
./start.sh prod   # production mode
```

## File Structure

```
project-root/
└── start.sh      # new file, chmod +x
```

No other files created or modified.

## Dependency Checks

Before starting any process, the script checks:

1. `frontend/node_modules` exists — if not: print yellow warning `"请先在 frontend/ 目录运行: npm install"` and exit 1
2. `backend/.venv` exists — if not: print yellow warning `"请先运行: python -m venv backend/.venv && backend/.venv/bin/pip install -r requirements.txt"` and exit 1

## Development Mode (`./start.sh`)

1. Print blue header: `🚀 AIops 开发模式启动中...`
2. Start backend in background:
   ```bash
   cd backend && ../backend/.venv/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```
3. Start frontend in background:
   ```bash
   cd frontend && npm run dev
   ```
4. Print green status:
   ```
   ✅ 后端运行中 → http://localhost:8000
   ✅ 前端运行中 → http://localhost:5173
   按 Ctrl+C 停止所有服务
   ```
5. `wait -n`: block until either process exits, then trigger cleanup

## Production Mode (`./start.sh prod`)

1. Print blue header: `🚀 AIops 生产模式启动中...`
2. Build frontend:
   ```bash
   cd frontend && npm run build
   ```
   - On failure: print red error `"前端构建失败，请检查上方错误信息"` and exit 1
   - On success: print green `"✅ 前端构建完成"`
3. Start backend in background (no `--reload`):
   ```bash
   cd backend && ../backend/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
   ```
4. Start frontend preview in background:
   ```bash
   cd frontend && npm run preview
   ```
5. Print green status:
   ```
   ✅ 后端 API → http://localhost:8000
   ✅ 前端预览 → http://localhost:4173
   按 Ctrl+C 停止所有服务
   ```
6. `wait -n` + cleanup (same as dev mode)

## Process Management

```bash
# All child PIDs collected into array
PIDS=()

# Trap Ctrl+C and any child exit
cleanup() {
    echo -e "\n${YELLOW}正在停止所有服务...${NC}"
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null
    done
    wait "${PIDS[@]}" 2>/dev/null
    echo -e "${GREEN}所有服务已停止${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

# After starting processes:
wait -n "${PIDS[@]}"   # returns when any one exits
cleanup                 # kill the rest
```

`wait -n` requires bash 4.3+. macOS ships bash 3.2 — use a polling loop fallback if needed (see implementation note below).

## Color Scheme

| Color | Usage | Code |
|-------|-------|------|
| Blue (`\033[0;34m`) | Section headers | `🚀 启动中...` |
| Green (`\033[0;32m`) | Success messages | `✅ 运行中` |
| Yellow (`\033[0;33m`) | Warnings, prompts | dependency missing |
| Red (`\033[0;31m`) | Errors | build failed |
| Reset (`\033[0m`) | After every colored string | `NC` |

## Implementation Note: macOS bash 3.2 Compatibility

macOS default bash is 3.2 (no `wait -n`). The script must handle this:

```bash
# Poll until any PID in PIDS array exits
while true; do
    for pid in "${PIDS[@]}"; do
        if ! kill -0 "$pid" 2>/dev/null; then
            cleanup
        fi
    done
    sleep 1
done
```

Use `#!/usr/bin/env bash` shebang. If user has bash 4+ (via Homebrew), `wait -n` works. Otherwise the poll loop handles it.

## Out of Scope

- Windows support
- Docker / containerization
- Automatic `npm install` or `pip install` (user must do this once manually)
- Port conflict detection
- Daemon / background service mode
