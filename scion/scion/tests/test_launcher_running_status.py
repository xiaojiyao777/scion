from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path


SCION_DIR = Path(__file__).resolve().parents[2]
TOOL = SCION_DIR / "tools" / "write_launcher_running_status.py"
CVRP_LAUNCHER = SCION_DIR / "tools" / "launch_cvrp_direct_campaign.py"
WAREHOUSE_LAUNCHER = SCION_DIR / "tools" / "launch_warehouse_direct_campaign.py"


def _load_tool_module():
    spec = importlib.util.spec_from_file_location("write_launcher_running_status", TOOL)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_status_marks_prepared_root_running(tmp_path: Path) -> None:
    tool = _load_tool_module()

    status = tool.build_status(
        run_root=tmp_path / "run",
        campaign_dir=tmp_path / "run" / "campaign",
        git_commit="abc1234",
        model="gpt-5.5",
        started_utc="2026-06-23T08:00:00Z",
        pid=12345,
        scion_base_url="http://127.0.0.1:8080",
        completion_preflight=True,
        postrun_reports=False,
    )

    assert status == {
        "schema": "outer-wrapper.v1",
        "status": "running",
        "prepared_only": False,
        "run_root": str(tmp_path / "run"),
        "campaign_dir": str(tmp_path / "run" / "campaign"),
        "git_commit": "abc1234",
        "model": "gpt-5.5",
        "started_utc": "2026-06-23T08:00:00Z",
        "pid": 12345,
        "scion_base_url": "http://127.0.0.1:8080",
        "completion_preflight": True,
        "postrun_reports": False,
        "proposal_runtime_mode": "direct_v3",
    }


def test_write_status_writes_json_payload(tmp_path: Path) -> None:
    tool = _load_tool_module()
    output = tmp_path / "run_status.json"

    written = tool.write_status(
        output=output,
        run_root=tmp_path / "run",
        campaign_dir=tmp_path / "run" / "campaign",
        git_commit="def5678",
        model="gpt-5.5",
        started_utc="2026-06-23T08:01:00Z",
        pid=12346,
    )

    loaded = json.loads(output.read_text(encoding="utf-8"))
    assert loaded == written
    assert loaded["status"] == "running"
    assert loaded["prepared_only"] is False


def test_build_status_preserves_resume_snapshot_metadata(tmp_path: Path) -> None:
    tool = _load_tool_module()

    status = tool.build_status(
        run_root=tmp_path / "run",
        campaign_dir=tmp_path / "run" / "campaign",
        git_commit="abc1234",
        model="gpt-5.5",
        started_utc="2026-06-23T08:00:00Z",
        pid=12345,
        resume_from_campaign="/tmp/source-campaign",
        resume_snapshot_ref="resume_snapshot/resume_source_manifest.v1.json",
        copied_campaign_status_present=True,
        copied_campaign_summary_present=True,
    )

    assert status["resume_from_campaign"] == "/tmp/source-campaign"
    assert (
        status["resume_snapshot_ref"]
        == "resume_snapshot/resume_source_manifest.v1.json"
    )
    assert status["copied_campaign_status_present"] is True
    assert status["copied_campaign_summary_present"] is True


def test_cvrp_launcher_marks_root_running_before_campaign(tmp_path: Path) -> None:
    status_before_campaign = tmp_path / "status-before-campaign.json"
    fake_python = _write_fake_campaign_python(tmp_path, status_before_campaign)

    result = subprocess.run(
        [
            sys.executable,
            str(CVRP_LAUNCHER),
            "--rounds",
            "1",
            "--label",
            "unit-cvrp-running-status",
            "--experiments-root",
            str(tmp_path / "runs"),
            "--python",
            str(fake_python),
            "--skip-postrun-reports",
        ],
        cwd=SCION_DIR,
        text=True,
        capture_output=True,
        check=True,
    )
    run_root = _run_root_from_stdout(result.stdout)
    _use_clean_git_guard_root(run_root / "launch.env", tmp_path / "cvrp-runtime")
    run_sh_text = (run_root / "run.sh").read_text(encoding="utf-8")

    run_result = subprocess.run(
        ["bash", str(run_root / "run.sh")],
        text=True,
        capture_output=True,
    )

    assert run_result.returncode == 0
    assert "tools/write_launcher_running_status.py" in run_sh_text
    assert '--resume-snapshot-ref "$RESUME_SNAPSHOT_MANIFEST_REF"' in run_sh_text
    assert (
        '--copied-campaign-status-present "$RESUME_COPIED_CAMPAIGN_STATUS_PRESENT"'
        in run_sh_text
    )
    assert run_sh_text.index("tools/write_launcher_running_status.py") < (
        run_sh_text.index("tools/check_completion_proxy.py")
    )
    assert run_sh_text.index("tools/write_launcher_running_status.py") < (
        run_sh_text.index('"$PY" -m scion.cli.main run')
    )
    _assert_running_status(status_before_campaign, run_root)


