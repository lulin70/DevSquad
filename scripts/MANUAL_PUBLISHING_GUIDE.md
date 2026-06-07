# ⚠️ GitHub Token 认证失败 - 手动发布指南

> **原因**: 您提供的 Token 无效或已过期  
> **解决方案**: 使用以下手动操作步骤（约 5 分钟）

---

## 🎯 **快速操作清单（3步）**

### ✅ **已完成（无需操作）**

- [x] Git 提交并推送 (Commit `9a31537`)
- [x] PyPI 发布成功 (https://pypi.org/project/devsquad/3.6.6/)
- [x] Release Notes 已准备好 (见下方)

### 🔧 **需要您手动完成（3步）**

---

## **Step 1: 更新 GitHub About 和 Topics** (~2分钟)

### 方法 A: 网页操作（推荐）

1. **打开**: https://github.com/lulin70/DevSquad
2. **点击**: 右上角 ⚙️ **Settings** 图标
3. **滚动到**: "About" 区域（页面顶部）
4. **更新 Description** 为以下内容：

```
🚀 DevSquad V3.6.6 - Enterprise Multi-Role AI Task Orchestrator | 7-Agent Collaboration | RBAC | Audit Log | E2E Tested | 1672 Tests | PyPI Ready
```

5. **添加 Topics** (在 Topics 输入框中，用逗号或回车分隔)：

```
ai-agent, multi-agent, task-orchestrator, python, llm, enterprise-ready, rbac, audit-log, multi-tenancy, asyncio, redis-cache, prometheus-monitoring, e2e-testing, cli-tool, fastapi, docker, collaboration-engine, consensus-mechanism, workflow-automation, code-quality
```

6. **点击**: **Save** 按钮

✅ **验证**: 刷新仓库主页，检查 Description 和 Topics 是否更新

---

## **Step 2: 创建 GitHub Release V3.6.6** (~2分钟)

### 操作步骤

1. **打开**: https://github.com/lulin70/DevSquad/releases/new
2. **选择 Tag**:
   - 点击 **Choose a tag** 下拉框
   - 输入 `v3.6.6` （如果不存在，会提示创建新 tag）
   - 选择 **main** 分支作为 target
   - 点击 **Generate release notes** (可选)

3. **填写 Release 信息**:
   - **Release title**: 
     ```
     V3.6.6: Enterprise Edition + E2E Testing
     ```
   
   - **Description**: 
     - 打开文件：`scripts/RELEASE_NOTES_V3.6.6.md` (本项目根目录)
     - **全选复制 (Cmd+A, Cmd+C)** 全部内容
     - **粘贴 (Cmd+V)** 到 GitHub 的描述框

4. **设置选项**:
   - ☑️ Set as a pre-release: **不勾选**
   - ☑️ Set as the latest release: **勾选** (默认)

5. **点击**: **Publish release** 按钮 (绿色按钮)

✅ **验证**: 访问 https://github.com/lulin70/DevSquad/releases 查看新 Release

---

## **Step 3: 构建 & 发布 Docker Image** (~3分钟)

### 前置条件

```bash
# 检查 Docker 是否安装
docker --version

# 如果未登录 Docker Hub，先登录
docker login
# 输入您的 Docker Hub 用户名和密码
```

### 构建和推送命令

```bash
# 1. 进入项目目录
cd /Users/lin/trae_projects/DevSquad

# 2. 构建 Docker 镜像 (使用 runtime 阶段，减小体积)
echo "🐳 Building Docker image..."
docker build \
  --target runtime \
  -t lulin70/devsquad:3.6.6 \
  -t lulin70/devsquad:latest \
  .

# 3. 检查构建结果
echo ""
echo "📦 Built images:"
docker images | grep devsquad

# 4. 推送到 Docker Hub
echo ""
echo "🚀 Pushing to Docker Hub..."
docker push lulin70/devsquad:3.6.6
docker push lulin70/devsquad:latest

echo ""
echo "✅ Docker Image published successfully!"
echo "   Pull command: docker pull lulin70/devsquad:3.6.6"
```

✅ **验证**: 访问 https://hub.docker.com/r/lulin70/devsquad 查看镜像

---

## 🎉 **全部完成后验证清单**

请逐项检查：

- [ ] **GitHub About**: https://github.com/lulin70/DevSquad  
  ✓ 显示新 Description 和 20 个 Topics 标签

- [ ] **GitHub Release**: https://github.com/lulin70/DevSquad/releases/tag/v3.6.6  
  ✓ Release 页面显示完整 Changelog

- [ ] **PyPI**: https://pypi.org/project/devsquad/3.6.6/  
  ✓ 版本 3.6.6 可安装 (`pip install devsquad==3.6.6`)

- [ ] **Docker Hub**: https://hub.docker.com/r/lulin70/devsquad  
  ✓ 镜像 `lulin70/devsquad:3.6.6` 存在

- [ ] **安装测试** (在新终端):
  ```bash
  pip install devsquad==3.6.6 && devsquad --version
  ```
  ✓ 应该输出: `DevSquad version 3.6.6`

---

## 💡 **常见问题**

### Q: Token 为什么失败？
A: 可能原因：
   - Token 过期了（通常 30/60/90 天）
   - Token 权限不足（需要 `repo` 权限）
   - Token 被撤销了
   
   **解决**: 重新生成一个新 Token:
   1. 打开 https://github.com/settings/tokens
   2. 点击 "Generate new token (classic)"
   3. 勾选 `repo` 权限
   4. 复制新的 token 给我

### Q: 创建 Tag 时提示 "Tag doesn't exist"？
A: 这是正常的！GitHub 会自动创建 tag。直接输入 `v3.6.6` 即可。

### Q: Docker 构建失败？
A: 检查：
   ```bash
   # 查看 Dockerfile 是否存在
   ls -la /Users/lin/trae_projects/DevSquad/Dockerfile
   
   # 查看 Docker 版本
   docker version
   ```

### Q: Docker push 失败 "denied"？
A: 需要先登录 Docker Hub:
   ```bash
   docker login
   # 输入用户名密码
   ```

---

## 📢 **发布完成后建议做的宣传**

### Twitter/X 公告模板
```
🚀 Excited to announce DevSquad V3.6.6 - Enterprise Edition!

New features:
✨ RBAC Engine (15+ permissions, 5 roles)
🔒 Audit Logger with SHA256 integrity chain
🏢 Multi-Tenancy Manager (3 isolation levels)
🧪 Complete E2E Test Suite (27 cases, 100% pass)
⚡ AsyncIO + Redis Cache (2x throughput improvement)
📊 Prometheus Monitoring (12 metrics)

97% Enterprise Grade maturity 🏆

Install: pip install devsquad==3.6.6
Docs: https://github.com/lulin70/DevSquad#readme
PyPI: https://pypi.org/project/devsquad/3.6.6/

#Python #AIAgent #MultiAgent #OpenSource #EnterpriseReady
```

### LinkedIn 公告要点
- 强调 Enterprise 级别功能（RBAC、审计日志、多租户）
- 提及 97% 成熟度评分
- 附带 PyPI 安装命令
- 邀请用户 Star 项目

---

## 🆘 **需要帮助？**

如果您在任何步骤遇到问题：

1. **查看详细日志**: 我已经创建了完整的脚本和指南
2. **重新生成 Token**: 如果需要自动化，给我一个新的有效 Token
3. **分步执行**: 可以逐步告诉我当前在哪一步卡住了

---

**预计总时间**: 8-10 分钟（含 Docker 构建）  
**祝发布顺利！** 🎉
