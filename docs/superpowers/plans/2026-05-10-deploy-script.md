# Deploy Script Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a single `start.sh` at the project root that starts both frontend and backend with colored output, dependency checks, and clean Ctrl+C shutdown.

**Architecture:** One bash script with two modes (`dev` and `prod`). Uses a background-process polling loop (macOS bash 3.2 has no `wait -n`) to detect when any child exits, then kills all children via a `trap`-registered cleanup function. Production mode runs `npm run build` before starting services.

**Tech Stack:** bash 3.2 (macOS default), uvicorn, npm/vite

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `start.sh` | Full deploy script |

---

## Task 1: Create `start.sh` with dependency checks and color helpers

**Files:**
- Create: `start.sh`

- [ ] **Step 1: Create `start.sh` with the skeleton**

```bash
cat > /path/to/AIops/start.sh << 'HEREDOC'
#!/usr/bin/env bash
set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Resolve project root regardless of where script is called from
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

MODE="${1:-dev}"

print_header() {
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  AIops 一键启动脚本${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
}

check_deps() {
    local ok=1
    if [ ! -d "frontend/node_modules" ]; then
        echo -e "${YELLOW}⚠️  未找到 frontend/node_modules${NC}"
        echo -e "   请先运行: ${GREEN}cd frontend && npm install${NC}"
        ok=0
    fi
    if [ ! -d "backend/.venv" ]; then
        echo -e "${YELLOW}⚠️  未找到 backend/.venv${NC}"
        echo -e "   请先运行: ${GREEN}python3 -m venv backend/.venv && backend/.venv/bin/pip install -r requirements.txt${NC}"
        ok=0
    fi
    if [ "$ok" -eq 0 ]; then
        echo -e "\n${RED}❌ 请先安装依赖后重试${NC}\n"
        exit 1
    fi
}

# Track child PIDs
PIDS=()

cleanup() {
    echo -e "\n${YELLOW}正在停止所有服务...${NC}"
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    # Wait briefly for graceful shutdown
    sleep 1
    for pid in "${PIDS[@]}"; do
        kill -9 "$pid" 2>/dev/null || true
    done
    echo -e "${GREEN}✅ 所有服务已停止${NC}\n"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Poll until any PID in PIDS exits, then cleanup
wait_any() {
    while true; do
        for pid in "${PIDS[@]}"; do
            if ! kill -0 "$pid" 2>/dev/null; then
                echo -e "\n${RED}❌ 进程 $pid 已意外退出${NC}"
                cleanup
            fi
        done
        sleep 1
    done
}

print_header
check_deps

if [ "$MODE" = "prod" ]; then
    echo -e "${BLUE}🚀 生产模式启动中...${NC}\n"

    echo -e "${YELLOW}🔨 正在构建前端...${NC}"
    if ! (cd frontend && npm run build); then
        echo -e "\n${RED}❌ 前端构建失败，请检查上方错误信息${NC}\n"
        exit 1
    fi
    echo -e "${GREEN}✅ 前端构建完成${NC}\n"

    (cd backend && .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 2>&1 | sed "s/^/[后端] /") &
    PIDS+=($!)

    (cd frontend && npm run preview 2>&1 | sed "s/^/[前端] /") &
    PIDS+=($!)

    echo -e "${GREEN}✅ 后端 API  → http://localhost:8000${NC}"
    echo -e "${GREEN}✅ 前端预览  → http://localhost:4173${NC}"

else
    echo -e "${BLUE}🚀 开发模式启动中...${NC}\n"

    (cd backend && .venv/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000 2>&1 | sed "s/^/[后端] /") &
    PIDS+=($!)

    (cd frontend && npm run dev 2>&1 | sed "s/^/[前端] /") &
    PIDS+=($!)

    echo -e "${GREEN}✅ 后端运行中 → http://localhost:8000${NC}"
    echo -e "${GREEN}✅ 前端运行中 → http://localhost:5173${NC}"
fi

echo -e "\n${YELLOW}按 Ctrl+C 停止所有服务${NC}\n"

wait_any
HEREDOC
```

Actually, write the file directly (not via heredoc) to avoid quoting issues. Create `start.sh` at `/Users/daiyutong/PycharmProjects/AIops/start.sh` with this exact content:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

MODE="${1:-dev}"

