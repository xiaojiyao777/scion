"""Run one provider-free fixed-candidate scientific funnel.

This driver accepts ordinary source and experiment paths, copies the two source
trees once into a private immutable execution snapshot, and then delegates all
comparative judgments to Protocol and deterministic Decision.  It keeps no
auxiliary trust lifecycle.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import stat
import sys
import tempfile
from collections.abc import Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from scion.config.problem import ProtocolConfig, SeedLedgerConfig, SplitManifest
from scion.contract.patch_paths import matches_config_pattern
from scion.contract.surface_access import SurfaceAccess
from scion.core.decision import DecisionEngine
from scion.core.features import SafeFeatureExtractor
from scion.core.models import BranchState, CanaryResult, Decision, ExperimentStage
from scion.problem.loader import load_problem_adapter, load_problem_spec_v1_from_yaml
from scion.protocol.experiment import (
    ExperimentProtocol,
    PairedExecutionSpec,
    SeedLedger,
    SplitManager,
)
from scion.protocol.experiment.selection import (
    resolve_case_path_details,
    validate_case_path_resolution,
)
from scion.runtime.runner import ResourceLimits, resolve_offloaded
from scion.runtime.subprocess_runner import LocalSubprocessRunner

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
_IGNORED_SOURCE_PARTS = frozenset({"__pycache__", ".pytest_cache"})
_FIXED_ACTION = "modify"


class PrepError(ValueError):
    """The explicit fixed-candidate inputs are not runnable as declared."""


class ScientificTerminal(RuntimeError):
    """A typed local/resource failure after the fresh output was created."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class Interrupted(BaseException):
    """Signal or outer-hardwall interruption."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ResourceEnvelope:
    max_solver_subprocesses: int
    nominal_subject_seconds: int
    guarded_subject_seconds: int
    max_time_limit_sec: int
    timeout_guard_sec: int
    outer_hardwall_sec: int
    fallback_time_limit_sec: int
    memory_mb: int


@dataclass(frozen=True)
class Prepared:
    label: str
    baseline: Path
    candidate: Path
    problem_spec_path: Path
    protocol_path: Path
    split_path: Path
    seeds_path: Path
    retained_split_path: Path
    retained_seeds_path: Path
    changed_files: tuple[str, ...]
    selected_surface: str
    protocol_config: ProtocolConfig
    split_manifest: SplitManifest
    seed_config: SeedLedgerConfig
    retained_split_manifest: SplitManifest
    retained_seed_config: SeedLedgerConfig
    adapter: Any
    envelope: ResourceEnvelope

    def input_record(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "baseline_source": str(self.baseline),
            "candidate_source": str(self.candidate),
            "problem_spec": str(self.problem_spec_path),
            "protocol": str(self.protocol_path),
            "split": str(self.split_path),
            "seeds": str(self.seeds_path),
            "retained_split": str(self.retained_split_path),
            "retained_seeds": str(self.retained_seeds_path),
            "changed_files": list(self.changed_files),
            "selected_surface": self.selected_surface,
            "action": _FIXED_ACTION,
            "resources": asdict(self.envelope),
            "provider_calls": 0,
        }


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise PrepError(f"{name} must be a positive integer")
    return value


def _ordinary_path(value: str | Path, name: str, *, directory: bool) -> Path:
    unresolved = Path(value).expanduser()
    if unresolved.is_symlink():
        raise PrepError(f"{name} must not be a symlink: {unresolved}")
    path = unresolved.resolve()
    valid = path.is_dir() if directory else path.is_file()
    if not valid or path.is_symlink():
        kind = "directory" if directory else "file"
        raise PrepError(f"{name} must be a regular {kind}: {path}")
    return path


def _relative_path(value: str, name: str) -> str:
    path = Path(value)
    if (
        not value
        or path.is_absolute()
        or ".." in path.parts
        or path.as_posix() != value
    ):
        raise PrepError(f"{name} must be a canonical relative path")
    return value


def _ignored_source_path(relative: Path) -> bool:
    return bool(_IGNORED_SOURCE_PARTS.intersection(relative.parts)) or (
        relative.suffix == ".pyc"
    )


def _source_bytes(root: Path) -> dict[str, bytes]:
    if not root.is_dir() or root.is_symlink():
        raise PrepError(f"source must be a regular directory: {root}")
    files: dict[str, bytes] = {}
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if path.is_symlink():
            raise PrepError(f"source contains a symlink: {relative.as_posix()}")
        if _ignored_source_path(relative):
            continue
        if path.is_dir():
            continue
        if not path.is_file():
            raise PrepError(
                f"source contains a non-regular entry: {relative.as_posix()}"
            )
        files[relative.as_posix()] = path.read_bytes()
    if not files:
        raise PrepError(f"source contains no ordinary files: {root}")
    return files


def validate_source_difference(
    baseline: Path,
    candidate: Path,
    expected_changed_files: Sequence[str],
) -> tuple[str, ...]:
    """Compare the two explicit sources directly, once, without identities."""

    expected = tuple(
        sorted(
            {_relative_path(value, "changed-file") for value in expected_changed_files}
        )
    )
    if len(expected_changed_files) != len(expected):
        raise PrepError("changed-file values must be unique")
    if not expected:
        raise PrepError("at least one changed-file is required")
    left = _source_bytes(baseline)
    right = _source_bytes(candidate)
    if set(left) != set(right):
        raise PrepError("baseline and candidate source file sets differ")
    actual = tuple(sorted(name for name in left if left[name] != right[name]))
    if actual != expected:
        raise PrepError(
            "direct source changed-file set differs: "
            f"expected {list(expected)}, actual {list(actual)}"
        )
    return actual


def validate_candidate_scope(
    problem_spec: Any,
    *,
    selected_surface: str,
    changed_files: Sequence[str],
) -> None:
    """Bind every changed file to the declared editable research surface."""

    surface_access = SurfaceAccess(problem_spec)
    selected = surface_access.surface_by_name(selected_surface)
    if selected is None:
        raise PrepError(
            "selected-surface must name a declared problem research surface"
        )
    if not surface_access.surface_action_allowed(selected, _FIXED_ACTION):
        raise PrepError("selected-surface does not allow fixed modify candidates")
    editable = tuple(problem_spec.search_space.editable)
    frozen = tuple(problem_spec.search_space.frozen)
    for changed_file in changed_files:
        if not surface_access.target_matches_surface(changed_file, selected):
            raise PrepError("changed-file is outside the selected research surface")
        if not any(
            matches_config_pattern(changed_file, pattern) for pattern in editable
        ):
            raise PrepError("changed-file is outside the editable search space")
        if any(matches_config_pattern(changed_file, pattern) for pattern in frozen):
            raise PrepError("changed-file is in the frozen search space")


def sources_equal(left: Path, right: Path) -> bool:
    """Return direct byte equality for the one post-promotion copy check."""

    return _source_bytes(left) == _source_bytes(right)


def _path_is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _validate_output_location(output: Path, prepared: Prepared) -> None:
    for source in (prepared.baseline, prepared.candidate):
        if _path_is_within(output, source):
            raise PrepError("output-dir must be outside both source trees")


def _snapshot_prepared_sources(prepared: Prepared, output: Path) -> Prepared:
    """Make the only source copies used by the live scientific run."""

    snapshot_root = output / "input_snapshots"
    snapshot_root.mkdir()
    baseline = snapshot_root / "baseline"
    candidate = snapshot_root / "candidate"
    shutil.copytree(prepared.baseline, baseline, ignore=_copy_ignore)
    shutil.copytree(prepared.candidate, candidate, ignore=_copy_ignore)
    if not sources_equal(prepared.baseline, baseline):
        raise ScientificTerminal(
            "BASELINE_SOURCE_CHANGED_DURING_SNAPSHOT",
            "baseline source changed while the private snapshot was created",
        )
    if not sources_equal(prepared.candidate, candidate):
        raise ScientificTerminal(
            "CANDIDATE_SOURCE_CHANGED_DURING_SNAPSHOT",
            "candidate source changed while the private snapshot was created",
        )
    validate_source_difference(baseline, candidate, prepared.changed_files)
    _make_tree_readonly(baseline)
    _make_tree_readonly(candidate)
    return replace(prepared, baseline=baseline, candidate=candidate)


def _all_unique(values: Iterable[Any], name: str) -> None:
    items = list(values)
    if len(items) != len(set(items)):
        raise PrepError(f"{name} must be disjoint and contain no duplicates")


def validate_population_shape(
    config: Any,
    split: Any,
    seeds: Any,
    retained_split: Any,
    retained_seeds: Any,
) -> None:
    """Validate the exact conditional funnel before creating live runtime."""

    initial_cases = int(config.screening.n_cases_modify)
    expanded_cases = int(config.screening.expand_to_modify)
    initial_seeds = int(config.screening.n_seeds)
    expanded_seeds = int(config.screening.expand_n_seeds)
    if expanded_cases <= initial_cases or expanded_seeds <= initial_seeds:
        raise PrepError("expanded screening must strictly grow cases and seeds")
    if not config.screening.require_expanded_for_pass:
        raise PrepError("fixed-candidate funnel requires expanded screening")
    if len(split.screening) != expanded_cases:
        raise PrepError("screening split must equal the expanded case count")
    if len(seeds.screening) != expanded_seeds:
        raise PrepError("screening seeds must equal the expanded seed count")
    if len(split.validation) != int(config.validation.n_cases):
        raise PrepError("validation split count differs from Protocol")
    if len(seeds.validation) != int(config.validation.n_seeds):
        raise PrepError("validation seed count differs from Protocol")
    if int(config.validation.expand_to) != int(config.validation.n_cases):
        raise PrepError("fixed funnel does not admit validation expansion")
    if len(split.frozen) != int(config.frozen.n_cases):
        raise PrepError("frozen split count differs from Protocol")
    if len(seeds.frozen) != int(config.frozen.n_seeds):
        raise PrepError("frozen seed count differs from Protocol")
    if not split.canary or not seeds.canary:
        raise PrepError("canary cases and seeds are required")
    if retained_split.screening or retained_split.validation or retained_split.canary:
        raise PrepError("retained split may contain only frozen cases")
    if retained_seeds.screening or retained_seeds.validation or retained_seeds.canary:
        raise PrepError("retained seeds may contain only frozen seeds")
    if len(retained_split.frozen) != int(config.frozen.n_cases):
        raise PrepError("retained case count differs from frozen Protocol")
    if len(retained_seeds.frozen) != int(config.frozen.n_seeds):
        raise PrepError("retained seed count differs from frozen Protocol")

    _all_unique(
        [
            *split.screening,
            *split.validation,
            *split.frozen,
            *split.canary,
            *retained_split.frozen,
        ],
        "funnel case paths",
    )
    _all_unique(
        [
            *seeds.screening,
            *seeds.validation,
            *seeds.frozen,
            *seeds.canary,
            *retained_seeds.frozen,
        ],
        "funnel seeds",
    )


def _time_limit(
    config: ProtocolConfig,
    *,
    stage: str,
    case_path: str,
    fallback: int,
) -> int:
    policy = getattr(getattr(config, "runtime", None), "time_limits", None)
    if policy is None:
        return fallback
    return int(
        policy.resolve(
            stage=stage,
            case_path=case_path,
            fallback_time_limit_sec=fallback,
        )
    )


def build_resource_envelope(
    config: ProtocolConfig,
    split: SplitManifest,
    seeds: SeedLedgerConfig,
    retained_split: SplitManifest,
    retained_seeds: SeedLedgerConfig,
    *,
    fallback_time_limit_sec: int,
    timeout_guard_sec: int,
    outer_hardwall_sec: int,
    memory_mb: int,
) -> ResourceEnvelope:
    calls = 0
    nominal = 0
    max_limit = 0
    matrices = (
        ("screening", split.screening, seeds.screening),
        ("validation", split.validation, seeds.validation),
        ("frozen", split.frozen, seeds.frozen),
        ("frozen", retained_split.frozen, retained_seeds.frozen),
        ("canary", split.canary, seeds.canary),
    )
    for stage, cases, stage_seeds in matrices:
        for case in cases:
            limit = _time_limit(
                config,
                stage=stage,
                case_path=case,
                fallback=fallback_time_limit_sec,
            )
            _positive_int(limit, f"{stage} time limit")
            max_limit = max(max_limit, limit)
            calls += len(stage_seeds) * 2
            nominal += limit * len(stage_seeds) * 2
    guarded = nominal + calls * timeout_guard_sec
    if outer_hardwall_sec <= guarded:
        raise PrepError(
            "outer-hardwall-sec must exceed the derived guarded subject seconds"
        )
    return ResourceEnvelope(
        max_solver_subprocesses=calls,
        nominal_subject_seconds=nominal,
        guarded_subject_seconds=guarded,
        max_time_limit_sec=max_limit,
        timeout_guard_sec=timeout_guard_sec,
        outer_hardwall_sec=outer_hardwall_sec,
        fallback_time_limit_sec=fallback_time_limit_sec,
        memory_mb=_positive_int(memory_mb, "memory-mb"),
    )


def _preparse_cases(prepared: Prepared) -> None:
    groups = (
        (
            [
                *prepared.split_manifest.screening,
                *prepared.split_manifest.validation,
                *prepared.split_manifest.frozen,
                *prepared.split_manifest.canary,
            ],
            prepared.split_manifest.safe_data_roots,
        ),
        (
            prepared.retained_split_manifest.frozen,
            prepared.retained_split_manifest.safe_data_roots,
        ),
    )
    for cases, roots in groups:
        for case in cases:
            resolution = resolve_case_path_details(
                case,
                workspace=str(prepared.baseline),
                safe_data_roots=roots,
            )
            validate_case_path_resolution(resolution, strict=True)
            prepared.adapter.load_instance(resolution.resolved)


def prepare(
    *,
    label: str,
    baseline_source: Path,
    candidate_source: Path,
    problem_spec: Path,
    protocol: Path,
    split: Path,
    seeds: Path,
    retained_split: Path,
    retained_seeds: Path,
    changed_files: Sequence[str],
    selected_surface: str,
    fallback_time_limit_sec: int,
    timeout_guard_sec: int,
    outer_hardwall_sec: int,
    memory_mb: int,
) -> Prepared:
    if not label.strip():
        raise PrepError("label must be non-empty")
    if not selected_surface.strip():
        raise PrepError("selected-surface must be non-empty")
    baseline = _ordinary_path(baseline_source, "baseline-source", directory=True)
    candidate = _ordinary_path(candidate_source, "candidate-source", directory=True)
    problem_spec_path = _ordinary_path(problem_spec, "problem-spec", directory=False)
    protocol_path = _ordinary_path(protocol, "protocol", directory=False)
    split_path = _ordinary_path(split, "split", directory=False)
    seeds_path = _ordinary_path(seeds, "seeds", directory=False)
    retained_split_path = _ordinary_path(
        retained_split, "retained-split", directory=False
    )
    retained_seeds_path = _ordinary_path(
        retained_seeds, "retained-seeds", directory=False
    )
    actual_changed = validate_source_difference(baseline, candidate, changed_files)

    protocol_config = ProtocolConfig.from_yaml(protocol_path)
    split_manifest = SplitManifest.from_yaml(split_path)
    seed_config = SeedLedgerConfig.from_yaml(seeds_path)
    retained_split_manifest = SplitManifest.from_yaml(retained_split_path)
    retained_seed_config = SeedLedgerConfig.from_yaml(retained_seeds_path)
    validate_population_shape(
        protocol_config,
        split_manifest,
        seed_config,
        retained_split_manifest,
        retained_seed_config,
    )
    adapter = load_problem_adapter(load_problem_spec_v1_from_yaml(problem_spec_path))
    validate_candidate_scope(
        adapter.spec,
        selected_surface=selected_surface,
        changed_files=actual_changed,
    )
    envelope = build_resource_envelope(
        protocol_config,
        split_manifest,
        seed_config,
        retained_split_manifest,
        retained_seed_config,
        fallback_time_limit_sec=_positive_int(
            fallback_time_limit_sec, "time-limit-sec"
        ),
        timeout_guard_sec=_positive_int(timeout_guard_sec, "timeout-guard-sec"),
        outer_hardwall_sec=_positive_int(outer_hardwall_sec, "outer-hardwall-sec"),
        memory_mb=memory_mb,
    )
    prepared = Prepared(
        label=label,
        baseline=baseline,
        candidate=candidate,
        problem_spec_path=problem_spec_path,
        protocol_path=protocol_path,
        split_path=split_path,
        seeds_path=seeds_path,
        retained_split_path=retained_split_path,
        retained_seeds_path=retained_seeds_path,
        changed_files=actual_changed,
        selected_surface=selected_surface,
        protocol_config=protocol_config,
        split_manifest=split_manifest,
        seed_config=seed_config,
        retained_split_manifest=retained_split_manifest,
        retained_seed_config=retained_seed_config,
        adapter=adapter,
        envelope=envelope,
    )
    _preparse_cases(prepared)
    return prepared


def _make_dirs_writable(root: Path) -> None:
    if not root.exists():
        return
    for directory, dirnames, filenames in os.walk(root):
        for item in (
            Path(directory),
            *(Path(directory) / name for name in dirnames),
            *(Path(directory) / name for name in filenames),
        ):
            try:
                mode = stat.S_IMODE(item.stat().st_mode)
                extra = stat.S_IRUSR | stat.S_IWUSR
                if item.is_dir():
                    extra |= stat.S_IXUSR
                os.chmod(item, mode | extra)
            except FileNotFoundError:
                pass


def _make_tree_readonly(root: Path) -> None:
    for path in sorted(root.rglob("*"), reverse=True):
        mode = stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH
        if path.is_dir():
            mode |= stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
        os.chmod(path, mode)
    os.chmod(
        root,
        stat.S_IRUSR
        | stat.S_IRGRP
        | stat.S_IROTH
        | stat.S_IXUSR
        | stat.S_IXGRP
        | stat.S_IXOTH,
    )


def _copy_ignore(_directory: str, names: list[str]) -> set[str]:
    return {
        name for name in names if name in _IGNORED_SOURCE_PARTS or name.endswith(".pyc")
    }


class FreshCopyRunner:
    """Copy each explicit subject into a private disposable run directory."""

    def __init__(
        self,
        output: Path,
        envelope: ResourceEnvelope,
        *,
        delegate: Any | None = None,
    ) -> None:
        self.envelope = envelope
        self.temp_root = output / "subject_workspaces"
        self.temp_root.mkdir()
        self.delegate = delegate or LocalSubprocessRunner(
            ResourceLimits(
                timeout_sec=(envelope.max_time_limit_sec + envelope.timeout_guard_sec),
                memory_mb=envelope.memory_mb,
            )
        )
        self.calls = 0
        self.nominal_seconds = 0
        self.guarded_seconds = 0

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
    ):
        source = Path(workdir).resolve()
        if not source.is_dir() or source.is_symlink():
            raise ScientificTerminal(
                "SOURCE_UNAVAILABLE", f"solver source is unavailable: {source}"
            )
        limit = _positive_int(time_limit_sec, "solver time limit")
        next_calls = self.calls + 1
        next_nominal = self.nominal_seconds + limit
        next_guarded = self.guarded_seconds + limit + self.envelope.timeout_guard_sec
        if (
            next_calls > self.envelope.max_solver_subprocesses
            or next_nominal > self.envelope.nominal_subject_seconds
            or next_guarded > self.envelope.guarded_subject_seconds
        ):
            raise ScientificTerminal(
                "SOLVER_RESOURCE_EXHAUSTED",
                "solver dispatch would exceed the declared resource envelope",
            )
        self.calls = next_calls
        self.nominal_seconds = next_nominal
        self.guarded_seconds = next_guarded

        parent = Path(tempfile.mkdtemp(prefix="subject-", dir=self.temp_root))
        copied = parent / "workspace"
        try:
            shutil.copytree(source, copied, ignore=_copy_ignore)
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
            stdout = resolve_offloaded(result.stdout)
            stderr = resolve_offloaded(result.stderr)
            if stdout != result.stdout or stderr != result.stderr:
                return replace(result, stdout=stdout, stderr=stderr)
            # Failures are ordinary RunResults.  Protocol must see both arms and
            # own candidate/champion/shared/bilateral attribution.
            return result
        finally:
            _make_dirs_writable(parent)
            shutil.rmtree(parent, ignore_errors=False)

    def counters(self) -> dict[str, int]:
        return {
            "solver_subprocesses": self.calls,
            "nominal_subject_seconds": self.nominal_seconds,
            "guarded_subject_seconds": self.guarded_seconds,
        }


def _make_protocol(
    prepared: Prepared,
    runner: FreshCopyRunner,
    output: Path,
    *,
    retained: bool,
) -> ExperimentProtocol:
    manifest = prepared.retained_split_manifest if retained else prepared.split_manifest
    ledger = prepared.retained_seed_config if retained else prepared.seed_config
    config = prepared.protocol_config.with_problem_measurement(
        prepared.adapter.spec,
        governance_mode="on",
    )
    protocol = ExperimentProtocol(
        config,
        SplitManager(manifest),
        SeedLedger(ledger),
        runner,
        time_limit_sec=prepared.envelope.fallback_time_limit_sec,
        metrics_dir=str(output / ("retained_metrics" if retained else "metrics")),
        adapter=prepared.adapter,
    )
    return protocol


def _make_protocols(
    prepared: Prepared, runner: FreshCopyRunner, output: Path
) -> tuple[ExperimentProtocol, ExperimentProtocol]:
    return (
        _make_protocol(prepared, runner, output, retained=False),
        _make_protocol(prepared, runner, output, retained=True),
    )


def _paired_spec(
    *, label: str, ordinal: int, cases: Sequence[str], seeds: Sequence[int]
) -> PairedExecutionSpec:
    return PairedExecutionSpec(
        candidate_ordinal=0,
        block_id=f"{label}:{ordinal}",
        block_ordinal=ordinal,
        case_ordinals={case: index for index, case in enumerate(cases)},
        seed_ordinals={seed: index for index, seed in enumerate(seeds)},
    )


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


def _decide(
    prepared: Prepared,
    *,
    state: BranchState,
    canary: CanaryResult,
    protocol: Any,
) -> Any:
    features = SafeFeatureExtractor().extract(
        branch_state=state,
        screening_expand_count=1,
        validation_expand_count=0,
        failure_codes=(),
        hypothesis_action=_FIXED_ACTION,
        contract=True,
        verification=True,
        canary=canary,
        protocol=protocol,
    )
    return DecisionEngine(prepared.protocol_config).decide(features)


def _supported(result: Any, decision: Any, expected: Decision) -> bool:
    return (
        result.gate_outcome == "pass"
        and int(result.stats.failed_pairs) == 0
        and decision.decision is expected
    )


def _comparator_evidence_incomplete(result: Any) -> bool:
    stats = result.stats
    return any(
        int(value) > 0
        for value in (
            stats.champion_failed_pairs,
            stats.shared_failed_pairs,
            stats.bilateral_failed_pairs,
        )
    )


def _copy_promoted_candidate(candidate: Path, snapshot: Path) -> None:
    shutil.copytree(candidate, snapshot, ignore=_copy_ignore)
    if not sources_equal(candidate, snapshot):
        raise ScientificTerminal(
            "PROMOTED_COPY_MISMATCH",
            "the one promoted copy differs from the evaluated candidate bytes",
        )
    _make_tree_readonly(snapshot)


def execute(
    prepared: Prepared,
    output: Path,
    runner: FreshCopyRunner,
) -> dict[str, Any]:
    main, retained_protocol = _make_protocols(prepared, runner, output)
    canary = main.run_canary(
        str(prepared.candidate),
        str(prepared.baseline),
        selected_surface=prepared.selected_surface,
        require_complete_pairs=True,
    )
    payload: dict[str, Any] = {
        "label": prepared.label,
        "status": "completed",
        "terminal_type": "NOT_CONFIRMED",
        "canary": {
            "passed": canary.passed,
            "reason_codes": list(canary.reason_codes),
            "details": dict(canary.details),
        },
        "stages": [],
    }
    if not canary.passed:
        payload["stop_stage"] = "canary"
        if canary.failure_category == "incomplete_evidence":
            payload["status"] = "completed_incomplete"
            payload["terminal_type"] = "INCOMPLETE_COMPARATOR_EVIDENCE"
        payload["counters"] = runner.counters()
        return payload

    stages = (
        (
            "expanded_screening",
            ExperimentStage.SCREENING,
            True,
            BranchState.EXPLORE_EXPAND,
            Decision.QUEUE_VALIDATE,
            prepared.split_manifest.screening,
            prepared.seed_config.screening,
        ),
        (
            "validation",
            ExperimentStage.VALIDATION,
            False,
            BranchState.VALIDATING,
            Decision.QUEUE_FROZEN,
            prepared.split_manifest.validation,
            prepared.seed_config.validation,
        ),
        (
            "frozen",
            ExperimentStage.FROZEN,
            False,
            BranchState.FROZEN_TESTING,
            Decision.PROMOTE,
            prepared.split_manifest.frozen,
            prepared.seed_config.frozen,
        ),
    )
    for ordinal, (
        name,
        stage,
        expand,
        state,
        expected,
        cases,
        seeds,
    ) in enumerate(stages):
        result = main.run_experiment(
            stage,
            str(prepared.candidate),
            str(prepared.baseline),
            _FIXED_ACTION,
            expand=expand,
            expand_round=1,
            selected_surface=prepared.selected_surface,
            paired_execution=_paired_spec(
                label=prepared.label,
                ordinal=ordinal,
                cases=cases,
                seeds=seeds,
            ),
        )
        protocol_summary = _protocol_summary(result)
        if _comparator_evidence_incomplete(result):
            payload["stages"].append(
                {
                    "name": name,
                    "protocol": protocol_summary,
                    "decision": None,
                    "decision_reason_codes": [],
                }
            )
            payload["status"] = "completed_incomplete"
            payload["terminal_type"] = "INCOMPLETE_COMPARATOR_EVIDENCE"
            payload["stop_stage"] = name
            payload["counters"] = runner.counters()
            return payload
        decision = _decide(
            prepared,
            state=state,
            canary=canary,
            protocol=result,
        )
        payload["stages"].append(
            {
                "name": name,
                "protocol": protocol_summary,
                "decision": decision.decision.value,
                "decision_reason_codes": list(decision.reason_codes),
            }
        )
        if not _supported(result, decision, expected):
            payload["stop_stage"] = name
            payload["counters"] = runner.counters()
            return payload

    snapshot = output / "promoted_candidate"
    _copy_promoted_candidate(prepared.candidate, snapshot)
    payload["promotion"] = {
        "decision": Decision.PROMOTE.value,
        "source": str(snapshot),
    }

    retained_result = retained_protocol.run_experiment(
        ExperimentStage.FROZEN,
        str(snapshot),
        str(prepared.baseline),
        _FIXED_ACTION,
        selected_surface=prepared.selected_surface,
        paired_execution=_paired_spec(
            label=prepared.label,
            ordinal=3,
            cases=prepared.retained_split_manifest.frozen,
            seeds=prepared.retained_seed_config.frozen,
        ),
    )
    retained_summary = _protocol_summary(retained_result)
    payload["retained"] = retained_summary
    if _comparator_evidence_incomplete(retained_result):
        payload["status"] = "completed_incomplete"
        payload["terminal_type"] = "INCOMPLETE_COMPARATOR_EVIDENCE"
        payload["stop_stage"] = "retained"
        payload["counters"] = runner.counters()
        return payload
    payload["terminal_type"] = (
        "PROMOTED_RETAINED"
        if retained_result.gate_outcome == "pass"
        and int(retained_result.stats.failed_pairs) == 0
        else "PROMOTED_NOT_RETAINED"
    )
    payload["stop_stage"] = "retained"
    payload["counters"] = runner.counters()
    if payload["terminal_type"] == "PROMOTED_RETAINED" and (
        runner.counters()
        != {
            "solver_subprocesses": prepared.envelope.max_solver_subprocesses,
            "nominal_subject_seconds": prepared.envelope.nominal_subject_seconds,
            "guarded_subject_seconds": prepared.envelope.guarded_subject_seconds,
        }
    ):
        raise ScientificTerminal(
            "SUCCESS_MATRIX_INCOMPLETE",
            "a positive terminal result did not consume the declared matrix",
        )
    return payload


def _atomic(path: Path, payload: Mapping[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise


@contextmanager
def hardwall(seconds: int) -> Iterator[None]:
    previous: dict[int, Any] = {}

    def stop(signum: int, _frame: Any) -> None:
        code = "OUTER_HARDWALL" if signum == signal.SIGALRM else "INTERRUPTED"
        raise Interrupted(code)

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


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one provider-free fixed-candidate full funnel"
    )
    parser.add_argument("--label", required=True)
    parser.add_argument("--baseline-source", required=True, type=Path)
    parser.add_argument("--candidate-source", required=True, type=Path)
    parser.add_argument("--problem-spec", required=True, type=Path)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--split", required=True, type=Path)
    parser.add_argument("--seeds", required=True, type=Path)
    parser.add_argument("--retained-split", required=True, type=Path)
    parser.add_argument("--retained-seeds", required=True, type=Path)
    parser.add_argument("--changed-file", action="append", default=[])
    parser.add_argument("--selected-surface", required=True)
    parser.add_argument("--time-limit-sec", type=int, default=30)
    parser.add_argument("--timeout-guard-sec", type=int, default=15)
    parser.add_argument("--outer-hardwall-sec", required=True, type=int)
    parser.add_argument("--memory-mb", type=int, default=4096)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--check", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        prepared = prepare(
            label=args.label,
            baseline_source=args.baseline_source,
            candidate_source=args.candidate_source,
            problem_spec=args.problem_spec,
            protocol=args.protocol,
            split=args.split,
            seeds=args.seeds,
            retained_split=args.retained_split,
            retained_seeds=args.retained_seeds,
            changed_files=args.changed_file,
            selected_surface=args.selected_surface,
            fallback_time_limit_sec=args.time_limit_sec,
            timeout_guard_sec=args.timeout_guard_sec,
            outer_hardwall_sec=args.outer_hardwall_sec,
            memory_mb=args.memory_mb,
        )
    except Exception as exc:  # noqa: BLE001 - prep must stay before live output
        print(f"PREP_INVALID: {exc}", file=sys.stderr)
        return 2
    if args.check:
        print(json.dumps({"status": "PREPARED", **prepared.input_record()}))
        return 0

    output = args.output_dir.expanduser().resolve()
    try:
        _validate_output_location(output, prepared)
    except Exception as exc:  # noqa: BLE001 - still before live output
        print(f"OUTPUT_INVALID: {exc}", file=sys.stderr)
        return 2
    try:
        output.mkdir(mode=0o700, parents=True, exist_ok=False)
    except OSError as exc:
        print(f"OUTPUT_INVALID: {exc}", file=sys.stderr)
        return 2
    runner: FreshCopyRunner | None = None
    try:
        with hardwall(prepared.envelope.outer_hardwall_sec):
            declared_sources = {
                "baseline": str(prepared.baseline),
                "candidate": str(prepared.candidate),
            }
            prepared = _snapshot_prepared_sources(prepared, output)
            input_record = prepared.input_record()
            input_record["declared_source_paths"] = declared_sources
            _atomic(output / "input.json", input_record)
            runner = FreshCopyRunner(
                output,
                prepared.envelope,
            )
            payload = execute(prepared, output, runner)
        _atomic(output / "terminal.json", payload)
        return 0
    except Interrupted as exc:
        if runner is not None:
            runner.terminate_active_processes(reason=exc.code)
        _atomic(
            output / "terminal.json",
            {
                "label": prepared.label,
                "status": "interrupted",
                "terminal_type": exc.code,
                "counters": runner.counters() if runner is not None else {},
            },
        )
        return 130
    except BaseException as exc:  # noqa: BLE001 - always write one typed terminal
        if runner is not None:
            runner.terminate_active_processes(reason="terminal")
        code = (
            exc.code if isinstance(exc, ScientificTerminal) else "UNHANDLED_EXCEPTION"
        )
        _atomic(
            output / "terminal.json",
            {
                "label": prepared.label,
                "status": "failed",
                "terminal_type": code,
                "message": str(exc),
                "counters": runner.counters() if runner is not None else {},
            },
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
