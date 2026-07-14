from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


SCION_DIR = Path(__file__).resolve().parents[2]
LAUNCHER = SCION_DIR / "tools" / "launch_cvrp_direct_campaign.py"


def _prepare(tmp_path: Path, *extra: str) -> tuple[Path, subprocess.CompletedProcess[str]]:
    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--rounds",
            "4",
            "--label",
            "unit-cvrp",
            "--experiments-root",
            str(tmp_path),
            *extra,
        ],
        cwd=SCION_DIR,
        text=True,
        capture_output=True,
        check=True,
    )
    run_root = Path(
        next(
            line for line in result.stdout.splitlines()
            if line.startswith("RUN_ROOT=")
        ).removeprefix("RUN_ROOT=")
    )
    return run_root, result


def test_cvrp_launcher_help_exposes_direct_runtime_only() -> None:
    result = subprocess.run(
        [sys.executable, str(LAUNCHER), "--help"],
        cwd=SCION_DIR,
        text=True,
        capture_output=True,
        check=True,
    )
    help_text = result.stdout
    for removed in (
        "--proposal-runtime-mode",
        "--proposal-attempt-limit",
        "--proposal-quality-loop-limit",
        "--llm-max-retries",
        "--sdk-max-retries",
        "--target-intent",
        "--measurement-governance",
        "--proposal-context-ablation",
    ):
        assert removed not in help_text


def test_cvrp_launcher_prepare_writes_open_direct_manifest(tmp_path: Path) -> None:
    run_root, _result = _prepare(tmp_path)
    status = json.loads((run_root / "run_status.json").read_text(encoding="utf-8"))
    manifest = json.loads(
        (run_root / "prepared_run_manifest.v1.json").read_text(encoding="utf-8")
    )
    data_identity = json.loads(
        (run_root / "prepared_cvrp_data_identity.v1.json").read_text(
            encoding="utf-8"
        )
    )
    manifest_md = (run_root / "prepared_run_manifest.md").read_text(
        encoding="utf-8"
    )
    launch_env = (run_root / "launch.env").read_text(encoding="utf-8")
    run_script = (run_root / "run.sh").read_text(encoding="utf-8")

    assert status["status"] == "prepared"
    assert status["prepared_only"] is True
    assert status["proposal_runtime_mode"] == "direct_v3"
    assert manifest["problem_family"] == "cvrp"
    assert manifest["execution"]["proposal_runtime_mode"] == "direct_v3"
    run_script_sha256 = hashlib.sha256(
        (run_root / "run.sh").read_bytes()
    ).hexdigest()
    assert f"RUN_SCRIPT_SHA256={run_script_sha256}" in launch_env
    assert manifest["run_script"] == {
        "path": str(run_root / "run.sh"),
        "sha256": run_script_sha256,
    }
    assert data_identity["ok"] is True
    assert data_identity["identity_file_count"] == 81
    assert manifest["config"]["data_identity_manifest"] == str(
        run_root / "prepared_cvrp_data_identity.v1.json"
    )
    assert manifest["config"]["data_identity_sha256"] == data_identity[
        "identity_sha256"
    ]
    assert (
        f"CVRP_DATA_IDENTITY_SHA256={data_identity['identity_sha256']}"
        in launch_env
    )
    assert manifest["research_guidance_contract"]["schema_version"] == (
        "scion.cvrp_research_guidance_contract.v3"
    )
    assert manifest["research_guidance_contract"]["required_mechanisms"] == []
    focus = manifest["research_focus"]
    assert focus["current_question"]
    assert focus["schema_version"] == "scion.cvrp_research_focus.v3"
    assert set(focus) == {
        "schema_version",
        "scope",
        "current_question",
        "decision_boundary",
    }
    assert "required_mechanism_ids" not in focus
    assert "next_required_direction" not in focus
    assert "Current Research Guidance" in manifest_md
    assert "Required mechanisms: none" in manifest_md
    for removed_env in (
        "PROPOSAL_RUNTIME_MODE",
        "MEASUREMENT_GOVERNANCE",
        "PROPOSAL_CONTEXT_ABLATION",
        "DISABLE_EARLY_STOP",
    ):
        assert removed_env not in launch_env
    for removed_option in (
        "--proposal-runtime-mode",
        "--measurement-governance",
        "--proposal-context-ablation",
        "--disable-early-stop",
    ):
        assert removed_option not in run_script
    assert "--api-key-env SCION_API_KEY" in run_script
    assert '--api-key "$SCION_API_KEY"' not in run_script
    assert "umask 077" in run_script
    assert 'umask "$PREFLIGHT_PREVIOUS_UMASK"' in run_script
    assert 'chmod 600 "$PREFLIGHT_DETAIL"' in run_script
    assert "tools/check_problem_split_data.py" in run_script
    assert run_script.count("tools/check_problem_split_data.py") == 2
    assert run_script.count("--expected-identity-sha256") == 2
    assert run_script.count(data_identity["identity_sha256"]) == 2
    assert "$CVRP_DATA_IDENTITY_SHA256" not in run_script
    assert "post_campaign_split_data.v1.json" in run_script
    assert "CVRP_DATA_IDENTITY_DRIFT" in run_script
    assert run_script.index("tools/check_problem_split_data.py") < run_script.index(
        "tools/check_completion_proxy.py"
    )

    rendered = "\n".join((launch_env, run_script, manifest_md)).lower()
    for removed in (
        "scion_sdk_max_retries",
        "scion_llm_max_retries",
        "proposal_attempt_limit",
        "proposal_quality_loop_limit",
        "target_intent",
        "successor",
        "nearest reviewed",
        "cmt2",
        "cmt4",
        "default-avoid",
        "denylist",
    ):
        assert removed not in rendered


