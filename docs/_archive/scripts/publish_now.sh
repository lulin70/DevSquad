# DevSquad V3.7.0 一键发布脚本 - 超简化版
# 使用方法: 复制粘贴以下全部内容到终端运行
#
# ⚠️ 安全提示：请使用环境变量传入 Token，不要硬编码！
#   export GITHUB_TOKEN="your_token_here"
#   bash scripts/publish_now.sh

set -e

echo "🚀 DevSquad V3.7.0 一键发布"
echo "========================="
cd /Users/lin/trae_projects/DevSquad

# ============================================
# 配置
# ============================================
REPO="lulin70/DevSquad"
VERSION="3.7.0"

# 从环境变量读取 Token（安全做法）
if [ -z "$GITHUB_TOKEN" ]; then
    echo "❌ 错误：未检测到 GITHUB_TOKEN 环境变量"
    echo ""
    echo "请设置环境变量后重试:"
    echo "  export GITHUB_TOKEN=\"ghp_your_token_here\""
    echo "  bash scripts/publish_now.sh"
    exit 1
fi
TOKEN="$GITHUB_TOKEN"

# ============================================
# Step 1: 创建 GitHub Release
# ============================================
echo ""
echo "📦 [1/3] 创建 GitHub Release..."

RELEASE_BODY=$(cat << 'ENDOFBODY'
## 🚀 DevSquad V3.7.0 - Documentation Experience + E2E Testing

> **Release Date**: 2026-05-27
> **Maturity Level**: 65% Maturity
> **PyPI**: https://pypi.org/project/devsquad/3.7.0/

### ✨ What's New

#### 🎯 Documentation Experience Enhancement (Major)
- **Three-Layer Funnel Documentation Structure**: 30-sec elevator pitch → Core workflow demo → Detailed specs in `<details>`
- **Framework Comparison Page**: COMPARISON.md with 60+ comparison points vs AutoGen/CrewAI/LangGraph
- **Version Consistency**: Unified V3.7.0 across all 27 documentation files

#### 🧪 Enhanced E2E Testing - User Journey Oriented (NEW)
- **User Journey 1: Developer Onboarding (Alice)**: 8 test cases covering installation, first task, status check, error handling
- **User Journey 2: Architecture Review (Bob)**: 8 test cases covering complex tasks, role-specific analysis, consensus mechanism, report generation
- **Total**: 16 new E2E tests with real user persona-based scenarios
- **Enhanced Test Plan**: Frontend Dashboard (15 planned) + Integration (12 planned)

#### 🐛 Bug Fixes
- **test_auth_phase5.py::test_auth_disabled_by_default**: Fixed config_path=None fallback issue
- Test now uses explicit non-existent path for proper "no config file" behavior testing

#### 📊 Quality Metrics
- Unit Tests: 1770+ passed (96.3%)
- E2E Tests: 16/16 passed (100%) ✅
- Code Review: 8.2/10 score (7-dimension) ✅
- Maturity: 65% Maturity 🏆

### 📦 Installation
```bash
pip install devsquad==3.7.0
docker pull lulin70/devsquad:3.7.0
```

### 📝 Migration from V3.6.5
```bash
pip install --upgrade devsquad==3.7.0
# No breaking changes - fully backward compatible
```

**🎉 Thank you for using DevSquad!**
ENDOFBODY
)

curl -s -X POST \
  -H "Authorization: token $TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  "https://api.github.com/repos/$REPO/releases" \
  -d "{
    \"tag_name\": \"v$VERSION\",
    \"target_commitish\": \"main\",
    \"name\": \"V$VERSION: Enterprise Edition + E2E Testing\",
    \"body\": $(echo "$RELEASE_BODY" | jq -Rs .),
    \"draft\": false,
    \"prerelease\": false
  }" > /tmp/release_result.json

RELEASE_URL=$(jq -r '.html_url // .message' /tmp/release_result.json)

if [[ "$RELEASE_URL" == https* ]]; then
    echo "✅ Release 创建成功!"
    echo "   URL: $RELEASE_URL"
else
    echo "⚠️  Release 可能失败，检查响应:"
    cat /tmp/release_result.json | jq '.message // .'
fi

# ============================================
# Step 2: 更新 About 和 Topics
# ============================================
echo ""
echo "📝 [2/3] 更新 GitHub About 和 Topics..."

curl -s -X PATCH \
  -H "Authorization: token $TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  "https://api.github.com/repos/$REPO" \
  -d '{
    "name": "DevSquad",
    "description": "🚀 DevSquad V3.7.0 - Enterprise Multi-Role AI Task Orchestrator | Documentation Experience | E2E Testing | 7-Agent Collaboration | RBAC | PyPI Ready",
    "homepage": "https://pypi.org/project/devsquad/",
    "topics": [
      "ai-agent", "multi-agent", "task-orchestrator", "python", "llm",
      "enterprise-ready", "rbac", "audit-log", "multi-tenancy",
      "asyncio", "redis-cache", "prometheus-monitoring", "e2e-testing",
      "cli-tool", "fastapi", "docker", "collaboration-engine",
      "consensus-mechanism", "workflow-automation", "code-quality"
    ]
  }' > /tmp/about_result.json

ABOUT_MSG=$(jq -r '.message // "success"' /tmp/about_result.json)

if [[ "$ABOUT_MSG" == "success" || -z "$ABOUT_MSG" ]]; then
    echo "✅ About 和 Topics 更新成功!"
else
    echo "⚠️  About 更新可能失败: $ABOUT_MSG"
fi

# ============================================
# Step 3: Docker 构建 (可选)
# ============================================
echo ""
echo "🐳 [3/3] Docker Image 构建..."

if command -v docker &> /dev/null && docker info &> /dev/null; then
    echo "   Building runtime image..."
    
    if docker build --target runtime \
        -t lulin70/devsquad:$VERSION \
        -t lulin70/devsquad:latest \
        . 2>&1 | tail -5; then
        
        echo "   Pushing to Docker Hub..."
        if docker push lulin70/devsquad:$VERSION && \
           docker push lulin70/devsquad:latest; then
            echo "✅ Docker Image 发布成功!"
        else
            echo "⚠️  Docker push 失败 (可能需要 docker login)"
        fi
    else
        echo "⚠️  Docker 构建失败"
    fi
else
    echo "⏭️  Docker 未运行或未安装，跳过"
    echo "   您可以稍后手动构建:"
    echo "   cd /Users/lin/trae_projects/DevSquad"
    echo "   docker build --target runtime -t lulin70/devsquad:$VERSION ."
    echo "   docker push lulin70/devsquad:$VERSION"
fi

# ============================================
# 完成
# ============================================
echo ""
echo "=============================="
echo "🎉 发布操作完成!"
echo ""
echo "📋 验证清单:"
echo "  🔗 PyPI:     https://pypi.org/project/devsquad/$VERSION/"
echo "  🔗 GitHub:   https://github.com/$REPO"
echo "  🔗 Release:  https://github.com/$REPO/releases/tag/v$VERSION"
echo "  🔗 Docker:   https://hub.docker.com/r/lulin70/devsquad"
echo ""
echo "💡 如果 Release 或 About 更新失败，请检查 Token 是否有效:"
echo "   open https://github.com/settings/tokens"
