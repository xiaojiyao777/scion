from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import stat
import tempfile
import threading
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from scion.config.problem import ProtocolConfig, SeedLedgerConfig, SplitManifest
from scion.core.decision import DecisionEngine
from scion.core.features import SafeFeatureExtractor
from scion.core.models import (
    BranchState,
    CanaryResult,
    Decision,
    ExperimentStage,
    ProtocolResult,
    RunResult,
)
from scion.problem.bridge import (
    bridge_problem_spec_v1,
    load_problem_spec_v1_from_yaml,
)
from scion.problem.loader import load_problem_adapter
from scion.protocol.experiment import (
    ExperimentProtocol,
    PairedExecutionSpec,
    SeedLedger,
    SplitManager,
)
from scion.runtime.audit import (
    format_runtime_audit_failure,
    runtime_audit_failure_from_result,
    runtime_audit_issue_blocks_execution,
)
from scion.runtime.runner import ResourceLimits, resolve_offloaded
from scion.runtime.subprocess_runner import LocalSubprocessRunner

SCHEMA = "scion.cvrp_fixed_candidate_confirmation.v1"
LABEL = "v04-cvrp-m7-fc1-r3-cumulative-new-population-full-funnel-20260816"
DIGEST_FRAMING = (
    "relative_path + literal_backslash_zero + sha256 + "
    "literal_backslash_zero + decimal_size + literal_backslash_n"
)
CHANGED_FILES = (
    "policies/baseline_modules/destroy_repair.py",
    "policies/baseline_modules/acceptance.py",
    "policies/baseline_modules/scheduler.py",
)
EXACT_SOURCES = {
    "b0": {
        "path": "subjects/b0",
        "sha256": "f2436c23b6c169f0cb9a167b4fd0bab45b87ec761aa9c5e5e401b9abae22ebf5",
        "file_count": 104,
        "total_bytes": 686_519,
    },
    "candidate": {
        "path": "subjects/candidate06",
        "sha256": "cf223be81b45d04164f0b7dd88c9d78a49b4419d115b1413405d9dcf2832cf53",
        "file_count": 104,
        "total_bytes": 693_394,
    },
}
EXPECTED_ORDER = {
    "arms": {"A": "b0", "B": "candidate"},
    "rule": (
        "AB when (block_ordinal0 + case_ordinal0 + seed_ordinal0) % 2 == 0, "
        "otherwise BA"
    ),
    "block_ordinals": {
        "initial_screening": 0,
        "expanded_screening": 1,
        "validation": 2,
        "frozen": 3,
        "retained": 4,
    },
    "canary": "b0_then_candidate",
}
EXPECTED_BUDGETS = {
    "initial_screening_cases": 8,
    "initial_screening_seeds": 4,
    "full_stage_cases": 12,
    "full_stage_seeds": 8,
    "formal_pairs": 416,
    "formal_subprocesses": 832,
    "canary_pairs": 4,
    "canary_subprocesses": 8,
    "max_solver_subprocesses": 840,
    "nominal_subject_seconds": 45_200,
    "fail_closed_nominal_ceiling": 50_000,
    "positive_hard_timeout_seconds": 57_800,
    "outer_hardwall_seconds": 64_800,
    "protocol_calls": 5,
    "safe_feature_calls": 4,
    "decision_calls": 4,
    "snapshots": 1,
    "concurrency": 1,
    "provider_calls": 0,
    "hypothesis_calls": 0,
    "code_calls": 0,
    "patch_generation_calls": 0,
    "current_contract_calls": 0,
    "current_verification_calls": 0,
    "current_v3_calls": 0,
    "current_v4_calls": 0,
    "retry": 0,
    "resume": 0,
    "repair": 0,
    "replacement": 0,
    "substitution": 0,
    "automatic_next_round": 0,
}
EXPECTED_CLAIM_BOUNDARY = {
    "candidate_selection_outcome_known": True,
    "candidate_discovery_independent": False,
    "incremental_effect_isolated": False,
    "population_selection_outcome_blind_relative_to_exact_estimand": True,
    "exact_candidate06_outcome_overlap_count": 0,
    "globally_case_unseen": False,
    "mde_at_power_80": None,
    "execution_replication_independent": None,
    "positive_claim": (
        "The outcome-known cumulative R3 candidate-06 retained a "
        "Protocol-qualified total-distance improvement over exact R3 B0 on the "
        "complete preregistered M7-FC1 population under the frozen V3 carrier."
    ),
    "forbidden_claims": [
        "independent candidate discovery",
        "an isolated causal effect of the final route-removal edit",
        "an isolated component-level causal effect",
        "global CVRP generalization",
        "provider improvement",
        "production readiness",
        "a new mechanism",
    ],
}
SUMMARY_FIELDS = (
    ("n_cases", "wins", "losses", "ties", "win_rate", "median_delta")
    + ("ci_low", "ci_high", "attempted_pairs", "valid_pairs", "failed_pairs")
    + ("candidate_failed_pairs", "champion_failed_pairs")
)
PrepError = ValueError


