#!/bin/bash
# DevSquad 一键启动脚本 (V3.9.2)
#
# 遵循项目硬约束：环境检查 → 数据库初始化 → 前端构建 → 服务启动
#
# 用法:
#   bash scripts/start.sh              # 启动 API server (默认)
#   bash scripts/start.sh --dashboard  # 同时启动 Streamlit dashboard
#   bash scripts/start.sh --help       # 显示帮助

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  DevSquad 一键启动脚本 (V3.9.2)${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# ============================================================================
# Step 1: 环境检查 (Environment Check)
# ============================================================================
echo -e "${BLUE}[1/4] 环境检查...${NC}"

# Python 版本检查 (>=3.10)
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "0.0")
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]; }; then
    echo -e "${RED}  ✗ Python $PYTHON_VERSION 检测到，需要 Python >= 3.10${NC}"
    exit 1
fi
echo -e "${GREEN}  ✓ Python $PYTHON_VERSION${NC}"

# 依赖检查
if ! python3 -c "import fastapi, uvicorn, yaml" 2>/dev/null; then
    echo -e "${YELLOW}  ⚠ API 依赖未安装，正在安装...${NC}"
    cd "$PROJECT_ROOT"
    pip install -e ".[api]" -q
    echo -e "${GREEN}  ✓ API 依赖已安装${NC}"
else
    echo -e "${GREEN}  ✓ API 依赖已就绪${NC}"
fi

# DevSquad 包检查
if ! python3 -c "import scripts" 2>/dev/null; then
    echo -e "${YELLOW}  ⚠ DevSquad 包未安装，正在安装...${NC}"
    cd "$PROJECT_ROOT"
    pip install -e . -q
    echo -e "${GREEN}  ✓ DevSquad 包已安装${NC}"
else
    echo -e "${GREEN}  ✓ DevSquad 包已就绪${NC}"
fi

# 配置文件检查
CONFIG_PATH="$PROJECT_ROOT/config/deployment.yaml"
if [ ! -f "$CONFIG_PATH" ]; then
    echo -e "${YELLOW}  ⚠ 配置文件不存在: $CONFIG_PATH${NC}"
    echo -e "${YELLOW}    将使用默认配置（认证关闭）${NC}"
else
    echo -e "${GREEN}  ✓ 配置文件: $CONFIG_PATH${NC}"
fi

# ============================================================================
# Step 2: 数据库初始化 (Database Initialization)
# ============================================================================
echo ""
echo -e "${BLUE}[2/4] 数据库初始化...${NC}"

# 创建运行时目录（SQLite + checkpoints + data）
RUNTIME_DIRS=(
    "$PROJECT_ROOT/data"
    "$PROJECT_ROOT/data/memory-bank"
    "$PROJECT_ROOT/data/role_templates"
    "$PROJECT_ROOT/checkpoints"
    "$PROJECT_ROOT/checkpoints/checkpoints"
    "$PROJECT_ROOT/checkpoints/handoffs"
    "$PROJECT_ROOT/.devsquad_data"
)

for dir in "${RUNTIME_DIRS[@]}"; do
    if [ ! -d "$dir" ]; then
        mkdir -p "$dir"
        echo -e "${GREEN}  ✓ 创建目录: $(basename "$dir")/${NC}"
    fi
done

# 初始化 SQLite 数据库（HistoryManager 自动创建表）
cd "$PROJECT_ROOT"
if python3 -c "
import sys
sys.path.insert(0, '.')
from scripts.history_manager import HistoryManager
hm = HistoryManager()
hm.init_schema()
print('  ✓ SQLite 数据库已初始化')
" 2>/dev/null; then
    :
else
    echo -e "${YELLOW}  ⚠ SQLite 初始化跳过（HistoryManager 不可用或无需初始化）${NC}"
fi

echo -e "${GREEN}  ✓ 数据库就绪${NC}"

# ============================================================================
# Step 3: 前端构建 (Frontend Build)
# ============================================================================
echo ""
echo -e "${BLUE}[3/4] 前端构建...${NC}"

# DevSquad 使用 Streamlit dashboard，无需传统前端构建
# 检查 Streamlit 是否可用
if python3 -c "import streamlit" 2>/dev/null; then
    echo -e "${GREEN}  ✓ Streamlit 可用（dashboard 无需构建）${NC}"
    DASHBOARD_AVAILABLE=1
else
    echo -e "${YELLOW}  ⚠ Streamlit 未安装，dashboard 不可用${NC}"
    echo -e "${YELLOW}    安装: pip install streamlit${NC}"
    DASHBOARD_AVAILABLE=0
fi

# ============================================================================
# Step 4: 服务启动 (Service Startup)
# ============================================================================
echo ""
echo -e "${BLUE}[4/4] 服务启动...${NC}"

# 解析参数
START_DASHBOARD=0
PORT_API="${DEVSQUAD_API_PORT:-8000}"
PORT_DASHBOARD="${DEVSQUAD_DASHBOARD_PORT:-8501}"
HOST="${DEVSQUAD_HOST:-0.0.0.0}"

for arg in "$@"; do
    case $arg in
        --dashboard)
            START_DASHBOARD=1
            ;;
        --help|-h)
            echo "用法: bash scripts/start.sh [--dashboard] [--help]"
            echo ""
            echo "选项:"
            echo "  --dashboard  同时启动 Streamlit dashboard"
            echo "  --help       显示此帮助信息"
            echo ""
            echo "环境变量:"
            echo "  DEVSQUAD_API_PORT        API server 端口 (默认: 8000)"
            echo "  DEVSQUAD_DASHBOARD_PORT  Dashboard 端口 (默认: 8501)"
            echo "  DEVSQUAD_HOST            监听地址 (默认: 0.0.0.0)"
            exit 0
            ;;
    esac
done

cd "$PROJECT_ROOT"

# 启动 API server
echo -e "${GREEN}  → 启动 API server: http://${HOST}:${PORT_API}${NC}"
echo -e "${GREEN}    Swagger UI: http://${HOST}:${PORT_API}/docs${NC}"
echo -e "${GREEN}    ReDoc:      http://${HOST}:${PORT_API}/redoc${NC}"

if [ "$START_DASHBOARD" -eq 1 ] && [ "$DASHBOARD_AVAILABLE" -eq 1 ]; then
    # 同时启动 API + Dashboard
    echo -e "${GREEN}  → 启动 Dashboard: http://${HOST}:${PORT_DASHBOARD}${NC}"
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  按 Ctrl+C 停止所有服务${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    # 后台启动 dashboard，前台启动 API
    streamlit run scripts/dashboard.py --server.port "$PORT_DASHBOARD" --server.address "$HOST" &
    DASHBOARD_PID=$!

    # 捕获退出信号，同时杀死 dashboard
    trap "kill $DASHBOARD_PID 2>/dev/null; exit 0" INT TERM EXIT

    # 前台启动 API server
    exec uvicorn scripts.api_server:app --host "$HOST" --port "$PORT_API"
else
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  按 Ctrl+C 停止服务${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    exec uvicorn scripts.api_server:app --host "$HOST" --port "$PORT_API"
fi
