import importlib.util
import json
import stat
import subprocess
import sys
from pathlib import Path

import yaml


SCION_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = Path(__file__).resolve().parents[3]
LAUNCHER = SCION_DIR / "tools" / "launch_warehouse_agentic_campaign.py"


def test_warehouse_agentic_launcher_help() -> None:
    result = subprocess.run(
        [sys.executable, str(LAUNCHER), "--help"],
        cwd=SCION_DIR,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "--rounds" in result.stdout
    assert "--launch" in result.stdout
    assert "--base-url" in result.stdout
    assert "--api-key" in result.stdout
    assert "--api-key-env" in result.stdout
    assert "--completion-preflight" in result.stdout
    assert "--skip-postrun-reports" in result.stdout
    assert "--warehouse-data-root" in result.stdout
    assert "--resume-from-campaign" in result.stdout
    assert "--problem-v1" in result.stdout
    assert "--measurement-governance" in result.stdout
    assert "--proposal-context-ablation" in result.stdout


def test_warehouse_agentic_launcher_prepare_writes_rewritten_run_files(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "scion-data"

    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--rounds",
            "6",
            "--label",
            "unit-warehouse",
            "--experiments-root",
            str(tmp_path / "experiments"),
            "--warehouse-data-root",
            str(data_root),
        ],
        cwd=SCION_DIR,
        text=True,
        capture_output=True,
        check=True,
    )

    run_root_line = next(
        line for line in result.stdout.splitlines() if line.startswith("RUN_ROOT=")
    )
    run_root = Path(run_root_line.removeprefix("RUN_ROOT="))

    assert run_root.parent == tmp_path / "experiments"
    assert run_root.name.startswith("unit-warehouse-6r-gpt55-")
    assert (run_root / "campaign").is_dir()
    assert (run_root / "config").is_dir()
    assert not (run_root / "pid").exists()
    prepare_status = json.loads(
        (run_root / "run_status.json").read_text(encoding="utf-8")
    )
    assert prepare_status["schema"] == "scion.launcher_prepare.v1"
    assert prepare_status["status"] == "prepared"
    assert prepare_status["prepared_only"] is True
    assert prepare_status["campaign_dir"] == str(run_root / "campaign")
    assert prepare_status["resume_from_campaign"] == ""
    assert prepare_status["copied_campaign_status_present"] is False
    assert prepare_status["completion_preflight"] is False
    assert prepare_status["postrun_reports"] is True

    launch_env_path = run_root / "launch.env"
    launch_env = launch_env_path.read_text(encoding="utf-8")
    assert stat.S_IMODE(launch_env_path.stat().st_mode) == 0o600
    assert f"REPO_ROOT={PROJECT_ROOT}" in launch_env
    assert f"SCION_DIR={SCION_DIR}" in launch_env
    assert f"PYTHONPATH={SCION_DIR}" in launch_env
    assert f"SCION_WAREHOUSE_DATA_ROOT={data_root}" in launch_env
    assert f"SCION_PROBLEM_DATA_ROOT={data_root}" in launch_env
    assert "SCION_MODEL=gpt-5.5" in launch_env
    assert "SCION_BASE_URL=http://127.0.0.1:8080" in launch_env
    assert "SCION_API_KEY=pwd" in launch_env
    assert "SCION_API_KEY_ENV=''" in launch_env
    assert "COMPLETION_PREFLIGHT=0" in launch_env
    assert "POSTRUN_REPORTS=1" in launch_env
    assert (
        "GIT_RUNTIME_GUARD_PATHS="
        "'scion/scion :(exclude)scion/scion/tests "
        "scion/problems/warehouse_delivery surrogate'" in launch_env
    )
    assert "ROUNDS=6" in launch_env
    assert "RESUME_FROM_CAMPAIGN=''" in launch_env
    assert f"PROBLEM={run_root / 'config' / 'problem.yaml'}" in launch_env
    assert f"PROBLEM_V1={run_root / 'config' / 'problem-v1.yaml'}" in launch_env
    assert f"PROTOCOL={run_root / 'config' / 'protocol_prod.yaml'}" in launch_env
    assert f"SPLIT={run_root / 'config' / 'split_manifest_prod.yaml'}" in launch_env
    assert f"SEEDS={run_root / 'config' / 'seed_ledger.yaml'}" in launch_env

    problem_v1 = yaml.safe_load(
        (run_root / "config" / "problem-v1.yaml").read_text(encoding="utf-8")
    )
    split = yaml.safe_load(
        (run_root / "config" / "split_manifest_prod.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert problem_v1["root_dir"] == str(PROJECT_ROOT / "surrogate")
    assert problem_v1["canary_case_path"] == str(
        PROJECT_ROOT / "surrogate" / "data" / "instance_small_1.json"
    )
    assert split["safe_data_roots"] == [str(data_root)]
    assert all(str(case).startswith(str(data_root)) for case in split["canary"])
    assert all(str(case).startswith(str(data_root)) for case in split["screening"])
    assert all(str(case).startswith(str(data_root)) for case in split["validation"])
    assert all(str(case).startswith(str(data_root)) for case in split["frozen"])

    run_sh = run_root / "run.sh"
    run_sh_text = run_sh.read_text(encoding="utf-8")
    command_txt = (run_root / "command.txt").read_text(encoding="utf-8")
    assert 'cd "$SCION_DIR"' in run_sh_text
    assert "GIT_RUNTIME_DIRTY" in run_sh_text
    assert "GIT_COMMIT_MISMATCH" in run_sh_text
    assert "GIT_COMMIT_DOC_ONLY_MISMATCH_ALLOWED" in run_sh_text
    assert "WAREHOUSE_DATA_ROOT_MISSING" in run_sh_text
    assert "COMPLETION_PREFLIGHT_FAILED" in run_sh_text
    assert "postrun_acceptance" in run_sh_text
    assert "report summary" in run_sh_text
    assert "report failures" in run_sh_text
    assert "report research-efficiency" in run_sh_text
    assert "report proposal-trajectory-manifest" in run_sh_text
    assert 'OBSERVED_CONTROL_ARM="${MEASUREMENT_GOVERNANCE//-/_}"' in run_sh_text
    assert 'manifest_args+=(--control-pair-key "$CONTROL_PAIR_KEY")' in run_sh_text
    assert "--agentic-proposal" in command_txt
    assert "--measurement-governance on" in command_txt
    assert "--proposal-context-ablation full" in command_txt
    assert "SCION_API_KEY=<set>" in command_txt
    assert (
        "GIT_RUNTIME_GUARD_PATHS="
        "scion/scion :(exclude)scion/scion/tests "
        "scion/problems/warehouse_delivery surrogate" in command_txt
    )
    assert "POSTRUN_REPORTS=1" in command_txt
    assert f"POSTRUN_REPORT_DIR={run_root / 'postrun_acceptance'}" in command_txt
    subprocess.run(["bash", "-n", str(run_sh)], check=True)


def test_warehouse_agentic_launcher_can_copy_resume_campaign(tmp_path: Path) -> None:
    source_campaign = tmp_path / "source-campaign"
    (source_campaign / "champions" / "champion_v2").mkdir(parents=True)
    (source_campaign / "champions" / "champion_v2" / "registry.yaml").write_text(
        "operators: {}\n",
        encoding="utf-8",
    )
    (source_campaign / "scion.db").write_text("fake-db", encoding="utf-8")
    (source_campaign / "run_status.json").write_text(
        json.dumps({"status": "finished", "wrapper_exit_status": 0}),
        encoding="utf-8",
    )
    (source_campaign / "campaign_summary.json").write_text(
        json.dumps({"run_complete": True}),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--rounds",
            "2",
            "--label",
            "unit-warehouse-resume",
            "--experiments-root",
            str(tmp_path / "experiments"),
            "--warehouse-data-root",
            str(tmp_path / "data"),
            "--resume-from-campaign",
            str(source_campaign),
        ],
        cwd=SCION_DIR,
        text=True,
        capture_output=True,
        check=True,
    )
    run_root_line = next(
        line for line in result.stdout.splitlines() if line.startswith("RUN_ROOT=")
    )
    run_root = Path(run_root_line.removeprefix("RUN_ROOT="))

    assert (run_root / "campaign" / "scion.db").read_text(encoding="utf-8") == "fake-db"
    assert (
        run_root / "campaign" / "champions" / "champion_v2" / "registry.yaml"
    ).is_file()
    prepare_status = json.loads(
        (run_root / "run_status.json").read_text(encoding="utf-8")
    )
    assert prepare_status["status"] == "prepared"
    assert prepare_status["prepared_only"] is True
    assert prepare_status["resume_from_campaign"] == str(source_campaign)
    assert prepare_status["copied_campaign_status_present"] is True
    assert prepare_status["copied_campaign_summary_present"] is True
    launch_env = (run_root / "launch.env").read_text(encoding="utf-8")
    command_txt = (run_root / "command.txt").read_text(encoding="utf-8")
    assert f"RESUME_FROM_CAMPAIGN={source_campaign}" in launch_env
    assert f"RESUME_FROM_CAMPAIGN={source_campaign}" in command_txt


def test_warehouse_agentic_launcher_api_key_env_avoids_secret_file(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--rounds",
            "1",
            "--label",
            "unit-warehouse-env",
            "--experiments-root",
            str(tmp_path),
            "--warehouse-data-root",
            str(tmp_path / "data"),
            "--api-key-env",
            "SCION_API_KEY",
            "--completion-preflight",
        ],
        cwd=SCION_DIR,
        text=True,
        capture_output=True,
        check=True,
    )
    run_root_line = next(
        line for line in result.stdout.splitlines() if line.startswith("RUN_ROOT=")
    )
    run_root = Path(run_root_line.removeprefix("RUN_ROOT="))

    launch_env = (run_root / "launch.env").read_text(encoding="utf-8")
    command_txt = (run_root / "command.txt").read_text(encoding="utf-8")
    assert "SCION_API_KEY=''" in launch_env
    assert "SCION_API_KEY_ENV=SCION_API_KEY" in launch_env
    assert "COMPLETION_PREFLIGHT=1" in launch_env
    assert "SCION_API_KEY=<from-env:SCION_API_KEY>" in command_txt


