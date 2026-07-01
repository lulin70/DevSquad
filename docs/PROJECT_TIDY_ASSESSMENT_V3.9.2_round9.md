# DevSquad 项目整理评估报告 — Round 9

> **评估日期**: 2026-06-30  
> **评估对象**: DevSquad V3.9.2 (`/Users/lin/trae_projects/DevSquad`)  
> **评估方法**: 7 维度独立评分 + 硬约束真实校验 + 命令输出证据  
> **上一轮自评**: 第八轮技术债清零 — 综合 9.3/10, A（2026-06-30 commit 4678f29）  
> **本轮独立评估**: **6.6/10, C+**（与自评差距 -2.7）

---

## 1. 执行摘要

本次评估采用 DevSquad Skill 定义的多角色协作流程，并行派出 6 个独立评估 Agent 对代码质量、测试质量、文档一致性、CI/CD、架构安全、目录结构与技术债务 6 个维度进行检查，并由 Coordinator 汇总验证。

**核心结论**：项目在经历 8 轮优化后，静态代码质量（ruff/mypy/bandit）达到较高水准，但**测试覆盖率、文档一致性、依赖可复现性**存在被上一轮自评掩盖的严重问题。特别是 `docs/PROJECT_STATUS.md` 声称“版本号一致性 15/15 PASS”，但根目录 `VERSION` 文件实际缺失；声称“E2E 模拟真实用户测试 PASS”，但 `pyproject.toml` 默认将 E2E/集成目录排除在 pytest 之外。这些问题直接挑战了发布就绪判断。

---

## 2. 7 维度评分表

| 维度 | 本轮得分 | 等级 | 上一轮自评 | 关键短板 |
|------|---------:|------|------------|----------|
| 代码质量 | 7.8 | B+ | A | `skills/` 未纳入 mypy；async 返回注解覆盖率 73% |
| 测试质量 | 4.0 | D+ | A | 覆盖率 25.26%；E2E/集成默认被排除；缺失关键测试文件 |
| 文档一致性 | 5.0 | C | A | VERSION 文件缺失；SKILL.md 模块数滞后；CHANGELOG 重复版本节 |
| CI/CD | 7.0 | B | A | Dockerfile 缺 ARG VERSION；requirements-dev.lock 缺失；lock 不完整 |
| 架构与安全 | 8.0 | B+ | A | api_security/cookie 生产覆盖未自动落地；API Key 比较未用 compare_digest |
| 目录结构与债务 | 7.5 | B+ | A | `scripts/tools/`、`tests/manual/` 仍存在；幽灵功能；51 处 pass 占位 |
| **综合** | **6.6** | **C+** | **9.3/A** | — |

**评分口径**：0-10 分，≥9 A，≥8 B+，≥7 B，≥6 C+，≥5 C。

---

## 3. 硬约束真实校验

项目硬约束要求 13/13 PASS。本次独立验证发现部分约束状态与 `docs/PROJECT_STATUS.md` 不一致。

| 硬约束 | PROJECT_STATUS.md 声称 | 独立验证结果 | 证据 |
|--------|------------------------|--------------|------|
| 版本号一致性 | ✅ PASS (15/15) | ⚠️ **FAIL** | 根目录 `VERSION` 文件不存在；`_version.py` 仅 3.9.2 |
| 依赖锁文件 | ✅ PASS | ⚠️ **部分 FAIL** | `requirements-dev.lock` 缺失；`requirements.lock` 注释表明核心依赖未锁定 |
| E2E 模拟真实用户测试 | ✅ PASS | ⚠️ **FAIL** | `pyproject.toml` 默认 `norecursedirs` 排除 `tests/e2e`、`tests/integration` |
| 覆盖率门禁 | 未明确 | ⚠️ **FAIL** | `coverage.json` 实测 25.26%，远低于 `pyproject.toml` `fail_under = 60` |
| RBAC fail-closed | ✅ PASS | ✅ PASS | `dispatcher.py:424-456` + `test_rbac_fail_closed.py` 验证 |
| ConsensusGate 前置介入 | ✅ PASS | ✅ PASS | `dispatch_steps.py:231` 在结果组装前调用 |
| PBKDF2 密码存储 | ✅ PASS | ✅ PASS | `auth.py:205-222` 使用 PBKDF2-HMAC-SHA256 |
| 一键启动脚本 start.sh | ✅ PASS | ✅ PASS | 文件存在且结构完整 |
| CI mypy 阻塞 | ✅ PASS | ✅ PASS | `test.yml` mypy job 无 `continue-on-error` |
| release.yml 含 publish-pypi | ✅ PASS | ✅ PASS | 3 jobs 含 build/publish-pypi/github-release |
| git tag 作为发布触发器 | ✅ PASS | ✅ PASS | v3.9.2 tag 已本地创建 |
| 不在 localStorage 明文存敏感信息 | ✅ PASS | ✅ PASS | 未检出 |
| 专业版路由 API Key 验证 | ✅ PASS | ✅ PASS | 未检出违规 |

