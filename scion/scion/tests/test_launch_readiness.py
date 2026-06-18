from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


SCION_DIR = Path(__file__).resolve().parents[2]
TOOL_PATH = SCION_DIR / "tools" / "check_launch_readiness.py"
SPEC = importlib.util.spec_from_file_location("check_launch_readiness", TOOL_PATH)
assert SPEC is not None
readiness_tool = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(readiness_tool)


def test_launch_readiness_accepts_clean_prepared_root(tmp_path: Path) -> None:
    run_root = _write_prepared_root(tmp_path)

    report = readiness_tool.build_readiness(run_root)

    assert report["schema_version"] == "scion.launch_readiness.v1"
    assert report["report_only"] is True
    assert report["decision_features_excluded"] is True
    assert report["ready"] is True
    assert report["static_ready"] is True
    assert report["launch_ready"] is False
    assert report["checks"]["prepared_only_not_started"]["status"] == "ok"
    assert report["checks"]["prepared_contract_complete"]["status"] == "ok"
    assert report["checks"]["git_runtime_consistent"]["status"] == "ok"
    assert report["checks"]["run_script_preflight_failure_reports"]["status"] == "ok"
    assert report["checks"]["completion_preflight"]["status"] == "skipped"
    markdown = readiness_tool.render_markdown(report)
    assert markdown.startswith("# Launch Readiness:")
    assert "Launch only after rerunning this tool" in markdown


def test_launch_readiness_rejects_already_started_root(tmp_path: Path) -> None:
    run_root = _write_prepared_root(tmp_path)
    (run_root / "exit.txt").write_text("WRAPPER_EXIT_STATUS:64\n", encoding="utf-8")

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    assert report["launch_ready"] is False
    assert report["checks"]["not_already_started"]["status"] == "failed"


def test_launch_readiness_rejects_preflight_failed_root(tmp_path: Path) -> None:
    run_root = _write_prepared_root(tmp_path)
    _write_json(
        run_root / "run_status.json",
        {
            "schema": "outer-wrapper.v1",
            "status": "finished",
            "wrapper_exit_status": 64,
            "pre_campaign_completion_preflight": "failed",
        },
    )
    (run_root / "postrun_acceptance" / "rebuild").mkdir(parents=True)

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    assert report["launch_ready"] is False
    assert report["checks"]["prepared_only_not_started"]["status"] == "failed"
    assert report["checks"]["zero_current_run_counters"]["status"] == "ok"
    assert report["checks"]["postrun_acceptance_not_present"]["status"] == "failed"


def test_launch_readiness_keeps_static_ready_when_completion_preflight_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    run_root = _write_prepared_root(tmp_path)

    def fail_preflight(**_: object) -> tuple[str, object]:
        return "failed", {"chat": {"classification": "not_authenticated"}}

    monkeypatch.setattr(
        readiness_tool,
        "_completion_preflight_check",
        fail_preflight,
    )

    report = readiness_tool.build_readiness(run_root, completion_preflight=True)

    assert report["ready"] is False
    assert report["static_ready"] is True
    assert report["launch_ready"] is False
    assert report["checks"]["completion_preflight"]["status"] == "failed"


def test_launch_readiness_cli_json_returns_unready_exit(tmp_path: Path) -> None:
    run_root = _write_prepared_root(tmp_path)
    (run_root / "exit.txt").write_text("WRAPPER_EXIT_STATUS:64\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(TOOL_PATH), str(run_root), "--format", "json"],
        text=True,
        capture_output=True,
        check=False,
    )
    payload = json.loads(result.stdout)

    assert result.returncode == 64
    assert payload["ready"] is False
    assert payload["checks"]["not_already_started"]["status"] == "failed"


def _write_prepared_root(tmp_path: Path) -> Path:
    run_root = tmp_path / "prepared-root"
    campaign_dir = run_root / "campaign"
    config_dir = run_root / "config"
    campaign_dir.mkdir(parents=True)
    config_dir.mkdir()
    for name in ("problem.yaml", "protocol.yaml", "split.yaml", "seeds.yaml"):
        (config_dir / name).write_text("ok: true\n", encoding="utf-8")

    command = (
        f"{sys.executable} -m scion.cli.main run "
        f"--problem {config_dir / 'problem.yaml'} "
        f"--protocol {config_dir / 'protocol.yaml'} "
        f"--split {config_dir / 'split.yaml'} "
        f"--seeds {config_dir / 'seeds.yaml'} "
        f"--campaign-dir {campaign_dir} --rounds 1 --agentic-proposal"
    )
    _write_json(
        run_root / "run_status.json",
        {
            "schema": "scion.launcher_prepare.v1",
            "status": "prepared",
            "prepared_only": True,
            "run_root": str(run_root),
            "campaign_dir": str(campaign_dir),
            "copied_campaign_status_present": True,
            "copied_campaign_summary_present": True,
        },
    )
    _write_json(
        run_root / "prepared_run_manifest.v1.json",
        {
            "schema_version": "scion.launcher_prepared_run_manifest.v1",
            "report_only": True,
            "quality_judgment": False,
            "decision_features_excluded": True,
            "campaign_state_mutated": False,
            "scheduler_state_mutated": False,
            "promotion_state_mutated": False,
            "run_root": str(run_root),
            "campaign_dir": str(campaign_dir),
            "problem_family": "cvrp",
            "analysis_intent": "Prepared launch readiness fixture.",
            "acceptance_focus": ["Stay report-only."],
            "resume_from_campaign": "/tmp/source-campaign",
            "command": command,
            "model": {
                "name": "gpt-5.5",
                "base_url": "http://127.0.0.1:8080",
                "completion_preflight": True,
            },
            "git": {
                "commit": _git_head_short(),
                "runtime_guard_paths": "scion/tools",
            },
            "config": {
                "problem": str(config_dir / "problem.yaml"),
                "protocol": str(config_dir / "protocol.yaml"),
                "split": str(config_dir / "split.yaml"),
                "seeds": str(config_dir / "seeds.yaml"),
            },
            "report_metadata": {
                "control_pair_key": "cvrp.ready:rep01",
                "postrun_reports": True,
                "postrun_acceptance_families": [
                    "summaries",
                    "failures",
                    "research_efficiency",
                    "manifests",
                    "analysis_brief",
                    "inventory",
                    "rebuild",
                ],
            },
        },
    )
    (run_root / "prepared_run_manifest.md").write_text("# prepared\n", encoding="utf-8")
    (run_root / "command.txt").write_text(
        "\n".join(
            [
                "report_metadata:",
                f"PREPARED_RUN_MANIFEST={run_root / 'prepared_run_manifest.v1.json'}",
                "",
                "command:",
                command,
            ]
        ),
        encoding="utf-8",
    )
    (run_root / "run.sh").write_text(
        """#!/usr/bin/env bash
set -uo pipefail
write_postrun_acceptance_reports() {
  return 0
}
if [[ "${COMPLETION_PREFLIGHT:-0}" == "1" ]]; then
  PREFLIGHT_STATUS=64
  if [[ "$PREFLIGHT_STATUS" -ne 0 ]]; then
    printf '{"schema":"outer-wrapper.v1","status":"finished","wrapper_exit_status":%s,"pre_campaign_completion_preflight":"failed"}\\n' "$PREFLIGHT_STATUS" > "$RUN_ROOT/run_status.json"
    write_postrun_acceptance_reports
    exit "$PREFLIGHT_STATUS"
  fi
fi
""",
        encoding="utf-8",
    )
    return run_root


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _git_head_short() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=SCION_DIR,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()
