#!/usr/bin/env python3
"""Real-browser E2E for the DevSquad Dashboard.

Why this exists
---------------
The Streamlit ``AppTest`` suite runs the real app script but not a real
browser. A defect that only appears in the browser — broken input binding,
JS error, missing render — stays invisible there. This module drives a
Chromium instance with Playwright.

The login path was previously unverifiable: an automation agent that types
via synthetic events left the Streamlit input state empty (server log:
``Login attempt for unknown user: ``). Playwright's ``fill()`` sets the value
through the input element, so the React state updates.

Requirements: ``pip install playwright && playwright install chromium``.
Without the SDK or the browser binary the module skips.
"""

from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytest.importorskip("playwright", reason="playwright not installed (pip install playwright)")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_APP = PROJECT_ROOT / "scripts" / "dashboard" / "app.py"
SCREENSHOT_DIR = PROJECT_ROOT / "artifacts" / "e2e_screenshots"
PASSWORD = "LocalE2E2026x"
DONE_PATTERN = re.compile(r"Status:\s*✅\s*Success")

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.slow,
    pytest.mark.requires_browser,
]


def _chromium_executable() -> str | None:
    """Return the Chromium binary to use, or ``""`` when none is available.

    ``None`` means "use the Playwright default". A partially downloaded newer
    revision must not block the run: any complete build in the Playwright cache
    is protocol-compatible with the installed SDK.
    """
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            if Path(p.chromium.executable_path).exists():
                return None
    except (ImportError, RuntimeError, OSError):
        return ""

    cache = Path.home() / "Library" / "Caches" / "ms-playwright"
    candidates = sorted(cache.glob("chromium-*/chrome-mac-arm64/**/Google Chrome for Testing"), reverse=True)
    candidates += sorted(cache.glob("chromium-*/chrome-linux/chrome"), reverse=True)
    return str(candidates[0]) if candidates else ""


_CHROMIUM = _chromium_executable()

if _CHROMIUM == "":
    pytest.skip("no Chromium build available (run: playwright install chromium)", allow_module_level=True)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _password_hash(password: str) -> str:
    sys.path.insert(0, str(PROJECT_ROOT))
    from scripts.auth import AuthManager

    return AuthManager.__new__(AuthManager)._hash_password(password)


def _wait_until_ready(url: str, timeout: float = 90.0) -> None:
    import httpx

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if httpx.get(url, timeout=2.0).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    raise RuntimeError(f"Streamlit did not become ready at {url}")


@pytest.fixture(scope="module")
def dashboard_url():
    """Start the real Streamlit server with real credential configuration."""
    port = _free_port()
    url = f"http://127.0.0.1:{port}"
    hashed = _password_hash(PASSWORD)
    env = os.environ.copy()
    env.update(
        {
            "DEVSQUAD_ADMIN_PASSWORD_HASH": hashed,
            "DEVSQUAD_OPERATOR_PASSWORD_HASH": hashed,
            "DEVSQUAD_VIEWER_PASSWORD_HASH": hashed,
            "DEVSQUAD_SESSION_KEY": "playwright_local_session_key",
            "DEVSQUAD_LLM_BACKEND": "mock",
            "PYTHONPATH": str(PROJECT_ROOT),
        }
    )
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(DASHBOARD_APP),
            "--server.port",
            str(port),
            "--server.headless",
            "true",
            "--server.address",
            "127.0.0.1",
            "--browser.gatherUsageStats",
            "false",
        ],
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_until_ready(url)
        yield url
    finally:
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()


def _login(page, url: str) -> None:
    page.goto(url, wait_until="domcontentloaded")
    page.get_by_label("Username").fill("operator")
    # Streamlit renders a "Show password" button with the same aria-label,
    # so target the input element directly.
    page.locator('input[aria-label="Password"]').fill(PASSWORD)
    page.get_by_role("button", name="Login").click()
    page.get_by_text("Task Dispatch", exact=True).wait_for(timeout=60_000)


def test_operator_login_and_dispatch_in_real_browser(dashboard_url: str) -> None:
    """Journey: operator logs in, opens Task Dispatch, submits a task, sees a result."""
    from playwright.sync_api import expect, sync_playwright

    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    js_errors: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=_CHROMIUM)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.on("pageerror", lambda error: js_errors.append(str(error)))

        _login(page, dashboard_url)
        page.screenshot(path=str(SCREENSHOT_DIR / "01_logged_in.png"), full_page=True)

        page.get_by_text("Task Dispatch", exact=True).click()
        textarea = page.get_by_role("textbox", name="Enter your task description...")
        textarea.click()
        # Type instead of fill(): Streamlit enables the submit button only after
        # its React state receives the keystrokes.
        textarea.type("Design a user authentication service", delay=15)
        # Streamlit commits a widget value on blur, not on each keystroke.
        page.keyboard.press("Tab")
        submit = page.get_by_role("button", name=re.compile("Submit Task"))
        expect(submit).to_be_enabled(timeout=30_000)
        submit.click()
        page.get_by_text(DONE_PATTERN).first.wait_for(timeout=240_000)
        page.screenshot(path=str(SCREENSHOT_DIR / "02_dispatch_result.png"), full_page=True)

        body = page.inner_text("body")
        assert "Status: ✅ Success" in body, "Dashboard did not report a successful dispatch"
        assert "architect" in body.lower(), "Matched roles are missing from the result panel"
        assert "Traceback" not in body, "Dashboard rendered a Python traceback"
        assert not js_errors, f"JavaScript errors: {js_errors}"
        browser.close()
