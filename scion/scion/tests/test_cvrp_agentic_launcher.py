import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest


SCION_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = Path(__file__).resolve().parents[3]
LAUNCHER = SCION_DIR / "tools" / "launch_cvrp_agentic_campaign.py"


def _load_launcher_module():
    spec = importlib.util.spec_from_file_location("cvrp_agentic_launcher", LAUNCHER)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cvrp_agentic_launcher_help() -> None:
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


def test_cvrp_agentic_launcher_prepare_writes_run_files(tmp_path: Path) -> None:
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

    assert run_root.parent == tmp_path
    assert run_root.name.startswith("unit-cvrp-4r-gpt55-")
    assert (run_root / "campaign").is_dir()
    assert not (run_root / "pid").exists()

    launch_env = (run_root / "launch.env").read_text(encoding="utf-8")
    assert f"SCION_DIR={SCION_DIR}" in launch_env
    assert f"PYTHONPATH={SCION_DIR}" in launch_env
    assert f"SCION_PROBLEM_DATA_ROOT={PROJECT_ROOT / 'vrp'}" in launch_env
    assert "SCION_MODEL=gpt-5.5" in launch_env
    assert "SCION_BASE_URL=http://127.0.0.1:8080" in launch_env
    assert "SCION_API_KEY=pwd" in launch_env
    assert "ROUNDS=4" in launch_env

    run_sh = run_root / "run.sh"
    run_sh_text = run_sh.read_text(encoding="utf-8")
    command_txt = (run_root / "command.txt").read_text(encoding="utf-8")
    assert 'cd "$SCION_DIR"' in run_sh_text
    assert "export PYTHONPATH SCION_MODEL SCION_BASE_URL SCION_API_KEY" in run_sh_text
    assert 'cp "$CAMPAIGN_DIR/run_status.json" "$RUN_ROOT/run_status.json"' in (
        run_sh_text
    )
    assert "SCION_BASE_URL=http://127.0.0.1:8080" in command_txt
    assert "SCION_API_KEY=<set>" in command_txt
    assert "--agentic-proposal" in command_txt
    assert "nohup setsid bash run.sh > nohup.log 2>&1 &" in command_txt

    subprocess.run(["bash", "-n", str(run_sh)], check=True)


def test_cvrp_agentic_launcher_prepare_accepts_base_url_override(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--rounds",
            "1",
            "--label",
            "unit-cvrp-base",
            "--base-url",
            "http://127.0.0.1:18080/v1",
            "--experiments-root",
            str(tmp_path),
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

    assert "SCION_BASE_URL=http://127.0.0.1:18080/v1" in launch_env
    assert "SCION_BASE_URL=http://127.0.0.1:18080/v1" in command_txt
    assert "SCION_API_KEY=''" in launch_env
    assert "SCION_API_KEY=<unset>" in command_txt


def test_cvrp_agentic_launcher_prepare_accepts_api_key_override(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--rounds",
            "1",
            "--label",
            "unit-cvrp-key",
            "--base-url",
            "http://127.0.0.1:18080/v1",
            "--api-key",
            "test-proxy-key",
            "--experiments-root",
            str(tmp_path),
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

    assert "SCION_API_KEY=test-proxy-key" in launch_env
    assert "test-proxy-key" not in command_txt
    assert "SCION_API_KEY=<set>" in command_txt


def test_cvrp_agentic_launcher_preflight_rejects_parameter_search_enabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_launcher_module()
    problem = tmp_path / "problem.yaml"
    problem_v1 = tmp_path / "problem-v1.yaml"
    problem.write_text("parameter_search:\n  enabled: false\n", encoding="utf-8")
    problem_v1.write_text("parameter_search:\n  enabled: true\n", encoding="utf-8")
    monkeypatch.setattr(
        module,
        "CVRP_SPECS_REQUIRING_PARAMETER_SEARCH_DISABLED",
        (problem.name, problem_v1.name),
    )

    with pytest.raises(SystemExit) as exc_info:
        module._preflight_cvrp_parameter_search_disabled(tmp_path)

    assert exc_info.value.code != 0
    assert "CVRP agentic launcher requires parameter_search.enabled=false" in str(
        exc_info.value
    )
    assert "problem-v1.yaml" in str(exc_info.value)
