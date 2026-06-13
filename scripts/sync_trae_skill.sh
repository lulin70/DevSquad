#!/bin/bash
set -e

# TRAE SKILL.md 同步工具 - V3.6.8
#
# ⚠️ 重要说明：
#   - TRAE 从 SKILL.md 的 YAML frontmatter 读取版本号
#   - 不是从 skill-manifest.yaml 读取！
#   - 本脚本动态复制源文件，不会硬编码内容
#
# 用法: bash scripts/sync_trae_skill.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TARGET_PATH="$HOME/.trae/skills/devsquad/SKILL.md"
SOURCE_PATH="$PROJECT_ROOT/SKILL.md"

echo "=========================================="
echo "DevSquad SKILL.md Sync Tool (V3.6.8)"
echo "=========================================="
echo ""
echo "Source: $SOURCE_PATH"
echo "Target: $TARGET_PATH"
echo ""

# 检查源文件是否存在
if [ ! -f "$SOURCE_PATH" ]; then
    echo "❌ ERROR: Source file not found: $SOURCE_PATH"
    exit 1
fi

# 提取源文件版本（从 frontmatter）- macOS compatible (no grep -P)
SRC_VER=$(grep -A1 "^description:" "$SOURCE_PATH" | head -2 | grep -oE 'V[0-9]+\.[0-9]+\.[0-9]+' | head -1)
echo "📌 源文件 SKILL.md frontmatter 版本: ${SRC_VER:-未检测到}"

# 创建目标目录
mkdir -p "$(dirname "$TARGET_PATH")"

# 备份现有文件（如果存在）
if [ -f "$TARGET_PATH" ]; then
    OLD_VER=$(grep -A1 "^description:" "$TARGET_PATH" | head -2 | grep -oE 'V[0-9]+\.[0-9]+\.[0-9]+' | head -1)
    echo "📋 当前目标文件版本: ${OLD_VER:-未检测到}"

    if [ "$OLD_VER" != "$SRC_VER" ]; then
        echo "⚠️  版本不同，备份旧文件..."
        cp "$TARGET_PATH" "${TARGET_PATH}.bak.$(date +%Y%m%d_%H%M%S)"
        echo "   备份完成"
    fi
fi

echo ""
echo "🔄 正在同步 SKILL.md..."

# 动态复制源文件（不是硬编码！）
cp "$SOURCE_PATH" "$TARGET_PATH"

# 验证复制结果
if cmp -s "$SOURCE_PATH" "$TARGET_PATH"; then
    echo "✅ 同步成功！"
else
    echo "❌ 同步失败：文件不一致"
    exit 1
fi

# 显示同步后的版本信息
NEW_VER=$(grep -A1 "^description:" "$TARGET_PATH" | head -2 | grep -oE 'V[0-9]+\.[0-9]+\.[0-9]+' | head -1)
echo ""
echo "📊 同步结果:"
echo "   文件位置: $TARGET_PATH"
echo "   文件大小: $(wc -c < "$TARGET_PATH") bytes"
echo "   行数: $(wc -l < "$TARGET_PATH")"
echo "   Frontmatter 版本: ${NEW_VER:-未检测到}"
echo ""
echo "✅ Done: SKILL.md synced (from source, not hardcoded)"
echo ""
echo "Sync completed at: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo ""
echo "💡 提示: 请完全退出 TRAE 后重新打开以加载新版本"
