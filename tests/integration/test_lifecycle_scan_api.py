"""Integration tests for the read-only lifecycle scan API."""

from fastapi.testclient import TestClient

from scripts.api_server import app


def test_lifecycle_scan_api_returns_findings_and_proposals(tmp_path, monkeypatch):
    document = tmp_path / "requirements.md"
    document.write_text("# Objectives\n", encoding="utf-8")
    monkeypatch.setenv("DEVSQUAD_API_AUTH_DISABLED", "1")
    monkeypatch.setenv("DEVSQUAD_PROJECT_ROOT", str(tmp_path))
    client = TestClient(app)
    response = client.post(
        "/api/v1/lifecycle/scan",
        json={
            "phase_id": "P1",
            "documents": [
                {
                    "path": str(document),
                    "required_sections": {"acceptance": "Acceptance Criteria"},
                }
            ],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["parsed"] is True
    assert payload["lifecycle_findings"][0]["lifecycle_phase"] == "P1"
    assert payload["remediation_proposals"][0]["approval_required"] is True


def test_lifecycle_scan_api_rejects_path_outside_project_root(tmp_path, monkeypatch):
    document = tmp_path / "requirements.md"
    document.write_text("# Objectives\n", encoding="utf-8")
    monkeypatch.setenv("DEVSQUAD_API_AUTH_DISABLED", "1")
    monkeypatch.setenv("DEVSQUAD_PROJECT_ROOT", str(tmp_path / "project"))
    (tmp_path / "project").mkdir()
    client = TestClient(app)
    response = client.post(
        "/api/v1/lifecycle/scan",
        json={"phase_id": "P1", "documents": [{"path": str(document)}]},
    )
    assert response.status_code == 400