def test_warehouse_launcher_marks_root_running_before_campaign(tmp_path: Path) -> None:
    status_before_campaign = tmp_path / "status-before-campaign.json"
    fake_python = _write_fake_campaign_python(tmp_path, status_before_campaign)
    data_root = tmp_path / "scion-data"
    (data_root / "production" / "generated").mkdir(parents=True)
    (data_root / "production" / "converted").mkdir(parents=True)

    result = subprocess.run(
        [
            sys.executable,
            str(WAREHOUSE_LAUNCHER),
            "--rounds",
            "1",
            "--label",
            "unit-warehouse-running-status",
            "--experiments-root",
            str(tmp_path / "runs"),
            "--warehouse-data-root",
            str(data_root),
            "--python",
            str(fake_python),
            "--skip-postrun-reports",
        ],
        cwd=SCION_DIR,
        text=True,
        capture_output=True,
        check=True,
    )
    run_root = _run_root_from_stdout(result.stdout)
    _use_clean_git_guard_root(
        run_root / "launch.env", tmp_path / "warehouse-runtime"
    )
    run_sh_text = (run_root / "run.sh").read_text(encoding="utf-8")

    run_result = subprocess.run(
        ["bash", str(run_root / "run.sh")],
        text=True,
        capture_output=True,
    )

    assert run_result.returncode == 0
    assert "tools/write_launcher_running_status.py" in run_sh_text
    assert '--resume-snapshot-ref "$RESUME_SNAPSHOT_MANIFEST_REF"' in run_sh_text
    assert (
        '--copied-campaign-status-present "$RESUME_COPIED_CAMPAIGN_STATUS_PRESENT"'
        in run_sh_text
    )
    assert run_sh_text.index("WAREHOUSE_DATA_ROOT_MISSING") < (
        run_sh_text.index("tools/write_launcher_running_status.py")
    )
    assert run_sh_text.index("tools/write_launcher_running_status.py") < (
        run_sh_text.index("tools/check_completion_proxy.py")
    )
    assert run_sh_text.index("tools/write_launcher_running_status.py") < (
        run_sh_text.index('"$PY" -m scion.cli.main run')
    )
    _assert_running_status(status_before_campaign, run_root)


def _write_fake_campaign_python(
    tmp_path: Path,
    status_before_campaign: Path,
) -> Path:
    fake_python = tmp_path / "fake-python"
    fake_python.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "if [[ \"${1:-}\" == \"-m\" ]]; then\n"
        "  campaign_dir=''\n"
        "  previous=''\n"
        "  for arg in \"$@\"; do\n"
        "    if [[ \"$previous\" == \"--campaign-dir\" ]]; then\n"
        "      campaign_dir=\"$arg\"\n"
        "      break\n"
        "    fi\n"
        "    previous=\"$arg\"\n"
        "  done\n"
        "  run_root=\"$(dirname \"$campaign_dir\")\"\n"
        f"  cp \"$run_root/run_status.json\" \"{status_before_campaign}\"\n"
        "  mkdir -p \"$campaign_dir\"\n"
        "  printf '{\"schema\":\"outer-wrapper.v1\",\"status\":\"finished\","
        "\"wrapper_exit_status\":0}\\n' > \"$campaign_dir/run_status.json\"\n"
        "  exit 0\n"
        "fi\n"
        "case \"${1:-}\" in\n"
        "  */write_launcher_running_status.py)\n"
        f"    exec {sys.executable} \"$@\"\n"
        "    ;;\n"
        "esac\n"
        "exit 0\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)
    return fake_python


def _run_root_from_stdout(stdout: str) -> Path:
    run_root_line = next(
        line for line in stdout.splitlines() if line.startswith("RUN_ROOT=")
    )
    return Path(run_root_line.removeprefix("RUN_ROOT="))


def _use_clean_git_guard_root(launch_env: Path, repo: Path) -> None:
    """Run wrapper behavior against the same exact-clean contract as production."""

    repo.mkdir()
    (repo / "README.md").write_text("runtime guard fixture\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"], cwd=repo, check=True
    )
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "fixture"], cwd=repo, check=True)
    commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()

    text = launch_env.read_text(encoding="utf-8")
    text = re.sub(r"(?m)^REPO_ROOT=.*$", f"REPO_ROOT={repo}", text)
    text = re.sub(r"(?m)^GIT_COMMIT=.*$", f"GIT_COMMIT={commit}", text)
    launch_env.write_text(text, encoding="utf-8")


def _assert_running_status(
    status_before_campaign: Path,
    run_root: Path,
) -> None:
    running_status = json.loads(status_before_campaign.read_text(encoding="utf-8"))
    assert running_status["schema"] == "outer-wrapper.v1"
    assert running_status["status"] == "running"
    assert running_status["prepared_only"] is False
    assert running_status["run_root"] == str(run_root)
    assert running_status["campaign_dir"] == str(run_root / "campaign")
    assert running_status["git_commit"]
    assert running_status["model"] == "gpt-5.5"
    assert running_status["scion_base_url"] == "http://127.0.0.1:8080"
    assert running_status["completion_preflight"] is False
    assert running_status["postrun_reports"] is False
    assert running_status["proposal_runtime_mode"] == "direct_v3"
    assert isinstance(running_status["pid"], int)
    assert running_status["pid"] > 0

    final_status = json.loads((run_root / "run_status.json").read_text(encoding="utf-8"))
    assert final_status["status"] == "finished"
