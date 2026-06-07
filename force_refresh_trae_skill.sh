#!/bin/bash
# TRAE Skill 强制刷新脚本 - DevSquad V3.6.6
#
# ⚠️ 重要：TRAE 从 SKILL.md 的 YAML frontmatter 读取版本号
#    不是 skill-manifest.yaml！
#
# 问题: TRAE 将技能信息缓存在内存中，普通重启不会重新读取文件
# 解决: 完全清除所有缓存 + 强制重置 + 特殊重启方式
#
# 用法: bash force_refresh_trae_skill.sh

set -e

echo "╔══════════════════════════════════════════════════════════╗"
echo "║   DevSquad V3.6.6 - TRAE Skill Force Refresh Tool       ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

PROJECT_DIR="/Users/lin/trae_projects/DevSquad"
L3_CACHE="$PROJECT_DIR/.trae/skills/devsquad"
L2_CACHE="$HOME/.trae/skills/devsquad"

echo "⚠️  当前状态:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 检查 SKILL.md frontmatter 版本（TRAE 实际读取的位置）
if [ -f "$L3_CACHE/SKILL.md" ]; then
    L3_SKILL_VER=$(grep -A1 "^description:" "$L3_CACHE/SKILL.md" | head -2 | grep -oP 'V\d+\.\d+\.\d+' | head -1)
    echo "  L3 (.trae/skills/) SKILL.md frontmatter: ${L3_SKILL_VER:-未检测到}"
else
    echo "  L3 (.trae/skills/): ❌ 不存在"
fi

if [ -f "$L2_CACHE/SKILL.md" ]; then
    L2_SKILL_VER=$(grep -A1 "^description:" "$L2_CACHE/SKILL.md" | head -2 | grep -oP 'V\d+\.\d+\.\d+' | head -1)
    echo "  L2 (~/.trae/skills/) SKILL.md frontmatter: ${L2_SKILL_VER:-未检测到}"
else
    echo "  L2 (~/.trae/skills/): ❌ 不存在"
fi

SRC_SKILL_VER=$(grep -A1 "^description:" "$PROJECT_DIR/SKILL.md" | head -2 | grep -oP 'V\d+\.\d+\.\d+' | head -1)
echo "  源文件 (项目根) SKILL.md frontmatter: ${SRC_SKILL_VER:-未检测到}"

if [ -f "$PROJECT_DIR/skill-manifest.yaml" ]; then
    SRC_MANIFEST_VER=$(grep "^version:" "$PROJECT_DIR/skill-manifest.yaml" | head -1)
    echo "  源文件 skill-manifest.yaml: $SRC_MANIFEST_VER"
fi
echo ""

read -p "是否继续强制刷新？(y/N) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ 已取消"
    exit 0
fi

echo ""
echo "🔄 开始强制刷新..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Step 1: 完全删除 L3 缓存
echo "🗑️  [1/5] 清除 L3 项目级缓存..."
rm -rf "$L3_CACHE"
mkdir -p "$L3_CACHE"
echo "   ✅ 已清除并重建"

# Step 2: 完全删除 L2 缓存
echo "🗑️  [2/5] 清除 L2 用户级缓存..."
rm -rf "$L2_CACHE"
mkdir -p "$L2_CACHE"
echo "   ✅ 已清除并重建"

# Step 3: 复制最新文件到 L3 (优先)
echo "📁 [3/5] 同步到 L3 (.trae/skills/) ⭐"
cp "$PROJECT_DIR/SKILL.md" "$L3_CACHE/SKILL.md"
cp "$PROJECT_DIR/skill-manifest.yaml" "$L3_CACHE/skill-manifest.yaml"
[ -f "$PROJECT_DIR/trae_agent.py" ] && cp "$PROJECT_DIR/trae_agent.py" "$L3_CACHE/"
ln -sf "$PROJECT_DIR/scripts" "$L3_CACHE/scripts" 2>/dev/null || true
echo "   ✅ 完成"

