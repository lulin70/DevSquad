# PyPI Trusted Publisher 配置指南

> **目标**：为 `devsquad` 包配置 PyPI Trusted Publishing（OIDC），使 `.github/workflows/release.yml` 在推送 `v*` tag 时自动发布到 PyPI，无需长期存储 `PYPI_API_TOKEN`。
> **版本**: 1.0  
> **日期**: 2026-07-01  
> **适用仓库**: `lulin70/DevSquad`

---

## 1. 前置条件

1. 你拥有 GitHub 仓库 `lulin70/DevSquad` 的管理员权限。
2. 你拥有 PyPI 账户，且是项目 `devsquad` 的 Owner 或 Maintainer。
3. 仓库中已存在 `.github/workflows/release.yml`，且 `publish-pypi` job 已配置 `permissions: id-token: write` 和 `environment: pypi`（当前已满足）。

---

## 2. 在 PyPI 端添加 Trusted Publisher

### 2.1 进入配置页面

访问：

```text
https://pypi.org/manage/account/publishing/
```

或在项目 `devsquad` 的管理页面中选择 **"Publishing"** → **"Add a new pending publisher"**。

### 2.2 填写字段

按以下字段填写：

| 字段 | 值 | 说明 |
|------|-----|------|
| **PyPI Project Name** | `devsquad` | 必须与 `pyproject.toml` 中的 `name` 一致 |
| **Owner** | `lulin70` | GitHub 仓库所有者 |
| **Repository name** | `DevSquad` | 仓库名称 |
| **Workflow name** | `.github/workflows/release.yml` | release 工作流路径 |
| **Environment name** | `pypi` | 必须与 `release.yml` 中 `environment: pypi` 一致 |

### 2.3 保存

点击 **"Add"** 后，PyPI 会生成一个 pending publisher。保存后，配置立即生效。

---

## 3. 在 GitHub 端配置 Environment Protection（推荐）

为防止误触发或恶意 tag 直接发布，建议为 `pypi` environment 添加保护规则：

1. 访问 `https://github.com/lulin70/DevSquad/settings/environments`
2. 点击 **"New environment"**，名称填写 `pypi`
3. 勾选 **"Required reviewers"**，添加至少 1 名审核人
4. （可选）勾选 **"Deployment branches and tags"**，限制仅 `v*` tag 可部署
5. 点击 **"Save protection rules"**

> 注意：如果 `pypi` environment 不存在，首次触发 release 时 GitHub 会自动创建，但不会有保护规则。建议提前配置。

---

## 4. 验证配置

### 4.1 本地模拟版本检查

在推送 tag 前，确保版本一致性脚本通过：

```bash
python scripts/check_version_consistency.py --strict
```

预期输出：`15 passed, 0 failed`。

### 4.2 推送 tag 触发 release

```bash
# 确保当前版本已 bump 并同步到所有文件
git tag -a v3.9.2 -m "Release DevSquad v3.9.2"
git push origin v3.9.2
```

或如果 `v3.9.2` 已推送但发布失败，可创建 post-release：

```bash
git tag -a v3.9.2.post1 -m "Post-release v3.9.2.post1"
git push origin v3.9.2.post1
```

### 4.3 观察 GitHub Actions

1. 访问 `https://github.com/lulin70/DevSquad/actions`
2. 找到 `Release` workflow 运行记录
3. `build` job 应显示绿色
4. `publish-pypi` job 会暂停在 `pypi` environment 审核步骤（如果配置了 reviewers）
5. 审核人批准后，`publish-pypi` 继续执行
6. 若 PyPI publisher 配置正确，日志应显示成功发布；若配置错误，会出现 `invalid-publisher` 错误

### 4.4 验证 PyPI 上的包

发布成功后，等待 30-60 秒索引：

```bash
pip install --no-deps "devsquad==3.9.2" --target /tmp/verify_install
python -c "import sys; sys.path.insert(0,'/tmp/verify_install'); from scripts.collaboration._version import __version__; print(__version__)"
```

应输出：`3.9.2`。

---

## 5. 常见问题

### Q1: 出现 `invalid-publisher` 错误

含义：PyPI 收到了有效的 OIDC token，但找不到匹配的 publisher。

排查：
- 检查 PyPI 填写的 Owner/Repository/Workflow/Environment 是否与 `release.yml` 完全一致
- 注意大小写：`DevSquad` vs `devsquad`
- 检查 `release.yml` 中 `publish-pypi` job 是否有 `environment: pypi`

### Q2: 出现 `missing or insufficient OIDC token permissions`

含义：GitHub Actions 没有获取 OIDC token 的权限。

排查：
- 确保 `publish-pypi` job 有 `permissions: id-token: write`
- 不要在工作流顶层用 `permissions: contents: write` 覆盖掉 job 级权限（当前已正确配置）

### Q3: 出现 `version already exists`

含义：该版本已发布到 PyPI。

处理：
- 如果是有意重新发布，需先删除 PyPI 上的该版本（通常不推荐）
- 否则创建新的 post-release tag，如 `v3.9.2.post1`

---

## 6. 安全说明

- Trusted Publishing 优于长期存储 `PYPI_API_TOKEN`，因为 token 是临时的、每次运行新生成
- 建议为 `pypi` environment 配置 required reviewers，防止未授权 tag 自动发布
- 建议限制 tag 匹配规则为 `v*`，避免分支推送触发 release

---

## 7. 相关文件

- [`.github/workflows/release.yml`](https://github.com/lulin70/DevSquad/blob/main/.github/workflows/release.yml)
- [`scripts/check_version_consistency.py`](https://github.com/lulin70/DevSquad/blob/main/scripts/check_version_consistency.py)
- [`docs/PROJECT_TIDY_FIX_REPORT_V3.9.2_round9.md`](./PROJECT_TIDY_FIX_REPORT_V3.9.2_round9.md)