def test_cvrp_launcher_rejects_conflicting_api_key_sources(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--rounds",
            "1",
            "--label",
            "conflicting-key-source",
            "--experiments-root",
            str(tmp_path),
            "--api-key",
            "inline-secret",
            "--api-key-env",
            "SCION_TEST_API_KEY",
        ],
        cwd=SCION_DIR,
        text=True,
        capture_output=True,
    )
    assert result.returncode != 0
    assert "mutually exclusive" in result.stderr.lower()


def test_cvrp_launcher_rejects_missing_split_data_before_writing_run_root(
    tmp_path: Path,
) -> None:
    experiments_root = tmp_path / "experiments"
    missing_data_root = tmp_path / "missing-vrp"
    missing_data_root.mkdir()

    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--rounds",
            "1",
            "--label",
            "missing-formal-data",
            "--experiments-root",
            str(experiments_root),
            "--data-root",
            str(missing_data_root),
        ],
        cwd=SCION_DIR,
        text=True,
        capture_output=True,
        env={
            **os.environ,
            "SCION_PROBLEM_DATA_ROOT": str(SCION_DIR.parent / "vrp"),
        },
    )

    assert result.returncode != 0
    assert "CVRP data-root preflight failed" in result.stderr
    assert "A-n64-k9.vrp" in result.stderr
    assert not experiments_root.exists()


def test_cvrp_launcher_rejects_target_binding_for_completion_preflight(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--rounds",
            "1",
            "--label",
            "target-bound-formal",
            "--experiments-root",
            str(tmp_path),
            "--completion-preflight",
            "--force-surface",
            "solver_design",
            "--force-target-file",
            "policies/baseline_algorithm.py",
        ],
        cwd=SCION_DIR,
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "requires an open research launch" in result.stderr


def test_cvrp_launcher_rejects_resume_for_completion_preflight(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--rounds",
            "1",
            "--label",
            "resumed-formal",
            "--experiments-root",
            str(tmp_path),
            "--completion-preflight",
            "--resume-from-campaign",
            str(tmp_path / "prior-campaign"),
        ],
        cwd=SCION_DIR,
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "requires a fresh campaign" in result.stderr


def test_cvrp_launcher_rejects_skipped_postrun_for_completion_preflight(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--rounds",
            "1",
            "--label",
            "postrun-skipped-formal",
            "--experiments-root",
            str(tmp_path),
            "--completion-preflight",
            "--skip-postrun-reports",
        ],
        cwd=SCION_DIR,
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "requires strict postrun reports" in result.stderr
