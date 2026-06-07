#!/bin/bash
# DevSquad V3.6.5 发布脚本 (SSH 认证版本)
# 前置条件: Git Tag v3.6.5 已推送，gh CLI 需要登录

set -e

echo "🚀 DevSquad V3.6.5 发布脚本 (SSH Mode)"
echo "======================================"
echo ""

# 配置
REPO="lulin70/DevSquad"
VERSION="3.6.5"
DOCKER_IMAGE="lulin70/devsquad"

# 检查 gh CLI 是否登录
if ! gh auth status &> /dev/null; then
    echo "❌ 错误: gh CLI 未登录"
    echo ""
    echo "请在终端运行以下命令登录:"
    echo ""
    echo "  方法 A (推荐 - Token):"
    echo "    1. 打开: https://github.com/settings/tokens/new?scopes=repo,write:packages"
    echo "    2. 生成 Token 并复制"
    echo "    3. 运行: echo '你的Token' | gh auth login --with-token"
    echo ""
    echo "  方法 B (设备码):"
    echo "    运行: gh auth login --web"
    echo "    然后在浏览器中输入显示的设备码"
    echo ""
    exit 1
fi

echo "✅ gh CLI 已登录"
echo ""

# ============================================
# Step 1: 创建 GitHub Release
# ============================================
echo "📦 Step 1/3: 创建 GitHub Release V${VERSION}..."
echo "----------------------------------------"

# 使用 gh release create
gh release create v${VERSION} \
    --title "V${VERSION}: Enterprise Edition + E2E Testing" \
    --notes-file scripts/RELEASE_NOTES_V3.6.5.md \
    --repo ${REPO}

echo "✅ GitHub Release 创建成功!"
echo "   URL: https://github.com/${REPO}/releases/tag/v${VERSION}"
echo ""

# ============================================
# Step 2: 更新 About 和 Topics
# ============================================
echo "📝 Step 2/3: 更新 GitHub About 和 Topics..."
echo "----------------------------------------"

# 使用 gh api 更新 repo 信息
gh api repos/${REPO} \
    -X PATCH \
    -f name="DevSquad" \
    -f description="🚀 DevSquad V${VERSION} - Enterprise Multi-Role AI Task Orchestrator | 7-Agent Collaboration | RBAC | Audit Log | E2E Tested | 1731 Tests | PyPI Ready" \
    -f homepage="https://pypi.org/project/devsquad/" \
    -f topics='["ai-agent","multi-agent","task-orchestrator","python","llm","enterprise-ready","rbac","audit-log","multi-tenancy","asyncio","redis-cache","prometheus-monitoring","e2e-testing","cli-tool","fastapi","docker","collaboration-engine","consensus-mechanism","workflow-automation","code-quality"]' \
    --quiet

echo "✅ GitHub About 和 Topics 更新成功!"
echo "   Description: 🚀 DevSquad V${VERSION} - Enterprise Multi-Role AI Task Orchestrator"
echo "   Topics: 20 tags updated"
echo ""

# ============================================
# Step 3: 构建 & 发布 Docker Image
# ============================================
echo "🐳 Step 3/3: 构建并发布 Docker Image..."
echo "----------------------------------------"

if [ ! -f "Dockerfile" ]; then
    echo "⚠️  警告: Dockerfile 不存在，跳过 Docker 发布"
else
    # 检查 Docker 是否登录
    if ! docker info &> /dev/null; then
        echo "⚠️  Docker 未运行或未登录，跳过 Docker 发布"
        echo "   您可以稍后手动执行:"
        echo "   docker build --target runtime -t ${DOCKER_IMAGE}:${VERSION} . && docker push ${DOCKER_IMAGE}:${VERSION}"
    else
        # 构建镜像
        echo "   Building runtime image..."
        docker build \
            --target runtime \
            -t ${DOCKER_IMAGE}:${VERSION} \
            -t ${DOCKER_IMAGE}:latest \
            .
        
        if [ $? -eq 0 ]; then
            echo "   ✅ Docker 镜像构建成功!"
            
            # 推送镜像
            echo "   Pushing to Docker Hub..."
            docker push ${DOCKER_IMAGE}:${VERSION}
            docker push ${DOCKER_IMAGE}:latest
            
            echo "   ✅ Docker Image 发布成功!"
            echo "   Images:"
            echo "     - ${DOCKER_IMAGE}:${VERSION}"
            echo "     - ${DOCKER_IMAGE}:latest"
        else
            echo "❌ Docker 构建失败"
            exit 1
        fi
    fi
fi

echo ""
echo "=============================="
echo "🎉 DevSquad V${VERSION} 发布完成!"
echo ""
echo "📦 发布清单:"
echo "  ✅ Git Tag v${VERSION} pushed via SSH"
echo "  ✅ GitHub Release created"
echo "  ✅ GitHub About & Topics updated (20 tags)"
echo "  ✅ Docker Image published (if available)"
echo ""
echo "🔗 重要链接:"
echo "  • PyPI:    https://pypi.org/project/devsquad/${VERSION}/"
echo "  • GitHub:  https://github.com/${REPO}"
echo "  • Release: https://github.com/${REPO}/releases/tag/v${VERSION}"
echo "  • Docker:  https://hub.docker.com/r/${DOCKER_IMAGE}"
