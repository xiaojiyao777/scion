from __future__ import annotations

from collections import Counter
from dataclasses import replace
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace
import sys

import pytest

from scion.problems.cvrp.evidence import b0_runner_contract as contract


TOOL_PATH = Path(__file__).resolve().parents[4] / "tools" / "cvrp_mechanism_matrix.py"


def _load_tool():
    module_name = f"cvrp_mechanism_matrix_b0_{id(object())}"
    spec = importlib.util.spec_from_file_location(module_name, TOOL_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _fixture(tmp_path: Path) -> dict[str, Path]:
    repo_root = tmp_path / "repo"
    package = repo_root / "scion" / "scion"
    workspace = package / "problems" / "cvrp"
    config = workspace / "policies" / "baseline_modules" / "config.py"
    config.parent.mkdir(parents=True)
    config.write_text(
        "\n".join(
            [
                'SOLVER_VARIANT = "alns_vns"',
                "USE_VNS = True",
                "ENABLE_INITIAL_VNS = True",
                "ENABLE_EMBEDDED_VNS = True",
                "ENABLE_SIZE70_TWO_OPT_FALLBACK = True",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (package / "core").mkdir(parents=True)
    (package / "core" / "runtime_marker.py").write_text(
        'RUNTIME_MARKER = "complete-package-snapshot"\n',
        encoding="utf-8",
    )
    solver = workspace / "solver.py"
    solver.write_text(
        """from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
from scion.problems.cvrp.policies.baseline_modules import config
import pydantic

def _main():
    parser = argparse.ArgumentParser()
    parser.add_argument("instance")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--time-limit", type=float)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    source = Path(os.environ["SCION_PROBLEM_DATA_ROOT"]) / args.instance
    if not source.is_file():
        raise SystemExit("missing staged input")
    payload = {
        "objective": {"total_distance": 1000.0, "routes": 1, "fleet_violation": 0.0},
        "runtime": {"elapsed_s": 0.01, "profile": config.SOLVER_VARIANT},
        "feasible": True,
    }
    Path(args.output).write_text(json.dumps(payload), encoding="utf-8")

if __name__ == "__main__":
    _main()
""",
        encoding="utf-8",
    )

    protocol = workspace / "formal" / "protocol.yaml"
    protocol.parent.mkdir(parents=True)
    protocol.write_text(
        """version: test-cvrp-b0
screening:
  n_cases_modify: 8
  n_cases_create: 12
  n_seeds: 4
  expand_to_modify: 12
  expand_to_create: 16
runtime:
  time_limits:
    stage_defaults:
      screening: 30
    rules:
    - stages: [screening]
      case_globs: [cvrplib/CMT/CMT4.vrp, CMT4.vrp]
      time_limit_sec: 45
    - stages: [screening]
      min_dimension: 150
      max_dimension: 250
      time_limit_sec: 45
""",
        encoding="utf-8",
    )
    rows = [
        ("A-n64-k9", "cvrplib/A/A-n64-k9.vrp", "A", 64),
        ("A-n80-k10", "cvrplib/A/A-n80-k10.vrp", "A", 80),
        ("B-n63-k10", "cvrplib/B/B-n63-k10.vrp", "B", 63),
        ("B-n67-k10", "cvrplib/B/B-n67-k10.vrp", "B", 67),
        ("E-n101-k14", "cvrplib/E/E-n101-k14.vrp", "E", 101),
        ("E-n101-k8", "cvrplib/E/E-n101-k8.vrp", "E", 101),
        ("P-n65-k10", "cvrplib/P/P-n65-k10.vrp", "P", 65),
        ("P-n76-k4", "cvrplib/P/P-n76-k4.vrp", "P", 76),
        ("P-n101-k4", "cvrplib/P/P-n101-k4.vrp", "P", 101),
        ("CMT2", "cvrplib/CMT/CMT2.vrp", "CMT", 76),
        ("CMT3", "cvrplib/CMT/CMT3.vrp", "CMT", 101),
        ("X-n110-k13", "cvrplib/X/X-n110-k13.vrp", "X", 110),
        ("CMT4", "cvrplib/CMT/CMT4.vrp", "CMT", 151),
        ("M-n151-k12", "cvrplib/M/M-n151-k12.vrp", "M", 151),
        ("M-n200-k17", "cvrplib/M/M-n200-k17.vrp", "M", 200),
        ("Tai150c", "cvrplib/tai/tai150c.vrp", "tai", 151),
    ]
    data_root = tmp_path / "vrp"
    cases = []
    for index, (case_id, relative, subset, dimension) in enumerate(rows):
        source = data_root / relative
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(
            f"NAME : {case_id}\nDIMENSION : {dimension}\n",
            encoding="utf-8",
        )
        cases.append(
            {
                "case_id": case_id,
                "source_path": relative,
                "subset": subset,
                "dimension": dimension,
                "bks": float(1000 + index),
                "bks_routes": index + 1,
            }
        )
    manifest = workspace / "formal" / "manifests" / "screening.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "schema": "scion.cvrp_case_manifest.v1",
                "problem_id": "cvrp",
                "config": {"seeds": [11, 29, 43, 59]},
                "metadata": {"stage": "screening"},
                "cases": cases,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "repo_root": repo_root,
        "package": package,
        "workspace": workspace,
        "config": config,
        "protocol": protocol,
        "manifest": manifest,
        "data_root": data_root,
        "output": tmp_path / "run",
    }


def _args(paths: dict[str, Path], *, dry_run: bool = True) -> list[str]:
    values = [
        "--matrix-contract",
        "b0",
        "--repo-root",
        str(paths["repo_root"]),
        "--workspace",
        str(paths["workspace"]),
        "--data-root",
        str(paths["data_root"]),
        "--protocol-config",
        str(paths["protocol"]),
        "--case-manifest",
        str(paths["manifest"]),
        "--output-dir",
        str(paths["output"]),
        "--python",
        sys.executable,
    ]
    if dry_run:
        values.append("--dry-run")
    return values


def _prepare(paths: dict[str, Path], output: Path | None = None):
    return contract.prepare_b0_launch_plan(
        source_package_root=paths["package"],
        source_data_root=paths["data_root"],
        protocol_path=paths["protocol"],
        case_manifest_path=paths["manifest"],
        output_root=output or paths["output"],
        python=sys.executable,
        selected_surface="solver_design",
        outer_timeout_padding_sec=60,
        dry_run=True,
    )


def _make_tree_removable(root: Path) -> None:
    for path in (root, *root.rglob("*")):
        try:
            path.chmod(0o700 if path.is_dir() else 0o600)
        except FileNotFoundError:
            pass


def test_b0_dry_run_stages_four_real_import_authorities(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    tool = _load_tool()

    assert tool.main(_args(paths)) == 0

    manifest = json.loads((paths["output"] / "manifest.json").read_text())
    assert manifest["matrix_contract"] == contract.B0_CONTRACT
    assert len(manifest["jobs"]) == len(manifest["execution_jobs"]) == 256
    assert Counter(row["resolved_time_limit_sec"] for row in manifest["jobs"]) == {
        30: 192,
        45: 64,
    }
    assert len({row["job_identity_sha256"] for row in manifest["jobs"]}) == 256
    assert {
        "runtime_snapshot_sha256",
        "selected_surface",
        "protocol_identity_sha256",
        "case_manifest_identity_sha256",
        "input_snapshot_identity_sha256",
        "profile_config_sha256",
        "profile_manifest_sha256",
        "import_probe_identity_sha256",
        "dependency_identity_sha256",
        "python_runtime_identity_sha256",
        "input_case_sha256",
        "execution_ordinal",
        "execution_position",
        "rotation_offset",
        "order_contract",
        "outer_timeout_padding_sec",
    } <= set(manifest["jobs"][0])
    assert {row["selected_surface"] for row in manifest["jobs"]} == {
        contract.B0_SELECTED_SURFACE
    }
    python_runtime = manifest["python_runtime"]
    executable = Path(python_runtime["executable_path"])
    assert executable == Path(sys.executable).resolve()
    assert python_runtime["executable_sha256"] == hashlib.sha256(
        executable.read_bytes()
    ).hexdigest()
    assert python_runtime["build_identity"]["executable_path"] == str(executable)
    expected_flags = {
        "canonical_alns_vns": (True, True, True, True),
        "pure_alns_no_polish": (False, False, False, False),
        "embedded_vns_disabled": (True, True, False, True),
        "initial_vns_disabled": (True, False, True, True),
    }
    for profile in manifest["profiles"]:
        probe = profile["import_probe"]
        profile_id = profile["profile_id"]
        assert Path(probe["solver_file"]).is_relative_to(
            paths["output"] / "runtime_snapshots" / profile_id
        )
        assert Path(probe["config_file"]).is_relative_to(
            paths["output"] / "runtime_snapshots" / profile_id
        )
        assert tuple(
            probe[name]
            for name in (
                "USE_VNS",
                "ENABLE_INITIAL_VNS",
                "ENABLE_EMBEDDED_VNS",
                "ENABLE_SIZE70_TWO_OPT_FALLBACK",
            )
        ) == expected_flags[profile_id]
        assert probe["runtime_snapshot_sha256"] == profile[
            "runtime_snapshot_sha256"
        ]
        assert probe["config_sha256"] == profile["config_sha256"]
        assert probe["python_executable_path"] == str(executable)
        assert probe["dependency_modules"]
        assert profile["dependency_identity_sha256"]
        for dependency in probe["dependency_modules"]:
            dependency_file = Path(dependency["file"])
            assert "site-packages" in str(dependency_file) or "dist-packages" in str(
                dependency_file
            )
            assert dependency["file_sha256"] == hashlib.sha256(
                dependency_file.read_bytes()
            ).hexdigest()
        assert not any(str(paths["package"]) in value for value in probe["sys_path"])
        assert (
            Path(profile["package_root"])
            / "scion"
            / "core"
            / "runtime_marker.py"
        ).is_file()


def test_b0_latin_rotation_balances_every_profile_position(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    plan = _prepare(paths)

    for profile in contract.B0_PROFILES:
        positions = Counter(
            planned.execution_position
            for planned in plan.execution_jobs
            if planned.runtime.profile.profile_id == profile.profile_id
        )
        assert positions == {0: 16, 1: 16, 2: 16, 3: 16}
    first_case = plan.cases[0].case_id
    per_seed = {
        seed: [
            planned.runtime.profile.profile_id
            for planned in plan.execution_jobs
            if planned.job.case.case_id == first_case and planned.job.seed == seed
        ]
        for seed in contract.B0_SEEDS
    }
    assert per_seed == {
        11: [
            "canonical_alns_vns",
            "pure_alns_no_polish",
            "embedded_vns_disabled",
            "initial_vns_disabled",
        ],
        29: [
            "pure_alns_no_polish",
            "embedded_vns_disabled",
            "initial_vns_disabled",
            "canonical_alns_vns",
        ],
        43: [
            "embedded_vns_disabled",
            "initial_vns_disabled",
            "canonical_alns_vns",
            "pure_alns_no_polish",
        ],
        59: [
            "initial_vns_disabled",
            "canonical_alns_vns",
            "pure_alns_no_polish",
            "embedded_vns_disabled",
        ],
    }
    assert [item.runtime.profile.profile_id for item in plan.summary_jobs[:4]] == [
        profile.profile_id for profile in contract.B0_PROFILES
    ]


@pytest.mark.parametrize(
    "extra, match",
    [
        (["--resume"], "forbids --resume"),
        (["--reuse-workspaces"], "forbids --reuse-workspaces"),
        (["--seed", "101"], "selectors are forbidden"),
        (["--case-id", "unknown-case"], "selectors are forbidden"),
        (["--stage", "validation"], "only --stage screening"),
        (["--time-budget-sec", "30"], "legacy-only"),
        (["--timeout-padding-sec", "61"], "frozen at 60s"),
        (
            ["--selected-surface", "runtime"],
            "selected surface is frozen",
        ),
    ],
)
def test_b0_denies_runtime_or_population_overrides(
    tmp_path: Path,
    extra: list[str],
    match: str,
) -> None:
    paths = _fixture(tmp_path)
    tool = _load_tool()
    with pytest.raises(SystemExit, match=match):
        tool.main(_args(paths) + extra)


def test_no_mode_no_time_is_fail_closed_and_legacy_time_remains(tmp_path: Path) -> None:
    tool = _load_tool()
    with pytest.raises(SystemExit, match="select --matrix-contract b0 explicitly"):
        tool.main([])
    args = tool._parse_args(["--time-budget-sec", "1"])
    assert tool._resolve_matrix_contract(args) == "legacy-uniform"


def test_b0_rejects_repo_workspace_mixing(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    tool = _load_tool()
    args = _args(paths)
    index = args.index("--workspace") + 1
    args[index] = str(tmp_path / "other-workspace")
    with pytest.raises(SystemExit, match="canonical package workspace"):
        tool.main(args)


def test_launcher_rejects_different_child_python(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    launcher = Path(sys.executable).resolve()
    child = next(
        (
            candidate.resolve()
            for candidate in (
                Path("/usr/bin/python3"),
                Path("/home/clawd/miniconda3/envs/claw/bin/python"),
            )
            if candidate.is_file() and candidate.resolve() != launcher
        ),
        None,
    )
    if child is None:
        pytest.skip("no second Python executable is available")
    args = _args(paths)
    args[args.index("--python") + 1] = str(child)
    completed = subprocess.run(
        [str(launcher), str(TOOL_PATH), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    assert completed.returncode != 0
    assert "launcher Python must exactly match --python" in completed.stderr


def test_b0_rejects_symlink_input_and_stale_output(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    first_case = json.loads(paths["manifest"].read_text())["cases"][0]
    source = paths["data_root"] / first_case["source_path"]
    target = tmp_path / "real-input.vrp"
    target.write_text(source.read_text(), encoding="utf-8")
    source.unlink()
    source.symlink_to(target)
    with pytest.raises(ValueError, match="contains a symlink"):
        _prepare(paths)

    paths = _fixture(tmp_path / "stale")
    paths["output"].mkdir(parents=True)
    (paths["output"] / "old.raw").write_text("stale", encoding="utf-8")
    with pytest.raises(ValueError, match="fresh/empty"):
        _prepare(paths)


def test_source_copy_race_and_postcopy_config_drift_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _fixture(tmp_path / "race")
    original_copyfile = contract.shutil.copyfile
    mutated = False

    def racing_copy(source, target):
        nonlocal mutated
        result = original_copyfile(source, target)
        if not mutated:
            Path(source).write_text(
                Path(source).read_text() + "# raced\n",
                encoding="utf-8",
            )
            mutated = True
        return result

    monkeypatch.setattr(contract.shutil, "copyfile", racing_copy)
    with pytest.raises(ValueError, match="changed during copy"):
        _prepare(paths)
    monkeypatch.setattr(contract.shutil, "copyfile", original_copyfile)

    paths = _fixture(tmp_path / "drift")
    plan = _prepare(paths)
    config = plan.profiles[0].config_path
    config.chmod(0o600)
    config.write_text(config.read_text() + "# drift\n", encoding="utf-8")
    with pytest.raises(ValueError, match="runtime snapshot drift"):
        contract.verify_b0_launch_plan(plan)


def test_authority_descriptor_race_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _fixture(tmp_path)
    original_read = contract.os.read
    raced = False

    def racing_read(descriptor: int, size: int) -> bytes:
        nonlocal raced
        captured = original_read(descriptor, size)
        if captured and not raced:
            paths["protocol"].write_bytes(
                paths["protocol"].read_bytes() + b"\n# raced\n"
            )
            raced = True
        return captured

    monkeypatch.setattr(contract.os, "read", racing_read)
    with pytest.raises(ValueError, match="changed during descriptor capture"):
        _prepare(paths)


def test_authority_bytes_are_single_source_for_parse_snapshot_and_jobs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _fixture(tmp_path)
    original_capture = contract._capture_regular_file_bytes
    captured_protocol_sha256 = ""

    def mutate_after_capture(path: Path, *, label: str):
        nonlocal captured_protocol_sha256
        resolved, captured = original_capture(path, label=label)
        if label == "Protocol authority":
            captured_protocol_sha256 = hashlib.sha256(captured).hexdigest()
            resolved.write_bytes(captured + b"\n# source changed after capture\n")
        return resolved, captured

    monkeypatch.setattr(
        contract,
        "_capture_regular_file_bytes",
        mutate_after_capture,
    )
    plan = _prepare(paths)

    assert plan.protocol_identity_sha256 == captured_protocol_sha256
    assert hashlib.sha256(plan.protocol_snapshot_path.read_bytes()).hexdigest() == (
        captured_protocol_sha256
    )
    assert hashlib.sha256(paths["protocol"].read_bytes()).hexdigest() != (
        captured_protocol_sha256
    )
    assert {
        planned.protocol_identity_sha256 for planned in plan.execution_jobs
    } == {captured_protocol_sha256}
    assert {
        planned.case_manifest_identity_sha256 for planned in plan.execution_jobs
    } == {plan.case_manifest_identity_sha256}
    contract.verify_b0_launch_plan(plan)


def test_source_profile_flag_shape_drift_fails_closed(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    paths["config"].write_text(
        paths["config"].read_text().replace("USE_VNS = True", "USE_VNS = 1"),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="boolean config drift: USE_VNS"):
        _prepare(paths)


def test_manifest_is_deterministic_after_fresh_rematerialization(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    first = _prepare(paths).manifest_payload()
    _make_tree_removable(paths["output"])
    shutil.rmtree(paths["output"])
    second = _prepare(paths).manifest_payload()
    assert first == second


def test_atomic_publish_rejects_stale_and_never_exposes_partial(tmp_path: Path) -> None:
    tool = _load_tool()
    target = tmp_path / "artifact.json"
    tool._write_json(target, {"value": 1}, require_absent=True)
    with pytest.raises(FileExistsError):
        tool._write_json(target, {"value": 2}, require_absent=True)
    assert json.loads(target.read_text()) == {"value": 1}
    assert not list(tmp_path.glob(".*.tmp"))

    invalid = tmp_path / "invalid.json"
    with pytest.raises(ValueError):
        tool._write_json(invalid, {"value": float("nan")}, require_absent=True)
    assert not invalid.exists()
    assert not list(tmp_path.glob(".*.tmp"))


def test_invalid_solver_partial_is_cleaned_without_final_raw(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _fixture(tmp_path)
    plan = _prepare(paths)
    planned = plan.execution_jobs[0]
    tool = _load_tool()

    def invalid_run(command, **_kwargs):
        assert command[0] == str(plan.python_runtime.executable_path)
        Path(command[-1]).write_text("{partial", encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(tool.subprocess, "run", invalid_run)
    row = tool._run_solver_job(
        planned.job,
        workspace=planned.runtime.workspace,
        repo_root=paths["repo_root"],
        data_root=plan.input_root,
        python=sys.executable,
        selected_surface="solver_design",
        timeout_padding_sec=60,
        b0_planned=planned,
    )
    assert row["status"] == "invalid_solver_json"
    assert not Path(planned.job.output_path).exists()
    assert not list(Path(planned.job.output_path).parent.glob("*.partial"))


def test_legacy_runner_exception_is_not_converted_to_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _fixture(tmp_path)
    plan = _prepare(paths)
    planned = plan.execution_jobs[0]
    tool = _load_tool()

    def raising_runner(*_args, **_kwargs):
        raise RuntimeError("legacy runner failed")

    monkeypatch.setattr(tool, "_run_solver_job", raising_runner)
    with pytest.raises(RuntimeError, match="legacy runner failed"):
        tool._run_jobs(
            (planned.job,),
            mechanism_workspaces={
                planned.job.mechanism.mechanism_id: paths["workspace"]
            },
            repo_root=paths["repo_root"],
            data_root=paths["data_root"],
            python=sys.executable,
            selected_surface="solver_design",
            timeout_padding_sec=60,
            resume=False,
            b0_by_job=None,
        )


def _install_fake_success_runner(tool, *, fail_first: bool = False) -> None:
    calls = 0

    def fake_runner(job, *, b0_planned, **_kwargs):
        nonlocal calls
        calls += 1
        assert b0_planned is not None
        if fail_first and calls == 1:
            return {
                "job_id": job.job_id,
                "status": "failed",
                **b0_planned.contract_payload(),
            }
        raw = {
            "objective": {
                "total_distance": 1000.0,
                "routes": 1,
                "fleet_violation": 0.0,
            },
            "runtime": {"elapsed_s": 0.01},
            "feasible": True,
            "matrix_contract": contract.B0_CONTRACT,
            "job_identity_sha256": b0_planned.job_identity_sha256,
            "b0_job": b0_planned.contract_payload(),
        }
        tool._write_json(Path(job.output_path), raw, require_absent=True)
        return {
            "job_id": job.job_id,
            "status": "solver_json_available",
            **b0_planned.contract_payload(),
        }

    tool._run_solver_job = fake_runner


def test_one_failed_job_returns_nonzero_without_closed_receipt(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    tool = _load_tool()
    _install_fake_success_runner(tool, fail_first=True)

    assert tool.main(_args(paths, dry_run=False)) == 1

    results = json.loads((paths["output"] / "results.json").read_text())
    assert len(results["jobs"]) == 256
    assert Counter(row["status"] for row in results["jobs"])["failed"] == 1
    assert not (paths["output"] / "matrix.closed.receipt.json").exists()


def test_all_256_successes_publish_closed_receipt(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    tool = _load_tool()
    _install_fake_success_runner(tool)

    assert tool.main(_args(paths, dry_run=False)) == 0

    receipt_path = paths["output"] / "matrix.closed.receipt.json"
    receipt = json.loads(receipt_path.read_text())
    assert receipt["status"] == "closed"
    assert receipt["job_count"] == 256
    assert len(receipt["raw_results"]) == 256
    assert len({row["job_identity_sha256"] for row in receipt["raw_results"]}) == 256
    results = json.loads((paths["output"] / "results.json").read_text())
    assert {row["status"] for row in results["jobs"]} == {"completed"}
    assert all("job_identity_sha256" in row for row in results["jobs"])
    assert not list(paths["output"].rglob("*.tmp"))
    assert not list(paths["output"].rglob("*.partial"))


def test_dependency_probe_drift_fails_plan_verification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _fixture(tmp_path)
    plan = _prepare(paths)
    original_probe = contract._run_import_probe

    def drifting_probe(**kwargs):
        observed = dict(original_probe(**kwargs))
        dependencies = list(observed["dependency_modules"])
        dependencies[0] = {**dependencies[0], "file_sha256": "0" * 64}
        observed["dependency_modules"] = dependencies
        return observed

    monkeypatch.setattr(contract, "_run_import_probe", drifting_probe)
    with pytest.raises(ValueError, match="import/dependency identity drift"):
        contract.verify_b0_launch_plan(plan)


def test_symlinked_dependency_records_lexical_and_resolved_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _fixture(tmp_path)
    solver = paths["workspace"] / "solver.py"
    solver.write_text(
        solver.read_text().replace(
            "import pydantic\n",
            "import pydantic\nimport symlinked_dependency\n",
        ),
        encoding="utf-8",
    )
    dependency_root = tmp_path / "fake-site-packages"
    dependency_root.mkdir()
    target = tmp_path / "symlinked_dependency_target.py"
    target.write_text('__version__ = "1.0"\n', encoding="utf-8")
    lexical = dependency_root / "symlinked_dependency.py"
    lexical.symlink_to(target)
    original_discover = contract._discover_python_dependency_paths

    def discover_with_symlink_root(**kwargs):
        return (*original_discover(**kwargs), str(dependency_root.resolve()))

    monkeypatch.setattr(
        contract,
        "_discover_python_dependency_paths",
        discover_with_symlink_root,
    )
    plan = _prepare(paths)
    dependencies = plan.profiles[0].import_probe["dependency_modules"]
    imported = next(
        row for row in dependencies if row["module"] == "symlinked_dependency"
    )
    assert imported["lexical_file"] == str(lexical)
    assert imported["resolved_target_file"] == str(target.resolve())
    assert imported["file_sha256"] == hashlib.sha256(target.read_bytes()).hexdigest()
    assert imported["module_version"] == "1.0"
    assert imported["lexical_lstat"]["is_symlink"] is True
    assert imported["symlink_chain"][-1]["path"] == str(lexical)

    target.write_text('__version__ = "2.0"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="import/dependency identity drift"):
        contract.verify_b0_launch_plan(plan)


def test_post_execution_python_drift_is_nonzero_without_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _fixture(tmp_path)
    tool = _load_tool()
    _install_fake_success_runner(tool)
    original_capture = contract._capture_python_runtime
    captures = 0

    def drifting_capture(value):
        nonlocal captures
        captures += 1
        observed = original_capture(value)
        if captures >= 4:
            return replace(observed, executable_sha256="0" * 64)
        return observed

    monkeypatch.setattr(contract, "_capture_python_runtime", drifting_capture)
    assert tool.main(_args(paths, dry_run=False)) == 1

    results = json.loads((paths["output"] / "results.json").read_text())
    assert results["snapshot_verification"]["status"] == "failed"
    assert results["snapshot_verification"]["error"] in {
        "CVRP B0 launcher Python executable hash drift",
        "CVRP B0 Python executable/build identity drift",
    }
    assert not (paths["output"] / "matrix.closed.receipt.json").exists()
