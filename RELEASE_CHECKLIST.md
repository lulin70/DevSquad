# DevSquad Release Checklist

> 发布前必执行的检查清单。每项必须 ✅ 通过才能发布。

## 1. 版本一致性

```bash
# 检查所有版本源（VERSION / _version.py / SKILL.md / CLAUDE.md / pyproject.toml 等）
python scripts/check_version_consistency.py --strict
```

- [ ] 全部检查通过（以脚本实际输出为准；可选 TRAE 缓存层在缺失环境中显示 SKIP，不计失败）
- [ ] `SKILL.md` frontmatter 含 `version: X.Y.Z` 字段
- [ ] `skill-manifest.yaml` 的 `version:` 与 `_version.py` 一致
- [ ] `CLAUDE.md` 版本引用已更新
- [ ] CHANGELOG.md 最新条目为当前版本（V4.4.1+ EN-only；CHANGELOG-CN.md 已于 V4.4.1 退役）

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
pytest tests/e2e/test_lifecycle_cli_scan_e2e.py tests/e2e/test_remediation_patch_e2e.py -q
pytest tests/test_autonomous.py -q
pytest tests/test_dispatcher.py -q
pytest tests/test_consensus.py -q
```

- [ ] 全量测试通过（无新增失败）
- [ ] autonomous LLM 装配测试通过（`TestDispatchAutonomousLLMWiring`）
- [ ] 无 skip 测试（除非有明确理由并记录）

## 4. 代码质量

```bash
# Lint（全仓）
ruff check .

# 格式检查（全仓唯一格式化门禁）
ruff format --check .
```

- [ ] ruff 无错误
- [ ] 无未使用的 import
- [ ] 无调试代码残留（print / breakpoint / TODO hack）

## 5. 文档

- [ ] README.md / README-CN.md 版本号已更新
- [ ] CHANGELOG.md 已添加本次版本条目
- [ ] docs/PROJECT_STATUS.md 已刷新至本次发布现实（代码版本 / 发布状态 / PyPI 实测链接 / GitHub Release 链接；PyPI 版本须附采集命令并实测，禁止沿用上次数字）
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

# 确认当前分支和未推送 commit
git branch --show-current
git log origin/<current-branch>..HEAD --oneline

# 检查 PR 状态和所有 CI 检查
gh pr checks <number> --repo <owner>/<repo>
gh pr view <number> --repo <owner>/<repo> --json state,mergeStateStatus,statusCheckRollup
```

- [ ] 工作树干净（无未提交的修改）
- [ ] 变更已推送到功能分支
- [ ] 已创建 Pull Request；不直接推送 `main`
- [ ] 所有必需 CI 和安全检查通过
- [ ] 自审已完成，PR 对话已解决
- [ ] 单维护者模式：不要求第二位维护者批准；由仓库所有者在 CI 通过后合并
- [ ] 多维护者模式：恢复至少 1 个其他维护者批准后再合并
- [ ] 本批 Git tag / GitHub Release 按当批发布裁定执行（如 P0 执行计划 §4.2 默认裁定：独立小发布含 tag）；裁定记录于执行计划 §10
- [ ] GitHub Release / tag 与当批裁定不一致时，先重裁定再行动，禁止事后改单
- [ ] `.github/workflows/devsquad-gate.yml` 的 `devsquad-version` 默认值已随本次发布 bump（V4.8.0 起；`tests/unit/test_devsquad_gate_workflow.py::TestReusability::test_declared_inputs_match_the_design` 锚定该默认值，必须同 PR 同步更新，否则结构防腐测试红）
- [ ] QUICKSTART 通道 C 的 `uses: lulin70/DevSquad/.github/workflows/devsquad-gate.yml@vX.Y.Z` 示例 ref 已指向本次 tag

## 8. 发布后验证

- [ ] `pip install devsquad==X.Y.Z` 可正常安装
- [ ] `devsquad --version` 显示正确版本
- [ ] `devsquad demo` 可正常运行
- [ ] TRAE 技能列表显示正确版本号
- [ ] docs/PROJECT_STATUS.md 发布后已更新（PyPI 链接 / GitHub Release 链接 / 最后更新日期；实测采集，不沿用旧数字）
- [ ] E2E：模拟真实用户使用流程（CLI + TRAE skill 调用）
- [ ] 生命周期扫描 E2E：CLI/REST 显式文档扫描和 JUnit 证据适配通过
- [ ] 修复建议 E2E：未批准不写文件；批准后测试/重扫通过；失败回滚

---

## 历史教训

- **V4.0.0**: TRAE 有 3 层技能缓存（global/workspace/project），只更新主仓库不会刷新技能列表。必须运行 `sync_trae_skill.sh`。
- **V3.9.x**: `dispatch_autonomous()` 漏传 `llm_backend` 导致生产路径幽灵功能（pytest 通过但 TRAE 实际调用回退 mock）。发布前必须验证生产路径装配。
- **V3.6.x-V3.8.x**: 版本号在多个文件间漂移。`check_version_consistency.py` 由此引入。
- **V4.7.1（2026-10-20 复盘）**: docs/PROJECT_STATUS.md 落后两个发布版本（仍写"V4.7.0 未打 tag、PyPI 最新 4.6.0"，实测 v4.7.1 已 tag + Release + PyPI）。状态文档刷新由此入清单（§5/§8）；用户可见面另有 6 处过时版本串，由 V4.7.2 门禁负向扫描根治。
