#!/bin/bash
set -uo pipefail

# DevSquad TRAE Skill Cache Sync Tool (V4.0.0)
#
# 同步主仓库的 SKILL.md 和 skill-manifest.yaml 到 3 层 TRAE 技能缓存：
#   1. Global:    ~/.trae/skills/devsquad/
#   2. Workspace: <projects>/.trae/skills/devsquad/
#   3. Project:   <DevSquad>/.trae/skills/devsquad/
#
# 用法:
#   bash scripts/sync_trae_skill.sh            # 同步并备份旧文件
#   bash scripts/sync_trae_skill.sh --dry-run  # 只预览，不实际复制
#   bash scripts/sync_trae_skill.sh --force    # 跳过版本检查，强制覆盖

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

SOURCE_SKILL="$PROJECT_ROOT/SKILL.md"
SOURCE_MANIFEST="$PROJECT_ROOT/skill-manifest.yaml"

# 3 层缓存路径
CACHE_PATHS=(
    "$HOME/.trae/skills/devsquad"                          # Global
    "$PROJECT_ROOT/.trae/skills/devsquad"                  # Project
    "$(dirname "$PROJECT_ROOT")/.trae/skills/devsquad"     # Workspace (parent of project)
)

CACHE_LABELS=("Global" "Project" "Workspace")

# 要同步的文件（用普通变量，避免关联数组键含 "." 的 bash 语法问题）
SYNC_FILENAMES=("SKILL.md" "skill-manifest.yaml")
get_source_path() {
    case "$1" in
        "SKILL.md")           echo "$SOURCE_SKILL" ;;
        "skill-manifest.yaml") echo "$SOURCE_MANIFEST" ;;
        *) echo "" ;;
    esac
}

DRY_RUN=false
FORCE=false

for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=true ;;
        --force)   FORCE=true ;;
        *) echo "Unknown option: $arg"; exit 1 ;;
    esac
done

echo "=========================================="
echo "DevSquad TRAE Skill Cache Sync (V4.0.0)"
echo "=========================================="
echo ""

# 检查源文件
for fname in "${SYNC_FILENAMES[@]}"; do
    src="$(get_source_path "$fname")"
    if [ ! -f "$src" ]; then
        echo "❌ ERROR: Source file not found: $src"
        exit 1
    fi
done

# 提取源文件版本
SRC_VER=$(grep '^version:' "$SOURCE_MANIFEST" | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')
if [ -z "$SRC_VER" ]; then
    SRC_VER=$(grep -oE 'V[0-9]+\.[0-9]+\.[0-9]+' "$SOURCE_SKILL" | head -1 | tr -d 'V')
fi
echo "📌 源文件版本: ${SRC_VER:-未检测到}"
echo "   SKILL.md:           $SOURCE_SKILL"
echo "   skill-manifest.yaml: $SOURCE_MANIFEST"
echo ""

TOTAL=0
SYNCED=0
SKIPPED=0
FAILED=0

for i in "${!CACHE_PATHS[@]}"; do
    cache_dir="${CACHE_PATHS[$i]}"
    label="${CACHE_LABELS[$i]}"
    echo "--- [$label] $cache_dir ---"

    if [ ! -d "$cache_dir" ]; then
        echo "   ⏭️  目录不存在，跳过"
        SKIPPED=$((SKIPPED + 1))
        echo ""
        continue
    fi

    for fname in "SKILL.md" "skill-manifest.yaml"; do
        src="$(get_source_path "$fname")"
        target="$cache_dir/$fname"
        TOTAL=$((TOTAL + 1))

        if [ ! -f "$target" ]; then
            echo "   ⏭️  $fname: 目标不存在，跳过"
            SKIPPED=$((SKIPPED + 1))
            continue
        fi

        # 提取目标版本
        if [ "$fname" = "skill-manifest.yaml" ]; then
            OLD_VER=$(grep '^version:' "$target" 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')
        else
            OLD_VER=$(grep -oE 'V[0-9]+\.[0-9]+\.[0-9]+' "$target" 2>/dev/null | head -1 | tr -d 'V')
        fi

        if [ "$FORCE" = false ] && [ "$OLD_VER" = "$SRC_VER" ] && cmp -s "$src" "$target"; then
            echo "   ✅ $fname: 已是 V${OLD_VER}，无需同步"
            SYNCED=$((SYNCED + 1))
            continue
        fi

        echo "   🔄 $fname: V${OLD_VER:-?} → V${SRC_VER}"

        if [ "$DRY_RUN" = true ]; then
            echo "      (dry-run) 将备份并覆盖"
            continue
        fi

        # 备份旧文件（失败不中断）
        if ! cp "$target" "${target}.bak.$(date +%Y%m%d_%H%M%S)" 2>/dev/null; then
            echo "      ⚠️  备份失败（权限？），继续覆盖"
        fi

        # 同步（失败不中断，记录错误）
        if cp "$src" "$target" 2>/dev/null; then
            # 验证
            if cmp -s "$src" "$target"; then
                echo "      ✅ 同步成功"
                SYNCED=$((SYNCED + 1))
            else
                echo "      ❌ 同步失败：文件不一致"
                FAILED=$((FAILED + 1))
            fi
        else
            echo "      ❌ 同步失败：权限不足（需在 macOS 终端执行）"
            FAILED=$((FAILED + 1))
        fi
    done
    echo ""
done

echo "=========================================="
echo "📊 同步结果:"
echo "   源版本: V${SRC_VER:-未检测到}"
echo "   总计: $TOTAL | 已同步: $SYNCED | 跳过: $SKIPPED | 失败: $FAILED"
if [ "$DRY_RUN" = true ]; then
    echo "   (dry-run 模式，未实际执行)"
fi
echo "=========================================="

if [ "$DRY_RUN" = false ] && [ "$FAILED" -gt 0 ]; then
    exit 1
fi

echo ""
echo "💡 提示: 请执行 'Developer: Reload Window' (Cmd+Shift+P) 刷新 TRAE 技能列表"
