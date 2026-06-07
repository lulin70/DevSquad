#!/bin/bash
# TRAE 环境完整同步脚本 - DevSquad V3.6.5 (修复版)
# 
# ⚠️ 重要：TRAE 优先使用 L3 项目级缓存 (.trae/skills/)
#    而不是 L2 用户级缓存 (~/.trae/skills/)
#
# 用法: bash sync_trae_v3.6.5_fixed.sh

set -e

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  DevSquad V3.6.5 - TRAE Complete Sync (L2 + L3)       ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

PROJECT_DIR="/Users/lin/trae_projects/DevSquad"
L2_CACHE_DIR="$HOME/.trae/skills/devsquad"      # 用户级缓存
L3_CACHE_DIR="$PROJECT_DIR/.trae/skills/devsquad" # 项目级缓存 ⭐

echo "📋 缓存层级说明:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  L1: CrossOver Container (全局，只读)"
echo "  L2: ~/.trae/skills/        (用户级)"
echo "  L3: .trae/skills/          (项目级) ⭐ TRAE 优先使用"
echo ""

# 检查源文件
echo "📂 [0] 检查源文件..."
if [ ! -f "$PROJECT_DIR/SKILL.md" ]; then
    echo "❌ SKILL.md 不存在!"
    exit 1
fi
if [ ! -f "$PROJECT_DIR/skill-manifest.yaml" ]; then
    echo "❌ skill-manifest.yaml 不存在!"
    exit 1
fi
echo "   ✅ 源文件就绪"

# 创建目录（如不存在）
mkdir -p "$L2_CACHE_DIR"
mkdir -p "$L3_CACHE_DIR"

echo ""
echo "🔄 开始同步..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 备份旧版本
BACKUP_DIR_L2="$L2_CACHE_DIR/backup_$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR_L3="$L3_CACHE_DIR/backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR_L2"
mkdir -p "$BACKUP_DIR_L3"

for f in SKILL.md skill-manifest.yaml; do
    [ -f "$L2_CACHE_DIR/$f" ] && cp "$L2_CACHE_DIR/$f" "$BACKUP_DIR_L2/" 2>/dev/null || true
    [ -f "$L3_CACHE_DIR/$f" ] && cp "$L3_CACHE_DIR/$f" "$BACKUP_DIR_L3/" 2>/dev/null || true
done

# 同步到 L2 (用户级)
echo "📁 [1/4] 同步 L2: ~/.trae/skills/devsquad/"
cp "$PROJECT_DIR/SKILL.md" "$L2_CACHE_DIR/SKILL.md"
cp "$PROJECT_DIR/skill-manifest.yaml" "$L2_CACHE_DIR/skill-manifest.yaml"
echo "   ✅ 完成"

# 同步到 L3 (项目级) ⭐ 关键！
echo "📁 [2/4] 同步 L3: .trae/skills/devsquad/ ⭐"
cp "$PROJECT_DIR/SKILL.md" "$L3_CACHE_DIR/SKILL.md"
cp "$PROJECT_DIR/skill-manifest.yaml" "$L3_CACHE_DIR/skill-manifest.yaml"
echo "   ✅ 完成 (这是 TRAE 实际读取的位置)"

# 更新 scripts 链接
echo "🔗 [3/4] 检查符号链接..."
if [ ! -L "$L2_CACHE_DIR/scripts" ]; then
    ln -sf "$PROJECT_DIR/scripts" "$L2_CACHE_DIR/scripts" 2>/dev/null || true
fi
if [ ! -L "$L3_CACHE_DIR/scripts" ]; then
    ln -sf "$PROJECT_DIR/scripts" "$L3_CACHE_DIR/scripts" 2>/dev/null || true
fi
echo "   ✅ 完成"

# 同步 trae_agent.py
echo "📁 [4/4] 同步 trae_agent.py..."
[ -f "$PROJECT_DIR/trae_agent.py" ] && cp "$PROJECT_DIR/trae_agent.py" "$L2_CACHE_DIR/" 2>/dev/null || true
[ -f "$PROJECT_DIR/trae_agent.py" ] && cp "$PROJECT_DIR/trae_agent.py" "$L3_CACHE_DIR/" 2>/dev/null || true
echo "   ✅ 完成"

echo ""
echo "✅ 同步完成！验证结果:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 对比验证
echo ""
echo "📊 文件版本对比:"
printf "%-25s %-15s %-15s %s\n" "文件" "源文件" "L2缓存" "L3缓存 ⭐"
printf "%-25s %-15s %-15s %s\n" "-------------------------" "---------------" "---------------" "---------------"

for file in SKILL.md skill-manifest.yaml; do
    SRC_TIME=$(stat -f "%Sm" -t "%m-%d %H:%M" "$PROJECT_DIR/$file")
    L2_TIME=$(stat -f "%Sm" -t "%m-%d %H:%M" "$L2_CACHE_DIR/$file")
    L3_TIME=$(stat -f "%Sm" -t "%m-%d %H:%M" "$L3_CACHE_DIR/$file")
    
    printf "%-25s %-15s %-15s %s\n" "$file" "$SRC_TIME" "$L2_TIME" "$L3_TIME"
    
    # 检查一致性
    if cmp -s "$PROJECT_DIR/$file" "$L3_CACHE_DIR/$file"; then
        echo "  ✅ $file: L3 与源文件一致"
    else
        echo "  ❌ $file: L3 与源文件不一致！"
    fi
done

echo ""
echo "📌 版本信息:"
echo "--- 源文件 ---"
grep -E "^(name|version|updated_at):" "$PROJECT_DIR/skill-manifest.yaml" | head -3
echo ""
echo "--- L3 缓存 (TRAE 使用) ---"
grep -E "^(name|version|updated_at):" "$L3_CACHE_DIR/skill-manifest.yaml" | head -3

echo ""
echo "🎯 关键发现:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ⚠️  TRAE IDE 优先读取 L3 项目级缓存 (.trae/skills/)"
echo "  ⚠️  而非 L2 用户级缓存 (~/.trae/skills/)"
echo "  ✅ 两个位置都已同步到最新版本"
echo ""

echo "🚀 下一步操作:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1. 完全退出 TRAE IDE (Cmd+Q 或菜单栏 → Quit Trae)"
echo "   ⚠️  注意：不是 Restart/Reload，是完全退出！"
echo ""
echo "2. 重新打开 TRAE 并加载 DevSquad 项目"
echo ""
echo "3. 打开 Skills 面板，确认 devsquad 显示 V3.6.5"
echo ""
echo "4. 测试技能功能:"
echo "   - 在聊天中输入: /devsquad help"
echo "   - 或运行命令: devsquad --version"
echo ""

# 清理旧备份
cleanup_old_backups() {
    local dir=$1
    local count=$(ls -d ${dir}/backup_* 2>/dev/null | wc -l | tr -d ' ')
    if [ "$count" -gt 3 ]; then
        ls -dt ${dir}/backup_* | tail -n +4 | xargs rm -rf 2>/dev/null || true
        echo "🧹 已清理旧备份（保留最近 3 个）"
    fi
}
cleanup_old_backups "$L2_CACHE_DIR"
cleanup_old_backups "$L3_CACHE_DIR"

echo "╔══════════════════════════════════════════════════════════╗"
echo "║              ✅ Complete Sync Finished!                 ║"
echo "║     Please RESTART (Quit & Reopen) TRAE IDE            ║"
echo "╚══════════════════════════════════════════════════════════╝"
