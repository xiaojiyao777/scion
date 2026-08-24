"""Generic, fail-closed reader for a completed qualification campaign.

The auditor has no Provider, solver, or LineageRegistry dependency.  Its
problem-specific facts live only in a strict expectation JSON supplied at
invocation time.  SQLite is opened read-only and source blobs are compared as
opaque bytes only.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import stat
import subprocess
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote

from scion.config.problem import ProblemSpec
from scion.core.execution_outcome import ExecutionOutcome
from scion.core.models import Decision
from scion.core.path_match import segment_glob_match
from scion.core.paths import normalize_relative_patch_path
from scion.core.research_history import (
    normalize_research_history_record,
    problem_id_from_spec,
)
from scion.core.research_surface_index import editable_patterns
from scion.postrun.handoff.candidate_carrier import (
    CandidateCarrier,
    select_candidate_carrier,
)
from scion.runtime.workspace import WorkspaceMaterializer

QUALIFIED_TOKEN = "QUALIFIED_FOR_NEW_FIXED_CANDIDATE_FUNNEL"
UNAVAILABLE_TOKEN = "QUALIFICATION_CARRIER_UNAVAILABLE"
_EXPECTATION_SCHEMA = "scion.qualification_audit_expectation.v1"
_LIMIT_KEYS = frozenset(
    {
        "max_proposal_attempts",
        "max_verified_candidate_chains",
        "max_formal_screening_stages",
    }
)


class QualificationAuditUnavailable(ValueError):
    """The public artifacts cannot establish the expected candidate carrier."""


@dataclass(frozen=True)
class ScreeningExpectation:
    case_ids: tuple[str, ...]
    seed_set: tuple[int, ...]
    valid_pairs: int
    gate_outcome: str
    decision: str
    require_contract_verification: bool


@dataclass(frozen=True)
class QualificationAuditExpectation:
    base_revision: str
    source_prefix: str
    source_file_count: int
    hash_spec_path: str
    ignored_directory_names: frozenset[str]
    ignored_suffixes: frozenset[str]
    limits: dict[str, int]
    formal_stage: str
    required_action: str
    stop_reason: str
    ready_disposition: str
    protocol_stages: frozenset[str]
    forbidden_stages: frozenset[str]
    zero_metrics: frozenset[str]
    screening: tuple[ScreeningExpectation, ...]


@dataclass(frozen=True)
class _WorkspacePolicy:
    compute_hash: Callable[[Path], str]
    path_is_editable: Callable[[str], bool]
    problem_id: str


def load_qualification_audit_expectation(
    path: str | Path,
) -> QualificationAuditExpectation:
    """Load a duplicate-key-free, exact-schema audit expectation."""

    try:
        value = _read_json_object(Path(path))
        _require(
            set(value)
            == {
                "schema_version",
                "base_revision",
                "source",
                "qualification",
                "screening",
            }
        )
        _require(value["schema_version"] == _EXPECTATION_SCHEMA)
        source = _mapping(value["source"])
        _require(
            set(source)
            == {
                "prefix",
                "file_count",
                "hash_spec_path",
                "ignored_directory_names",
                "ignored_suffixes",
            }
        )
        qualification = _mapping(value["qualification"])
        _require(
            set(qualification)
            == {
                "limits",
                "formal_stage",
                "required_action",
                "stop_reason",
                "ready_disposition",
                "protocol_stages",
                "forbidden_stages",
                "zero_metrics",
            }
        )
        limits = dict(_mapping(qualification["limits"]))
        _require(set(limits) == _LIMIT_KEYS)
        _require(all(type(item) is int and item > 0 for item in limits.values()))
        base_revision = value["base_revision"]
        source_prefix = source["prefix"]
        _require(
            isinstance(base_revision, str)
            and re.fullmatch(r"[0-9a-f]{40}", base_revision) is not None
        )
        _require(
            isinstance(source_prefix, str)
            and bool(source_prefix)
            and "\\" not in source_prefix
        )
        prefix = PurePosixPath(source_prefix)
        _require(
            prefix.as_posix() == source_prefix
            and not prefix.is_absolute()
            and all(part not in {"", ".", ".."} for part in prefix.parts)
        )
        _require(type(source["file_count"]) is int and source["file_count"] > 0)
        hash_spec_path = _relative_path(source["hash_spec_path"])
        ignored_directories = _unique_string_set(source["ignored_directory_names"])
        ignored_suffixes = _unique_string_set(source["ignored_suffixes"])
        _require(
            all("/" not in item and "\\" not in item for item in ignored_directories)
        )
        _require(
            all(item.startswith(".") and "/" not in item for item in ignored_suffixes)
        )
        forbidden_stages = _unique_string_set(qualification["forbidden_stages"])
        protocol_stages = _unique_string_set(qualification["protocol_stages"])
        zero_metrics = _unique_string_set(qualification["zero_metrics"])
        formal_stage = _string(qualification["formal_stage"])
        _require(
            bool(protocol_stages) and bool(forbidden_stages) and bool(zero_metrics)
        )
        _require(formal_stage in protocol_stages)
        _require(forbidden_stages.issubset(protocol_stages - {formal_stage}))
        screens: list[ScreeningExpectation] = []
        for raw in _sequence(value["screening"]):
            item = _mapping(raw)
            _require(
                set(item)
                == {
                    "case_ids",
                    "seed_set",
                    "valid_pairs",
                    "gate_outcome",
                    "decision",
                    "require_contract_verification",
                }
            )
            cases = tuple(_string(value) for value in _sequence(item["case_ids"]))
            seeds = tuple(item["seed_set"])
            _require(bool(cases) and bool(seeds))
            _require(all(type(seed) is int for seed in seeds))
            _require(len(cases) == len(set(cases)))
            _require(len(seeds) == len(set(seeds)))
            _require(
                type(item["valid_pairs"]) is int
                and item["valid_pairs"] == len(cases) * len(seeds)
            )
            _require(isinstance(item["require_contract_verification"], bool))
            screens.append(
                ScreeningExpectation(
                    case_ids=cases,
                    seed_set=seeds,
                    valid_pairs=item["valid_pairs"],
                    gate_outcome=_string(item["gate_outcome"]),
                    decision=_string(item["decision"]),
                    require_contract_verification=item["require_contract_verification"],
                )
            )
        _require(len(screens) == 2)
        _require(screens[0].require_contract_verification)
        initial, expanded = screens
        _require(set(initial.case_ids) <= set(expanded.case_ids))
        _require(set(initial.seed_set) <= set(expanded.seed_set))
        _require(
            set(initial.case_ids) < set(expanded.case_ids)
            or set(initial.seed_set) < set(expanded.seed_set)
        )
        return QualificationAuditExpectation(
            base_revision=base_revision,
            source_prefix=prefix.as_posix(),
            source_file_count=source["file_count"],
            hash_spec_path=hash_spec_path,
            ignored_directory_names=ignored_directories,
            ignored_suffixes=ignored_suffixes,
            limits=limits,
            formal_stage=formal_stage,
            required_action=_string(qualification["required_action"]),
            stop_reason=_string(qualification["stop_reason"]),
            ready_disposition=_string(qualification["ready_disposition"]),
            protocol_stages=protocol_stages,
            forbidden_stages=forbidden_stages,
            zero_metrics=zero_metrics,
            screening=tuple(screens),
        )
    except Exception as exc:
        raise QualificationAuditUnavailable(UNAVAILABLE_TOKEN) from exc


def audit_qualification_campaign(
    campaign_dir: str | Path,
    *,
    expectation: QualificationAuditExpectation,
    repository: str | Path,
    base_revision: str,
) -> str:
    """Audit one root and return the one fixed token on complete success."""

    try:
        _require(base_revision == expectation.base_revision)
        root = _regular_directory(Path(campaign_dir))
        repo = _regular_directory(Path(repository))
        status = _read_json_object(root / "status.json")
        summary = _read_json_object(root / "campaign_summary.json")
        _audit_terminal_boundary(
            status=status,
            summary=summary,
            expectation=expectation,
        )
        history = _read_json_lines(root / "research_history.jsonl")
        lineage = _read_lineage_events(root / "scion.db")
        _require_canonical_commit(repository=repo, base_revision=base_revision)
        with tempfile.TemporaryDirectory(
            prefix="scion_qualification_audit_"
        ) as scratch_text:
            baseline = Path(scratch_text) / "baseline"
            _materialize_tracked_source(
                repository=repo,
                base_revision=base_revision,
                source_prefix=expectation.source_prefix,
                source_file_count=expectation.source_file_count,
                destination=baseline,
            )
            _make_tree_readonly(baseline)
            return _audit_qualification_artifacts(
                status=status,
                summary=summary,
                history=history,
                lineage_events=lineage,
                candidate_workspaces=root / "candidate_workspaces",
                baseline=baseline,
                expectation=expectation,
            )
    except QualificationAuditUnavailable:
        raise
    except Exception as exc:
        raise QualificationAuditUnavailable(UNAVAILABLE_TOKEN) from exc


def _audit_terminal_boundary(
    *,
    status: Mapping[str, Any],
    summary: Mapping[str, Any],
    expectation: QualificationAuditExpectation,
) -> None:
    """Reject a nonterminal or corrupt root before any tracked blob is read."""

    _require(isinstance(status, Mapping) and isinstance(summary, Mapping))
    run = _mapping(status.get("run_result"))
    _require(summary.get("run_result") == run)
    _require(run.get("status") == "completed")
    _require(run.get("stop_reason") == expectation.stop_reason)
    _require(
        run.get("run_validity") == {"valid": True, "status": "valid", "reason": "valid"}
    )
    qualification = _mapping(run.get("qualification"))
    _require(qualification.get("mode") == "qualification_only")
    _require(qualification.get("limits") == expectation.limits)
    _require(qualification.get("disposition") == expectation.ready_disposition)
    _require(
        _bounded_int(
            qualification.get("proposal_attempts"),
            1,
            expectation.limits["max_proposal_attempts"],
        )
    )
    _require(
        _bounded_int(
            qualification.get("verified_candidate_chains"),
            1,
            expectation.limits["max_verified_candidate_chains"],
        )
    )
    _require(
        _bounded_int(
            qualification.get("formal_screening_stages"),
            len(expectation.screening),
            expectation.limits["max_formal_screening_stages"],
        )
    )
    _require(
        qualification.get("formal_screening_stages")
        == qualification.get("initial_screening_stages", 0)
        + qualification.get("expanded_screening_stages", 0)
    )
    _require(
        _bounded_int(
            qualification.get("initial_screening_stages"),
            1,
            expectation.limits["max_formal_screening_stages"],
        )
    )
    _require(
        _bounded_int(
            qualification.get("expanded_screening_stages"),
            1,
            expectation.limits["max_formal_screening_stages"],
        )
    )
    counts = _mapping(run.get("protocol_stage_counts"))
    _require(set(counts) == expectation.protocol_stages)
    _require(all(type(value) is int and value >= 0 for value in counts.values()))
    _require(
        counts.get(expectation.formal_stage)
        == qualification.get("formal_screening_stages")
    )
    _require(
        all(
            counts.get(stage) == 0
            for stage in expectation.protocol_stages
            if stage != expectation.formal_stage
        )
    )
    _require(run.get("unknown_outcome_count") == 0)
    _require(summary.get("branches") == status.get("branches"))
    branches = _mapping_sequence(status.get("branches"))
    ready_branches = tuple(
        branch for branch in branches if branch.get("state") == "ready_validate"
    )
    _require(len(ready_branches) == 1)
    ready_branch_id = _string(ready_branches[0].get("id"))
    steps = _mapping_sequence(summary.get("steps"))
    n_steps = status.get("n_steps")
    _require(type(n_steps) is int and n_steps == summary.get("n_steps") == len(steps))
    _require(status.get("total_rounds") == summary.get("total_rounds") == n_steps)
    _require(run.get("scheduled_calls") == len(steps))
    for ordinal, step in enumerate(steps, 1):
        _require(type(step.get("round")) is int and step.get("round") == ordinal)
    _require(
        run.get("evaluated_rounds") == qualification.get("formal_screening_stages")
    )
    _require(
        run.get("formal_screened_candidates")
        == qualification.get("formal_screening_stages")
    )
    known_outcomes = tuple(outcome.value for outcome in ExecutionOutcome)
    observed_outcomes = {name: 0 for name in known_outcomes}
    for step in steps:
        outcome = _mapping(step.get("execution_outcome"))
        outcome_name = outcome.get("outcome")
        _require(outcome_name in observed_outcomes)
        observed_outcomes[str(outcome_name)] += 1
    _require(run.get("execution_outcome_counts") == observed_outcomes)
    last_outcome = _mapping(steps[-1].get("execution_outcome"))
    expected_last = {
        "outcome": _string(last_outcome.get("outcome")),
        "reason_code": _string(last_outcome.get("reason_code")),
    }
    last_stage = _mapping(last_outcome.get("provenance")).get("stage")
    if isinstance(last_stage, str) and last_stage.strip():
        expected_last["stage"] = last_stage.strip()
    _require(run.get("last_execution_outcome") == expected_last)
    last_result = _mapping(status.get("last_result"))
    _require(
        set(last_result)
        == {
            "action",
            "branch_id",
            "decision",
            "stopped",
            "reason",
            "execution_outcome",
        }
    )
    _require(bool(_string(last_result.get("action"))))
    _require(last_result.get("branch_id") == ready_branch_id)
    _require(isinstance(last_result.get("decision"), str))
    _require(type(last_result.get("stopped")) is bool)
    _require(isinstance(last_result.get("reason"), str))
    _require(last_result.get("execution_outcome") == expected_last)
    _audit_qualification_counters(
        steps=steps,
        qualification=qualification,
        formal_stage=expectation.formal_stage,
        screening=expectation.screening,
        records=None,
        lineage_events=None,
    )


def _audit_qualification_artifacts(
    *,
    status: Mapping[str, Any],
    summary: Mapping[str, Any],
    history: Sequence[Mapping[str, Any]],
    lineage_events: Sequence[Mapping[str, Any]],
    candidate_workspaces: str | Path,
    baseline: str | Path,
    expectation: QualificationAuditExpectation,
) -> str:
    """Audit artifacts using authority derived only from the trusted baseline."""

    try:
        _audit_terminal_boundary(
            status=status,
            summary=summary,
            expectation=expectation,
        )
        _require(isinstance(status, Mapping) and isinstance(summary, Mapping))
        baseline_path = Path(baseline)
        baseline_source = _source_tree_bytes(
            root=baseline_path,
            ignored_directory_names=expectation.ignored_directory_names,
            ignored_suffixes=expectation.ignored_suffixes,
        )
        _require(len(baseline_source) == expectation.source_file_count)
        with tempfile.TemporaryDirectory(
            prefix="scion_qualification_policy_"
        ) as scratch_text:
            policy = _production_workspace_policy(
                baseline=baseline_path,
                scratch=Path(scratch_text),
                expectation=expectation,
            )
            normalized_history = _normalize_history_sequence(
                history,
                expected_problem_id=policy.problem_id,
            )
            carrier = select_candidate_carrier(
                status=status,
                summary=summary,
                history=normalized_history,
                lineage_events=lineage_events,
                candidate_workspaces=Path(candidate_workspaces),
                compute_workspace_hash=policy.compute_hash,
            )
            _audit_ready_candidate(
                carrier=carrier,
                status=status,
                summary=summary,
                history=normalized_history,
                lineage_events=lineage_events,
                baseline=baseline_path,
                expectation=expectation,
                compute_workspace_hash=policy.compute_hash,
                path_is_editable=policy.path_is_editable,
            )
            return QUALIFIED_TOKEN
    except Exception as exc:
        raise QualificationAuditUnavailable(UNAVAILABLE_TOKEN) from exc


def _audit_ready_candidate(
    *,
    carrier: CandidateCarrier,
    status: Mapping[str, Any],
    summary: Mapping[str, Any],
    history: Sequence[Mapping[str, Any]],
    lineage_events: Sequence[Mapping[str, Any]],
    baseline: Path,
    expectation: QualificationAuditExpectation,
    compute_workspace_hash: Callable[[Path], str],
    path_is_editable: Callable[[str], bool],
) -> None:
    _require(summary.get("branches") == status.get("branches"))
    steps = _mapping_sequence(summary.get("steps"))
    records = _mapping_sequence(history)
    _require(len(steps) == len(records))
    run = _mapping(status.get("run_result"))
    formal_count = run["qualification"]["formal_screening_stages"]
    _audit_qualification_counters(
        steps=steps,
        qualification=_mapping(run["qualification"]),
        formal_stage=expectation.formal_stage,
        screening=expectation.screening,
        records=records,
        lineage_events=lineage_events,
    )
    _require(_count_stage_in_steps(steps, expectation.formal_stage) == formal_count)
    _require(_count_stage_in_history(records, expectation.formal_stage) == formal_count)
    _require(
        _count_stage_in_events(lineage_events, expectation.formal_stage) == formal_count
    )
    _require(
        _only_formal_protocol_stage(
            steps,
            records,
            lineage_events,
            formal_stage=expectation.formal_stage,
        )
    )
    _require(
        _all_formal_canaries_passed(steps, lineage_events, expectation.formal_stage)
    )
    _require(len(carrier.screening_indices) == len(expectation.screening))
    _require(carrier.screening_indices[-1] == len(steps) - 1)
    ready_steps = tuple(steps[index] for index in carrier.screening_indices)
    ready_records = tuple(records[index] for index in carrier.screening_indices)
    last_result = _mapping(status.get("last_result"))
    _require(last_result.get("branch_id") == carrier.branch_id)
    _require(last_result.get("decision") == expectation.screening[-1].decision)
    _require(ready_steps[-1].get("branch_id") == carrier.branch_id)
    _require(ready_steps[-1].get("decision") == expectation.screening[-1].decision)
    _require(
        _mapping(ready_records[-1].get("decision")).get("value")
        == expectation.screening[-1].decision
    )
    hypotheses = tuple(_mapping(record.get("hypothesis")) for record in ready_records)
    patches = tuple(_mapping(record.get("patch")) for record in ready_records)
    _require(
        all(dict(hypothesis) == dict(hypotheses[0]) for hypothesis in hypotheses[1:])
    )
    _require(all(dict(patch) == dict(patches[0]) for patch in patches[1:]))
    _require(hypotheses[0].get("action") == expectation.required_action)
    _require(isinstance(hypotheses[0].get("change_locus"), str))
    target_file = normalize_relative_patch_path(hypotheses[0].get("target_file"))
    _require(target_file == hypotheses[0].get("target_file"))
    changes = _mapping_sequence(patches[0].get("changes"))
    _require(bool(changes))
    paths: list[str] = []
    for change in changes:
        _require(change.get("action") == expectation.required_action)
        _require(isinstance(change.get("source"), str))
        normalized_path = normalize_relative_patch_path(change.get("file_path"))
        _require(normalized_path == change.get("file_path"))
        _require(path_is_editable(normalized_path))
        paths.append(normalized_path)
    _require(len(paths) == len(set(paths)))
    _require(
        any(
            path == target_file and change.get("action") == hypotheses[0].get("action")
            for path, change in zip(paths, changes, strict=True)
        )
    )
    for ordinal, (step, record, required) in enumerate(
        zip(ready_steps, ready_records, expectation.screening, strict=True)
    ):
        summary_outcome = _mapping(step.get("execution_outcome"))
        history_outcome = _mapping(record.get("outcome"))
        _require(
            summary_outcome
            == {
                "outcome": "evaluated",
                "reason_code": "EVALUATION_COMPLETED",
                "detail": "",
                "provenance": {"stage": expectation.formal_stage},
            }
        )
        _require(
            history_outcome
            == {
                "outcome": "evaluated",
                "stage": expectation.formal_stage,
                "reason_code": "EVALUATION_COMPLETED",
            }
        )
        _require(summary_outcome["outcome"] == history_outcome["outcome"])
        _require(summary_outcome["reason_code"] == history_outcome["reason_code"])
        _require(
            _mapping(summary_outcome["provenance"]).get("stage")
            == history_outcome["stage"]
        )
        protocol = _mapping(step.get("protocol_result"))
        _require(protocol.get("stage") == expectation.formal_stage)
        _require(protocol.get("case_ids") == list(required.case_ids))
        _require(protocol.get("seed_set") == list(required.seed_set))
        _require(
            all(
                protocol.get(field) == required.valid_pairs
                for field in ("total_pairs", "attempted_pairs", "valid_pairs")
            )
        )
        _require(
            all(
                protocol.get(field) == 0
                for field in (
                    "failed_pairs",
                    "candidate_failed_pairs",
                    "champion_failed_pairs",
                    "shared_failed_pairs",
                    "bilateral_failed_pairs",
                )
            )
        )
        _require(_zero_metrics(protocol, expectation.zero_metrics))
        _require(protocol.get("gate_outcome") == required.gate_outcome)
        _require(step.get("decision") == required.decision)
        _require(_mapping(record.get("decision")).get("value") == required.decision)
        evidence = _mapping(_mapping(record.get("protocol")).get("evidence"))
        _require(
            _mapping(evidence.get("protocol_outcome")).get("gate_outcome")
            == required.gate_outcome
        )
        _require(protocol.get("selected_surface") == hypotheses[0].get("change_locus"))
        _require(_mapping(step.get("canary_result")).get("passed") is True)
        if required.require_contract_verification:
            _require(step.get("contract_passed") is True)
            _require(step.get("verification_passed") is True)
        else:
            _require(step.get("contract_passed") is None)
            _require(step.get("verification_passed") is None)
    ready_events = [
        _mapping(event)
        for event in lineage_events
        if _mapping(event).get("event_kind") == "experiment"
        and _mapping(event).get("stage") == expectation.formal_stage
        and _mapping(event).get("branch_id") == carrier.branch_id
    ]
    _require(len(ready_events) == len(expectation.screening))
    for event, required in zip(ready_events, expectation.screening, strict=True):
        _require(event.get("code_hash") == carrier.code_hash)
        _require(event.get("hypothesis_text") == hypotheses[0].get("text"))
        _require(event.get("patch_action") == changes[0].get("action"))
        _require(event.get("patch_file") == changes[0].get("file_path"))
        _require(event.get("canary_result") == "passed")
        _require(event.get("decision") == required.decision)
        if required.require_contract_verification:
            _require(event.get("contract_result") == "passed")
            _require(event.get("verification_result") == "passed")
        else:
            _require(event.get("contract_result") == "not_run")
            _require(event.get("verification_result") == "not_run")
    base_source = _source_tree_bytes(
        root=baseline,
        ignored_directory_names=expectation.ignored_directory_names,
        ignored_suffixes=expectation.ignored_suffixes,
    )
    candidate_source = _source_tree_bytes(
        root=carrier.candidate_workspace,
        ignored_directory_names=expectation.ignored_directory_names,
        ignored_suffixes=expectation.ignored_suffixes,
    )
    _require(len(base_source) == expectation.source_file_count)
    rebuilt = dict(base_source)
    for path, change in zip(paths, changes, strict=True):
        _require(path in rebuilt)
        rebuilt[path] = str(change["source"]).encode("utf-8")
    _require(set(base_source) == set(rebuilt) == set(candidate_source))
    _require(rebuilt == candidate_source)
    changed = sorted(
        path for path in base_source if base_source[path] != candidate_source[path]
    )
    _require(bool(changed) and changed == sorted(paths))
    _require(compute_workspace_hash(carrier.candidate_workspace) == carrier.code_hash)


def _audit_qualification_counters(
    *,
    steps: Sequence[Mapping[str, Any]],
    qualification: Mapping[str, Any],
    formal_stage: str,
    screening: Sequence[ScreeningExpectation],
    records: Sequence[Mapping[str, Any]] | None,
    lineage_events: Sequence[Mapping[str, Any]] | None,
) -> None:
    _require(len(screening) == 2)
    initial_screening, expanded_screening = screening
    verified_branches = tuple(
        _string(step.get("branch_id"))
        for step in steps
        if step.get("verification_passed") is True
    )
    _require(len(verified_branches) == len(set(verified_branches)))
    _require(qualification.get("verified_candidate_chains") == len(verified_branches))
    formal_rows = tuple(
        (index, step)
        for index, step in enumerate(steps)
        if step.get("protocol_result") is not None
        and _mapping(step["protocol_result"]).get("stage") == formal_stage
    )
    formal_branches = tuple(_string(step.get("branch_id")) for _, step in formal_rows)
    formal_shapes = tuple(
        (step.get("contract_passed"), step.get("verification_passed"))
        for _, step in formal_rows
    )
    _require(all(shape in {(True, True), (None, None)} for shape in formal_shapes))
    for (_index, step), shape in zip(formal_rows, formal_shapes, strict=True):
        _audit_formal_screening_population(
            step=step,
            required=(
                initial_screening if shape == (True, True) else expanded_screening
            ),
            formal_stage=formal_stage,
        )
    _require(
        qualification.get("initial_screening_stages")
        == sum(shape == (True, True) for shape in formal_shapes)
    )
    _require(
        qualification.get("expanded_screening_stages")
        == sum(shape == (None, None) for shape in formal_shapes)
    )
    _require(qualification.get("formal_screening_stages") == len(formal_rows))
    formal_by_branch: dict[str, list[tuple[int, tuple[Any, Any], str | None]]] = {}
    for (index, step), branch_id, shape in zip(
        formal_rows, formal_branches, formal_shapes, strict=True
    ):
        decision = step.get("decision")
        _require(decision is None or isinstance(decision, str))
        formal_by_branch.setdefault(branch_id, []).append((index, shape, decision))
    expansion_dispatch_indices: set[int] = set()
    for branch_id, rows in formal_by_branch.items():
        shapes = tuple(row[1] for row in rows)
        _require(shapes in {((True, True),), ((True, True), (None, None))})
        initial_index, _initial_shape, initial_decision = rows[0]
        branch_indices = tuple(
            index
            for index, step in enumerate(steps)
            if step.get("branch_id") == branch_id
        )
        post_initial_indices = tuple(
            index for index in branch_indices if index >= initial_index
        )
        if initial_decision == initial_screening.decision:
            dispatch = tuple(
                index
                for index in branch_indices
                if index > initial_index
                and (
                    steps[index].get("contract_passed"),
                    steps[index].get("verification_passed"),
                )
                == (None, None)
            )
            _require(len(dispatch) == 1)
            _require(dispatch[0] == initial_index + 1)
            _require(post_initial_indices == (initial_index, dispatch[0]))
            _audit_expansion_dispatch_summary(
                initial=steps[initial_index],
                dispatch=steps[dispatch[0]],
                formal_stage=formal_stage,
            )
            expansion_dispatch_indices.add(dispatch[0])
        else:
            _require(post_initial_indices == (initial_index,))
            _require(len(rows) == 1)
    _require(
        qualification.get("proposal_attempts")
        == len(steps) - len(expansion_dispatch_indices)
    )
    if lineage_events is None:
        return
    if records is None:
        raise QualificationAuditUnavailable(UNAVAILABLE_TOKEN)
    _require(len(records) == len(steps))
    decision_indices = tuple(
        index for index, step in enumerate(steps) if step.get("decision") is not None
    )
    experiment_events = tuple(
        event for event in lineage_events if event.get("event_kind") == "experiment"
    )
    _require(len(experiment_events) == len(decision_indices))
    event_by_step = dict(zip(decision_indices, experiment_events, strict=True))
    for index, event in event_by_step.items():
        _require(event.get("branch_id") == steps[index].get("branch_id"))
        _require(event.get("decision") == steps[index].get("decision"))
    for (index, step), shape in zip(formal_rows, formal_shapes, strict=True):
        _audit_formal_artifact_row(
            step=step,
            shape=shape,
            record=records[index],
            event=_mapping(event_by_step.get(index)),
            formal_stage=formal_stage,
        )
    for branch_id, rows in formal_by_branch.items():
        initial_index, _shape, initial_decision = rows[0]
        if initial_decision != initial_screening.decision:
            continue
        dispatch_index = initial_index + 1
        _audit_expansion_dispatch_artifacts(
            initial_index=initial_index,
            dispatch_index=dispatch_index,
            steps=steps,
            records=records,
            event_by_step=event_by_step,
            formal_stage=formal_stage,
        )
    lineage_verified = tuple(
        _string(event.get("branch_id"))
        for event in lineage_events
        if event.get("event_kind") == "experiment"
        and event.get("verification_result") == "passed"
    )
    _require(len(lineage_verified) == len(set(lineage_verified)))
    _require(set(lineage_verified) == set(verified_branches))
    lineage_formal_branches = tuple(
        _string(event.get("branch_id"))
        for event in lineage_events
        if event.get("event_kind") == "experiment"
        and event.get("stage") == formal_stage
    )
    _require(lineage_formal_branches == formal_branches)


def _audit_formal_screening_population(
    *,
    step: Mapping[str, Any],
    required: ScreeningExpectation,
    formal_stage: str,
) -> None:
    protocol = _mapping(step.get("protocol_result"))
    _require(protocol.get("stage") == formal_stage)
    _require(protocol.get("case_ids") == list(required.case_ids))
    _require(protocol.get("seed_set") == list(required.seed_set))
    total = _nonnegative_int(protocol.get("total_pairs"))
    attempted = _nonnegative_int(protocol.get("attempted_pairs"))
    valid = _nonnegative_int(protocol.get("valid_pairs"))
    failed = _nonnegative_int(protocol.get("failed_pairs"))
    candidate_failed = _nonnegative_int(protocol.get("candidate_failed_pairs"))
    champion_failed = _nonnegative_int(protocol.get("champion_failed_pairs"))
    shared_failed = _nonnegative_int(protocol.get("shared_failed_pairs"))
    bilateral_failed = _nonnegative_int(protocol.get("bilateral_failed_pairs"))
    _require(total == attempted == required.valid_pairs)
    _require(valid + failed == attempted)
    _require(shared_failed <= champion_failed)
    _require(bilateral_failed <= min(candidate_failed, champion_failed))
    _require(shared_failed + bilateral_failed <= failed)
    _require(failed == candidate_failed + champion_failed - bilateral_failed)
    _require(_mapping(step.get("canary_result")).get("passed") is True)
    _require(
        step.get("execution_outcome")
        == {
            "outcome": "evaluated",
            "reason_code": "EVALUATION_COMPLETED",
            "detail": "",
            "provenance": {"stage": formal_stage},
        }
    )


def _audit_expansion_dispatch_summary(
    *,
    initial: Mapping[str, Any],
    dispatch: Mapping[str, Any],
    formal_stage: str,
) -> None:
    initial_hypothesis = _mapping(initial.get("hypothesis"))
    _require(bool(initial_hypothesis))
    _require(dispatch.get("hypothesis") == initial_hypothesis)
    if dispatch.get("protocol_result") is not None:
        _require(_mapping(dispatch["protocol_result"]).get("stage") == formal_stage)
        return
    _require(dispatch.get("contract_passed") is None)
    _require(dispatch.get("verification_passed") is None)
    _require(dispatch.get("failure_stage") == "canary")
    _require(dispatch.get("decision") == Decision.ABANDON.value)
    canary = _mapping(dispatch.get("canary_result"))
    _require(canary.get("passed") is False)
    _require(canary.get("failure_category") == "candidate_failure")
    _require(
        dispatch.get("execution_outcome")
        == {
            "outcome": "evaluated",
            "reason_code": "EVALUATION_COMPLETED",
            "detail": "",
            "provenance": {"stage": formal_stage},
        }
    )


def _audit_formal_artifact_row(
    *,
    step: Mapping[str, Any],
    shape: tuple[Any, Any],
    record: Mapping[str, Any],
    event: Mapping[str, Any],
    formal_stage: str,
) -> None:
    _require(
        _mapping(record.get("outcome"))
        == {
            "outcome": "evaluated",
            "stage": formal_stage,
            "reason_code": "EVALUATION_COMPLETED",
        }
    )
    _require(
        _mapping(_mapping(record.get("protocol")).get("evidence")).get("stage")
        == formal_stage
    )
    _require(_mapping(record.get("decision")).get("value") == step.get("decision"))
    _require(event.get("stage") == formal_stage)
    _require(event.get("canary_result") == "passed")
    if shape == (True, True):
        _require(event.get("contract_result") == "passed")
        _require(event.get("verification_result") == "passed")
    else:
        _require(shape == (None, None))
        _require(event.get("contract_result") == "not_run")
        _require(event.get("verification_result") == "not_run")


def _audit_expansion_dispatch_artifacts(
    *,
    initial_index: int,
    dispatch_index: int,
    steps: Sequence[Mapping[str, Any]],
    records: Sequence[Mapping[str, Any]],
    event_by_step: Mapping[int, Mapping[str, Any]],
    formal_stage: str,
) -> None:
    initial_record = _mapping(records[initial_index])
    dispatch_record = _mapping(records[dispatch_index])
    _require(dispatch_record.get("hypothesis") == initial_record.get("hypothesis"))
    _require(dispatch_record.get("patch") == initial_record.get("patch"))
    initial_event = _mapping(event_by_step.get(initial_index))
    dispatch_event = _mapping(event_by_step.get(dispatch_index))
    for field in (
        "branch_id",
        "code_hash",
        "patch_action",
        "patch_file",
        "hypothesis_text",
    ):
        _require(dispatch_event.get(field) == initial_event.get(field))
    if steps[dispatch_index].get("protocol_result") is not None:
        _require(
            _mapping(dispatch_record.get("outcome"))
            == {
                "outcome": "evaluated",
                "stage": formal_stage,
                "reason_code": "EVALUATION_COMPLETED",
            }
        )
        _require(dispatch_record.get("protocol") is not None)
        _require(dispatch_event.get("stage") == formal_stage)
        _require(dispatch_event.get("contract_result") == "not_run")
        _require(dispatch_event.get("verification_result") == "not_run")
        _require(dispatch_event.get("canary_result") == "passed")
        return
    _require(
        _mapping(dispatch_record.get("outcome"))
        == {
            "outcome": "evaluated",
            "stage": "canary",
            "reason_code": "EVALUATION_COMPLETED",
        }
    )
    _require(dispatch_record.get("protocol") is None)
    _require(
        _mapping(dispatch_record.get("decision")).get("value") == Decision.ABANDON.value
    )
    _require(dispatch_event.get("stage") == "")
    _require(dispatch_event.get("contract_result") == "not_run")
    _require(dispatch_event.get("verification_result") == "not_run")
    _require(dispatch_event.get("canary_result") == "failed")
    _require(dispatch_event.get("decision") == Decision.ABANDON.value)


def _read_json_object(path: Path) -> dict[str, Any]:
    _regular_file(path)
    return dict(
        _mapping(
            json.loads(
                path.read_text(encoding="utf-8"), object_pairs_hook=_no_duplicate_pairs
            )
        )
    )


def _read_json_lines(path: Path) -> tuple[dict[str, Any], ...]:
    _regular_file(path)
    values: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        _require(bool(line.strip()))
        values.append(
            dict(_mapping(json.loads(line, object_pairs_hook=_no_duplicate_pairs)))
        )
    return tuple(values)


def _normalize_history_sequence(
    history: Sequence[Mapping[str, Any]], *, expected_problem_id: str
) -> tuple[dict[str, Any], ...]:
    records = _mapping_sequence(history)
    normalized = tuple(
        normalize_research_history_record(
            record,
            expected_problem_id=expected_problem_id,
        )
        for record in records
    )
    _require(
        all(
            dict(record) == value
            for record, value in zip(records, normalized, strict=True)
        )
    )
    return normalized


def _no_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, child in pairs:
        if key in value:
            raise QualificationAuditUnavailable(UNAVAILABLE_TOKEN)
        value[key] = child
    return value


def _read_lineage_events(path: Path) -> tuple[dict[str, Any], ...]:
    suffixes = ("", "-wal", "-shm")
    snapshots: dict[str, tuple[bytes, tuple[int, ...]]] = {}
    absent: set[str] = set()
    for suffix in suffixes:
        source = Path(str(path) + suffix)
        try:
            snapshots[suffix] = _stable_regular_file_snapshot(source)
        except FileNotFoundError:
            _require(bool(suffix))
            absent.add(suffix)
    for suffix, (_payload, fingerprint) in snapshots.items():
        _require(_file_fingerprint(Path(str(path) + suffix)) == fingerprint)
    for suffix in absent:
        try:
            Path(str(path) + suffix).lstat()
        except FileNotFoundError:
            continue
        raise QualificationAuditUnavailable(UNAVAILABLE_TOKEN)
    query = (
        "SELECT event_kind, branch_id, code_hash, patch_action, patch_file, "
        "hypothesis_text, contract_result, verification_result, canary_result, "
        "stage, decision FROM experiment_events ORDER BY rowid ASC"
    )
    with tempfile.TemporaryDirectory(prefix="scion_qualification_lineage_") as temp:
        copied = Path(temp) / path.name
        for suffix, (payload, _fingerprint) in snapshots.items():
            Path(str(copied) + suffix).write_bytes(payload)
        uri = "file:" + quote(str(copied), safe="/") + "?mode=ro"
        with sqlite3.connect(uri, uri=True) as connection:
            connection.row_factory = sqlite3.Row
            return tuple(dict(row) for row in connection.execute(query))


def _stable_regular_file_snapshot(path: Path) -> tuple[bytes, tuple[int, ...]]:
    before = _file_fingerprint(path)
    with path.open("rb") as source:
        opened = os.fstat(source.fileno())
        _require(stat.S_ISREG(opened.st_mode) and not stat.S_ISLNK(opened.st_mode))
        _require((opened.st_dev, opened.st_ino) == before[:2])
        payload = source.read()
        after_read = os.fstat(source.fileno())
    _require(_stat_fingerprint(after_read) == before)
    _require(_file_fingerprint(path) == before)
    return payload, before


def _file_fingerprint(path: Path) -> tuple[int, ...]:
    return _stat_fingerprint(path.lstat())


def _stat_fingerprint(value: os.stat_result) -> tuple[int, ...]:
    _require(stat.S_ISREG(value.st_mode) and not stat.S_ISLNK(value.st_mode))
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _materialize_tracked_source(
    *,
    repository: Path,
    base_revision: str,
    source_prefix: str,
    source_file_count: int,
    destination: Path,
) -> None:
    """Materialize an exact tracked source prefix after validating every name.

    This postrun-only operation treats every regular blob as opaque bytes.  It
    never parses, prints, or sends a blob to a Provider; it never addresses any
    path outside the expectation's exact tracked source prefix.
    """

    raw = subprocess.check_output(
        ["git", "ls-tree", "-r", "-z", base_revision, "--", source_prefix],
        cwd=repository,
        stderr=subprocess.DEVNULL,
        env=_git_environment(),
    )
    entries = [_parse_tree_record(record) for record in raw.split(b"\0") if record]
    _require(len(entries) == source_file_count)
    prefix = source_prefix.rstrip("/") + "/"
    seen_paths: set[str] = set()
    for mode, kind, object_id, path in entries:
        _require(mode in {"100644", "100755"} and kind == "blob")
        _require(re.fullmatch(r"[0-9a-f]{40}", object_id) is not None)
        _require("\\" not in path and path.startswith(prefix))
        _require(PurePosixPath(path).as_posix() == path)
        relative_text = _relative_path(path.removeprefix(prefix))
        _require(path not in seen_paths)
        seen_paths.add(path)
        _require(PurePosixPath(relative_text).as_posix() == relative_text)
    destination.mkdir(parents=True, exist_ok=False)
    for _mode, _kind, object_id, path in entries:
        relative_path = PurePosixPath(_relative_path(path.removeprefix(prefix)))
        target = destination.joinpath(*relative_path.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(
            subprocess.check_output(
                ["git", "cat-file", "blob", object_id],
                cwd=repository,
                stderr=subprocess.DEVNULL,
                env=_git_environment(),
            )
        )


def _parse_tree_record(record: bytes) -> tuple[str, str, str, str]:
    try:
        metadata, raw_path = record.split(b"\t", 1)
        mode, kind, object_id = metadata.split(b" ", 2)
        return (
            mode.decode("ascii"),
            kind.decode("ascii"),
            object_id.decode("ascii"),
            raw_path.decode("utf-8"),
        )
    except (UnicodeDecodeError, ValueError) as exc:
        raise QualificationAuditUnavailable(UNAVAILABLE_TOKEN) from exc


def _require_canonical_commit(*, repository: Path, base_revision: str) -> None:
    resolved = subprocess.check_output(
        ["git", "rev-parse", "--verify", f"{base_revision}^{{commit}}"],
        cwd=repository,
        stderr=subprocess.DEVNULL,
        env=_git_environment(),
        text=True,
    ).strip()
    _require(resolved == base_revision)


def _git_environment() -> dict[str, str]:
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }
    environment["GIT_NO_REPLACE_OBJECTS"] = "1"
    return environment


def _production_workspace_policy(
    *, baseline: Path, scratch: Path, expectation: QualificationAuditExpectation
) -> _WorkspacePolicy:
    spec = ProblemSpec.from_yaml(str(baseline / expectation.hash_spec_path))
    editable = editable_patterns(spec)
    frozen = frozenset(str(pattern) for pattern in spec.search_space.frozen)
    _require(bool(editable))
    materializer = WorkspaceMaterializer(
        str(scratch),
        frozen_patterns=frozen,
        editable_patterns=editable,
    )

    def path_is_editable(path: str) -> bool:
        return any(
            segment_glob_match(path, pattern) for pattern in editable
        ) and not any(_matches_frozen(path, pattern) for pattern in frozen)

    def compute_hash(workspace: Path) -> str:
        _source_tree_bytes(
            root=workspace,
            ignored_directory_names=expectation.ignored_directory_names,
            ignored_suffixes=expectation.ignored_suffixes,
        )
        return materializer.compute_code_hash(str(workspace))

    return _WorkspacePolicy(
        compute_hash=compute_hash,
        path_is_editable=path_is_editable,
        problem_id=problem_id_from_spec(spec),
    )


def _matches_frozen(path: str, pattern: str) -> bool:
    return fnmatch(path, pattern) or (
        "/" not in pattern and fnmatch(Path(path).name, pattern)
    )


def _make_tree_readonly(root: Path) -> None:
    entries = sorted(root.rglob("*"), key=lambda path: len(path.parts), reverse=True)
    for path in entries:
        mode = path.lstat().st_mode
        _require(not stat.S_ISLNK(mode))
        _require(stat.S_ISREG(mode) or stat.S_ISDIR(mode))
        path.chmod(0o555 if stat.S_ISDIR(mode) else 0o444)
    root.chmod(0o555)


def _source_tree_bytes(
    *,
    root: Path,
    ignored_directory_names: frozenset[str],
    ignored_suffixes: frozenset[str],
) -> dict[str, bytes]:
    root = _readonly_regular_directory(root)
    values: dict[str, bytes] = {}
    stack = [(root, True)]
    while stack:
        parent, project = stack.pop()
        for path in parent.iterdir():
            mode = path.lstat().st_mode
            _require(not stat.S_ISLNK(mode))
            _require(stat.S_ISDIR(mode) or stat.S_ISREG(mode))
            _require(mode & 0o222 == 0)
            ignored = (
                path.name in ignored_directory_names or path.suffix in ignored_suffixes
            )
            if stat.S_ISDIR(mode):
                stack.append((path, project and not ignored))
                continue
            if not project or ignored:
                continue
            canonical = PurePosixPath(*path.relative_to(root).parts).as_posix()
            _require(canonical not in values)
            values[canonical] = path.read_bytes()
    return values


def _count_stage_in_steps(steps: Sequence[Mapping[str, Any]], stage: str) -> int:
    return sum(
        _mapping(item["protocol_result"]).get("stage") == stage
        for item in steps
        if item.get("protocol_result") is not None
    )


def _count_stage_in_history(records: Sequence[Mapping[str, Any]], stage: str) -> int:
    return sum(
        _mapping(_mapping(item["protocol"]).get("evidence")).get("stage") == stage
        for item in records
        if item.get("protocol") is not None
    )


def _count_stage_in_events(events: Sequence[Mapping[str, Any]], stage: str) -> int:
    return sum(
        item.get("event_kind") == "experiment" and item.get("stage") == stage
        for item in events
    )


def _only_formal_protocol_stage(
    steps: Sequence[Mapping[str, Any]],
    records: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
    *,
    formal_stage: str,
) -> bool:
    summary_stages = (
        _mapping(item["protocol_result"]).get("stage")
        for item in steps
        if item.get("protocol_result") is not None
    )
    history_stages = (
        _mapping(_mapping(item["protocol"]).get("evidence")).get("stage")
        for item in records
        if item.get("protocol") is not None
    )
    lineage_stages = (
        item.get("stage")
        for item in events
        if item.get("event_kind") == "experiment" and item.get("stage") != ""
    )
    return all(
        stage == formal_stage
        for stage in (*summary_stages, *history_stages, *lineage_stages)
    )


def _zero_metrics(
    protocol: Mapping[str, Any], required_metrics: frozenset[str]
) -> bool:
    metrics = tuple(_mapping(item) for item in _sequence(protocol.get("metric_stats")))
    for name in required_metrics:
        matches = tuple(item for item in metrics if item.get("metric_name") == name)
        if len(matches) != 1:
            return False
        if any(
            type(matches[0].get(field)) not in {int, float}
            or isinstance(matches[0].get(field), bool)
            or matches[0].get(field) != 0
            for field in ("median_delta", "ci_low", "ci_high")
        ):
            return False
    return True


def _all_formal_canaries_passed(
    steps: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
    formal_stage: str,
) -> bool:
    formal_steps = (
        item
        for item in steps
        if item.get("protocol_result") is not None
        and _mapping(item["protocol_result"]).get("stage") == formal_stage
    )
    formal_events = (
        item
        for item in events
        if item.get("event_kind") == "experiment" and item.get("stage") == formal_stage
    )
    return all(
        _mapping(item.get("canary_result")).get("passed") is True
        for item in formal_steps
    ) and all(item.get("canary_result") == "passed" for item in formal_events)


def _relative_path(value: Any) -> str:
    _require(isinstance(value, str) and bool(value) and "\\" not in value)
    path = PurePosixPath(value)
    _require(bool(path.parts) and path.as_posix() == value and not path.is_absolute())
    _require(all(part not in {"", ".", ".."} for part in path.parts))
    return path.as_posix()


def _regular_file(path: Path) -> Path:
    mode = path.lstat().st_mode
    _require(stat.S_ISREG(mode) and not stat.S_ISLNK(mode))
    return path


def _regular_directory(path: Path) -> Path:
    mode = path.lstat().st_mode
    _require(stat.S_ISDIR(mode) and not stat.S_ISLNK(mode))
    return path.resolve()


def _readonly_regular_directory(path: Path) -> Path:
    mode = path.lstat().st_mode
    _require(stat.S_ISDIR(mode) and not stat.S_ISLNK(mode) and mode & 0o222 == 0)
    return path.resolve()


def _mapping(value: Any) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping))
    return value


def _mapping_sequence(value: Any) -> tuple[Mapping[str, Any], ...]:
    return tuple(_mapping(item) for item in _sequence(value))


def _sequence(value: Any) -> Sequence[Any]:
    _require(
        isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))
    )
    return value


def _string(value: Any) -> str:
    _require(isinstance(value, str) and bool(value))
    return value


def _unique_string_set(value: Any) -> frozenset[str]:
    items = tuple(_string(item) for item in _sequence(value))
    result = frozenset(items)
    _require(len(result) == len(items))
    return result


def _bounded_int(value: Any, lower: int, upper: int) -> bool:
    return type(value) is int and lower <= value <= upper


def _nonnegative_int(value: Any) -> int:
    _require(type(value) is int and value >= 0)
    return int(value)


def _require(condition: bool) -> None:
    if not condition:
        raise QualificationAuditUnavailable(UNAVAILABLE_TOKEN)


__all__ = [
    "QUALIFIED_TOKEN",
    "UNAVAILABLE_TOKEN",
    "QualificationAuditExpectation",
    "QualificationAuditUnavailable",
    "ScreeningExpectation",
    "audit_qualification_campaign",
    "load_qualification_audit_expectation",
]