class Terminal(RuntimeError):
    def __init__(
        self,
        kind: str,
        message: str,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.details = dict(details or {})


class Interrupted(BaseException):
    pass


@dataclass(frozen=True)
class Prepared:
    config: dict[str, Any]
    config_path: Path
    b0: Path
    candidate: Path
    data_root: Path
    protocol_path: Path
    sources: dict[str, dict[str, Any]]
    bridge: Any
    adapter: Any

    def stage(self, name: str) -> dict[str, Any]:
        return self.config["population"][name]

    @property
    def canary(self) -> dict[str, Any]:
        return self.config["population"]["canary"]


@dataclass(frozen=True)
class Runtime:
    protocol: Any
    retained_protocol: Any
    runner: Any
    features: Any
    decisions: Any


def _integer(value: Any, name: str, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise PrepError(f"{name} must be an integer")
    if positive and value <= 0:
        raise PrepError(f"{name} must be positive")
    return value


def _sha(value: Any, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise PrepError(f"{name} must be lowercase SHA-256 hex")
    return value


def _relative(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PrepError(f"{name} must be a non-empty relative path")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise PrepError(f"{name} must not be absolute or contain '..'")
    return path.as_posix()


def _inside(root: Path, relative: str, name: str) -> Path:
    path = (root / relative).resolve(strict=False)
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise PrepError(f"{name} escapes its root") from exc
    return path


def _file(path: Path, sha256: str, size: int, name: str) -> None:
    if not path.is_file() or path.is_symlink():
        raise PrepError(f"{name} is absent or non-regular: {path}")
    raw = path.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if len(raw) != size or actual != sha256:
        raise PrepError(
            f"{name} digest mismatch: expected {sha256}/{size}, "
            f"actual {actual}/{len(raw)}"
        )


def source_summary(root: Path) -> dict[str, Any]:
    if not root.is_dir() or root.is_symlink():
        raise PrepError(f"source is not a regular directory: {root}")
    digest = hashlib.sha256()
    count = total = 0
    for path in sorted(root.rglob("*"), key=lambda p: p.relative_to(root).as_posix()):
        if path.is_symlink():
            raise PrepError(f"source contains a symlink: {path}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise PrepError(f"source contains a non-regular entry: {path}")
        raw = path.read_bytes()
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\\0")
        digest.update(hashlib.sha256(raw).hexdigest().encode("ascii"))
        digest.update(b"\\0")
        digest.update(str(len(raw)).encode("ascii"))
        digest.update(b"\\n")
        count += 1
        total += len(raw)
    return {"sha256": digest.hexdigest(), "file_count": count, "total_bytes": total}


def _changed_files(b0: Path, candidate: Path) -> tuple[str, ...]:
    def files(root: Path) -> dict[str, Path]:
        return {
            path.relative_to(root).as_posix(): path
            for path in root.rglob("*")
            if path.is_file() and not path.is_symlink()
        }

    left, right = files(b0), files(candidate)
    if set(left) != set(right):
        raise PrepError("b0 and candidate source file sets differ")
    changed = {
        name for name in left if left[name].read_bytes() != right[name].read_bytes()
    }
    if changed != set(CHANGED_FILES):
        raise PrepError(
            f"exact three-file source difference changed: {sorted(changed)}"
        )
    return CHANGED_FILES


def _validate_science(config: dict[str, Any]) -> None:
    if config["schema_version"] != SCHEMA:
        raise PrepError(f"schema_version must be {SCHEMA}")
    if (
        config.get("label") != LABEL
        or config.get("selection_salt") != f"{LABEL}|population-v1"
        or config.get("protocol_config") != "subjects/b0/formal/protocol.yaml"
        or config.get("problem_spec") != "subjects/b0/problem-v1.yaml"
        or config.get("data_root") != "data"
    ):
        raise PrepError("label, selection salt, or scientific input paths differ")
    if config["source_digest_framing"] != DIGEST_FRAMING:
        raise PrepError("source_digest_framing differs")
    if config["selected_surface"] != "solver_design":
        raise PrepError("selected_surface must be solver_design")
    if config.get("sources") != EXACT_SOURCES:
        raise PrepError(
            "sources must be the exact historically validated B0 and candidate"
        )
    if config.get("historical_validation") != {
        "contract": True,
        "verification": True,
        "source_relation": "same_exact_source",
        "current_contract_calls": 0,
        "current_verification_calls": 0,
    }:
        raise PrepError("historical validation must describe the same exact source")
    if config.get("order") != EXPECTED_ORDER:
        raise PrepError("pair order differs from the one-shot envelope")
    if config.get("budgets") != EXPECTED_BUDGETS:
        raise PrepError("execution budgets differ from the one-shot envelope")
    if config.get("claim_boundary") != EXPECTED_CLAIM_BOUNDARY:
        raise PrepError("claim boundary differs from the one-shot envelope")


def _validate_population(
    config: dict[str, Any], data_root: Path, b0: Path, candidate: Path
) -> None:
    population = config["population"]
    paths: list[str] = []
    seeds: list[int] = []
    nominal_full = 0
    for stage_name in ("screening", "validation", "frozen", "retained"):
        stage = population[stage_name]
        if not isinstance(stage["cases"], list) or len(stage["cases"]) != 12:
            raise PrepError(f"population.{stage_name} must contain 12 cases")
        if not isinstance(stage["seeds"], list) or len(stage["seeds"]) != 8:
            raise PrepError(f"population.{stage_name} must contain 8 seeds")
        stage_seeds = [
            _integer(seed, f"population.{stage_name}.seeds[{index}]")
            for index, seed in enumerate(stage["seeds"])
        ]
        if len(set(stage_seeds)) != 8:
            raise PrepError(f"population.{stage_name} seeds repeat")
        seeds.extend(stage_seeds)
        stage_seconds = 0
        for index, case_raw in enumerate(stage["cases"]):
            name = f"population.{stage_name}.cases[{index}]"
            case = case_raw
            relative = _relative(case["path"], f"{name}.path")
            limit = _integer(
                case["time_limit_sec"], f"{name}.time_limit_sec", positive=True
            )
            if limit not in {30, 45, 60, 90, 120}:
                raise PrepError(f"{name}.time_limit_sec is not allowed")
            case_path = _inside(data_root, relative, f"{name}.path")
            _file(
                case_path,
                _sha(case["sha256"], f"{name}.sha256"),
                _integer(case["bytes"], f"{name}.bytes", positive=True),
                name,
            )
            _file(
                case_path.with_suffix(".sol"),
                _sha(case["solution_sha256"], f"{name}.solution_sha256"),
                _integer(
                    case["solution_bytes"], f"{name}.solution_bytes", positive=True
                ),
                f"{name}.solution",
            )
            paths.append(relative)
            stage_seconds += limit
        nominal_full += stage_seconds * 8 * 2
    if len(set(paths)) != 48 or len(set(seeds)) != 32:
        raise PrepError("formal cases and seeds must be disjoint across stages")

    canary = population["canary"]
    if not isinstance(canary["cases"], list) or len(canary["cases"]) != 1:
        raise PrepError("canary must contain one case")
    canary_case = canary["cases"][0]
    if (
        _relative(canary_case["path"], "canary.path")
        != "controlled/data/synthetic_controlled_canary_5.vrp"
        or canary["seeds"] != [2267]
        or canary["time_limit_sec"] != 10
    ):
        raise PrepError("canary differs from the exact one-pair freeze")
    canary_sha = _sha(canary_case["sha256"], "canary.sha256")
    canary_bytes = _integer(canary_case["bytes"], "canary.bytes", positive=True)
    for source in (b0, candidate):
        _file(
            _inside(source, canary_case["path"], "canary.path"),
            canary_sha,
            canary_bytes,
            "canary",
        )

    initial = (
        sum(case["time_limit_sec"] for case in population["screening"]["cases"][:8])
        * 4
        * 2
    )
    nominal = initial + nominal_full + 10 * 2 * 4
    if nominal != 45_200 or nominal + 15 * 840 != 57_800:
        raise PrepError("population does not imply the frozen time budgets")


def preparse_formal_cases(
    adapter: Any, config: Mapping[str, Any], data_root: Path
) -> None:
    for stage_name in ("screening", "validation", "frozen", "retained"):
        for case in config["population"][stage_name]["cases"]:
            try:
                adapter.load_instance(
                    str(_inside(data_root, case["path"], "formal case"))
                )
            except Exception as exc:
                raise PrepError(f"adapter rejected {case['path']}: {exc}") from exc


def prepare(config_path: Path, input_root: Path) -> Prepared:
    config_path = config_path.expanduser().resolve()
    input_root = input_root.expanduser().resolve()
    if not config_path.is_file() or not input_root.is_dir():
        raise PrepError("config and input-root must exist")
    try:
        config = json.loads(config_path.read_text())
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PrepError(f"cannot read config: {exc}") from exc
    _validate_science(config)
    sources_cfg = config["sources"]
    source_paths: dict[str, Path] = {}
    summaries: dict[str, dict[str, Any]] = {}
    for arm in ("b0", "candidate"):
        item = sources_cfg[arm]
        source = _inside(
            input_root,
            _relative(item["path"], f"sources.{arm}.path"),
            f"sources.{arm}.path",
        )
        actual = source_summary(source)
        expected = {
            "sha256": _sha(item["sha256"], f"sources.{arm}.sha256"),
            "file_count": _integer(
                item["file_count"], f"sources.{arm}.file_count", positive=True
            ),
            "total_bytes": _integer(
                item["total_bytes"], f"sources.{arm}.total_bytes", positive=True
            ),
        }
        if actual != expected:
            raise PrepError(f"sources.{arm} compact digest differs")
        source_paths[arm], summaries[arm] = source, actual
    _changed_files(source_paths["b0"], source_paths["candidate"])

    protocol_path = _inside(
        input_root,
        _relative(config["protocol_config"], "protocol_config"),
        "protocol_config",
    )
    problem_path = _inside(
        input_root, _relative(config["problem_spec"], "problem_spec"), "problem_spec"
    )
    data_root = _inside(
        input_root, _relative(config["data_root"], "data_root"), "data_root"
    )
    if (
        not protocol_path.is_file()
        or not problem_path.is_file()
        or not data_root.is_dir()
    ):
        raise PrepError("protocol, problem, and data inputs must exist")
    ProtocolConfig.from_yaml(protocol_path)
    bridge = bridge_problem_spec_v1(load_problem_spec_v1_from_yaml(problem_path))
    adapter = load_problem_adapter(bridge.spec_v1)
    _validate_population(
        config, data_root, source_paths["b0"], source_paths["candidate"]
    )
    preparse_formal_cases(adapter, config, data_root)
    return Prepared(
        config,
        config_path,
        source_paths["b0"],
        source_paths["candidate"],
        data_root,
        protocol_path,
        summaries,
        bridge,
        adapter,
    )


def _subject_failure(
    result: RunResult, problem_spec: Any, surface: str | None
) -> str | None:
    if not result.success:
        return result.error_category or "process_failure"
    if result.output is None:
        return "missing_output"
    issue = runtime_audit_failure_from_result(
        result,
        problem_spec=problem_spec,
        selected_surface=surface,
    )
    if runtime_audit_issue_blocks_execution(issue):
        return format_runtime_audit_failure(issue)
    return None if result.output.feasible else "infeasible"


def _make_dirs_writable(root: Path) -> None:
    if not root.exists():
        return
    for directory, dirnames, _files in os.walk(root):
        for name in [Path(directory), *(Path(directory) / child for child in dirnames)]:
            try:
                os.chmod(
                    name,
                    stat.S_IMODE(name.stat().st_mode)
                    | stat.S_IRUSR
                    | stat.S_IWUSR
                    | stat.S_IXUSR,
                )
            except FileNotFoundError:
                pass


class FreshRunner:
    def __init__(self, delegate: Any, temp_root: Path, prepared: Prepared) -> None:
        self.delegate = delegate
        self.temp_root = temp_root
        self.problem_spec = prepared.bridge.problem_spec
        self.b0 = prepared.b0.resolve()
        self.candidates = {prepared.candidate.resolve()}
        self.calls = self.nominal = self.hard = self.active = 0
        self.lock = threading.Lock()

    def register_snapshot(self, path: Path) -> None:
        self.candidates.add(path.resolve())

    def set_progress_callback(self, callback: Callable[..., None] | None) -> None:
        setter = getattr(self.delegate, "set_progress_callback", None)
        if callable(setter):
            setter(callback)

    def terminate_active_processes(self, *, reason: str = "shutdown") -> int:
        terminate = getattr(self.delegate, "terminate_active_processes", None)
        return int(terminate(reason=reason) or 0) if callable(terminate) else 0

    def run_solver(
        self,
        workdir: str,
        instance_path: str,
        seed: int,
        time_limit_sec: int,
        registry_path: str,
        selected_surface: str | None = None,
    ) -> RunResult:
        source = Path(workdir).resolve()
        limit = _integer(time_limit_sec, "time_limit_sec", positive=True)
        parent = Path(tempfile.mkdtemp(prefix="subject-", dir=self.temp_root))
        copied = parent / "workspace"
        try:
            shutil.copytree(source, copied)
            _make_dirs_writable(copied)
            with self.lock:
                if (
                    self.calls + 1 > 840
                    or self.nominal + limit > 50_000
                    or self.hard + limit + 15 > 57_800
                    or self.active + 1 > 1
                ):
                    raise Terminal(
                        "BUDGET_OR_CONCURRENCY_VIOLATION", "solver envelope exceeded"
                    )
                self.calls += 1
                self.nominal += limit
                self.hard += limit + 15
                self.active += 1
            try:
                result = self.delegate.run_solver(
                    workdir=str(copied),
                    instance_path=str(_remap(source, copied, Path(instance_path))),
                    seed=seed,
                    time_limit_sec=limit,
                    registry_path=str(_remap(source, copied, Path(registry_path))),
                    selected_surface=selected_surface,
                )
            finally:
                with self.lock:
                    self.active -= 1
            failure = _subject_failure(result, self.problem_spec, selected_surface)
            if failure:
                arm = (
                    "b0"
                    if source == self.b0
                    else "candidate"
                    if source in self.candidates
                    else "unknown"
                )
                kind = (
                    "COMPARATOR_SUBJECT_INFRA_INVALID"
                    if arm == "b0"
                    else "CANDIDATE_SUBJECT_VETO"
                )
                raise Terminal(
                    kind,
                    f"{arm} subject failed: {failure}",
                    {
                        "arm": arm,
                        "case": instance_path,
                        "seed": seed,
                        "failure": failure,
                    },
                )
            return replace(
                result,
                stdout=resolve_offloaded(result.stdout),
                stderr=resolve_offloaded(result.stderr),
            )
        finally:
            _make_dirs_writable(parent)
            try:
                shutil.rmtree(parent)
            except OSError as exc:
                raise Terminal(
                    "SUBJECT_CLEANUP_FAILED", f"private workspace cleanup failed: {exc}"
                ) from exc

    def counters(self) -> dict[str, int]:
        return {
            "solver_subprocesses": self.calls,
            "nominal_subject_seconds": self.nominal,
            "positive_hard_timeout_seconds": self.hard,
        }


def _remap(source: Path, copied: Path, path: Path) -> Path:
    resolved = (path if path.is_absolute() else source / path).resolve(strict=False)
    try:
        return copied / resolved.relative_to(source)
    except ValueError:
        return resolved


def _protocol_config(prepared: Prepared, retained: bool) -> ProtocolConfig:
    payload = ProtocolConfig.from_yaml(prepared.protocol_path).model_dump()
    payload["screening"].update(
        n_cases_modify=8,
        n_cases_create=8,
        n_seeds=4,
        expand_n_seeds=8,
        expand_to_modify=12,
        expand_to_create=12,
        priority_case_ids=[
            case["path"] for case in prepared.stage("screening")["cases"][:8]
        ],
        require_expanded_for_pass=True,
    )
    payload["validation"].update(n_cases=12, n_seeds=8, expand_to=12)
    payload["frozen"].update(n_cases=12, n_seeds=8)
    payload["canary"] = {
        "cases": [case["path"] for case in prepared.canary["cases"]],
        "seeds": prepared.canary["seeds"],
    }
    names = ("retained",) if retained else ("screening", "validation", "frozen")
    rules = [
        {
            "time_limit_sec": case["time_limit_sec"],
            "stages": ["frozen" if name == "retained" else name],
            "case_globs": [case["path"]],
        }
        for name in names
        for case in prepared.stage(name)["cases"]
    ]
    payload["runtime"]["time_limits"] = {
        "stage_defaults": {
            "canary": 10,
            "screening": 30,
            "validation": 30,
            "frozen": 30,
        },
        "rules": rules,
    }
    return ProtocolConfig.model_validate(payload).with_problem_measurement(
        prepared.bridge.problem_spec,
        governance_mode="on",
    )


def _make_protocol(
    prepared: Prepared, runner: Any, metrics: Path, retained: bool
) -> ExperimentProtocol:
    names = ("retained",) if retained else ("screening", "validation", "frozen")
    split_payload = {
        "version": prepared.config["label"],
        "screening": []
        if retained
        else [case["path"] for case in prepared.stage("screening")["cases"]],
        "validation": []
        if retained
        else [case["path"] for case in prepared.stage("validation")["cases"]],
        "frozen": [case["path"] for case in prepared.stage(names[-1])["cases"]],
        "canary": [case["path"] for case in prepared.canary["cases"]],
        "safe_data_roots": [str(prepared.data_root)],
    }
    seed_payload = {
        "version": prepared.config["label"],
        "screening": [] if retained else prepared.stage("screening")["seeds"],
        "validation": [] if retained else prepared.stage("validation")["seeds"],
        "frozen": prepared.stage(names[-1])["seeds"],
        "canary": prepared.canary["seeds"],
    }
    protocol = ExperimentProtocol(
        _protocol_config(prepared, retained),
        SplitManager(SplitManifest.model_validate(split_payload)),
        SeedLedger(SeedLedgerConfig.model_validate(seed_payload)),
        runner,
        time_limit_sec=30,
        metrics_dir=str(metrics),
        metric_specs=prepared.bridge.metric_specs,
        objective_policy=prepared.bridge.objective_policy,
        problem_spec=prepared.bridge.problem_spec,
    )
    protocol.set_problem_adapter(prepared.adapter)
    return protocol


def build_runtime(prepared: Prepared, output: Path) -> Runtime:
    delegate = LocalSubprocessRunner(ResourceLimits(timeout_sec=135, memory_mb=4096))
    temp_root = output / "subject_workspaces"
    temp_root.mkdir()
    runner = FreshRunner(delegate, temp_root, prepared)
    config = _protocol_config(prepared, False)
    return Runtime(
        _make_protocol(prepared, runner, output / "metrics", False),
        _make_protocol(prepared, runner, output / "retained_metrics", True),
        runner,
        SafeFeatureExtractor(),
        DecisionEngine(config),
    )


def strict_canary(protocol: Any, prepared: Prepared) -> CanaryResult:
    case = prepared.canary["cases"][0]["path"]
    seed = prepared.canary["seeds"][0]
    surface = prepared.config["selected_surface"]

    def run(workspace: Path) -> RunResult:
        return protocol.runner.run_solver(
            workdir=str(workspace),
            instance_path=str(_inside(workspace, case, "canary")),
            seed=seed,
            time_limit_sec=10,
            registry_path=str(workspace / "registry.yaml"),
            selected_surface=surface,
        )

    b0_result = run(prepared.b0)
    candidate_result = run(prepared.candidate)
    if b0_result.output is None or candidate_result.output is None:
        raise Terminal("CANARY_OUTPUT_INVALID", "validated canary result has no output")
    b0_fleet = b0_result.output.objective.get("fleet_violation")  # type: ignore[union-attr]
    candidate_fleet = candidate_result.output.objective.get("fleet_violation")  # type: ignore[union-attr]
    if not all(
        isinstance(value, (int, float)) and not isinstance(value, bool)
        for value in (b0_fleet, candidate_fleet)
    ):
        raise Terminal(
            "CANARY_OBJECTIVE_INVALID", "canary fleet_violation is not numeric"
        )
    if candidate_fleet > b0_fleet:
        raise Terminal(
            "CANARY_CANDIDATE_VETO", "candidate canary regressed fleet_violation"
        )
    return CanaryResult(
        True,
        details={
            "case_ids": [case],
            "seed_set": [seed],
            "order": "b0_then_candidate",
            "passed": True,
        },
    )


def _paired(prepared: Prepared, block: str) -> PairedExecutionSpec:
    name = "screening" if block.startswith(("initial_", "expanded_")) else block
    stage = prepared.stage(name)
    return PairedExecutionSpec(
        candidate_ordinal=0,
        block_id=block,
        block_ordinal=prepared.config["order"]["block_ordinals"][block],
        case_ordinals={
            case["path"]: index for index, case in enumerate(stage["cases"])
        },
        seed_ordinals={seed: index for index, seed in enumerate(stage["seeds"])},
    )


def _summary(result: ProtocolResult) -> dict[str, Any]:
    stats = result.stats
    return {
        "stage": result.stage.value,
        "gate_outcome": result.gate_outcome,
        "reason_codes": list(result.reason_codes),
        "case_ids": list(result.case_ids),
        "seed_set": list(result.seed_set),
        "raw_metrics_ref": result.raw_metrics_ref,
        "stats": {name: getattr(stats, name) for name in SUMMARY_FIELDS},
    }


def _exact_copy(source: Path, copied: Path) -> None:
    left = {
        p.relative_to(source).as_posix(): p for p in source.rglob("*") if p.is_file()
    }
    right = {
        p.relative_to(copied).as_posix(): p for p in copied.rglob("*") if p.is_file()
    }
    if set(left) != set(right) or any(
        left[name].read_bytes() != right[name].read_bytes() for name in left
    ):
        raise Terminal(
            "SNAPSHOT_COPY_INVALID", "snapshot differs from evaluated candidate bytes"
        )


def execute(
    prepared: Prepared,
    output: Path,
    runtime: Runtime,
    *,
    canary: Callable[[Any, Prepared], CanaryResult] = strict_canary,
) -> dict[str, Any]:
    trace: list[dict[str, Any]] = []
    stages = zip(
        ("initial_screening", "expanded_screening", "validation", "frozen"),
        (
            ExperimentStage.SCREENING,
            ExperimentStage.SCREENING,
            ExperimentStage.VALIDATION,
            ExperimentStage.FROZEN,
        ),
        (False, True, False, False),
        (
            BranchState.EXPLORE,
            BranchState.EXPLORE_EXPAND,
            BranchState.VALIDATING,
            BranchState.FROZEN_TESTING,
        ),
        (
            Decision.EXPAND_SCREENING,
            Decision.QUEUE_VALIDATE,
            Decision.QUEUE_FROZEN,
            Decision.PROMOTE,
        ),
    )
    for block, stage, expand, state, expected in stages:
        try:
            canary_result = canary(runtime.protocol, prepared)
            result = runtime.protocol.run_experiment(
                stage,
                str(prepared.candidate),
                str(prepared.b0),
                "modify",
                expand=expand,
                expand_round=1,
                selected_surface=prepared.config["selected_surface"],
                paired_execution=_paired(prepared, block),
            )
        except Terminal as exc:
            exc.details.setdefault("completed_trace", list(trace))
            raise
        features = runtime.features.extract(
            branch_state=state,
            screening_expand_count=int(expand),
            validation_expand_count=0,
            failure_codes=(),
            hypothesis_action="modify",
            contract=True,
            verification=True,
            canary=canary_result,
            protocol=result,
        )
        decision = runtime.decisions.decide(features)
        trace.append(
            {
                "block": block,
                "canary": dict(canary_result.details),
                "protocol": _summary(result),
                "decision": decision.decision.value,
                "decision_reason_codes": list(decision.reason_codes),
            }
        )
        if decision.decision != expected:
            raise Terminal(
                f"{block.upper()}_{decision.decision.value.upper()}",
                f"{block} returned {decision.decision.value}, expected {expected.value}",
                {"trace": trace},
            )

    snapshot = output / "promoted_candidate_snapshot"
    shutil.copytree(prepared.candidate, snapshot)
    _exact_copy(prepared.candidate, snapshot)
    register = getattr(runtime.runner, "register_snapshot", None)
    if callable(register):
        register(snapshot)
    try:
        retained = runtime.retained_protocol.run_experiment(
            ExperimentStage.FROZEN,
            str(snapshot),
            str(prepared.b0),
            "modify",
            selected_surface=prepared.config["selected_surface"],
            paired_execution=_paired(prepared, "retained"),
        )
    except Terminal as exc:
        exc.details.setdefault("completed_trace", list(trace))
        raise
    if retained.gate_outcome != "pass" or retained.stats.failed_pairs:
        raise Terminal(
            "RETAINED_NOT_CONFIRMED",
            "retained comparison did not pass",
            {"retained": _summary(retained)},
        )
    counters = runtime.runner.counters()
    expected_counts = {
        "solver_subprocesses": 840,
        "nominal_subject_seconds": 45_200,
        "positive_hard_timeout_seconds": 57_800,
    }
    if counters != expected_counts:
        raise Terminal(
            "EXECUTION_COUNT_MISMATCH",
            "exact execution matrix was not consumed",
            {"expected": expected_counts, "actual": counters},
        )
    return {
        "status": "COMPLETED_PROMOTED_RETAINED",
        "terminal_type": "PROMOTED_RETAINED",
        "message": "candidate passed the four-gate funnel and retained comparison",
        "trace": trace,
        "retained": _summary(retained),
        "snapshot": str(snapshot),
        "counters": counters,
        "claims": dict(prepared.config["claim_boundary"]),
    }


def _atomic(path: Path, payload: Mapping[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("x") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


@contextmanager
def hardwall(runner: Any) -> Iterator[None]:
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    previous: dict[int, Any] = {}

    def stop(signum: int, _frame: Any) -> None:
        name = signal.Signals(signum).name
        raise Interrupted(
            "OUTER_HARDWALL" if signum == signal.SIGALRM else "INTERRUPTED",
            f"received {name}",
        )

    for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGALRM):
        previous[signum] = signal.getsignal(signum)
        signal.signal(signum, stop)
    signal.setitimer(signal.ITIMER_REAL, 64_800)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def _failed_terminal(
    base: Mapping[str, Any],
    runtime: Runtime | None,
    kind: str,
    message: str,
    **extra: Any,
) -> dict[str, Any]:
    return {
        **base,
        "status": "TERMINAL",
        "terminal_type": kind,
        "message": message,
        "counters": runtime.runner.counters() if runtime else {},
        **extra,
    }


def run_once(
    prepared: Prepared,
    output: Path,
    *,
    runtime_builder: Callable[[Prepared, Path], Runtime] = build_runtime,
    canary: Callable[[Any, Prepared], CanaryResult] = strict_canary,
) -> tuple[int, dict[str, Any]]:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    runtime: Runtime | None = None
    base = {
        "schema_version": SCHEMA,
        "label": prepared.config["label"],
        "config": str(prepared.config_path),
        "sources": prepared.sources,
        "changed_files": list(CHANGED_FILES),
        "historical_validation": prepared.config["historical_validation"],
    }
    code = 1
    try:
        runtime = runtime_builder(prepared, output)
        with hardwall(runtime.runner):
            terminal = {**base, **execute(prepared, output, runtime, canary=canary)}
        code = 0
    except Terminal as exc:
        if runtime:
            runtime.runner.terminate_active_processes(reason=exc.kind.lower())
        terminal = _failed_terminal(
            base, runtime, exc.kind, str(exc), details=exc.details
        )
        code = 2
    except (Interrupted, KeyboardInterrupt) as exc:
        if runtime:
            runtime.runner.terminate_active_processes(reason="interrupted")
        kind = exc.args[0] if isinstance(exc, Interrupted) else "INTERRUPTED"
        terminal = _failed_terminal(
            base, runtime, kind, str(exc.args[-1] if exc.args else exc)
        )
        code = 130
    except BaseException as exc:  # noqa: BLE001 - fail closed at the outer boundary
        if runtime:
            runtime.runner.terminate_active_processes(reason="execution_error")
        terminal = _failed_terminal(
            base, runtime, "EXECUTION_ERROR", f"{type(exc).__name__}: {exc}"
        )
    _atomic(output / "terminal.json", terminal)
    return code, terminal


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        prepared = prepare(args.config, args.input_root)
    except (KeyError, TypeError, ValueError) as exc:
        print(
            json.dumps({"status": "PREP_INVALID", "message": str(exc)}, sort_keys=True)
        )
        return 2
    if args.check:
        print(
            json.dumps(
                {
                    "status": "CHECK_PASS",
                    "label": prepared.config["label"],
                    "sources": prepared.sources,
                    "changed_files": list(CHANGED_FILES),
                    "solver_subprocesses": 0,
                    "provider_calls": 0,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    try:
        code, terminal = run_once(prepared, args.output_dir)
    except FileExistsError:
        print(
            json.dumps(
                {
                    "status": "PREP_INVALID",
                    "message": "output directory must not exist",
                },
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps(terminal, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
