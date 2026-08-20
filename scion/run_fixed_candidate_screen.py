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
from collections.abc import Iterator, Mapping
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
    RunResult,
)
from scion.problem.bridge import bridge_problem_spec_v1, load_problem_spec_v1_from_yaml
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

SCHEMA = "scion.fixed_candidate_screen.v1"
SUMMARY_FIELDS = (
    "n_cases",
    "wins",
    "losses",
    "ties",
    "win_rate",
    "median_delta",
    "ci_low",
    "ci_high",
    "attempted_pairs",
    "valid_pairs",
    "failed_pairs",
    "candidate_failed_pairs",
    "champion_failed_pairs",
    "shared_failed_pairs",
    "bilateral_failed_pairs",
)


class PrepError(ValueError):
    pass


class ScientificTerminal(RuntimeError):
    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind


class Interrupted(BaseException):
    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind


@dataclass(frozen=True)
class Prepared:
    config: dict[str, Any]
    b0: Path
    candidate: Path
    data_root: Path
    protocol_config: ProtocolConfig
    bridge: Any
    adapter: Any


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise PrepError(f"{name} must be a positive integer")
    return value


def _relative(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise PrepError(f"{name} must be a non-empty relative path")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        raise PrepError(f"{name} must be a canonical relative path")
    return value


def _inside(root: Path, relative: str, name: str) -> Path:
    candidate = (root / relative).resolve(strict=False)
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise PrepError(f"{name} escapes its root") from exc
    return candidate


def _regular_file(path: Path, name: str) -> bytes:
    if not path.is_file() or path.is_symlink():
        raise PrepError(f"{name} must be a regular file")
    return path.read_bytes()


def source_summary(root: Path) -> dict[str, Any]:
    if not root.is_dir() or root.is_symlink():
        raise PrepError(f"source is not a real directory: {root}")
    files: list[Path] = []
    for path in root.rglob("*"):
        if path.is_symlink():
            raise PrepError(f"source contains a symlink: {path}")
        if path.is_file():
            files.append(path)
    digest = hashlib.sha256()
    total = 0
    for path in sorted(files, key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        raw = path.read_bytes()
        total += len(raw)
        digest.update(relative.encode())
        digest.update(b"\0")
        digest.update(hashlib.sha256(raw).hexdigest().encode())
        digest.update(b"\0")
        digest.update(str(len(raw)).encode())
        digest.update(b"\n")
    return {
        "sha256": digest.hexdigest(),
        "file_count": len(files),
        "total_bytes": total,
    }


def _validate_source(input_root: Path, config: Mapping[str, Any], arm: str) -> Path:
    item = config["sources"][arm]
    path = _inside(input_root, _relative(item["path"], f"sources.{arm}.path"), arm)
    expected = {
        "sha256": item["sha256"],
        "file_count": _positive_int(item["file_count"], f"{arm}.file_count"),
        "total_bytes": _positive_int(item["total_bytes"], f"{arm}.total_bytes"),
    }
    if source_summary(path) != expected:
        raise PrepError(f"{arm} source summary differs")
    return path


def _changed_files(left: Path, right: Path) -> list[str]:
    left_files = {
        path.relative_to(left).as_posix(): path
        for path in left.rglob("*")
        if path.is_file()
    }
    right_files = {
        path.relative_to(right).as_posix(): path
        for path in right.rglob("*")
        if path.is_file()
    }
    if set(left_files) != set(right_files):
        raise PrepError("source file sets differ")
    return [
        name
        for name in sorted(left_files)
        if left_files[name].read_bytes() != right_files[name].read_bytes()
    ]


def _validate_population(prepared: Prepared) -> None:
    population = prepared.config["population"]
    cases = population["cases"]
    seeds = population["seeds"]
    if not isinstance(cases, list) or not cases:
        raise PrepError("population.cases must be non-empty")
    if not isinstance(seeds, list) or not seeds:
        raise PrepError("population.seeds must be non-empty")
    if len(set(seeds)) != len(seeds) or any(
        isinstance(seed, bool) or not isinstance(seed, int) for seed in seeds
    ):
        raise PrepError("population seeds must be unique integers")
    seen: set[str] = set()
    nominal = 0
    for index, item in enumerate(cases):
        relative = _relative(item["path"], f"cases[{index}].path")
        if relative in seen:
            raise PrepError("population cases must be unique")
        seen.add(relative)
        case = _inside(prepared.data_root, relative, "case")
        solution = case.with_suffix(".sol")
        for path, size_key, sha_key in (
            (case, "bytes", "sha256"),
            (solution, "solution_bytes", "solution_sha256"),
        ):
            raw = _regular_file(path, relative)
            if len(raw) != _positive_int(item[size_key], size_key):
                raise PrepError(f"{relative} size differs")
            if hashlib.sha256(raw).hexdigest() != item[sha_key]:
                raise PrepError(f"{relative} digest differs")
        prepared.adapter.load_instance(str(case))
        nominal += _positive_int(item["time_limit_sec"], "time_limit_sec")

    canary = population["canary"]
    relative = _relative(canary["path"], "canary.path")
    expected_canary = {
        "bytes": _positive_int(canary["bytes"], "canary.bytes"),
        "sha256": canary["sha256"],
    }
    for source in (prepared.b0, prepared.candidate):
        raw = _regular_file(_inside(source, relative, "canary"), "canary")
        actual = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        if actual != expected_canary:
            raise PrepError("canary bytes differ between source and config")

    budgets = prepared.config["budgets"]
    formal_pairs = len(cases) * len(seeds)
    solver_subprocesses = formal_pairs * 2 + 2
    nominal_seconds = nominal * len(seeds) * 2 + canary["time_limit_sec"] * 2
    implied = {
        "formal_pairs": formal_pairs,
        "formal_solver_subprocesses": formal_pairs * 2,
        "canary_solver_subprocesses": 2,
        "max_solver_subprocesses": solver_subprocesses,
        "nominal_subject_seconds": nominal_seconds,
        "positive_hard_timeout_seconds": nominal_seconds + 15 * solver_subprocesses,
    }
    if any(budgets.get(key) != value for key, value in implied.items()):
        raise PrepError("population does not imply the declared resource budget")
    if any(
        budgets.get(key) != 0
        for key in (
            "provider_calls",
            "hypothesis_calls",
            "code_calls",
            "patch_calls",
            "retry",
            "resume",
            "automatic_next_round",
        )
    ):
        raise PrepError("fixed-candidate action budgets must be zero")


def prepare(config_path: Path, input_root: Path) -> Prepared:
    config_path = config_path.expanduser().resolve()
    input_root = input_root.expanduser().resolve()
    raw = _regular_file(config_path, "config")
    try:
        config = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PrepError(f"invalid config JSON: {exc}") from exc
    if config.get("schema_version") != SCHEMA:
        raise PrepError("unsupported config schema")
    b0 = _validate_source(input_root, config, "b0")
    candidate = _validate_source(input_root, config, "candidate")
    if _changed_files(b0, candidate) != config["changed_files"]:
        raise PrepError("candidate changed-file set differs")
    data_root = _inside(input_root, _relative(config["data_root"], "data_root"), "data")
    if not data_root.is_dir() or data_root.is_symlink():
        raise PrepError("data_root must be a real directory")
    protocol_path = Path(config["protocol_config"]).expanduser().resolve()
    protocol_config = ProtocolConfig.from_yaml(protocol_path)
    bridge = bridge_problem_spec_v1(
        load_problem_spec_v1_from_yaml(b0 / "problem-v1.yaml")
    )
    adapter = load_problem_adapter(bridge.spec_v1)
    prepared = Prepared(
        config, b0, candidate, data_root, protocol_config, bridge, adapter
    )
    _validate_population(prepared)
    return prepared


def _make_dirs_writable(root: Path) -> None:
    if not root.exists():
        return
    for directory, dirnames, _files in os.walk(root):
        for item in [Path(directory), *(Path(directory) / name for name in dirnames)]:
            try:
                os.chmod(
                    item,
                    stat.S_IMODE(item.stat().st_mode)
                    | stat.S_IRUSR
                    | stat.S_IWUSR
                    | stat.S_IXUSR,
                )
            except FileNotFoundError:
                pass


class FreshCopyRunner:
    def __init__(self, prepared: Prepared, output: Path) -> None:
        max_limit = max(
            item["time_limit_sec"] for item in prepared.config["population"]["cases"]
        )
        self.delegate = LocalSubprocessRunner(
            ResourceLimits(timeout_sec=max_limit + 15, memory_mb=4096)
        )
        self.sources = {prepared.b0.resolve(), prepared.candidate.resolve()}
        self.temp_root = output / "subject_workspaces"
        self.temp_root.mkdir()
        self.max_calls = prepared.config["budgets"]["max_solver_subprocesses"]
        self.calls = 0
        self.nominal_seconds = 0
        self.hard_seconds = 0
        self._lock = threading.Lock()

    def terminate_active_processes(self, *, reason: str = "shutdown") -> int:
        return int(self.delegate.terminate_active_processes(reason=reason) or 0)

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
        if source not in self.sources:
            raise ScientificTerminal(
                "UNKNOWN_SOURCE", "runner received an unknown source"
            )
        limit = _positive_int(time_limit_sec, "time_limit_sec")
        with self._lock:
            if self.calls >= self.max_calls:
                raise ScientificTerminal(
                    "SOLVER_BUDGET_EXHAUSTED", "solver cap reached"
                )
            self.calls += 1
            self.nominal_seconds += limit
            self.hard_seconds += limit + 15
        parent = Path(tempfile.mkdtemp(prefix="subject-", dir=self.temp_root))
        copied = parent / "workspace"
        try:
            shutil.copytree(source, copied)
            _make_dirs_writable(copied)

            def remap(value: str) -> str:
                path = Path(value).resolve(strict=False)
                try:
                    return str(copied / path.relative_to(source))
                except ValueError:
                    return str(path)

            result = self.delegate.run_solver(
                workdir=str(copied),
                instance_path=remap(instance_path),
                seed=seed,
                time_limit_sec=limit,
                registry_path=remap(registry_path),
                selected_surface=selected_surface,
            )
            return replace(
                result,
                stdout=resolve_offloaded(result.stdout),
                stderr=resolve_offloaded(result.stderr),
            )
        finally:
            _make_dirs_writable(parent)
            shutil.rmtree(parent)

    def counters(self) -> dict[str, int]:
        return {
            "solver_subprocesses": self.calls,
            "nominal_subject_seconds": self.nominal_seconds,
            "positive_hard_timeout_seconds": self.hard_seconds,
        }


def _subject_failure(result: RunResult, prepared: Prepared) -> str | None:
    if not result.success:
        return result.error_category or "process_failure"
    if result.output is None:
        return "missing_output"
    issue = runtime_audit_failure_from_result(
        result,
        problem_spec=prepared.bridge.problem_spec,
        selected_surface=prepared.config["selected_surface"],
    )
    if runtime_audit_issue_blocks_execution(issue):
        return format_runtime_audit_failure(issue)
    return None if result.output.feasible else "infeasible"


def _strict_canary(runner: FreshCopyRunner, prepared: Prepared) -> CanaryResult:
    population = prepared.config["population"]
    canary = population["canary"]
    relative = canary["path"]

    def run(source: Path) -> RunResult:
        return runner.run_solver(
            workdir=str(source),
            instance_path=str(source / relative),
            seed=canary["seed"],
            time_limit_sec=canary["time_limit_sec"],
            registry_path=str(source / "registry.yaml"),
            selected_surface=prepared.config["selected_surface"],
        )

    b0_result = run(prepared.b0)
    candidate_result = run(prepared.candidate)
    for arm, result in (("b0", b0_result), ("candidate", candidate_result)):
        failure = _subject_failure(result, prepared)
        if failure:
            raise ScientificTerminal(
                "CANARY_INVALID", f"{arm} canary failed: {failure}"
            )
    assert b0_result.output is not None and candidate_result.output is not None
    b0_fleet = b0_result.output.objective.get("fleet_violation")
    candidate_fleet = candidate_result.output.objective.get("fleet_violation")
    if not all(
        isinstance(value, (int, float)) and not isinstance(value, bool)
        for value in (b0_fleet, candidate_fleet)
    ):
        raise ScientificTerminal("CANARY_INVALID", "fleet objective is not numeric")
    if candidate_fleet > b0_fleet:
        raise ScientificTerminal("CANARY_CANDIDATE_VETO", "candidate fleet regressed")
    return CanaryResult(
        passed=True,
        details={
            "case": relative,
            "seed": canary["seed"],
            "order": "b0_then_candidate",
        },
    )


def _make_protocol(
    prepared: Prepared, runner: FreshCopyRunner, output: Path
) -> ExperimentProtocol:
    population = prepared.config["population"]
    cases = [item["path"] for item in population["cases"]]
    seeds = list(population["seeds"])
    protocol_config = prepared.protocol_config.with_problem_measurement(
        prepared.bridge.problem_spec, governance_mode="on"
    )
    protocol = ExperimentProtocol(
        protocol_config,
        SplitManager(
            SplitManifest.model_validate(
                {
                    "version": prepared.config["label"],
                    "screening": cases,
                    "validation": [],
                    "frozen": [],
                    "canary": [population["canary"]["path"]],
                    "safe_data_roots": [str(prepared.data_root)],
                }
            )
        ),
        SeedLedger(
            SeedLedgerConfig.model_validate(
                {
                    "version": prepared.config["label"],
                    "screening": seeds,
                    "validation": [],
                    "frozen": [],
                    "canary": [population["canary"]["seed"]],
                }
            )
        ),
        runner,
        time_limit_sec=30,
        metrics_dir=str(output / "metrics"),
        metric_specs=prepared.bridge.metric_specs,
        objective_policy=prepared.bridge.objective_policy,
        problem_spec=prepared.bridge.problem_spec,
    )
    protocol.set_problem_adapter(prepared.adapter)
    return protocol


def _protocol_summary(result: Any) -> dict[str, Any]:
    return {
        "stage": result.stage.value,
        "gate_outcome": result.gate_outcome,
        "reason_codes": list(result.reason_codes),
        "case_ids": list(result.case_ids),
        "seed_set": list(result.seed_set),
        "raw_metrics_ref": result.raw_metrics_ref,
        "stats": {name: getattr(result.stats, name) for name in SUMMARY_FIELDS},
    }


def execute(
    prepared: Prepared, output: Path, runner: FreshCopyRunner
) -> dict[str, Any]:
    protocol = _make_protocol(prepared, runner, output)
    canary = _strict_canary(runner, prepared)
    population = prepared.config["population"]
    cases = [item["path"] for item in population["cases"]]
    seeds = list(population["seeds"])
    result = protocol.run_experiment(
        ExperimentStage.SCREENING,
        str(prepared.candidate),
        str(prepared.b0),
        "modify",
        expand=True,
        expand_round=1,
        selected_surface=prepared.config["selected_surface"],
        paired_execution=PairedExecutionSpec(
            candidate_ordinal=0,
            block_id="fixed_candidate_confirmation",
            block_ordinal=0,
            case_ordinals={case: index for index, case in enumerate(cases)},
            seed_ordinals={seed: index for index, seed in enumerate(seeds)},
        ),
    )
    features = SafeFeatureExtractor().extract(
        branch_state=BranchState.EXPLORE_EXPAND,
        screening_expand_count=1,
        validation_expand_count=0,
        failure_codes=(),
        hypothesis_action="modify",
        contract=True,
        verification=True,
        canary=canary,
        protocol=result,
    )
    decision = DecisionEngine(prepared.protocol_config).decide(features)
    counters = runner.counters()
    budgets = prepared.config["budgets"]
    expected = {
        "solver_subprocesses": budgets["max_solver_subprocesses"],
        "nominal_subject_seconds": budgets["nominal_subject_seconds"],
        "positive_hard_timeout_seconds": budgets["positive_hard_timeout_seconds"],
    }
    if counters != expected:
        raise ScientificTerminal(
            "EXECUTION_COUNT_MISMATCH", "execution matrix is incomplete"
        )
    supported = (
        result.gate_outcome == "pass"
        and not result.stats.failed_pairs
        and decision.decision is Decision.QUEUE_VALIDATE
    )
    return {
        "schema_version": SCHEMA,
        "label": prepared.config["label"],
        "status": "completed",
        "terminal_type": (
            "CONFIRMATION_SUPPORTED" if supported else "CONFIRMATION_NOT_SUPPORTED"
        ),
        "canary": dict(canary.details),
        "protocol": _protocol_summary(result),
        "decision": decision.decision.value,
        "decision_reason_codes": list(decision.reason_codes),
        "counters": counters,
        "claim_boundary": dict(prepared.config["claim_boundary"]),
    }


def _atomic(path: Path, payload: Mapping[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


@contextmanager
def hardwall(seconds: int) -> Iterator[None]:
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
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one fixed-candidate screening")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--input-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    prepared = prepare(args.config, args.input_root)
    if args.check:
        print(json.dumps({"status": "PREPARED", "label": prepared.config["label"]}))
        return 0

    output = args.output_dir.expanduser().resolve()
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    _atomic(output / "input.json", prepared.config)
    runner: FreshCopyRunner | None = None
    try:
        runner = FreshCopyRunner(prepared, output)
        with hardwall(
            _positive_int(
                prepared.config["budgets"]["outer_hardwall_seconds"],
                "outer_hardwall_seconds",
            )
        ):
            payload = execute(prepared, output, runner)
        _atomic(output / "terminal.json", payload)
        return 0
    except Interrupted as exc:
        if runner is not None:
            runner.terminate_active_processes(reason=exc.kind)
        _atomic(
            output / "terminal.json",
            {
                "schema_version": SCHEMA,
                "status": "interrupted",
                "terminal_type": exc.kind,
            },
        )
        return 130
    except BaseException as exc:
        if runner is not None:
            runner.terminate_active_processes(reason="terminal")
        kind = (
            exc.kind if isinstance(exc, ScientificTerminal) else "UNHANDLED_EXCEPTION"
        )
        _atomic(
            output / "terminal.json",
            {
                "schema_version": SCHEMA,
                "status": "failed",
                "terminal_type": kind,
                "message": str(exc),
            },
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