**硬约束真实通过率**: **9/13 PASS，4/13 存在争议或 FAIL**。

---

## 4. 关键问题清单（按优先级）

### P0 — 发布阻塞项

| ID | 问题 | 证据 | 建议 |
|----|------|------|------|
| P0-1 | **VERSION 文件缺失，版本号一致性校验虚假 PASS** | `ls VERSION` → No such file；`scripts/collaboration/_version.py` 存在 `__version__ = "3.9.2"` | 恢复根目录 `VERSION` 文件；在版本一致性校验脚本中增加文件存在性检查 |
| P0-2 | **测试覆盖率仅 25.26%，远低于 60% 门禁** | `coverage.json`: `percent_covered: 25.256893860561913`, `percent_branches_covered: 9.042236763831053` | 将覆盖率接入 CI 阻断；优先为核心编排模块补单测；明确豁免清单 |
| P0-3 | **E2E/集成测试默认被 pytest 排除** | `pyproject.toml`: `norecursedirs = [..., "tests/integration", "tests/e2e"]` | 改为 marker 过滤（`-m "not e2e"`），确保 CI/本地默认可选择运行 |
| P0-4 | **SKILL.md 模块数严重滞后** | SKILL.md 写“118 core modules”，实际 `ls scripts/collaboration/*.py | wc -l` = 149 | 统一改为 149+ modules / 2857+ tests |

### P1 — 高优先级

| ID | 问题 | 证据 | 建议 |
|----|------|------|------|
| P1-1 | `skills/` 未纳入 mypy 类型检查 | `mypy scripts/` 0 错误；`mypy skills/` 60+ 错误 | 将 `skills/` 加入 CI type check，或先在 pyproject.toml 逐步开启 |
| P1-2 | async 函数返回注解覆盖率 73% | 160 个 `async def` 中 117 个带返回注解 | 补齐公共 async API 与核心协程注解，目标 ≥90% |
| P1-3 | 缺少 `tests/test_version.py`、`test_docker_deployment.py`、`test_data_backup.py` | `ls` 返回 No such file | 按硬约束要求补齐；建议与版本 bump 脚本联动 |
| P1-4 | `requirements-dev.lock` 缺失；`requirements.lock` 不完整 | 目录只有 `requirements-dev.txt`；lock 中 `fastapi/uvicorn/pydantic` 被注释为未锁定 | 生成完整 lock；CI 增加 lock 与安装一致性校验 |
| P1-5 | Dockerfile 缺少 `ARG VERSION` | `Dockerfile` 仅 `LABEL version="3.9.2"` | 新增 `ARG VERSION=3.9.2` 并在构建中引用 |
| P1-6 | SKILL.md 仍列出已删除模块 | `PromptVariantGenerator`、`ConfigManager`、`RoleTemplateMarket`、`AlertManager` 带 *(Removed)* 标记 | 删除或移入历史附录 |
| P1-7 | `scripts/tools/`、`tests/manual/` 已清理 | `_find_missing_hints.py` 迁移至 `scripts/utils/`；其余工具与手动测试已删除；`.gitignore` 与文档已同步 | 完成 |
| P1-8 | 幽灵功能：`test_quality_guard.py` 的 `project_audit`/`quick_audit`/`validate_call_against_signature` | `grep` 仅命中定义与测试 | 标记为 internal utility 并在代码注释与文档中说明，保留给测试/外部审计使用 |
| P1-9 | api_security 生产模式强制 enabled=true 未在代码层落地 | `deployment.yaml` 顶层 `enabled=false`；`api/security.py` 未合并 environments 覆盖 | 按 `DEVSQUAD_ENV` 合并环境配置；生产模式禁用 dev bypass |
| P1-10 | Cookie 安全配置依赖 YAML 覆盖而非代码强制 | `auth.py:168-194` 仅告警，不强制 secure/Strict | 生产模式代码层强制覆盖 cookie 安全属性 |

