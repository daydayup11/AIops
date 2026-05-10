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

# Validate mode parameter
if [ "$MODE" != "dev" ] && [ "$MODE" != "prod" ]; then
    echo -e "${RED}用法: $0 [dev|prod]${NC}"
    exit 1
fi

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
        # Kill the entire subprocess tree
        pkill -P "$pid" 2>/dev/null || true
        kill "$pid" 2>/dev/null || true
    done
    sleep 1
    for pid in "${PIDS[@]}"; do
        pkill -9 -P "$pid" 2>/dev/null || true
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

    (cd backend && PYTHONUNBUFFERED=1 .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 2>&1 | sed "s/^/[后端] /") &
    PIDS+=($!)

    (cd frontend && npm run preview 2>&1 | sed "s/^/[前端] /") &
    PIDS+=($!)

    echo -e "${GREEN}✅ 后端 API  → http://localhost:8000${NC}"
    echo -e "${GREEN}✅ 前端预览  → http://localhost:4173${NC}"

else
    echo -e "${BLUE}🚀 开发模式启动中...${NC}\n"

    (cd backend && PYTHONUNBUFFERED=1 .venv/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000 2>&1 | sed "s/^/[后端] /") &
    PIDS+=($!)

    (cd frontend && npm run dev 2>&1 | sed "s/^/[前端] /") &
    PIDS+=($!)

    echo -e "${GREEN}✅ 后端运行中 → http://localhost:8000${NC}"
    echo -e "${GREEN}✅ 前端运行中 → http://localhost:5173${NC}"
fi

echo -e "\n${YELLOW}按 Ctrl+C 停止所有服务${NC}\n"

wait_any
