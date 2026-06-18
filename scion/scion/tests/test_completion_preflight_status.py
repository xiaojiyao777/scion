from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


SCION_DIR = Path(__file__).resolve().parents[2]
TOOL = SCION_DIR / "tools" / "write_completion_preflight_status.py"


def _load_tool_module():
    spec = importlib.util.spec_from_file_location(
        "write_completion_preflight_status",
        TOOL,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_status_projects_actionable_preflight_failure(tmp_path: Path) -> None:
    tool = _load_tool_module()
    detail_path = tmp_path / "pre_campaign_completion_preflight.v1.json"
    detail_path.write_text(
        json.dumps(
            {
                "ok": False,
                "chat": {
                    "classification": "not_authenticated",
                    "code": "invalid_api_key",
                    "http_status": 401,
                    "message": "Not authenticated. Please login first at /",
                },
                "auth_status": {
                    "authenticated": False,
                    "pool": {"active": 0, "refreshing": 1},
                },
                "login_url": "https://auth.example.test/login",
            }
        ),
        encoding="utf-8",
    )

    status = tool.build_status(exit_code=64, detail_path=detail_path)

    assert status["schema"] == "outer-wrapper.v1"
    assert status["wrapper_exit_status"] == 64
    assert status["pre_campaign_completion_preflight"] == "failed"
    assert status["pre_campaign_completion_preflight_detail_file"] == (
        "pre_campaign_completion_preflight.v1.json"
    )
    assert status["pre_campaign_completion_preflight_classification"] == (
        "not_authenticated"
    )
    assert status["pre_campaign_completion_preflight_http_status"] == 401
    assert status["pre_campaign_completion_preflight_code"] == "invalid_api_key"
    assert status["pre_campaign_completion_preflight_authenticated"] is False
    assert status["pre_campaign_completion_preflight_active_accounts"] == 0
    assert status["pre_campaign_completion_preflight_refreshing_accounts"] == 1
    assert status["pre_campaign_completion_preflight_login_url_present"] is True
    assert "Refresh the local proxy login" in status[
        "pre_campaign_completion_preflight_operator_action"
    ]


def test_write_status_tolerates_missing_detail(tmp_path: Path) -> None:
    tool = _load_tool_module()
    output = tmp_path / "run_status.json"

    tool.write_status(
        output_path=output,
        exit_code=64,
        detail_path=tmp_path / "missing.json",
    )

    status = json.loads(output.read_text(encoding="utf-8"))
    assert status["pre_campaign_completion_preflight"] == "failed"
    assert "pre_campaign_completion_preflight_detail_error" in status
