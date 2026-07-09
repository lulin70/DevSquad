# DevSquad Release Checklist

> 发布前必执行的检查清单。每项必须 ✅ 通过才能发布。

## 1. 版本一致性

```bash
# 检查所有版本源（VERSION / _version.py / SKILL.md / CLAUDE.md / pyproject.toml 等）
python scripts/check_version_consistency.py --strict
```

- [ ] 15/15 检查通过
- [ ] `SKILL.md` frontmatter 含 `version: X.Y.Z` 字段
- [ ] `skill-manifest.yaml` 的 `version:` 与 `_version.py` 一致
- [ ] `CLAUDE.md` 版本引用已更新
- [ ] CHANGELOG.md / CHANGELOG-CN.md 最新条目为当前版本

## 2. TRAE 技能缓存同步

TRAE 有 3 层技能缓存，主仓库更新后必须同步，否则技能列表显示旧版本。

```bash
# 预览（不实际执行）
bash scripts/sync_trae_skill.sh --dry-run

# 实际同步（自动备份旧文件）
bash scripts/sync_trae_skill.sh
```

- [ ] Global 缓存 `~/.trae/skills/devsquad/` 已同步
- [ ] Workspace 缓存 `<projects>/.trae/skills/devsquad/` 已同步
- [ ] Project 缓存 `<DevSquad>/.trae/skills/devsquad/` 已同步
- [ ] TRAE 中 `Cmd+Shift+P` → `Developer: Reload Window` 后技能列表显示正确版本

## 3. 测试

```bash
# 全量测试
pytest tests/ -q

# 关键模块测试
pytest tests/test_autonomous.py -q
pytest tests/test_dispatcher.py -q
pytest tests/test_consensus.py -q
```

- [ ] 全量测试通过（无新增失败）
- [ ] autonomous LLM 装配测试通过（`TestDispatchAutonomousLLMWiring`）
- [ ] 无 skip 测试（除非有明确理由并记录）

## 4. 代码质量

```bash
# Lint
ruff check scripts/ tests/

# 格式检查
ruff format --check scripts/ tests/
```

- [ ] ruff 无错误
- [ ] 无未使用的 import
- [ ] 无调试代码残留（print / breakpoint / TODO hack）

## 5. 文档

- [ ] README.md / README-CN.md 版本号已更新
- [ ] CHANGELOG.md 已添加本次版本条目
- [ ] docs/spec/ 下的 spec 文档与代码一致
- [ ] .env.example 与实际使用的环境变量一致

## 6. 安全

- [ ] `.env` 未被 git 跟踪（`.gitignore` 包含）
- [ ] 代码中无硬编码 API key / 密码 / token
- [ ] `SKILL.md` / `skill-manifest.yaml` 中无敏感信息
- [ ] install 脚本不包含明文密钥

## 7. Git 与发布

```bash
# 确认工作树状态
git status

# 确认无未推送的 commit
git log origin/main..HEAD --oneline
```

- [ ] 工作树干净（无未提交的修改）
- [ ] 所有 commit 已推送到 origin/main
- [ ] Git tag 已创建（`git tag vX.Y.Z`）
- [ ] GitHub Release 已发布（含 CHANGELOG 摘要）

## 8. 发布后验证

- [ ] `pip install devsquad==X.Y.Z` 可正常安装
- [ ] `devsquad --version` 显示正确版本
- [ ] `devsquad demo` 可正常运行
- [ ] TRAE 技能列表显示正确版本号
- [ ] E2E：模拟真实用户使用流程（CLI + TRAE skill 调用）

---

## 历史教训

- **V4.0.0**: TRAE 有 3 层技能缓存（global/workspace/project），只更新主仓库不会刷新技能列表。必须运行 `sync_trae_skill.sh`。
- **V3.9.x**: `dispatch_autonomous()` 漏传 `llm_backend` 导致生产路径幽灵功能（pytest 通过但 TRAE 实际调用回退 mock）。发布前必须验证生产路径装配。
- **V3.6.x-V3.8.x**: 版本号在多个文件间漂移。`check_version_consistency.py` 由此引入。