def test_warehouse_agentic_launcher_api_key_env_missing_writes_valid_status(
    tmp_path: Path,
) -> None:
    missing_python = tmp_path / "missing-python"
    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--rounds",
            "1",
            "--label",
            "unit-warehouse-missing-key-env",
            "--experiments-root",
            str(tmp_path / "runs"),
            "--warehouse-data-root",
            str(tmp_path / "data"),
            "--api-key-env",
            "SCION_MISSING_TEST_KEY",
            "--python",
            str(missing_python),
        ],
        cwd=SCION_DIR,
        text=True,
        capture_output=True,
        check=True,
    )
    run_root_line = next(
        line for line in result.stdout.splitlines() if line.startswith("RUN_ROOT=")
    )
    run_root = Path(run_root_line.removeprefix("RUN_ROOT="))

    run_result = subprocess.run(
        ["bash", str(run_root / "run.sh")],
        text=True,
        capture_output=True,
    )

    assert run_result.returncode == 64
    assert not (run_root / "campaign" / "campaign_summary.json").exists()
    assert "SCION_API_KEY_ENV_MISSING:SCION_MISSING_TEST_KEY" in (
        run_root / "exit.txt"
    ).read_text(encoding="utf-8")
    status = json.loads((run_root / "run_status.json").read_text(encoding="utf-8"))
    assert status["wrapper_exit_status"] == 64
    assert status["api_key_env_missing"] == "SCION_MISSING_TEST_KEY"


