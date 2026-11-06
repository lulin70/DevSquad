#!/bin/bash
# DevSquad 项目清理脚本
# 评估日期: 2026-11-06
# 用途: 清理临时文件和过期产物

set -e

PROJECT_ROOT="/Users/lin/trae_projects/DevSquad"
cd "$PROJECT_ROOT"

echo "=== DevSquad 项目清理脚本 ==="
echo "开始时间: $(date)"
echo ""

# 1. 清理 artifacts 目录 (保留最近 10 天)
echo "[1/4] 清理 artifacts 目录..."
if [ -d "artifacts/" ]; then
    BEFORE_SIZE=$(du -sh artifacts/ | cut -f1)
    echo "  当前大小: $BEFORE_SIZE"
    echo "  清理 10 天前的文件..."
    find artifacts/ -type f -mtime +10 -delete 2>/dev/null || true
    find artifacts/ -type d -empty -delete 2>/dev/null || true
    AFTER_SIZE=$(du -sh artifacts/ | cut -f1)
    echo "  清理后大小: $AFTER_SIZE"
else
    echo "  artifacts 目录不存在,跳过"
fi
echo ""

# 2. 清理 __pycache__ (tests/ 下)
echo "[2/4] 清理 __pycache__ 缓存..."
PYCACHE_COUNT=$(find tests/ -name "__pycache__" -type d 2>/dev/null | wc -l | tr -d ' ')
echo "  找到 $PYCACHE_COUNT 个 __pycache__ 目录"
find tests/ -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find tests/ -name "*.pyc" -delete 2>/dev/null || true
echo "  清理完成"
echo ""

# 3. 清理 .DS_Store (macOS)
echo "[3/4] 清理 .DS_Store 文件..."
DS_COUNT=$(find . -name ".DS_Store" 2>/dev/null | wc -l | tr -d ' ')
if [ "$DS_COUNT" -gt 0 ]; then
    echo "  找到 $DS_COUNT 个 .DS_Store 文件"
    find . -name ".DS_Store" -delete 2>/dev/null || true
else
    echo "  未发现 .DS_Store 文件"
fi
echo ""

# 4. 清理 pytest 缓存
echo "[4/4] 清理 pytest 缓存..."
if [ -d ".pytest_cache/" ]; then
    rm -rf .pytest_cache/
    echo "  已清理 .pytest_cache"
fi
if [ -d ".hypothesis/" ]; then
    rm -rf .hypothesis/
    echo "  已清理 .hypothesis"
fi
echo ""

# 总结
echo "=== 清理完成 ==="
echo "完成时间: $(date)"
echo ""
echo "后续建议:"
echo "  1. 运行测试: pytest -v"
echo "  2. 检查 git 状态: git status"
echo "  3. 确认清理效果: du -sh artifacts/ tests/"
echo ""