### P2 — 中优先级

| ID | 问题 | 证据 | 建议 |
|----|------|------|------|
| P2-1 | API Key 哈希比较未使用 `hmac.compare_digest` | `scripts/api/security.py:144-145` 直接 dict.get 比对 | 遍历存储哈希并用恒定时间比较 |
| P2-2 | 部署文档仍指导使用 SHA-256 | `config/deployment.yaml`、`config/samples/env.production` 写“SHA-256 hashed” | 同步为 PBKDF2 生成命令 |
| P2-3 | Prompt injection 检测后未模板降级 | `input_validator.py:191-192` 返回 valid=False；无 fallback 路径 | 触发时返回安全模板响应并审计 |
| P2-4 | CHANGELOG 存在重复 `[3.9.2]` 节 | 第 10 行 2026-06-28、第 23 行 2026-06-26 | 合并或重命名；更新日期与测试数 |
| P2-5 | 三语 README “5 种使用方式”顺序不一致 | EN 顺序 CLI→Dashboard→REST→Python→start.sh；CN/JP 顺序不同 | 统一顺序与编号 |
| P2-6 | pre-commit mypy 范围与 CI 不一致 | `.pre-commit-config.yaml` 仅检查 `scripts/collaboration/` | 扩展为 `scripts/` 全目录 |
| P2-7 | CI 安装步骤隐藏失败 | `test.yml` 使用 `2>/dev/null` + fallback | 移除静默降级，确保 dev 依赖完整安装 |
| P2-8 | `pass` 占位符已复核并标注 | `scripts/` 非抽象/非 fallback 空实现已加 `# intentional no-op` 注释 | 完成 |
| P2-9 | docs/_archive 已部分清理 | 删除无外部引用的过期根报告与 stale archive_v2 文件；保留被引用与有历史价值的归档 | 后续按 6 个月无引用原则继续清理 |

### P3 — 低优先级

| ID | 问题 | 证据 | 建议 |
|----|------|------|------|
| P3-1 | Bandit 完整扫描 38 Low issues | `assert_used` / subprocess 相关 | 生产代码避免 assert 做运行时校验；加 nosec 注释 |
| P3-2 | CORS 未包含 `https://promiselink.cn` | `api_server.py:123-127` 仅 localhost | 如需对接 PromiseLink，通过 env 加入 |
| P3-3 | E2E job 不在 PR 触发 | 仅 schedule/workflow_dispatch/tags | 发布前手动触发 workflow_dispatch 跑通 |
| P3-4 | 性能测试未在 CI 定时运行 | benchmark marker 6 条用例 | 增加定时 benchmark job 并存储基线 |

---

## 5. 与上一轮评估（Round 8）的差异分析