def test_warehouse_agentic_launcher_missing_data_root_writes_valid_status(
    tmp_path: Path,
) -> None:
    missing_python = tmp_path / "missing-python"
    missing_data_root = tmp_path / "missing-data-root"
    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--rounds",
            "1",
            "--label",
            "unit-warehouse-missing-data",
            "--experiments-root",
            str(tmp_path / "runs"),
            "--warehouse-data-root",
            str(missing_data_root),
            "--python",
            str(missing_python),
        ],
        cwd=SCION_DIR,
        text=True,
        capture_output=True,
        check=True,
    )
    run_root_line = next(
        line for line in result.stdout.splitlines() if line.startswith("RUN_ROOT=")
    )
    run_root = Path(run_root_line.removeprefix("RUN_ROOT="))
    launch_env = run_root / "launch.env"
    launch_env.write_text(
        launch_env.read_text(encoding="utf-8").replace(
            "GIT_RUNTIME_GUARD_PATHS="
            "'scion/scion :(exclude)scion/scion/tests "
            "scion/problems/warehouse_delivery surrogate'",
            "GIT_RUNTIME_GUARD_PATHS=scion/design/scion-architecture-v3.md",
        ),
        encoding="utf-8",
    )

    run_result = subprocess.run(
        ["bash", str(run_root / "run.sh")],
        text=True,
        capture_output=True,
    )

    assert run_result.returncode == 64
    assert f"WAREHOUSE_DATA_ROOT_MISSING:{missing_data_root}" in (
        run_root / "exit.txt"
    ).read_text(encoding="utf-8")
    status = json.loads((run_root / "run_status.json").read_text(encoding="utf-8"))
    assert status["wrapper_exit_status"] == 64
    assert status["warehouse_data_root_missing"] is True


def test_warehouse_agentic_launcher_can_skip_postrun_reports(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--rounds",
            "1",
            "--label",
            "unit-warehouse-no-reports",
            "--experiments-root",
            str(tmp_path),
            "--warehouse-data-root",
            str(tmp_path / "data"),
            "--skip-postrun-reports",
        ],
        cwd=SCION_DIR,
        text=True,
        capture_output=True,
        check=True,
    )
    run_root_line = next(
        line for line in result.stdout.splitlines() if line.startswith("RUN_ROOT=")
    )
    run_root = Path(run_root_line.removeprefix("RUN_ROOT="))

    launch_env = (run_root / "launch.env").read_text(encoding="utf-8")
    command_txt = (run_root / "command.txt").read_text(encoding="utf-8")
    assert "POSTRUN_REPORTS=0" in launch_env
    assert "POSTRUN_REPORTS=0" in command_txt


def test_warehouse_agentic_launcher_rejects_invalid_api_key_env() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--rounds",
            "1",
            "--label",
            "bad-env",
            "--api-key-env",
            "bad-name",
        ],
        cwd=SCION_DIR,
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "--api-key-env must be a valid shell environment variable name" in (
        result.stderr
    )
