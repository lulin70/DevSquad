#!/bin/bash
# DevSquad V3.6.5 → TRAE L2 缓存同步脚本
# 用法: bash sync_trae_v3.6.5.sh

set -e

echo "🔄 DevSquad V3.6.5 → TRAE L2 缓存同步"
echo "===================================="

SRC="/Users/lin/trae_projects/DevSquad"
DST="$HOME/.trae/skills/devsquad"

# 检查源文件
if [ ! -f "$SRC/SKILL.md" ]; then
    echo "❌ 错误: 找不到 $SRC/SKILL.md"
    exit 1
fi

if [ ! -f "$SRC/skill-manifest.yaml" ]; then
    echo "❌ 错误: 找不到 $SRC/skill-manifest.yaml"
    exit 1
fi

# 创建目标目录（如果不存在）
mkdir -p "$DST"

# 同步文件
echo ""
echo "📦 [1/2] 同步 SKILL.md..."
cp -f "$SRC/SKILL.md" "$DST/SKILL.md"
echo "   ✅ 完成 ($(wc -c < "$DST/SKILL.md") bytes)"

echo "📋 [2/2] 同步 skill-manifest.yaml..."
cp -f "$SRC/skill-manifest.yaml" "$DST/skill-manifest.yaml"
echo "   ✅ 完成 ($(wc -c < "$DST/skill-manifest.yaml") bytes)"

# 验证
echo ""
echo "=== ✅ 同步完成! 验证版本 ==="
echo ""

SKILL_VER=$(grep "V3\." "$DST/SKILL.md" | head -1 | grep -oE "V[0-9]+\.[0-9]+")
MANIFEST_VER=$(grep "^version:" "$DST/skill-manifest.yaml" | awk '{print $2}')

echo "📄 SKILL.md:        $SKILL_VER"
echo "📋 skill-manifest: $MANIFEST_VER"

if [[ "$MANIFEST_VER" == "3.6.5" ]]; then
    echo ""
    echo "🎉 成功! TRAE 本地环境已更新到 V3.6.5!"
    echo ""
    echo "💡 提示: 如果 TRAE 仍显示旧版本，请重启 TRAE"
else
    echo ""
    echo "⚠️  版本可能未更新 (当前: $MANIFEST_VER)"
fi

echo ""
echo "🔗 相关路径:"
echo "  • 项目源码: $SRC/"
echo "  • TRAE L2:   $DST/"
echo "  • PyPI:      https://pypi.org/project/devsquad/3.6.5/"
echo "  • GitHub:    https://github.com/lulin70/DevSquad/releases/tag/v3.6.5"
