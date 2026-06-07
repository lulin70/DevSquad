#!/bin/bash
# Sync L2 global cache from L3 project source (V3.6.1)
L3="/Users/lin/trae_projects/devsquad"
L2="$HOME/.trae/skills/devsquad"

echo "=== L3 → L2 Cache Sync ==="
echo "Source: $L3"
echo "Target: $L2"
echo ""

for f in skill-manifest.yaml SKILL.md; do
    if [ -f "$L3/$f" ]; then
        cp "$L3/$f" "$L2/$f"
        echo "✅ $f synced ($(head -1 "$L2/$f"))"
    else
        echo "⚠️  $f not found in L3"
    fi
done

echo ""
echo "=== L2 State After Sync ==="
head -2 "$L2/skill-manifest.yaml"
ls -la "$L2/skill-manifest.yaml" "$L2/SKILL.md"
echo ""
echo "Done. TRAE should pick up V3.6.1 on next skill load."