# Step 4: 复制到 L2
echo "📁 [4/5] 同步到 L2 (~/.trae/skills/) "
cp "$PROJECT_DIR/SKILL.md" "$L2_CACHE/SKILL.md"
cp "$PROJECT_DIR/skill-manifest.yaml" "$L2_CACHE/skill-manifest.yaml"
[ -f "$PROJECT_DIR/trae_agent.py" ] && cp "$PROJECT_DIR/trae_agent.py" "$L2_CACHE/"
ln -sf "$PROJECT_DIR/scripts" "$L2_CACHE/scripts" 2>/dev/null || true
echo "   ✅ 完成"

# Step 5: 清除 TRAE 可能的其他缓存位置
echo "🧹 [5/5] 清除 TRAE 其他缓存..."

# 清除可能的工作区状态缓存
rm -rf "$PROJECT_DIR/.trae/workspace_state" 2>/dev/null || true
rm -rf "$HOME/Library/Application Support/Trae CN/Cache/"*devsquad* 2>/dev/null || true
rm -rf "$HOME/Library/Caches/com.trae*" 2>/dev/null || true

echo "   ✅ 清除完成"

echo ""
echo "✅ 强制同步完成！验证结果:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 验证 SKILL.md frontmatter 版本（关键！）
for cache_dir in "$L3_CACHE" "$L2_CACHE"; do
    if [ -f "$cache_dir/SKILL.md" ]; then
        VER=$(grep -A1 "^description:" "$cache_dir/SKILL.md" | head -2 | grep -oP 'V\d+\.\d+\.\d+' | head -1)
        SIZE=$(du -sh "$cache_dir" | cut -f1)
        echo "  ✅ $cache_dir"
        echo "     SKILL.md frontmatter 版本: ${VER:-未检测到} | 大小: $SIZE"
    fi
done

# 额外验证：确保 frontmatter 与源文件一致
echo ""
echo "🔍 关键验证: SKILL.md frontmatter 一致性"
if cmp -s "$PROJECT_DIR/SKILL.md" "$L3_CACHE/SKILL.md"; then
    echo "  ✅ L3 缓存 SKILL.md 与源文件完全一致"
else
    echo "  ❌ L3 缓存 SKILL.md 与源文件不一致！请检查"
fi

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║              🚨 重要：特殊重启步骤                       ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "请按以下顺序操作（必须全部执行）："
echo ""
echo "1️⃣  完全退出 TRAE（不是 Restart）"
echo "   - 菜单栏 → Trae → Quit Trae（或 Cmd+Q）"
echo "   - 确认 Dock 栏图标下没有小点"
echo ""
echo "2️⃣  清除 TRAE 进程残留"
echo "   在终端执行:"
echo "   killall Trae 2>/dev/null || true"
echo "   sleep 2"
echo ""
echo "3️⃣  重新打开 TRAE"
echo "   - 点击 Dock 栏的 TRE 图标"
echo ""
echo "4️⃣  在 TRAE 内部执行技能刷新（关键！）"
echo "   打开 TRAE 的命令面板（Cmd+Shift+P）"
echo "   输入: Developer: Reload Window"
echo "   或者: 重新加载窗口"
echo ""
echo "5️⃣  如果仍未更新，尝试:"
echo "   - 关闭 DevSquad 项目"
echo "   - 重新打开项目"
echo "   - 或者在 TRAE Settings 中找到 Skills 相关选项并点击 Refresh"
echo ""

# 自动执行 killall
echo "🔧 是否自动清除 TRAE 进程？"
read -p "   执行 killall Trae? (y/N) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "   正在清除 TRAE 进程..."
    killall Trae 2>/dev/null || echo "   （无运行中的 TRAE 进程）"
    sleep 2
    echo "   ✅ 进程已清除"
    echo ""
    echo "🚀 现在请手动重新打开 TRAE"
else
    echo "   跳过。请手动执行上述步骤 1-5"
fi

echo ""
echo "💡 如果以上都不行，终极方案:"
echo "   1. 删除整个 .trae 目录: rm -rf /Users/lin/trae_projects/DevSquad/.trae"
echo "   2. 重启 TRAE（会自动重建 .trae 目录）"
echo "   3. 重新执行本脚本"
echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║              ✅ Force Refresh Complete!                 ║"
echo "╚══════════════════════════════════════════════════════════╝"