| 维度 | Round 8 自评 | Round 9 独立评估 | 差异原因 |
|------|--------------|------------------|----------|
| 综合 | 9.3/A | 6.6/C+ | -2.7 |
| 代码质量 | A | B+ | 本次独立跑通 `mypy skills/`，发现类型检查缺口 |
| 测试质量 | A | D+ | 上次未实测 `coverage.json`；未发现 E2E 被排除 |
| 文档一致性 | A | C | 上次未验证 `VERSION` 文件存在性；未精读 SKILL.md 过时条目 |
| CI/CD | A | B | 上次未检查 Dockerfile ARG 与 lock 完整性 |
| 架构安全 | A | B+ | 上次未深入代码层验证生产配置强制覆盖 |
| 目录债务 | A | B+ | 上次误以为 `scripts/tools/`、`tests/manual/` 已清理 |

**教训**：自评数据必须与真实命令输出对账，否则容易出现“虚假 PASS”。本次评估严格执行了“证据附录”要求。

---

## 6. 行动计划建议

### 阶段 1：发布前必须完成（P0，阻塞）
1. 恢复 `VERSION` 文件并同步 `_version.py`
2. 将 `tests/e2e`、`tests/integration` 改由 marker 控制，默认不排除
3. 补齐 `tests/test_version.py`、`test_docker_deployment.py`、`test_data_backup.py`
4. 修复 SKILL.md 模块数与已删除模块残留
5. 制定覆盖率提升计划：优先覆盖 `scripts/collaboration/` 核心编排路径

### 阶段 2：V3.9.2 补丁或 V3.10.0（P1）
1. `skills/` 纳入 mypy；async 注解率提升至 90%
2. 生成完整 `requirements-dev.lock`，修复 `requirements.lock`
3. Dockerfile 增加 `ARG VERSION`
4. 清理 `scripts/tools/`、`tests/manual/`，处理幽灵功能
5. 代码层强制 api_security/cookie 生产安全配置

### 阶段 3：持续改进（P2-P3）
1. API Key 比较改用 `hmac.compare_digest`
2. 部署文档同步 PBKDF2
3. Prompt injection 模板降级
4. 三语 README 对齐、CHANGELOG 整理
5. CI 增加覆盖率阻断与定时 benchmark

---

## 7. 证据附录

### A. 版本号文件缺失
```bash
$ ls -la /Users/lin/trae_projects/DevSquad/VERSION
ls: /Users/lin/trae_projects/DevSquad/VERSION: No such file or directory

$ cat /Users/lin/trae_projects/DevSquad/scripts/collaboration/_version.py
__version__ = "3.9.2"
```

### B. 覆盖率实测
```bash
$ cat coverage.json | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['totals']['percent_covered'], d['totals']['percent_branches_covered'])"
25.256893860561913 9.042236763831053
```

### C. E2E/集成默认排除
```toml
# pyproject.toml
[tool.pytest.ini_options]
norecursedirs = [
    "tests/manual",
    "tests/integration",
    "tests/e2e",
]
```

### D. 遗留目录清理结果
```bash
$ ls /Users/lin/trae_projects/DevSquad/scripts/tools/
ls: /Users/lin/trae_projects/DevSquad/scripts/tools/: No such file or directory

$ ls /Users/lin/trae_projects/DevSquad/scripts/utils/
_find_missing_hints.py

$ ls /Users/lin/trae_projects/DevSquad/tests/manual/
ls: /Users/lin/trae_projects/DevSquad/tests/manual/: No such file or directory
```

### E. 未提交改动规模
```bash
$ git diff --stat | tail -3
 94 files changed, 1518 insertions(+), 1899 deletions(-)
```

---

## 8. 结论

DevSquad V3.9.2 在静态代码质量、核心安全控制、CI 基础框架方面已具备较高完成度，但**本轮独立评估发现多项被上一轮自评掩盖的关键问题**。项目**尚未达到发布就绪状态**，主要阻塞项为：版本号文件缺失、测试覆盖率严重不足、E2E/集成默认被排除、文档模块数严重滞后。

建议在完成 P0 修复并重新跑通全量测试与文档一致性校验后，再进行下一轮评估与 tag 推送。

---

**评估报告生成时间**: 2026-06-30  
**评估人**: DevSquad Multi-Agent Assessment Team  
**下轮目标**: 修复 P0/P1 后，综合得分回升至 ≥8.5/A-
