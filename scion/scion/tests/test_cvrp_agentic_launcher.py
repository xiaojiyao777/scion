import subprocess
import sys
from pathlib import Path


SCION_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = Path(__file__).resolve().parents[3]
LAUNCHER = SCION_DIR / "tools" / "launch_cvrp_agentic_campaign.py"


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
    assert "ROUNDS=4" in launch_env

    run_sh = run_root / "run.sh"
    command_txt = (run_root / "command.txt").read_text(encoding="utf-8")
    assert 'cd "$SCION_DIR"' in run_sh.read_text(encoding="utf-8")
    assert 'cp "$CAMPAIGN_DIR/run_status.json" "$RUN_ROOT/run_status.json"' in (
        run_sh.read_text(encoding="utf-8")
    )
    assert "--agentic-proposal" in command_txt
    assert "nohup setsid bash run.sh > nohup.log 2>&1 &" in command_txt

    subprocess.run(["bash", "-n", str(run_sh)], check=True)
