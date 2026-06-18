import importlib.util
import json
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
    assert "--api-key-env" in result.stdout
    assert "--completion-preflight" in result.stdout
    assert "--python" in result.stdout
    assert "--problem" in result.stdout
    assert "--protocol" in result.stdout
    assert "--split" in result.stdout
    assert "--seeds" in result.stdout
    assert "--measurement-governance" in result.stdout
    assert "--proposal-context-ablation" in result.stdout
    assert "--control-pair-key" in result.stdout
    assert "--stage-transition-drain-limit" in result.stdout


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
    assert "PY=/home/clawd/miniconda3/envs/claw/bin/python" in launch_env
    assert f"PYTHONPATH={SCION_DIR}" in launch_env
    assert f"SCION_PROBLEM_DATA_ROOT={PROJECT_ROOT / 'vrp'}" in launch_env
    assert "SCION_MODEL=gpt-5.5" in launch_env
    assert "SCION_BASE_URL=http://127.0.0.1:8080" in launch_env
    assert "SCION_API_KEY=pwd" in launch_env
    assert "SCION_API_KEY_ENV=''" in launch_env
    assert "COMPLETION_PREFLIGHT=0" in launch_env
    assert "SCION_STAGE_TRANSITION_DRAIN_LIMIT=4" in launch_env
    assert "ROUNDS=4" in launch_env
    assert "PROBLEM=scion/problems/cvrp/problem.yaml" in launch_env
    assert "PROTOCOL=scion/problems/cvrp/formal/protocol.yaml" in launch_env
    assert "SPLIT=scion/problems/cvrp/formal/split_manifest.yaml" in launch_env
    assert "SEEDS=scion/problems/cvrp/formal/seed_ledger.yaml" in launch_env
    assert "MEASUREMENT_GOVERNANCE=on" in launch_env
    assert "PROPOSAL_CONTEXT_ABLATION=full" in launch_env
    assert "CONTROL_PAIR_KEY=''" in launch_env

    run_sh = run_root / "run.sh"
    run_sh_text = run_sh.read_text(encoding="utf-8")
    command_txt = (run_root / "command.txt").read_text(encoding="utf-8")
    assert 'cd "$SCION_DIR"' in run_sh_text
    assert "export PYTHONPATH SCION_MODEL SCION_BASE_URL SCION_API_KEY" in run_sh_text
    assert "SCION_STAGE_TRANSITION_DRAIN_LIMIT" in run_sh_text
    assert 'cp "$CAMPAIGN_DIR/run_status.json" "$RUN_ROOT/run_status.json"' in (
        run_sh_text
    )
    assert "SCION_BASE_URL=http://127.0.0.1:8080" in command_txt
    assert "SCION_STAGE_TRANSITION_DRAIN_LIMIT=4" in command_txt
    assert "SCION_API_KEY=<set>" in command_txt
    assert "COMPLETION_PREFLIGHT=0" in command_txt
    assert "--agentic-proposal" in command_txt
    assert "--measurement-governance on" in command_txt
    assert "--proposal-context-ablation full" in command_txt
    assert '--measurement-governance "$MEASUREMENT_GOVERNANCE"' in run_sh_text
    assert '--proposal-context-ablation "$PROPOSAL_CONTEXT_ABLATION"' in run_sh_text
    assert "nohup setsid bash run.sh > nohup.log 2>&1 &" in command_txt

    subprocess.run(["bash", "-n", str(run_sh)], check=True)


