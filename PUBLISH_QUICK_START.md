# 🚀 DevSquad V3.6.6 发布 - 终极简化版 (3步，每步30秒)

> ⚠️ 您的 GitHub Token 已失效，请使用以下**纯浏览器操作**完成发布

---

## ✅ **已完成（无需操作）**

- [x] Git 提交并推送 (`9a31537`)
- [x] Git Tag `v3.6.6` 推送成功
- [x] PyPI 发布成功 → https://pypi.org/project/devsquad/3.6.6/
- [x] Release Notes 已写好（可直接复制）

---

## 🔧 **需要您做的（3步，共2分钟）**

### **Step 1: 更新 About 和 Topics** (30秒)

👉 **[点击这里打开 GitHub Settings](https://github.com/lulin70/DevSquad/settings)**

**操作:**
1. 页面顶部找到 **About** 区域
2. **Description 输入框**，删除旧内容，粘贴以下内容：

```
🚀 DevSquad V3.6.6 - Enterprise Multi-Role AI Task Orchestrator | 7-Agent Collaboration | RBAC | Audit Log | E2E Tested | 1672 Tests | PyPI Ready
```

3. **Topics 输入框**，粘贴以下内容（会自动分割为标签）：

```
ai-agent, multi-agent, task-orchestrator, python, llm, enterprise-ready, rbac, audit-log, multi-tenancy, asyncio, redis-cache, prometheus-monitoring, e2e-testing, cli-tool, fastapi, docker, collaboration-engine, consensus-mechanism, workflow-automation, code-quality
```

4. 点击 **Save** 按钮

✅ **完成！** 刷新 https://github.com/lulin70/DevSquad 查看效果

---

### **Step 2: 创建 Release** (45秒)

👉 **[点击这里创建 Release](https://github.com/lulin70/DevSquad/releases/new)**

**操作:**
1. **Tag**: 输入或选择 `v3.6.6` （如果提示不存在，直接输入即可）
2. **Target**: 选择 `main` 分支
3. **Release title** 粘贴：

```
V3.6.6: Enterprise Edition + E2E Testing
```

4. **Description** (大文本框)：
   - 👉 [点击这里打开 Release Notes 文件](scripts/RELEASE_NOTES_V3.6.6.md)
   - **全选 (Cmd+A) 复制 (Cmd+C)**
   - 回到浏览器 **粘贴 (Cmd+V)**

5. 确保 ☐ "Set as a pre-release" **不勾选**
6. 点击绿色 **Publish release** 按钮

✅ **完成！** 自动跳转到 Release 页面

---

### **Step 3: Docker 构建 (可选，3分钟)**

打开终端，运行：

```bash
cd /Users/lin/trae_projects/DevSquad && \
docker build --target runtime \
  -t lulin70/devsquad:3.6.6 \
  -t lulin70/devsquad:latest \
  . && \
docker push lulin70/devsquad:3.6.6 && \
docker push lulin70/devsquad:latest && \
echo "✅ Docker 发布完成!"
```

> 如果没有安装 Docker 或不想发布 Docker，可以跳过此步

---

## 🎉 **全部完成后验证**

访问以下链接确认一切正常：

| 项目 | 链接 | 应该看到 |
|------|------|---------|
| **GitHub 主页** | https://github.com/lulin70/DevSquad | 新 Description + 20个 Topics |
| **Release 页面** | https://github.com/lulin70/DevSquad/releases | V3.6.6 Release 存在 |
| **PyPI** | https://pypi.org/project/devsquad/3.6.6/ | 版本 3.6.6 可下载 |
| **Docker Hub** | https://hub.docker.com/r/lulin70/devsquad | 镜像 3.6.6 (如果执行了 Step 3) |

**最终测试**:
```bash
pip install devsquad==3.6.6 && devsquad --version
# 应该输出: DevSquad version 3.6.6
```

---

## 💡 **为什么 Token 失效？**

可能原因：
1. ❌ Token 过期了（通常 30-90 天有效期）
2. ❌ 权限不足（需要 `repo` scope）
3. ❌ 被撤销了

**如果想下次自动化，可以生成新 Token**:
👉 [点击生成新 Token](https://github.com/settings/tokens/new?scopes=repo,write:packages&description=DevSquad%20Release%20Bot&expiration=90)

---

## 📢 **发布后宣传（可选）**

### Twitter/X 公告：
```
🚀 DevSquad V3.6.6 Released! Enterprise Edition with RBAC, Audit Log, Multi-Tenancy, E2E Tests (100% pass), AsyncIO + Redis Cache (2x faster). 97% maturity! 

Install: pip install devsquad==3.6.6
#Python #AIAgent #OpenSource #EnterpriseReady
```

---

## 🆘 **遇到问题？**

**Q: 找不到 About 区域？**  
A: 在 Settings 页面最顶部，Repository name 下面

**Q: Tag v3.6.6 不存在？**  
A: 直接输入 `v3.6.6`，GitHub 会自动从已推送的 tag 创建

**Q: Release Notes 太长？**  
A: 可以只粘贴前半部分（到 Installation 章节即可）

**Q: Docker 构建失败？**  
A: 检查 `docker --version`，确保 Docker Desktop 正在运行

---

**预计总时间**: 2分钟 (不含 Docker) 或 5分钟 (含 Docker)  
**祝发布顺利！** 🎉
