#!/bin/bash
set -e

# DevSquad V3.6.6 Full Cache Sync
#
# ⚠️ 重要：
#   - TRAE 从 SKILL.md frontmatter 读取版本号（优先级最高）
#   - 同步所有缓存位置：L1(trae-cn) + L2(~/.trae) + L3(.trae)
#   - 动态复制源文件，不硬编码内容
#
# 用法: bash scripts/sync_all_cache.sh

echo "=== DevSquad V3.6.6 Full Cache Sync ==="
echo ""

# 修复后的源路径
SRC="/Users/lin/trae_projects/DevSquad"
if [ ! -d "$SRC" ]; then
    echo "❌ ERROR: Project directory not found: $SRC"
    exit 1
fi

echo "Source: $SRC"
echo ""

# 所有需要同步的目标位置（按优先级排序）
TARGETS=(
    "/Users/lin/.trae-cn/skills/devsquad"      # L1: TraeCN 全局缓存
    "/Users/lin/.trae/skills/devsquad"          # L2: 用户级缓存
    "$SRC/.trae/skills/devsquad"                # L3: 项目级缓存 ⭐ TRAE 优先读取
)

# 需要同步的文件列表
FILES=(
    "SKILL.md"               # ⭐ 关键！TRAE 从此文件 frontmatter 读取版本
    "skill-manifest.yaml"    # 辅助配置文件
)

# 提取源文件的 SKILL.md 版本
SRC_SKILL_VER=$(grep -A1 "^description:" "$SRC/SKILL.md" | head -2 | grep -oP 'V\d+\.\d+\.\d+' | head -1)
SRC_MANIFEST_VER=$(grep "^version:" "$SRC/skill-manifest.yaml" | head -1)

echo "📌 源文件版本:"
echo "   SKILL.md frontmatter: ${SRC_SKILL_VER:-未检测到}"
echo "   skill-manifest.yaml: $SRC_MANIFEST_VER"
echo ""

# 同步到每个目标位置
for TARGET in "${TARGETS[@]}"; do
    echo ""
    echo "--- Syncing to $TARGET ---"
    mkdir -p "$TARGET"

    for f in "${FILES[@]}"; do
        if [ -f "$SRC/$f" ]; then
            cp "$SRC/$f" "$TARGET/$f"

            # 根据文件类型提取版本信息
            if [ "$f" = "SKILL.md" ]; then
                VER=$(grep -A1 "^description:" "$TARGET/$f" | head -2 | grep -oP 'V\d+\.\d+\.\d+' | head -1)
                echo "  ✅ $f -> Frontmatter Version: ${VER:-未检测到}"
            else
                VER=$(grep "^version:" "$TARGET/$f" | head -1)
                echo "  ✅ $f -> $VER"
            fi
        else
            echo "  ⚠️  SKIP $f (not found in source)"
        fi
    done
done

echo ""
echo "=== Verification ==="

# 验证所有位置的 SKILL.md frontmatter 版本
echo ""
echo "🔍 SKILL.md Frontmatter Version Check (TRAE reads this!):"
for TARGET in "${TARGETS[@]}"; do
    if [ -f "$TARGET/SKILL.md" ]; then
        VER=$(grep -A1 "^description:" "$TARGET/SKILL.md" | head -2 | grep -oP 'V\d+\.\d+\.\d+' | head -1)

        # 检查是否与源文件一致
        if cmp -s "$SRC/SKILL.md" "$TARGET/SKILL.md"; then
            STATUS="✅ 一致"
        else
            STATUS="❌ 不一致！"
        fi

        echo "  $TARGET -> ${VER:-未检测到} [$STATUS]"
    else
        echo "  $TARGET -> ❌ 文件不存在"
    fi
done

# 最终验证 L3 缓存（TRAE 最优先读取）
L3_CACHE="$SRC/.trae/skills/devsquad"
echo ""
echo "=== Final Status ==="
if [ -f "$L3_CACHE/SKILL.md" ] && cmp -s "$SRC/SKILL.md" "$L3_CACHE/SKILL.md"; then
    echo "✅ SUCCESS: L3 cache (.trae/skills/) synced and verified"
    echo "   TRAE should display version: ${SRC_SKILL_VER:-check manually}"
else
    echo "❌ WARNING: L3 cache verification failed"
    exit 1
fi

echo ""
echo "Done. Restart TRAE to pick up V3.6.6."
echo ""
echo "💡 Reminder: TRAE reads version from SKILL.md frontmatter, not skill-manifest.yaml!"