def test_cvrp_agentic_launcher_prepare_accepts_custom_phase_b_flags(
    tmp_path: Path,
) -> None:
    baseline_root = tmp_path / "copied-baseline"
    formal_dir = baseline_root / "formal"
    formal_dir.mkdir(parents=True)
    problem = baseline_root / "problem.yaml"
    problem_v1 = baseline_root / "problem-v1.yaml"
    protocol = formal_dir / "matched-protocol.yaml"
    split = formal_dir / "matched-split.yaml"
    seeds = formal_dir / "matched-seeds.yaml"
    problem.write_text("parameter_search:\n  enabled: false\n", encoding="utf-8")
    problem_v1.write_text("parameter_search:\n  enabled: false\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--rounds",
            "2",
            "--label",
            "unit-cvrp-phase-b",
            "--problem",
            str(problem),
            "--protocol",
            str(protocol),
            "--split",
            str(split),
            "--seeds",
            str(seeds),
            "--measurement-governance",
            "record-only",
            "--proposal-context-ablation",
            "compact-measurement-diagnostics",
            "--control-pair-key",
            "pair-a-vs-b",
            "--stage-transition-drain-limit",
            "2",
            "--python",
            str(tmp_path / "python-bin"),
            "--experiments-root",
            str(tmp_path / "runs"),
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
    run_sh_text = (run_root / "run.sh").read_text(encoding="utf-8")
    command_txt = (run_root / "command.txt").read_text(encoding="utf-8")

    assert f"PROBLEM={problem}" in launch_env
    assert f"PY={tmp_path / 'python-bin'}" in launch_env
    assert f"PROTOCOL={protocol}" in launch_env
    assert f"SPLIT={split}" in launch_env
    assert f"SEEDS={seeds}" in launch_env
    assert "MEASUREMENT_GOVERNANCE=record-only" in launch_env
    assert (
        "PROPOSAL_CONTEXT_ABLATION=compact-measurement-diagnostics" in launch_env
    )
    assert "CONTROL_PAIR_KEY=pair-a-vs-b" in launch_env
    assert "SCION_STAGE_TRANSITION_DRAIN_LIMIT=2" in launch_env
    assert f"--problem {problem}" in command_txt
    assert f"--protocol {protocol}" in command_txt
    assert f"--split {split}" in command_txt
    assert f"--seeds {seeds}" in command_txt
    assert "--measurement-governance record-only" in command_txt
    assert (
        "--proposal-context-ablation compact-measurement-diagnostics" in command_txt
    )
    assert "CONTROL_PAIR_KEY=pair-a-vs-b" in command_txt
    assert "SCION_STAGE_TRANSITION_DRAIN_LIMIT=2" in command_txt
    assert "--control-pair-key" not in command_txt
    assert "--control-pair-key" not in run_sh_text

    subprocess.run(["bash", "-n", str(run_root / "run.sh")], check=True)


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


def test_cvrp_agentic_launcher_prepare_accepts_api_key_env_without_secret(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--rounds",
            "1",
            "--label",
            "unit-cvrp-key-env",
            "--base-url",
            "https://aihubmix.com",
            "--api-key-env",
            "SCION_API_KEY",
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
    launch_env_path = run_root / "launch.env"
    launch_env = launch_env_path.read_text(encoding="utf-8")
    run_sh_text = (run_root / "run.sh").read_text(encoding="utf-8")
    command_txt = (run_root / "command.txt").read_text(encoding="utf-8")

    assert "SCION_BASE_URL=https://aihubmix.com" in launch_env
    assert "SCION_API_KEY=''" in launch_env
    assert "SCION_API_KEY_ENV=SCION_API_KEY" in launch_env
    assert "SCION_API_KEY=<from-env:SCION_API_KEY>" in command_txt
    assert '_INHERITED_SCION_API_KEY="${SCION_API_KEY:-}"' in run_sh_text
    assert '_RESOLVED_SCION_API_KEY="${!SCION_API_KEY_ENV:-}"' in run_sh_text
    assert "SCION_API_KEY_ENV_MISSING" in run_sh_text
    assert oct(launch_env_path.stat().st_mode & 0o777) == "0o600"

    subprocess.run(["bash", "-n", str(run_root / "run.sh")], check=True)


def test_cvrp_agentic_launcher_api_key_env_missing_fails_before_campaign(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--rounds",
            "1",
            "--label",
            "unit-cvrp-missing-key-env",
            "--api-key-env",
            "SCION_MISSING_TEST_KEY",
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


def test_cvrp_agentic_launcher_api_key_env_preserves_inherited_scion_key(
    tmp_path: Path,
) -> None:
    fake_python = tmp_path / "fake-python"
    seen_env = tmp_path / "seen-env.txt"
    fake_python.write_text(
        "#!/usr/bin/env bash\n"
        f"printf '%s\\n' \"$SCION_API_KEY\" > {seen_env}\n"
        "exit 0\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)
    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--rounds",
            "1",
            "--label",
            "unit-cvrp-inherited-key-env",
            "--api-key-env",
            "SCION_API_KEY",
            "--python",
            str(fake_python),
            "--experiments-root",
            str(tmp_path / "runs"),
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
        env={"SCION_API_KEY": "fake-inherited-secret"},
        text=True,
        capture_output=True,
    )

    assert run_result.returncode == 0
    assert seen_env.read_text(encoding="utf-8").strip() == "fake-inherited-secret"
    assert "SCION_API_KEY_ENV_MISSING" not in (
        run_root / "exit.txt"
    ).read_text(encoding="utf-8")


def test_cvrp_agentic_launcher_prepare_writes_completion_preflight(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--rounds",
            "1",
            "--label",
            "unit-cvrp-preflight",
            "--completion-preflight",
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
    run_sh_text = (run_root / "run.sh").read_text(encoding="utf-8")
    command_txt = (run_root / "command.txt").read_text(encoding="utf-8")

    assert "COMPLETION_PREFLIGHT=1" in launch_env
    assert "COMPLETION_PREFLIGHT=1" in command_txt
    assert "COMPLETION_PREFLIGHT_OK" in run_sh_text
    assert "pre_campaign_completion_preflight" in run_sh_text
    assert "/v1/models" not in run_sh_text

    subprocess.run(["bash", "-n", str(run_root / "run.sh")], check=True)


def test_cvrp_agentic_launcher_rejects_api_key_and_api_key_env(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--rounds",
            "1",
            "--label",
            "unit-cvrp-key-conflict",
            "--api-key",
            "test-key",
            "--api-key-env",
            "SCION_API_KEY",
            "--experiments-root",
            str(tmp_path),
        ],
        cwd=SCION_DIR,
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "--api-key and --api-key-env are mutually exclusive" in result.stderr


def test_cvrp_agentic_launcher_rejects_invalid_api_key_env(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--rounds",
            "1",
            "--label",
            "unit-cvrp-key-invalid",
            "--api-key-env",
            "not-valid-name",
            "--experiments-root",
            str(tmp_path),
        ],
        cwd=SCION_DIR,
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "--api-key-env must be a valid shell environment variable name" in (
        result.stderr
    )


def test_cvrp_agentic_launcher_preflight_rejects_parameter_search_enabled(
    tmp_path: Path,
) -> None:
    module = _load_launcher_module()
    problem = tmp_path / "problem.yaml"
    problem_v1 = tmp_path / "problem-v1.yaml"
    problem.write_text("parameter_search:\n  enabled: false\n", encoding="utf-8")
    problem_v1.write_text("parameter_search:\n  enabled: true\n", encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        module._preflight_cvrp_parameter_search_disabled(SCION_DIR, str(problem))

    assert exc_info.value.code != 0
    assert "CVRP agentic launcher requires parameter_search.enabled=false" in str(
        exc_info.value
    )
    assert "problem-v1.yaml" in str(exc_info.value)


def test_cvrp_agentic_launcher_preflight_rejects_custom_problem_path(
    tmp_path: Path,
) -> None:
    module = _load_launcher_module()
    problem = tmp_path / "custom-problem.yaml"
    problem.write_text("parameter_search:\n  enabled: true\n", encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        module._preflight_cvrp_parameter_search_disabled(SCION_DIR, str(problem))

    assert exc_info.value.code != 0
    assert "CVRP agentic launcher requires parameter_search.enabled=false" in str(
        exc_info.value
    )
    assert str(problem) in str(exc_info.value)