print_header() {
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  AIops 一键启动脚本${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
}

check_deps() {
    local ok=1
    if [ ! -d "frontend/node_modules" ]; then
        echo -e "${YELLOW}⚠️  未找到 frontend/node_modules${NC}"
        echo -e "   请先运行: ${GREEN}cd frontend && npm install${NC}"
        ok=0
    fi
    if [ ! -d "backend/.venv" ]; then
        echo -e "${YELLOW}⚠️  未找到 backend/.venv${NC}"
        echo -e "   请先运行: ${GREEN}python3 -m venv backend/.venv && backend/.venv/bin/pip install -r requirements.txt${NC}"
        ok=0
    fi
    if [ "$ok" -eq 0 ]; then
        echo -e "\n${RED}❌ 请先安装依赖后重试${NC}\n"
        exit 1
    fi
}

PIDS=()

cleanup() {
    echo -e "\n${YELLOW}正在停止所有服务...${NC}"
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    sleep 1
    for pid in "${PIDS[@]}"; do
        kill -9 "$pid" 2>/dev/null || true
    done
    echo -e "${GREEN}✅ 所有服务已停止${NC}\n"
    exit 0
}

trap cleanup SIGINT SIGTERM

wait_any() {
    while true; do
        for pid in "${PIDS[@]}"; do
            if ! kill -0 "$pid" 2>/dev/null; then
                echo -e "\n${RED}❌ 进程 $pid 已意外退出${NC}"
                cleanup
            fi
        done
        sleep 1
    done
}

print_header
check_deps

if [ "$MODE" = "prod" ]; then
    echo -e "${BLUE}🚀 生产模式启动中...${NC}\n"

    echo -e "${YELLOW}🔨 正在构建前端...${NC}"
    if ! (cd frontend && npm run build); then
        echo -e "\n${RED}❌ 前端构建失败，请检查上方错误信息${NC}\n"
        exit 1
    fi
    echo -e "${GREEN}✅ 前端构建完成${NC}\n"

    (cd backend && .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 2>&1 | sed "s/^/[后端] /") &
    PIDS+=($!)

    (cd frontend && npm run preview 2>&1 | sed "s/^/[前端] /") &
    PIDS+=($!)

    echo -e "${GREEN}✅ 后端 API  → http://localhost:8000${NC}"
    echo -e "${GREEN}✅ 前端预览  → http://localhost:4173${NC}"

else
    echo -e "${BLUE}🚀 开发模式启动中...${NC}\n"

    (cd backend && .venv/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000 2>&1 | sed "s/^/[后端] /") &
    PIDS+=($!)

    (cd frontend && npm run dev 2>&1 | sed "s/^/[前端] /") &
    PIDS+=($!)

    echo -e "${GREEN}✅ 后端运行中 → http://localhost:8000${NC}"
    echo -e "${GREEN}✅ 前端运行中 → http://localhost:5173${NC}"
fi

echo -e "\n${YELLOW}按 Ctrl+C 停止所有服务${NC}\n"

wait_any
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x /Users/daiyutong/PycharmProjects/AIops/start.sh
```

- [ ] **Step 3: Test dependency check (missing node_modules)**

Temporarily rename node_modules to verify the check fires:

```bash
cd /Users/daiyutong/PycharmProjects/AIops
mv frontend/node_modules frontend/node_modules_bak
bash start.sh
# Expected: yellow warning about missing node_modules, exits with code 1
mv frontend/node_modules_bak frontend/node_modules
```

Expected output contains:
```
⚠️  未找到 frontend/node_modules
   请先运行: cd frontend && npm install
❌ 请先安装依赖后重试
```

- [ ] **Step 4: Test that the script starts (syntax check)**

```bash
bash -n /Users/daiyutong/PycharmProjects/AIops/start.sh
```

Expected: no output (syntax OK).

- [ ] **Step 5: Commit**

```bash
cd /Users/daiyutong/PycharmProjects/AIops
git add start.sh
git commit -m "feat: add one-click start script for dev and prod modes"
```

---

## Task 2: Smoke test dev mode startup

**Files:**
- No changes — verification only

- [ ] **Step 1: Start in dev mode and verify both processes launch**

```bash
cd /Users/daiyutong/PycharmProjects/AIops
./start.sh &
SCRIPT_PID=$!
sleep 8
```

- [ ] **Step 2: Check backend is responding**

```bash
curl -s http://localhost:8000/api/v1/health | head -c 200
```

Expected: JSON response (e.g. `{"status":"ok"}` or similar). If the health endpoint returns anything other than a connection error, the backend started successfully.

- [ ] **Step 3: Check frontend is serving**

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:5173
```

Expected: `200`

- [ ] **Step 4: Kill the script and verify cleanup**

```bash
kill -SIGINT $SCRIPT_PID
sleep 3
# Verify nothing is left on ports 8000 and 5173
lsof -i :8000 -i :5173 | grep LISTEN || echo "Ports are clean"
```

Expected: `Ports are clean` (no processes holding the ports).

- [ ] **Step 5: No commit needed** — this is a verification-only task.

---

## Task 3: Smoke test prod mode startup

**Files:**
- No changes — verification only

- [ ] **Step 1: Start in prod mode**

```bash
cd /Users/daiyutong/PycharmProjects/AIops
./start.sh prod &
SCRIPT_PID=$!
# Wait for build + startup (up to 60s)
sleep 30
```

- [ ] **Step 2: Check backend**

```bash
curl -s http://localhost:8000/api/v1/health | head -c 200
```

Expected: JSON health response (not a connection error).

- [ ] **Step 3: Check frontend preview**

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:4173
```

Expected: `200`

- [ ] **Step 4: Kill and verify cleanup**

```bash
kill -SIGINT $SCRIPT_PID
sleep 3
lsof -i :8000 -i :4173 | grep LISTEN || echo "Ports are clean"
```

Expected: `Ports are clean`

- [ ] **Step 5: No commit needed** — verification only.
