#!/usr/bin/env python3
"""P0 Docker deployment sanity checks.

Statically verifies that the Dockerfile exists, declares a build-time
VERSION argument, and contains the expected production runtime structure.

Actual image build is not run in this environment (no Docker daemon), so the
"image build基础检查" is implemented by validating the Dockerfile stages and
HEALTHCHECK wiring.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent


def _read_dockerfile() -> str:
    dockerfile_path = PROJECT_ROOT / "Dockerfile"
    if not dockerfile_path.exists():
        pytest.fail("Dockerfile does not exist")
    return dockerfile_path.read_text(encoding="utf-8")


def test_dockerfile_exists():
    """Dockerfile 必须存在于项目根目录。"""
    assert (PROJECT_ROOT / "Dockerfile").exists()


def test_dockerfile_declares_version_arg():
    """Dockerfile 必须声明可构建时覆盖的 ARG VERSION。"""
    text = _read_dockerfile()
    match = re.search(r'^ARG\s+VERSION\s*=\s*"?([^\s"]+)"?', text, re.MULTILINE)
    assert match, "Dockerfile does not declare ARG VERSION"
    assert match.group(1).startswith("4."), f"Unexpected default VERSION: {match.group(1)}"


def test_dockerfile_has_builder_and_runtime_stages():
    """Dockerfile 必须至少包含 builder 和 runtime 两个阶段。"""
    text = _read_dockerfile()
    stages = re.findall(r"^FROM\s+\S+\s+AS\s+(\w+)", text, re.MULTILINE)
    assert "builder" in stages, "Missing builder stage"
    assert "runtime" in stages, "Missing runtime stage"


def test_dockerfile_runtime_base_image():
    """生产运行时应基于 python:3.12-slim。"""
    text = _read_dockerfile()
    runtime_match = re.search(r"^FROM\s+(\S+)\s+AS\s+runtime", text, re.MULTILINE)
    assert runtime_match, "Could not find runtime stage"
    assert "python:3.12-slim" in runtime_match.group(1)


def test_dockerfile_version_label_is_parameterized():
    """LABEL version 应引用 ARG VERSION。"""
    text = _read_dockerfile()
    assert 'LABEL version="${VERSION}"' in text, "Dockerfile LABEL version is not parameterized with VERSION"


def test_dockerfile_has_healthcheck():
    """Dockerfile 必须包含基于 _version 的健康检查。"""
    text = _read_dockerfile()
    assert "HEALTHCHECK" in text
    assert "scripts.collaboration._version" in text


def test_dockerfile_exposes_expected_ports():
    """Dockerfile 必须暴露 API (8000) 和 dashboard (8501) 端口。"""
    text = _read_dockerfile()
    assert "EXPOSE 8000 8501" in text


def test_dockerfile_installs_project():
    """builder 阶段必须通过 pip 安装项目。"""
    text = _read_dockerfile()
    assert re.search(r"RUN\s+pip\s+install.*\.\[all\]", text) is not None


def test_dockerfile_copies_source_directories():
    """runtime 阶段必须复制 scripts/ 和 skills/ 源码目录。"""
    text = _read_dockerfile()
    assert "COPY scripts/ ./scripts/" in text
    assert "COPY skills/ ./skills/" in text


def test_dockerfile_runs_as_non_root():
    """生产容器应以非 root 用户运行。"""
    text = _read_dockerfile()
    assert "USER devsquad" in text
