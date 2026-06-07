#!/bin/bash
# TRAE 环境同步脚本 - DevSquad V3.6.5
# 用法: bash sync_trae_v3.6.5.sh

set -e

echo "╔══════════════════════════════════════════════════════════╗"
echo "║     DevSquad V3.6.5 - TRAE Environment Sync Tool        ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

PROJECT_DIR="/Users/lin/trae_projects/DevSquad"
TRAE_CACHE_DIR="$HOME/.trae/skills/devsquad"

echo "📋 同步前状态检查:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📂 项目目录: $PROJECT_DIR"
if [ -f "$PROJECT_DIR/SKILL.md" ]; then
    echo "  ✅ SKILL.md ($(du -h $PROJECT_DIR/SKILL.md | cut -f1))"
else
    echo "  ❌ SKILL.md 不存在!"
    exit 1
fi

if [ -f "$PROJECT_DIR/skill-manifest.yaml" ]; then
    echo "  ✅ skill-manifest.yaml ($(du -h $PROJECT_DIR/skill-manifest.yaml | cut -f1))"
else
    echo "  ❌ skill-manifest.yaml 不存在!"
    exit 1
fi

echo ""
echo "📂 TRAE 缓存目录: $TRAE_CACHE_DIR"
if [ -d "$TRAE_CACHE_DIR" ]; then
    echo "  📁 目录已存在"
else
    echo "  🔨 创建缓存目录..."
    mkdir -p "$TRAE_CACHE_DIR"
fi

echo ""
echo "🔄 开始同步文件..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 备份旧版本（可选）
BACKUP_DIR="$TRAE_CACHE_DIR/backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
if [ -f "$TRAE_CACHE_DIR/SKILL.md" ]; then
    cp "$TRAE_CACHE_DIR/SKILL.md" "$BACKUP_DIR/" 2>/dev/null || true
fi
if [ -f "$TRAE_CACHE_DIR/skill-manifest.yaml" ]; then
    cp "$TRAE_CACHE_DIR/skill-manifest.yaml" "$BACKUP_DIR/" 2>/dev/null || true
fi

# 同步核心文件
echo "📁 [1/4] 同步 SKILL.md..."
cp "$PROJECT_DIR/SKILL.md" "$TRAE_CACHE_DIR/SKILL.md"
echo "   ✅ 完成 (新版本: $(head -3 $TRAE_CACHE_DIR/SKILL.md | grep version || echo 'V3.6.5'))"

echo "📁 [2/4] 同步 skill-manifest.yaml..."
cp "$PROJECT_DIR/skill-manifest.yaml" "$TRAE_CACHE_DIR/skill-manifest.yaml"
VERSION=$(grep "^version:" $TRAE_CACHE_DIR/skill-manifest.yaml | head -1)
echo "   ✅ 完成 ($VERSION)"

# 同步 scripts 符号链接（如果不存在）
echo "🔗 [3/4] 检查 scripts 链接..."
if [ ! -L "$TRAE_CACHE_DIR/scripts" ] && [ ! -d "$TRAE_CACHE_DIR/scripts" ]; then
    ln -s "$PROJECT_DIR/scripts" "$TRAE_CACHE_DIR/scripts"
    echo "   ✅ 创建符号链接: scripts -> $PROJECT_DIR/scripts"
elif [ -L "$TRAE_CACHE_DIR/scripts" ]; then
    echo "   ℹ️  符号链接已存在"
else
    echo "   ⚠️  scripts 是真实目录（非链接）"
fi

# 同步 trae_agent.py（如果存在）
echo "📁 [4/4] 同步 trae_agent.py..."
if [ -f "$PROJECT_DIR/trae_agent.py" ]; then
    cp "$PROJECT_DIR/trae_agent.py" "$TRAE_CACHE_DIR/trae_agent.py"
    echo "   ✅ 完成"
else
    echo "   ⏭️  跳过（源文件不存在）"
fi

echo ""
echo "✅ 同步完成！验证结果:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 验证同步结果
echo "📊 文件大小对比:"
printf "%-25s %-12s %-12s\n" "文件" "项目版本" "缓存版本"
printf "%-25s %-12s %-12s\n" "-------------------------" "------------" "------------"

for file in SKILL.md skill-manifest.yaml; do
    if [ -f "$PROJECT_DIR/$file" ] && [ -f "$TRAE_CACHE_DIR/$file" ]; then
        PROJECT_SIZE=$(du -h "$PROJECT_DIR/$file" | cut -f1)
        CACHE_SIZE=$(du -h "$TRAE_CACHE_DIR/$file" | cut -f1)
        printf "%-25s %-12s %-12s\n" "$file" "$PROJECT_SIZE" "$CACHE_SIZE"
        
        # 检查是否一致
        if cmp -s "$PROJECT_DIR/$file" "$TRAE_CACHE_DIR/$file"; then
            echo "  ✅ $file 内容一致"
        else
            echo "  ⚠️  $file 内容不一致（可能正常，如果项目有更新）"
        fi
    fi
done

echo ""
echo "📌 版本信息:"
if [ -f "$TRAE_CACHE_DIR/skill-manifest.yaml" ]; then
    grep -E "^(name|version|updated_at):" "$TRAE_CACHE_DIR/skill-manifest.yaml" | head -3
fi

echo ""
echo "🎯 下一步操作:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1. 重启 TRAE IDE 以加载最新版本"
echo "   - 点击菜单栏 → File → Restart IDE"
echo "   - 或按 Cmd+Shift+P → 输入 'Reload Window'"
echo ""
echo "2. 验证技能加载:"
echo "   - 打开 TRAE 的 Skills 面板"
echo "   - 找到 devsquad 技能"
echo "   - 确认显示版本 V3.6.5"
echo ""
echo "3. 测试技能功能:"
echo "   - 在聊天中输入: /devsquad help"
echo "   - 或运行: devsquad --version"
echo ""

# 清理旧的备份（保留最近 3 个）
BACKUP_COUNT=$(ls -d $TRAE_CACHE_DIR/backup_* 2>/dev/null | wc -l | tr -d ' ')
if [ "$BACKUP_COUNT" -gt 3 ]; then
    ls -dt $TRAE_CACHE_DIR/backup_* | tail -n +4 | xargs rm -rf 2>/dev/null || true
    echo "🧹 已清理旧备份（保留最近 3 个）"
fi

echo "╔══════════════════════════════════════════════════════════╗"
echo "║              ✅ TRAE Sync Complete!                    ║"
echo "╚══════════════════════════════════════════════════════════╝"
