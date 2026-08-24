"""Provider-, solver- and reserved-body-free M30 preregistration replay."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sqlite3
import stat
import subprocess
from copy import deepcopy
from pathlib import Path, PurePosixPath
from typing import Any

import pytest
import yaml

from scion.cli.commands.init_run import (
    _completion_from_run_result,
    _load_research_input,
)
from scion.config.problem import ProtocolConfig, SeedLedgerConfig, SplitManifest
from scion.core.campaign_loop import CampaignRunResult
from scion.core.execution_outcome import ExecutionOutcome
from scion.core.qualification import (
    QUALIFICATION_BOUNDARY_REACHED,
    QUALIFICATION_NOT_REACHED,
    QUALIFICATION_READY_DISPOSITION,
    QualificationOnlyConfig,
    QualificationProgress,
    QualificationRuntime,
)
from scion.core.research_history import (
    load_research_histories,
    provider_research_history,
)
from scion.postrun.handoff import (
    QUALIFIED_TOKEN,
    QualificationAuditUnavailable,
    audit_qualification_campaign,
    load_qualification_audit_expectation,
)
from scion.problems.cvrp.prior_research_observation import (
    CvrpPriorResearchObservationProvider,
)
from scion.proposal.hypothesis_research_corpus import build_hypothesis_research_corpus
from scion.runtime.workspace import WorkspaceMaterializer

_SCION_ROOT = Path(__file__).resolve().parents[4]
_REPOSITORY = _SCION_ROOT.parent
_INPUT_ROOT = _SCION_ROOT / "docs" / "experiments" / "v0.4" / "inputs"
_M28_INPUT = _INPUT_ROOT / "v04-cvrp-m28-m27-terminal-research-input.json"
_M30_INPUT = _INPUT_ROOT / "v04-cvrp-m30-m28-terminal-research-input.json"
_M30_HISTORY_COPY = _INPUT_ROOT / "v04-cvrp-m30-m28-research-history.jsonl"
_M28_PROTOCOL = _INPUT_ROOT / "v04-cvrp-m28-seen-bank-qualification-protocol.yaml"
_M28_SPLIT = _INPUT_ROOT / "v04-cvrp-m28-seen-bank-qualification-split.yaml"
_M28_SEEDS = _INPUT_ROOT / "v04-cvrp-m28-seen-bank-qualification-seeds.yaml"
_M30_PROTOCOL = (
    _INPUT_ROOT / "v04-cvrp-m30-fresh-development-qualification-only-protocol.yaml"
)
_M30_SPLIT = (
    _INPUT_ROOT / "v04-cvrp-m30-fresh-development-qualification-only-split.yaml"
)
_M30_SEEDS = (
    _INPUT_ROOT / "v04-cvrp-m30-fresh-development-qualification-only-seeds.yaml"
)
_M30_QUALIFICATION_EXPECTATION = (
    _INPUT_ROOT
    / "v04-cvrp-m30-fresh-development-qualification-only-qualification-expectation.json"
)
_M30_HISTORY_PATHS = tuple(
    _INPUT_ROOT / filename
    for filename in (
        "v04-cvrp-m10-m9-research-history.jsonl",
        "v04-cvrp-m11-m10-research-history.jsonl",
        "v04-cvrp-m12-m11-research-history.jsonl",
        "v04-cvrp-m13-m12-research-history.jsonl",
        "v04-cvrp-m14-m13-research-history.jsonl",
        "v04-cvrp-m15-m14-research-history.jsonl",
        "v04-cvrp-m16-m15-research-history.jsonl",
        "v04-cvrp-m19-m16-research-history.jsonl",
        "v04-cvrp-m20-m19-research-history.jsonl",
        "v04-cvrp-m21-m20-research-history.jsonl",
        "v04-cvrp-m22-m21-research-history.jsonl",
        "v04-cvrp-m24-m22-research-history.jsonl",
        "v04-cvrp-m26-m25-research-history.jsonl",
        "v04-cvrp-m27-m26-research-history.jsonl",
        "v04-cvrp-m28-m27-research-history.jsonl",
        "v04-cvrp-m30-m28-research-history.jsonl",
    )
)
_FIXTURE_PATH = (
    _SCION_ROOT
    / "scion"
    / "tests"
    / "fixtures"
    / "m30_fresh_development_qualification_only_replay.json"
)
_PREREG_PATH = (
    _SCION_ROOT
    / "docs"
    / "experiments"
    / "v0.4"
    / "v04-cvrp-m30-fresh-development-qualification-only-autonomous-continuation-preregistration-20260824.md"
)
_SOURCE_STEMS = (
    "v04-cvrp-m19-fresh-development",
    "v04-cvrp-m20-frontier-development",
    "v04-cvrp-m22-provider-recovery-development",
)
_OUTCOME_SCREEN_STEMS = (
    "v04-cvrp-m9-development",
    "v04-cvrp-m19-fresh-development",
    "v04-cvrp-m20-frontier-development",
    "v04-cvrp-m22-provider-recovery-development",
)
_FULL_EXCLUSION_STEMS = (
    "v04-cvrp-m21-strict-expansion-development",
    "v04-cvrp-m24-autonomous-direction-research-development",
)
_CVRPLIB_CASE = re.compile(r"^(A|B|P|X)-n([1-9][0-9]*)-k([1-9][0-9]*)\.vrp$")
_SAFE_SEED_SCAN_SUFFIXES = frozenset(
    {".csv", ".json", ".jsonl", ".md", ".py", ".yaml", ".yml"}
)
_RAW_BODY_SUFFIXES = frozenset({".sol", ".vrp"})


def _fixture() -> dict[str, Any]:
    value = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _normalized_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", key.casefold()).strip("_")


def _iter_keys(value: Any):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from _iter_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_keys(child)


def _iter_scalars(value: Any):
    if isinstance(value, dict):
        for child in value.values():
            yield from _iter_scalars(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_scalars(child)
    else:
        yield value


def _diagnostics(observation: dict[str, Any]) -> dict[str, Any]:
    return {
        item["name"]: item["value"]
        for item in observation["terminal"]["failure"]["diagnostics"]
    }


def _canonical_case(raw: Any) -> tuple[str, str, int]:
    assert isinstance(raw, str)
    normalized = raw.strip().replace("\\", "/")
    path = PurePosixPath(normalized)
    canonical = path.as_posix()
    assert canonical == normalized
    assert not path.is_absolute()
    assert path.parts[0] == "cvrplib"
    assert all(part not in {"", ".", ".."} for part in path.parts)
    match = _CVRPLIB_CASE.fullmatch(path.name)
    assert match is not None
    return canonical, match.group(1), int(match.group(2))


def _time_band(dimension: int) -> int:
    if dimension <= 100:
        return 30
    if dimension <= 200:
        return 45
    if dimension <= 350:
        return 60
    if dimension <= 700:
        return 90
    if dimension <= 1001:
        return 120
    raise AssertionError(f"case dimension outside frozen bands: {dimension}")


def _source_pool() -> list[tuple[str, str, int]]:
    raw_cases: list[Any] = []
    for stem in _SOURCE_STEMS:
        split = _load_yaml(_INPUT_ROOT / f"{stem}-split.yaml")
        for field in ("validation", "frozen"):
            raw_cases.extend(split[field])
    return [_canonical_case(raw) for raw in raw_cases]


def _outcome_and_preservation_exclusions() -> set[str]:
    excluded: set[str] = set()
    for stem in _OUTCOME_SCREEN_STEMS:
        split = _load_yaml(_INPUT_ROOT / f"{stem}-split.yaml")
        excluded.update(split["screening"])
    for stem in _FULL_EXCLUSION_STEMS:
        split = _load_yaml(_INPUT_ROOT / f"{stem}-split.yaml")
        for field in ("screening", "validation", "frozen", "canary"):
            excluded.update(split[field])
    return excluded


def _rank_case_paths(
    records: list[tuple[str, str, int]],
    *,
    salt: str,
    predicate,
    count: int,
) -> list[tuple[str, str]]:
    salt_bytes = salt.encode("utf-8")
    ranked = sorted(
        (
            hashlib.sha256(salt_bytes + b"\0" + path.encode("utf-8")).digest(),
            path,
        )
        for path, family, dimension in records
        if predicate(family, dimension)
    )
    assert len(ranked) >= count
    return [(path, digest.hex()) for digest, path in ranked[:count]]


def _tracked_seed_scan_paths(
    base_revision: str,
) -> tuple[list[str], list[str], int, int]:
    raw_paths = subprocess.check_output(
        ["git", "ls-tree", "-r", "-z", "--name-only", base_revision],
        cwd=_REPOSITORY,
    )
    selected_names = [
        raw_path.decode("utf-8")
        for raw_path in raw_paths.split(b"\0")
        if raw_path and (b"cvrp" in raw_path.lower() or raw_path == b"scion/TASK.md")
    ]
    safe_paths: list[str] = []
    skipped_raw_paths: list[str] = []
    for path in selected_names:
        pure = PurePosixPath(path)
        suffix = pure.suffix.casefold()
        if suffix in _RAW_BODY_SUFFIXES or "raw" in {
            part.casefold() for part in pure.parts
        }:
            skipped_raw_paths.append(path)
            continue
        assert suffix in _SAFE_SEED_SCAN_SUFFIXES, (
            f"tracked seed scan refuses unapproved suffix before git show: {path}"
        )
        safe_paths.append(path)
    tracked_count = sum(bool(raw_path) for raw_path in raw_paths.split(b"\0"))
    return safe_paths, skipped_raw_paths, tracked_count, len(selected_names)


def _tracked_cvrp_seed_values(base_revision: str) -> tuple[set[int], int, int]:
    paths, _skipped_raw_paths, _tracked_count, _filtered_count = (
        _tracked_seed_scan_paths(base_revision)
    )
    seed_values: set[int] = set()
    structured_count = 0
    seed_line_match_count = 0

    def collect(value: Any, *, below_seed_key: bool) -> None:
        if type(value) is int:
            if below_seed_key:
                seed_values.add(value)
            return
        if isinstance(value, dict):
            for key, child in value.items():
                collect(
                    child,
                    below_seed_key=(
                        below_seed_key
                        or (isinstance(key, str) and "seed" in key.casefold())
                    ),
                )
            return
        if isinstance(value, list):
            for child in value:
                collect(child, below_seed_key=below_seed_key)

    integer_pattern = re.compile(r"(?<![A-Za-z0-9])([0-9]{1,9})(?![A-Za-z0-9])")
    for path in paths:
        text = subprocess.check_output(
            ["git", "show", f"{base_revision}:{path}"], cwd=_REPOSITORY
        ).decode("utf-8")
        suffix = PurePosixPath(path).suffix.casefold()
        parsed: Any = None
        if suffix == ".json":
            parsed = json.loads(text)
            structured_count += 1
        elif suffix in {".yaml", ".yml"}:
            parsed = yaml.safe_load(text)
            structured_count += 1
        if parsed is not None:
            collect(
                parsed,
                below_seed_key="seed" in PurePosixPath(path).name.casefold(),
            )
        lines = text.splitlines()
        if any("seed" in line.casefold() for line in lines):
            seed_line_match_count += 1
        for line in lines:
            if "seed" in line.casefold():
                seed_values.update(
                    int(match.group(1)) for match in integer_pattern.finditer(line)
                )
    return seed_values, structured_count, seed_line_match_count


def _history_and_context() -> tuple[
    dict[str, Any], tuple[dict[str, Any], ...], dict[str, Any]
]:
    research_input = _load_research_input(_M30_INPUT)
    history = load_research_histories(
        _M30_HISTORY_PATHS,
        expected_problem_id="cvrp",
    )
    projector = CvrpPriorResearchObservationProvider()
    observations = [
        projector.project_prior_research_observation(observation=observation)
        for observation in research_input["observations"]
    ]
    context = {
        "problem_summary": "Generic bounded optimization subject.",
        "branch_id": "m30-provider-free-context-replay",
        "research_surfaces": [{"name": "solver_design", "kind": "generic_algorithm"}],
        "available_actions": ["modify"],
        "existing_target_files": ["operators/main.py"],
        "champion_operators_code": (
            "### operators/main.py\n```python\ndef improve(value):\n"
            "    return value\n```\n"
        ),
        "champion_stats": {},
        "prior_research_observations": observations,
        "prior_research_history": provider_research_history(history),
        "research_question": {"current_question": research_input["current_question"]},
    }
    return research_input, history, context


def _empty_run_result(
    *,
    stop_reason: str,
    progress: QualificationProgress,
    last_outcome: dict[str, str] | None = None,
) -> CampaignRunResult:
    return CampaignRunResult(
        requested_rounds=4,
        evaluated_rounds=0,
        scheduled_calls=0,
        stop_reason=stop_reason,
        failure_categories={},
        protocol_stage_counts={"screening": 0, "validation": 0, "frozen": 0},
        formal_screened_candidates=0,
        execution_outcome_counts={outcome.value: 0 for outcome in ExecutionOutcome},
        unknown_outcome_count=0,
        last_execution_outcome=last_outcome,
        qualification=progress,
    )


def _screen_protocol(
    *,
    cases: list[str],
    seeds: list[int],
    pairs: int,
    gate: str,
) -> dict[str, Any]:
    return {
        "stage": "screening",
        "case_ids": list(cases),
        "seed_set": list(seeds),
        "total_pairs": pairs,
        "attempted_pairs": pairs,
        "valid_pairs": pairs,
        "failed_pairs": 0,
        "candidate_failed_pairs": 0,
        "champion_failed_pairs": 0,
        "shared_failed_pairs": 0,
        "bilateral_failed_pairs": 0,
        "metric_stats": [
            {
                "metric_name": "fleet_violation",
                "median_delta": 0,
                "ci_low": 0,
                "ci_high": 0,
            }
        ],
        "gate_outcome": gate,
        "reason_codes": [],
        "decision_reason_codes": [],
        "diagnostic_reason_codes": [],
        "bypass_reason_codes": [],
        "selected_surface": "solver_design",
    }


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _write_history(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )


def _git(repository: Path, *arguments: str) -> str:
    return subprocess.check_output(
        ["git", *arguments], cwd=repository, text=True
    ).strip()


def _make_readonly(root: Path) -> None:
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        path.chmod(0o555 if path.is_dir() else 0o444)
    root.chmod(0o555)


def _history_hypothesis(*, text: str, source_file: str) -> dict[str, Any]:
    return {
        "text": text,
        "change_locus": "solver_design",
        "action": "modify",
        "target_file": source_file,
        "predicted_direction": "exploratory",
        "target_weakness": "synthetic quality weakness",
        "expected_effect": "synthetic objective improvement",
        "suggested_weight": None,
    }


def _summary_hypothesis(hypothesis: dict[str, Any]) -> dict[str, Any]:
    return {
        key: hypothesis[key]
        for key in ("text", "action", "change_locus", "target_file")
    }


def _history_protocol(gate: str, *, source_file: str) -> dict[str, Any]:
    return {
        "candidate_composition": {
            "attribution_scope": "cumulative_branch_candidate",
            "protocol_comparison_scope": "candidate_vs_champion",
            "evaluation_candidate": "branch_state_after_current_step_patch",
            "current_step_change_scope": "incremental_patch",
            "incremental_effect_isolated": False,
            "current_step": {"target_files": [source_file]},
        },
        "evidence": {
            "stage": "screening",
            "protocol_outcome": {"gate_outcome": gate, "reason_codes": []},
            "case_outcomes": {"case_feedback": []},
        },
    }


def _history_record(
    *,
    hypothesis: dict[str, Any],
    patch: dict[str, Any],
    gate: str,
    decision: str,
    source_file: str,
) -> dict[str, Any]:
    return {
        "schema_version": "scion.research_history.step.v1",
        "problem_id": "cvrp",
        "hypothesis": deepcopy(hypothesis),
        "patch": deepcopy(patch),
        "outcome": {
            "outcome": "evaluated",
            "stage": "screening",
            "reason_code": "EVALUATION_COMPLETED",
        },
        "protocol": _history_protocol(gate, source_file=source_file),
        "decision": {
            "value": decision,
            "reason_codes": [],
            "engine_reason_codes": [],
            "diagnostic_reason_codes": [],
            "bypass_reason_codes": [],
        },
    }


def _synthetic_qualification_campaign(
    tmp_path: Path, *, competing_shape: str
) -> tuple[Path, Path, str, Path]:
    """Build an isolated M30-shaped root audited only through the public API."""

    fixture = _fixture()
    frozen = fixture["qualification_only"]
    cases = fixture["case_selection"]["split_order"]
    seeds = [item["seed"] for item in fixture["seed_selection"]["selected"][:4]]
    source_prefix = Path("scion/scion/problems/cvrp")
    source_file = "policies/baseline_algorithm.py"

    repository = tmp_path / "repo"
    baseline = repository / source_prefix
    (baseline / "policies").mkdir(parents=True)
    _write_json(
        baseline / "problem.yaml",
        {
            "name": "cvrp",
            "operator_categories": ["solver_design"],
            "search_space": {
                "editable": ["policies/*.py"],
                "frozen": ["policies/frozen.py"],
                "import_whitelist": [],
            },
        },
    )
    (baseline / source_file).write_text("VALUE = 0\n", encoding="utf-8")
    for ordinal in range(97):
        (baseline / f"source_{ordinal:03d}.py").write_text(
            f"VALUE = {ordinal}\n", encoding="utf-8"
        )
    subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
    subprocess.run(["git", "add", source_prefix.as_posix()], cwd=repository, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=synthetic",
            "-c",
            "user.email=synthetic@example.invalid",
            "commit",
            "-qm",
            "synthetic M30 source",
        ],
        cwd=repository,
        check=True,
    )
    revision = _git(repository, "rev-parse", "HEAD")

    expectation_value = json.loads(_M30_QUALIFICATION_EXPECTATION.read_text())
    expectation_value["base_revision"] = revision
    expectation_path = tmp_path / "qualification-expectation.json"
    _write_json(expectation_path, expectation_value)

    campaign = tmp_path / "campaign"
    candidate_root = campaign / "candidate_workspaces"
    ready_workspace = candidate_root / "candidate-ready"
    historical_workspace = candidate_root / "candidate-historical"
    candidate_root.mkdir(parents=True)
    shutil.copytree(baseline, ready_workspace)
    shutil.copytree(baseline, historical_workspace)
    (ready_workspace / source_file).write_text("VALUE = 1\n", encoding="utf-8")
    (historical_workspace / source_file).write_text("VALUE = 2\n", encoding="utf-8")
    materializer = WorkspaceMaterializer(
        str(tmp_path / "hashing"),
        frozen_patterns=frozenset({"policies/frozen.py"}),
        editable_patterns=["policies/*.py"],
    )
    ready_hash = materializer.compute_code_hash(str(ready_workspace))
    historical_hash = materializer.compute_code_hash(str(historical_workspace))

    ready_h = _history_hypothesis(text="bounded candidate", source_file=source_file)
    ready_patch = {
        "changes": [
            {
                "file_path": source_file,
                "action": "modify",
                "source": "VALUE = 1\n",
            }
        ]
    }
    competing_h = _history_hypothesis(
        text="competing negative candidate", source_file=source_file
    )
    competing_patch = {
        "changes": [
            {
                "file_path": source_file,
                "action": "modify",
                "source": "VALUE = 2\n",
            }
        ]
    }
    evaluated = {
        "outcome": "evaluated",
        "reason_code": "EVALUATION_COMPLETED",
        "detail": "",
        "provenance": {"stage": "screening"},
    }
    initial = _screen_protocol(cases=cases[:3], seeds=seeds[:2], pairs=6, gate="expand")
    expanded = _screen_protocol(cases=cases, seeds=seeds, pairs=24, gate="pass")
    if competing_shape == "screened":
        competing_protocol = _screen_protocol(
            cases=cases[:3], seeds=seeds[:2], pairs=6, gate="fail"
        )
        competing_protocol.update(
            valid_pairs=5,
            failed_pairs=1,
            candidate_failed_pairs=1,
        )
        competing_step = {
            "branch_id": "negative",
            "hypothesis": _summary_hypothesis(competing_h),
            "protocol_result": competing_protocol,
            "decision": "continue_explore",
            "contract_passed": True,
            "verification_passed": True,
            "canary_result": {"passed": True},
            "execution_outcome": evaluated,
        }
        competing_record = _history_record(
            hypothesis=competing_h,
            patch=competing_patch,
            gate="fail",
            decision="continue_explore",
            source_file=source_file,
        )
        competing_event = (
            "experiment",
            "negative",
            historical_hash,
            "modify",
            source_file,
            competing_h["text"],
            "passed",
            "passed",
            "passed",
            "screening",
            "continue_explore",
        )
        formal_count = 3
    else:
        assert competing_shape == "canary_negative"
        competing_step = {
            "branch_id": "negative",
            "hypothesis": _summary_hypothesis(competing_h),
            "protocol_result": None,
            "decision": "abandon",
            "contract_passed": True,
            "verification_passed": True,
            "failure_stage": "canary",
            "canary_result": {
                "passed": False,
                "failure_category": "candidate_failure",
            },
            "execution_outcome": evaluated,
        }
        competing_record = {
            **_history_record(
                hypothesis=competing_h,
                patch=competing_patch,
                gate="unused",
                decision="abandon",
                source_file=source_file,
            ),
            "outcome": {
                "outcome": "evaluated",
                "stage": "canary",
                "reason_code": "EVALUATION_COMPLETED",
            },
            "protocol": None,
        }
        competing_event = (
            "experiment",
            "negative",
            historical_hash,
            "modify",
            source_file,
            competing_h["text"],
            "passed",
            "passed",
            "failed",
            "",
            "abandon",
        )
        formal_count = 2

    steps: list[dict[str, Any]] = [
        {
            "branch_id": "ready",
            "hypothesis": None,
            "protocol_result": None,
            "decision": None,
            "contract_passed": None,
            "verification_passed": None,
            "failure_stage": "proposal_hypothesis",
            "canary_result": None,
            "execution_outcome": {
                "outcome": "research_rejected",
                "reason_code": "SYNTHETIC_ABSTAINED",
                "detail": "",
                "provenance": {"stage": "proposal_hypothesis"},
            },
        },
        competing_step,
        {
            "branch_id": "ready",
            "hypothesis": _summary_hypothesis(ready_h),
            "protocol_result": initial,
            "decision": "expand_screening",
            "contract_passed": True,
            "verification_passed": True,
            "canary_result": {"passed": True},
            "execution_outcome": evaluated,
        },
        {
            "branch_id": "ready",
            "hypothesis": _summary_hypothesis(ready_h),
            "protocol_result": expanded,
            "decision": "queue_validate",
            "contract_passed": None,
            "verification_passed": None,
            "canary_result": {"passed": True},
            "execution_outcome": evaluated,
        },
    ]
    for ordinal, step in enumerate(steps, 1):
        step["round"] = ordinal
        step.setdefault("decision_reason_codes", [])
        step.setdefault("diagnostic_reason_codes", [])
        step.setdefault("bypass_reason_codes", [])
    history = [
        {
            "schema_version": "scion.research_history.step.v1",
            "problem_id": "cvrp",
            "hypothesis": None,
            "patch": None,
            "outcome": {
                "outcome": "research_rejected",
                "stage": "proposal_hypothesis",
                "reason_code": "SYNTHETIC_ABSTAINED",
            },
            "protocol": None,
            "decision": None,
        },
        competing_record,
        _history_record(
            hypothesis=ready_h,
            patch=ready_patch,
            gate="expand",
            decision="expand_screening",
            source_file=source_file,
        ),
        _history_record(
            hypothesis=ready_h,
            patch=ready_patch,
            gate="pass",
            decision="queue_validate",
            source_file=source_file,
        ),
    ]
    outcome_counts = {outcome.value: 0 for outcome in ExecutionOutcome}
    outcome_counts["evaluated"] = 3
    outcome_counts["research_rejected"] = 1
    run = {
        "status": "completed",
        "evaluated_rounds": formal_count,
        "scheduled_calls": 4,
        "formal_screened_candidates": formal_count,
        "stop_reason": frozen["positive_stop_reason"],
        "run_validity": {"valid": True, "status": "valid", "reason": "valid"},
        "protocol_stage_counts": {
            "screening": formal_count,
            "validation": 0,
            "frozen": 0,
        },
        "unknown_outcome_count": 0,
        "execution_outcome_counts": outcome_counts,
        "last_execution_outcome": {
            "outcome": "evaluated",
            "reason_code": "EVALUATION_COMPLETED",
            "stage": "screening",
        },
        "qualification": {
            "mode": "qualification_only",
            "limits": {
                "max_proposal_attempts": frozen["max_proposal_attempts"],
                "max_verified_candidate_chains": frozen[
                    "max_verified_candidate_chains"
                ],
                "max_formal_screening_stages": frozen["max_formal_screening_stages"],
            },
            "proposal_attempts": 3,
            "verified_candidate_chains": 2,
            "formal_screening_stages": formal_count,
            "initial_screening_stages": formal_count - 1,
            "expanded_screening_stages": 1,
            "disposition": frozen["positive_runtime_disposition"],
        },
    }
    branches = [
        {
            "id": "negative",
            "state": "parked_lineage",
            "base_champion_id": "synthetic-b0",
            "current_code_hash": None,
            "weight_revision": 0,
            "direction": None,
            "failure_codes": [],
            "created_at": "2026-08-24T00:00:00",
            "updated_at": "2026-08-24T00:00:01",
        },
        {
            "id": "ready",
            "state": "ready_validate",
            "base_champion_id": "synthetic-b0",
            "current_code_hash": ready_hash,
            "weight_revision": 0,
            "direction": "solver_design: bounded candidate",
            "failure_codes": [],
            "created_at": "2026-08-24T00:00:02",
            "updated_at": "2026-08-24T00:00:03",
        },
    ]
    active_slots = {
        "used": 1,
        "max": 2,
        "available": 1,
        "branch_ids": ["ready"],
    }
    _write_json(
        campaign / "status.json",
        {
            "campaign_mode": "qualification_only",
            "n_steps": 4,
            "total_rounds": 4,
            "n_experiments": formal_count,
            "screened_experiments": formal_count,
            "n_active_branches": 1,
            "active_slots": active_slots,
            "branches": branches,
            "last_result": {
                "action": "explore",
                "branch_id": "ready",
                "decision": "queue_validate",
                "stopped": False,
                "reason": "",
                "execution_outcome": {
                    "outcome": "evaluated",
                    "reason_code": "EVALUATION_COMPLETED",
                    "stage": "screening",
                },
            },
            "run_result": run,
        },
    )
    _write_json(
        campaign / "campaign_summary.json",
        {
            "campaign_mode": "qualification_only",
            "n_steps": 4,
            "total_rounds": 4,
            "n_experiments": formal_count,
            "screened_experiments": formal_count,
            "n_active_branches": 1,
            "active_slots": active_slots,
            "branches": branches,
            "steps": steps,
            "run_result": run,
        },
    )
    _write_history(campaign / "research_history.jsonl", history)
    with sqlite3.connect(campaign / "scion.db") as connection:
        connection.execute(
            "CREATE TABLE experiment_events (event_kind TEXT, branch_id TEXT, "
            "code_hash TEXT, patch_action TEXT, patch_file TEXT, "
            "hypothesis_text TEXT, contract_result TEXT, verification_result TEXT, "
            "canary_result TEXT, stage TEXT, decision TEXT, decision_reason TEXT, "
            "execution_outcome TEXT, execution_outcome_reason_code TEXT)"
        )
        rows = (
            (
                "proposal_execution_outcome",
                "ready",
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                "proposal_hypothesis",
                None,
                None,
                "research_rejected",
                "SYNTHETIC_ABSTAINED",
            ),
            (*competing_event, "[]", None, None),
            (
                "experiment",
                "ready",
                ready_hash,
                "modify",
                source_file,
                ready_h["text"],
                "passed",
                "passed",
                "passed",
                "screening",
                "expand_screening",
                "[]",
                None,
                None,
            ),
            (
                "experiment",
                "ready",
                ready_hash,
                "modify",
                source_file,
                ready_h["text"],
                "not_run",
                "not_run",
                "passed",
                "screening",
                "queue_validate",
                "[]",
                None,
                None,
            ),
        )
        for row in rows:
            connection.execute(
                "INSERT INTO experiment_events VALUES "
                "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                row,
            )
    _make_readonly(ready_workspace)
    _make_readonly(historical_workspace)
    (campaign / "scion.db").chmod(0o444)
    return campaign, repository, revision, expectation_path


def test_m30_first_h_context_is_eight_observations_plus_forty_two_histories() -> None:
    fixture = _fixture()
    research_input, history, context = _history_and_context()
    expected = fixture["history"]

    assert (
        research_input["observations"][:7]
        == _load_research_input(_M28_INPUT)["observations"]
    )
    assert len(research_input["observations"]) == expected["prior_observations"]
    assert len(_M30_HISTORY_PATHS) == expected["history_files"]
    assert len(history) == expected["native_history"]

    copied_bytes = _M30_HISTORY_COPY.read_bytes()
    assert copied_bytes.count(b"\n") == expected["m28_history_lines"]
    assert len(copied_bytes) == expected["m28_history_bytes"]
    preserved_history = Path(expected["m28_preserved_history"])
    assert preserved_history.is_file() and not preserved_history.is_symlink()
    assert copied_bytes == preserved_history.read_bytes()
    canonical_m28 = load_research_histories(
        (_M30_HISTORY_COPY,), expected_problem_id="cvrp"
    )
    assert len(canonical_m28) == 3
    assert history[-3:] == canonical_m28
    assert [record["outcome"]["outcome"] for record in canonical_m28] == [
        "evaluated",
        "research_rejected",
        "resource_exhausted",
    ]
    assert [record["outcome"]["reason_code"] for record in canonical_m28] == [
        "EVALUATION_COMPLETED",
        "PATCH_PROPOSAL_INVALID",
        "PROVIDER_CALL_CAP_EXHAUSTED",
    ]

    _sources, indexed_history, compact = build_hypothesis_research_corpus(context)
    assert len(indexed_history) == expected["first_h_inventory"]
    assert [entry["kind"] for entry in indexed_history[:8]] == [
        "prior_research_observations"
    ] * 8
    assert [entry["kind"] for entry in indexed_history[8:]] == [
        "prior_research_history"
    ] * 42
    assert compact["prior_research_observations"]["record_count"] == 8
    assert compact["prior_research_history"]["record_count"] == 42
    eligible = [
        entry
        for entry in indexed_history
        if isinstance(entry["index"].get("hypothesis"), dict)
        and any(
            isinstance(value, str) and bool(value.strip())
            for value in entry["index"]["hypothesis"].values()
        )
    ]
    assert len(eligible) == expected["eligible_headline_entries"]
    assert [entry["ref"] for entry in eligible] == [
        f"history-{ordinal:04d}" for ordinal in range(9, 51)
    ]


def test_m30_m28_terminal_observation_is_sanitized_and_exactly_scoped() -> None:
    research_input, _history, context = _history_and_context()
    terminal = research_input["observations"][-1]
    projected = context["prior_research_observations"][-1]
    diagnostics = _diagnostics(terminal)

    assert terminal["observation_kind"] == "autonomous_candidate_evaluation_terminal"
    assert len(terminal["completed_stages"]) == 1
    stage = terminal["completed_stages"][0]
    assert (stage["block"], stage["valid_pairs"], stage["planned_pairs"]) == (
        "initial",
        6,
        6,
    )
    assert stage["case_outcomes"] == {
        "wins": 1,
        "losses": 1,
        "ties": 1,
        "median_delta": 0,
        "ci_low": -2.5,
        "ci_high": 206,
    }
    assert (stage["gate_outcome"], stage["decision"]) == (
        "fail",
        "continue_explore",
    )
    assert diagnostics["provider_calls_used"] == 34
    assert diagnostics["hypothesis_research_calls"] == 25
    assert diagnostics["code_research_calls"] == 8
    assert diagnostics["code_final_decision_calls"] == 1
    assert diagnostics["scheduled_attempts"] == 4
    assert diagnostics["evaluated_outcomes"] == 1
    assert diagnostics["research_rejected_outcomes"] == 2
    assert diagnostics["resource_exhausted_outcomes"] == 1
    assert diagnostics["ordinary_history_records_written"] == 3
    assert diagnostics["durable_research_rejected_records"] == 1
    assert diagnostics["unpersisted_safe_live_h_abstentions"] == 1
    assert diagnostics["solver_calls"] == 16
    assert diagnostics["ready_validate_branches"] == 0
    assert diagnostics["expanded_reached"] is False
    assert diagnostics["validation_reached"] is False
    assert diagnostics["frozen_reached"] is False
    assert diagnostics["promotion_reached"] is False
    assert diagnostics["retained_replay_reached"] is False
    assert projected["observed_outputs"] == {
        "terminal_stage_metrics": True,
        "terminal_safe_features": True,
        "terminal_decision": True,
        "later_stage_metrics": False,
        "promotion": False,
        "retained_baseline_comparison": False,
    }
    assert terminal["claim_context"] == {
        "evidence_scope": "seen_development_population",
        "candidate_selection_outcome_known": True,
        "candidate_discovery_independent": False,
        "incremental_effect_isolated": False,
        "population_selection_outcome_blind_relative_to_exact_estimand": False,
        "exact_candidate_outcome_overlap_count": 0,
        "globally_case_unseen": False,
        "mde_at_power_80": None,
    }

    normalized_keys = {_normalized_key(key) for key in _iter_keys(terminal)}
    assert normalized_keys.isdisjoint(
        {
            "action",
            "change_locus",
            "editable_source",
            "falsifier_source",
            "mechanism",
            "patch",
            "probe_body",
            "provider_response",
            "provider_trace",
            "repair",
            "research_basis",
            "surface",
            "target_file",
        }
    )
    strings = [value for value in _iter_scalars(terminal) if isinstance(value, str)]
    assert all(".vrp" not in value.casefold() for value in strings)
    assert all("policies/" not in value.casefold() for value in strings)
    assert set(_fixture()["case_selection"]["split_order"]).isdisjoint(strings)
    assert {
        item["seed"] for item in _fixture()["seed_selection"]["selected"]
    }.isdisjoint(set(_iter_scalars(terminal)))


def test_m30_controls_are_exact_m28_derivation_with_fresh_development_values() -> None:
    fixture = _fixture()
    m28_protocol = ProtocolConfig.from_yaml(_M28_PROTOCOL).model_dump(mode="json")
    protocol = ProtocolConfig.from_yaml(_M30_PROTOCOL).model_dump(mode="json")
    m28_split = SplitManifest.from_yaml(_M28_SPLIT).model_dump(mode="json")
    split = SplitManifest.from_yaml(_M30_SPLIT).model_dump(mode="json")
    m28_seeds = SeedLedgerConfig.from_yaml(_M28_SEEDS).model_dump(mode="json")
    seeds = SeedLedgerConfig.from_yaml(_M30_SEEDS).model_dump(mode="json")

    expected_cases = fixture["case_selection"]["split_order"]
    expected_seeds = [item["seed"] for item in fixture["seed_selection"]["selected"]]
    m28_protocol["version"] = fixture["control_version"]
    m28_protocol["screening"]["priority_case_ids"] = expected_cases[:3]
    m28_protocol["canary"]["seeds"] = [expected_seeds[4]]
    assert protocol == m28_protocol

    m28_split["version"] = fixture["control_version"]
    m28_split["screening"] = expected_cases
    assert split == m28_split

    m28_seeds["version"] = fixture["control_version"]
    m28_seeds["screening"] = expected_seeds[:4]
    m28_seeds["canary"] = [expected_seeds[4]]
    assert seeds == m28_seeds
    assert protocol["version"] == split["version"] == seeds["version"]


def test_m30_case_selector_replays_hash_ranking_without_reading_case_bodies() -> None:
    fixture = _fixture()
    selection = fixture["case_selection"]
    records = _source_pool()
    paths = [path for path, _family, _dimension in records]
    assert len(paths) == len(set(paths)) == selection["source_count"] == 18

    family_counts = {
        family: sum(item_family == family for _path, item_family, _size in records)
        for family in ("A", "B", "P", "X")
    }
    band_counts = {
        str(band): sum(_time_band(size) == band for _path, _family, size in records)
        for band in (30, 45, 60, 90, 120)
    }
    assert family_counts == selection["source_family_counts"]
    assert band_counts == selection["source_time_band_counts"]

    excluded = _outcome_and_preservation_exclusions()
    assert len(excluded) == selection["outcome_and_preservation_exclusion_count"]
    assert sum(path.endswith(".vrp") for path in excluded) == 48
    assert set(paths).isdisjoint(excluded)
    m24 = _load_yaml(
        _INPUT_ROOT
        / "v04-cvrp-m24-autonomous-direction-research-development-split.yaml"
    )
    m28 = _load_yaml(_M28_SPLIT)
    assert {key: value for key, value in m28.items() if key != "version"} == {
        key: value for key, value in m24.items() if key != "version"
    }

    # M23 declared these controls but never reached validation/frozen/retained.
    # Their overlap is therefore allowed fresh-at-start reserve, not outcome evidence.
    m23 = _load_yaml(_INPUT_ROOT / "v04-cvrp-m23-m20-swap-full-funnel-split.yaml")
    m23_retained = _load_yaml(
        _INPUT_ROOT / "v04-cvrp-m23-m20-swap-full-funnel-retained-split.yaml"
    )
    m23_unreached = {
        *m23["validation"],
        *m23["frozen"],
        *m23_retained["frozen"],
    }
    assert len(m23_unreached) == 9
    assert m23_unreached.issubset(set(paths))

    salt = selection["salt"]
    ranked_by_stratum = {
        "A20_100": _rank_case_paths(
            records,
            salt=salt,
            predicate=lambda family, size: family == "A" and 20 <= size <= 100,
            count=2,
        ),
        "P20_100": _rank_case_paths(
            records,
            salt=salt,
            predicate=lambda family, size: family == "P" and 20 <= size <= 100,
            count=1,
        ),
        "X101_200": _rank_case_paths(
            records,
            salt=salt,
            predicate=lambda family, size: family == "X" and 101 <= size <= 200,
            count=1,
        ),
        "X201_350": _rank_case_paths(
            records,
            salt=salt,
            predicate=lambda family, size: family == "X" and 201 <= size <= 350,
            count=1,
        ),
        "X351_700": _rank_case_paths(
            records,
            salt=salt,
            predicate=lambda family, size: family == "X" and 351 <= size <= 700,
            count=1,
        ),
    }
    assert ranked_by_stratum == {
        stratum: [(item["path"], item["digest"]) for item in selected]
        for stratum, selected in selection["selected_by_stratum"].items()
    }
    selected_paths = {
        path for ranked in ranked_by_stratum.values() for path, _digest in ranked
    }
    assert selected_paths == set(selection["split_order"])

    # Metadata-only companion check: do not open either reserved-derived body.
    data_root = _REPOSITORY / "vrp"
    for relative in selection["split_order"]:
        case = data_root / relative
        companion = case.with_suffix(".sol")
        for path in (case, companion):
            mode = path.lstat().st_mode
            assert stat.S_ISREG(mode)
            assert not path.is_symlink()


def test_m30_seed_selector_replays_final_base_scan_and_stays_disjoint_from_m31() -> (
    None
):
    fixture = _fixture()
    selection = fixture["seed_selection"]
    safe_paths, skipped_raw_paths, tracked_count, filtered_count = (
        _tracked_seed_scan_paths(fixture["base_revision"])
    )
    assert selection["scan_kind"] == "tracked_nonraw_only"
    assert sorted(_SAFE_SEED_SCAN_SUFFIXES) == selection["safe_suffixes"]
    assert (
        sorted(_RAW_BODY_SUFFIXES) == selection["raw_body_suffixes_skipped_before_read"]
    )
    assert (
        len(skipped_raw_paths) == selection["raw_body_paths_skipped_before_read"] == 18
    )
    assert tracked_count == selection["tracked_paths_total"] == 2163
    assert filtered_count == selection["filtered_paths"] == 524
    assert len(safe_paths) == selection["allowlisted_blobs"] == 506
    assert selection["unknown_suffix_paths"] == 0
    assert all(
        PurePosixPath(path).suffix.casefold() in _RAW_BODY_SUFFIXES
        or "raw" in {part.casefold() for part in PurePosixPath(path).parts}
        for path in skipped_raw_paths
    )
    assert all(
        PurePosixPath(path).suffix.casefold() in _SAFE_SEED_SCAN_SUFFIXES
        and "raw" not in {part.casefold() for part in PurePosixPath(path).parts}
        for path in safe_paths
    )
    values, structured_count, seed_line_match_count = _tracked_cvrp_seed_values(
        fixture["base_revision"]
    )
    assert structured_count == selection["structured_json_yaml_files"] == 69
    assert selection["structured_parse_errors"] == 0
    assert seed_line_match_count == selection["seed_line_match_files"] == 322
    assert len(values) == selection["tracked_seed_values"]
    excluded = sum(
        selection["domain_min"] <= value <= selection["domain_max"] for value in values
    )
    assert excluded == selection["excluded_domain_values"]
    assert (
        selection["domain_max"] - selection["domain_min"] + 1 - excluded
        == selection["eligible_domain_values"]
    )

    salt = selection["salt"].encode("utf-8")
    ranked = sorted(
        (
            hashlib.sha256(salt + b"\0" + str(seed).encode("ascii")).digest(),
            seed,
        )
        for seed in range(selection["domain_min"], selection["domain_max"] + 1)
        if seed not in values
    )
    expected = selection["selected"]
    assert [seed for _digest, seed in ranked[:5]] == [item["seed"] for item in expected]
    assert [digest.hex() for digest, _seed in ranked[:5]] == [
        item["digest"] for item in expected
    ]

    m31 = fixture["conditional_m31"]
    m31_excluded = sum(
        m31["seed_domain_min"] <= value <= m31["seed_domain_max"] for value in values
    )
    assert m31_excluded == m31["excluded_seed_domain_values"]
    assert (
        m31["seed_domain_max"] - m31["seed_domain_min"] + 1 - m31_excluded
        == m31["eligible_seed_domain_values"]
    )
    assert m31["eligible_seed_domain_values"] >= m31["required_seed_quota"]
    assert selection["domain_max"] < m31["seed_domain_min"]
    # The conditional record intentionally has rules/counts, never selected identities.
    assert set(m31).isdisjoint(
        {"selected", "selected_cases", "selected_seeds", "digests"}
    )
    assert all(
        ".vrp" not in value for value in _iter_scalars(m31) if isinstance(value, str)
    )


def test_conditional_m31_case_rule_is_feasible_by_counts_without_ranking() -> None:
    fixture = _fixture()
    selection = fixture["case_selection"]
    m31 = fixture["conditional_m31"]
    selected = set(selection["split_order"])
    remaining = [record for record in _source_pool() if record[0] not in selected]
    assert len(remaining) == m31["remaining_case_count_after_m30"] == 12

    predicates = {
        "A20_100": lambda family, size: family == "A" and 20 <= size <= 100,
        "B20_100": lambda family, size: family == "B" and 20 <= size <= 100,
        "P10_19": lambda family, size: family == "P" and 10 <= size <= 19,
        "P20_100": lambda family, size: family == "P" and 20 <= size <= 100,
        "X101_200": lambda family, size: family == "X" and 101 <= size <= 200,
        "X201_350": lambda family, size: family == "X" and 201 <= size <= 350,
        "X351_700": lambda family, size: family == "X" and 351 <= size <= 700,
        "X701_1001": lambda family, size: family == "X" and 701 <= size <= 1001,
    }
    counts = {
        name: sum(predicate(family, size) for _path, family, size in remaining)
        for name, predicate in predicates.items()
    }
    assert counts == m31["remaining_case_counts_after_m30"]

    # Feasibility subtracts the frozen six screening quotas arithmetically.
    # It never calculates which identity an independent M31 salt would rank first.
    after_screening = dict(counts)
    for stratum in (
        "A20_100",
        "B20_100",
        "P20_100",
        "X101_200",
        "X201_350",
        "X351_700",
    ):
        assert after_screening[stratum] >= 1
        after_screening[stratum] -= 1
    nonzero_after_screening = {
        key: value for key, value in after_screening.items() if value
    }
    assert (
        nonzero_after_screening == m31["remaining_case_counts_after_screening_quotas"]
    )
    for retained in ("P10_19", "X201_350", "X351_700"):
        assert after_screening[retained] >= 1
        after_screening[retained] -= 1
    assert sum(after_screening.values()) == m31["unused_after_retained"] == 3


def test_m30_qualification_only_limits_and_typed_terminal_meanings_are_exact() -> None:
    frozen = _fixture()["qualification_only"]
    config = QualificationOnlyConfig(
        max_proposal_attempts=frozen["max_proposal_attempts"],
        max_verified_candidate_chains=frozen["max_verified_candidate_chains"],
        max_formal_screening_stages=frozen["max_formal_screening_stages"],
    )
    assert config.to_projection() == {
        "max_proposal_attempts": 6,
        "max_verified_candidate_chains": 2,
        "max_formal_screening_stages": 4,
    }

    runtime = QualificationRuntime(config)
    runtime.reserve_proposal_attempt()
    runtime.record_verified_candidate("candidate-1")
    runtime.record_screening_stage("candidate-1", expanded=False)
    runtime.request_expansion("candidate-1")
    assert runtime.can_start_proposal() is False
    assert runtime.authorize_expansion("candidate-1") is True
    runtime.record_screening_stage("candidate-1", expanded=True)
    progress = runtime.progress()
    assert progress.to_projection(stop_reason=QUALIFICATION_BOUNDARY_REACHED) == {
        "mode": "qualification_only",
        "limits": config.to_projection(),
        "proposal_attempts": 1,
        "verified_candidate_chains": 1,
        "formal_screening_stages": 2,
        "initial_screening_stages": 1,
        "expanded_screening_stages": 1,
        "disposition": QUALIFICATION_READY_DISPOSITION,
    }
    positive = _empty_run_result(
        stop_reason=QUALIFICATION_BOUNDARY_REACHED, progress=progress
    )
    assert positive.completed is True
    assert positive.to_projection()["status"] == "completed"
    assert _completion_from_run_result(positive) == (0, QUALIFICATION_BOUNDARY_REACHED)

    empty_progress = QualificationProgress(config=config, proposal_attempts=6)
    bounded_negative = _empty_run_result(
        stop_reason=QUALIFICATION_NOT_REACHED,
        progress=empty_progress,
    )
    negative_projection = bounded_negative.to_projection()
    assert bounded_negative.completed is True
    assert negative_projection["status"] == "completed"
    assert negative_projection["run_validity"] == {
        "valid": True,
        "status": "valid",
        "reason": "valid",
    }
    assert negative_projection["qualification"]["disposition"] == (
        QUALIFICATION_NOT_REACHED
    )
    assert _completion_from_run_result(bounded_negative) == (
        0,
        QUALIFICATION_NOT_REACHED,
    )

    incomplete = _empty_run_result(
        stop_reason="execution_not_evaluated", progress=empty_progress
    )
    assert incomplete.completed is False
    assert _completion_from_run_result(incomplete)[0] == 22

    exhausted_counts = {outcome.value: 0 for outcome in ExecutionOutcome}
    exhausted_counts[ExecutionOutcome.RESOURCE_EXHAUSTED.value] = 1
    exhausted = CampaignRunResult(
        requested_rounds=4,
        evaluated_rounds=0,
        scheduled_calls=1,
        stop_reason="execution_resource_exhausted",
        failure_categories={"resource_exhausted": 1},
        protocol_stage_counts={"screening": 0, "validation": 0, "frozen": 0},
        formal_screened_candidates=0,
        execution_outcome_counts=exhausted_counts,
        unknown_outcome_count=0,
        last_execution_outcome={
            "outcome": "resource_exhausted",
            "reason_code": "PROVIDER_CALL_CAP_EXHAUSTED",
            "stage": "proposal_code",
        },
        qualification=empty_progress,
    )
    assert exhausted.completed is False
    assert _completion_from_run_result(exhausted)[0] == 21


def test_m30_qualification_expectation_is_strict_and_fixture_aligned() -> None:
    fixture = _fixture()
    frozen = fixture["qualification_only"]
    assert fixture["qualification_audit"] == {
        "expectation_path": (
            "docs/experiments/v0.4/inputs/"
            "v04-cvrp-m30-fresh-development-qualification-only-"
            "qualification-expectation.json"
        ),
        "expectation_sha256": (
            "4141167ecd1dfca46299940716f4e81ccaba26682240fd7e991a08615662ed57"
        ),
        "success_token": "QUALIFIED_FOR_NEW_FIXED_CANDIDATE_FUNNEL",
        "failure_token": "QUALIFICATION_CARRIER_UNAVAILABLE",
        "generic_auditor_tests": 136,
        "generic_auditor_carrier_cli_tests": 149,
        "postcommit_tests": 181,
    }
    assert (
        hashlib.sha256(_M30_QUALIFICATION_EXPECTATION.read_bytes()).hexdigest()
        == fixture["qualification_audit"]["expectation_sha256"]
    )
    expectation = load_qualification_audit_expectation(_M30_QUALIFICATION_EXPECTATION)

    assert expectation.base_revision == fixture["base_revision"]
    assert expectation.source_prefix == "scion/scion/problems/cvrp"
    assert expectation.source_file_count == frozen["ordinary_source_files"] == 99
    assert expectation.limits == {
        "max_proposal_attempts": frozen["max_proposal_attempts"],
        "max_verified_candidate_chains": frozen["max_verified_candidate_chains"],
        "max_formal_screening_stages": frozen["max_formal_screening_stages"],
    }
    assert [list(stage.case_ids) for stage in expectation.screening] == [
        fixture["case_selection"]["split_order"][:3],
        fixture["case_selection"]["split_order"],
    ]
    selected_seeds = [
        item["seed"] for item in fixture["seed_selection"]["selected"][:4]
    ]
    assert [list(stage.seed_set) for stage in expectation.screening] == [
        selected_seeds[:2],
        selected_seeds,
    ]
    assert [stage.valid_pairs for stage in expectation.screening] == [6, 24]
    assert [stage.gate_outcome for stage in expectation.screening] == [
        "expand",
        "pass",
    ]
    assert [stage.decision for stage in expectation.screening] == [
        "expand_screening",
        "queue_validate",
    ]


@pytest.mark.parametrize("competing_shape", ("screened", "canary_negative"))
def test_m30_public_qualification_audit_accepts_frozen_positive_shapes(
    tmp_path: Path, competing_shape: str
) -> None:
    campaign, repository, revision, expectation_path = (
        _synthetic_qualification_campaign(
            tmp_path,
            competing_shape=competing_shape,
        )
    )

    token = audit_qualification_campaign(
        campaign,
        expectation=load_qualification_audit_expectation(expectation_path),
        repository=repository,
        base_revision=revision,
    )

    assert (
        token == QUALIFIED_TOKEN == _fixture()["qualification_audit"]["success_token"]
    )
    summary = json.loads((campaign / "campaign_summary.json").read_text())
    if competing_shape == "canary_negative":
        assert summary["steps"][1]["failure_stage"] == "canary"
        assert summary["steps"][1]["decision"] == "abandon"


@pytest.mark.parametrize(
    "mutation",
    ("create_new", "wrong_bank", "heldout_stage", "multiple_ready"),
)
def test_m30_public_qualification_audit_fails_closed(
    tmp_path: Path, mutation: str
) -> None:
    campaign, repository, revision, expectation_path = (
        _synthetic_qualification_campaign(tmp_path, competing_shape="screened")
    )
    if mutation == "create_new":
        history_path = campaign / "research_history.jsonl"
        records = [json.loads(line) for line in history_path.read_text().splitlines()]
        for record in records[-2:]:
            record["hypothesis"]["action"] = "create_new"
            record["patch"]["changes"][0]["action"] = "create"
        _write_history(history_path, records)
    elif mutation == "wrong_bank":
        path = campaign / "campaign_summary.json"
        value = json.loads(path.read_text())
        value["steps"][-1]["protocol_result"]["seed_set"][0] = 1
        _write_json(path, value)
    elif mutation == "heldout_stage":
        for name in ("status.json", "campaign_summary.json"):
            path = campaign / name
            value = json.loads(path.read_text())
            value["run_result"]["protocol_stage_counts"]["validation"] = 1
            _write_json(path, value)
    elif mutation == "multiple_ready":
        for name in ("status.json", "campaign_summary.json"):
            path = campaign / name
            value = json.loads(path.read_text())
            value["branches"][0]["state"] = "ready_validate"
            _write_json(path, value)
    else:  # pragma: no cover - parametrization is frozen above
        raise AssertionError(mutation)

    with pytest.raises(QualificationAuditUnavailable):
        audit_qualification_campaign(
            campaign,
            expectation=load_qualification_audit_expectation(expectation_path),
            repository=repository,
            base_revision=revision,
        )


def test_m30_resource_envelope_replays_all_component_arithmetic() -> None:
    fixture = _fixture()
    resources = fixture["resources"]
    qualification = fixture["qualification_only"]
    protocol = ProtocolConfig.from_yaml(_M30_PROTOCOL)
    split = SplitManifest.from_yaml(_M30_SPLIT)
    time_limits = protocol.runtime.time_limits

    weighted_provider_by_c_sessions = []
    for c_sessions in range(7):
        c_calls = min(9 * c_sessions, 60 - 3 * c_sessions)
        h_calls = 60 - c_calls
        weighted_provider_by_c_sessions.append(c_calls * 240 + h_calls * 120)
    assert (
        max(weighted_provider_by_c_sessions)
        == resources["provider_weighted_timeout_sec"]
        == 12600
    )
    assert 6 * 90 == resources["development_sec"] == 540
    assert 6 * 120 == resources["verification_pytest_sec"] == 720

    initial_sum = sum(
        time_limits.resolve(
            stage="screening", case_path=case, fallback_time_limit_sec=30
        )
        for case in split.screening[:3]
    )
    expanded_sum = sum(
        time_limits.resolve(
            stage="screening", case_path=case, fallback_time_limit_sec=30
        )
        for case in split.screening
    )
    assert initial_sum == fixture["case_selection"]["initial_time_limit_sum"] == 120
    assert expanded_sum == fixture["case_selection"]["expanded_time_limit_sum"] == 285
    per_chain_formal = 2 * 2 * initial_sum + 2 * 4 * expanded_sum
    assert per_chain_formal == 2760

    verification_calls = qualification["max_proposal_attempts"] * 2
    canary_calls = qualification["max_formal_screening_stages"] * 2
    formal_calls = qualification["max_verified_candidate_chains"] * (12 + 48)
    assert verification_calls == resources["verification_solver_calls"] == 12
    assert canary_calls == resources["normal_canary_solver_calls"] == 8
    assert formal_calls == resources["formal_solver_calls"] == 120
    solver_calls = verification_calls + canary_calls + formal_calls
    assert solver_calls == resources["total_solver_calls"] == 140
    nominal = 2 * per_chain_formal + verification_calls * 30 + canary_calls * 10
    assert nominal == resources["solver_nominal_sec"] == 5960
    communicate_guarded = nominal + solver_calls * 15
    assert communicate_guarded == resources["solver_communicate_guarded_sec"] == 8060
    lifecycle = communicate_guarded + solver_calls * (5 + 1)
    assert lifecycle == resources["solver_lifecycle_conservative_sec"] == 8900
    all_known = 12600 + 540 + 720 + lifecycle
    assert all_known == resources["all_known_conservative_sec"] == 22760
    assert (
        qualification["outer_hardwall_sec"] - all_known
        == resources["hardwall_margin_sec"]
        == 5240
    )


def test_conditional_m31_resource_rule_uses_p10_19_thirty_second_band() -> None:
    m31 = _fixture()["conditional_m31"]
    retained = 2 * 2 * (30 + 60 + 90)
    nominal = 2 * 10 + 2280 + 720 + 1080 + retained
    assert retained == 720
    assert m31["solver_calls"] == 86
    assert nominal == m31["solver_nominal_sec"] == 4820
    guarded = nominal + m31["solver_calls"] * 15
    assert guarded == m31["solver_communicate_guarded_sec"] == 6110
    lifecycle = guarded + m31["solver_calls"] * (5 + 1)
    assert lifecycle == m31["solver_lifecycle_conservative_sec"] == 6626
    assert m31["hardwall_sec"] - lifecycle == m31["hardwall_margin_sec"] == 1374


def test_m30_base_has_exact_regular_ordinary_source_projection() -> None:
    fixture = _fixture()
    raw = subprocess.check_output(
        [
            "git",
            "ls-tree",
            "-r",
            "-z",
            fixture["base_revision"],
            "--",
            "scion/scion/problems/cvrp",
        ],
        cwd=_REPOSITORY,
    )
    records = [record for record in raw.split(b"\0") if record]
    assert len(records) == fixture["qualification_only"]["ordinary_source_files"] == 99
    assert all(
        record.split(b"\t", 1)[0].split()[:2]
        in ([b"100644", b"blob"], [b"100755", b"blob"])
        for record in records
    )


def test_m30_frozen_command_spells_every_independent_cap_explicitly(
    tmp_path: Path,
) -> None:
    fixture = _fixture()
    qualification = fixture["qualification_only"]
    text = _PREREG_PATH.read_text(encoding="utf-8")
    bash_blocks = re.findall(r"```bash\n(.*?)\n```", text, flags=re.DOTALL)
    assert len(bash_blocks) == 3
    for block in bash_blocks:
        syntax = subprocess.run(
            ["/bin/bash", "-n"],
            input=block,
            text=True,
            capture_output=True,
            check=False,
        )
        assert syntax.returncode == 0, syntax.stderr
    for block, delimiter in zip(
        bash_blocks[1:], ("M30_LAUNCH", "M30_POSTRUN"), strict=True
    ):
        assert block.startswith(
            'AUTHORIZED_M30_PREP_SHA="${AUTHORIZED_M30_PREP_SHA:'
            '?authorization must name exact reviewed prep commit}"\n'
            "/usr/bin/env -i \\"
        )
        assert f"/bin/bash --noprofile --norc <<'{delimiter}'" in block
        assert block.endswith(delimiter)
        assert "compgen -e" not in block

    poison = r"""
test() { /usr/bin/printf '%s\n' M30_INHERITED_FUNCTION_USED; return 0; }
read() { /usr/bin/printf '%s\n' M30_INHERITED_FUNCTION_USED; return 0; }
type() { /usr/bin/printf '%s\n' M30_INHERITED_FUNCTION_USED; return 0; }
compgen() { /usr/bin/printf '%s\n' M30_INHERITED_FUNCTION_USED; return 0; }
printf() { /usr/bin/printf '%s\n' M30_INHERITED_FUNCTION_USED; return 0; }
echo() { /usr/bin/printf '%s\n' M30_INHERITED_FUNCTION_USED; return 0; }
unset() { /usr/bin/printf '%s\n' M30_INHERITED_FUNCTION_USED; return 0; }
builtin() { /usr/bin/printf '%s\n' M30_INHERITED_FUNCTION_USED; return 0; }
export -f test read type compgen printf echo unset builtin
AUTHORIZED_M30_PREP_SHA=0000000000000000000000000000000000000000
"""
    for block in bash_blocks[1:]:
        injected = subprocess.run(
            ["/bin/bash", "--noprofile", "--norc"],
            input=poison + block,
            text=True,
            capture_output=True,
            cwd="/",
            timeout=10,
            check=False,
        )
        assert injected.returncode != 0
        assert "M30_INHERITED_FUNCTION_USED" not in (injected.stdout + injected.stderr)

    def embedded_python(function_name: str, next_function_name: str) -> str:
        section = text.split(f"{function_name}() {{", 1)[1].split(
            f"\n}}\n\n{next_function_name}() {{", 1
        )[0]
        marker = "/home/clawd/miniconda3/envs/claw/bin/python -S -B <<'PY'\n"
        start = section.index(marker) + len(marker)
        end = section.index("\nPY", start)
        return section[start:end]

    def run_embedded(script: str, *, environment: dict[str, str]) -> int:
        return subprocess.run(
            ["/home/clawd/miniconda3/envs/claw/bin/python", "-S", "-B"],
            input=script,
            text=True,
            capture_output=True,
            env=environment,
            check=False,
        ).returncode

    def producer(name: str, body: str) -> Path:
        path = tmp_path / name
        path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
        path.chmod(0o755)
        return path

    launch_process = embedded_python("m30_process_zero", "m30_untracked_gate")
    postrun_process = embedded_python(
        "m30_postrun_process_zero", "m30_postrun_untracked_gate"
    )
    process_environment = {"M30_LABEL": fixture["campaign_label"]}

    def process_result(script: str, fake_ps: Path) -> int:
        return run_embedded(
            script.replace('"/usr/bin/ps"', repr(str(fake_ps)), 1),
            environment=process_environment,
        )

    console_run = producer(
        "ps-console-run",
        "/usr/bin/printf '%s\\n' 'scion /usr/local/bin/scion run --problem fixture'\n",
    )
    console_audit = producer(
        "ps-console-audit",
        "/usr/bin/printf '%s\\n' "
        "'scion /usr/local/bin/scion audit-qualification-campaign /tmp/fixture'\n",
    )
    benign = producer(
        "ps-benign", "/usr/bin/printf '%s\\n' 'scion /usr/local/bin/scion status'\n"
    )
    failed_ps = producer("ps-failed", "exit 7\n")
    assert process_result(launch_process, console_run) != 0
    assert process_result(postrun_process, console_run) != 0
    assert process_result(launch_process, console_audit) == 0
    assert process_result(postrun_process, console_audit) != 0
    assert process_result(launch_process, benign) == 0
    assert process_result(postrun_process, benign) == 0
    assert process_result(launch_process, failed_ps) != 0
    assert process_result(postrun_process, failed_ps) != 0

    launch_untracked = embedded_python("m30_untracked_gate", "m30_tree_gate")
    postrun_untracked = embedded_python(
        "m30_postrun_untracked_gate", "m30_postrun_tree_gate"
    )

    def untracked_result(script: str, fake_git: Path) -> int:
        return run_embedded(
            script.replace('"/usr/bin/git"', repr(str(fake_git)), 1),
            environment={"REPO": str(tmp_path)},
        )

    allowed_git = producer(
        "git-allowed",
        "/usr/bin/printf "
        "'scion/docs/engineering/module-debt/"
        "v04-large-file-modularization-plan-20260629.md\\0"
        "scion/docs/planning/v0.5/plan.md\\0'\n",
    )
    unknown_git = producer("git-unknown", "/usr/bin/printf 'scion/json.py\\0'\n")
    ignored_pyc = producer(
        "git-ignored-pyc",
        "case \" $* \" in *' --ignored '*) "
        "/usr/bin/printf 'scion/json.pyc\\0' ;; esac\n",
    )
    ignored_cache_pyc = producer(
        "git-ignored-cache-pyc",
        "case \" $* \" in *' --ignored '*) "
        "/usr/bin/printf 'scion/scion/__pycache__/json.cpython-312.pyc\\0' ;; "
        "esac\n",
    )
    failed_git = producer("git-failed", "exit 7\n")
    for script in (launch_untracked, postrun_untracked):
        assert untracked_result(script, allowed_git) == 0
        assert untracked_result(script, unknown_git) != 0
        assert untracked_result(script, ignored_pyc) != 0
        assert untracked_result(script, ignored_cache_pyc) == 0
        assert untracked_result(script, failed_git) != 0
    expected_once = (
        "  --qualification-only \\",
        f"  --max-proposal-attempts {qualification['max_proposal_attempts']} \\",
        (
            "  --max-verified-candidate-chains "
            f"{qualification['max_verified_candidate_chains']} \\"
        ),
        (
            "  --max-formal-screening-stages "
            f"{qualification['max_formal_screening_stages']} \\"
        ),
        f"  --provider-call-cap {qualification['provider_call_cap']} \\",
        f"  --outer-hardwall-sec {qualification['outer_hardwall_sec']} \\",
        f"  --rounds {qualification['requested_rounds']} \\",
    )
    assert all(text.count(snippet) == 1 for snippet in expected_once)
    assert text.count("  --research-history ") == len(_M30_HISTORY_PATHS)
    assert str(_M30_INPUT) in text
    assert str(_M30_PROTOCOL) in text
    assert str(_M30_SPLIT) in text
    assert str(_M30_SEEDS) in text
    assert text.count("  audit-qualification-campaign \\") == 1
    assert (
        'M30_EXPECTATIONS="$REPO/scion/docs/experiments/v0.4/inputs/'
        'v04-cvrp-m30-fresh-development-qualification-only-qualification-expectation.json"'
    ) in text
    assert text.count("B30=5d282ea8e9133e0146c47588f2310c9bd2493e50") == 2
    assert '  --base-commit "$B30"\n)"' in text
    assert "QUALIFIED_FOR_NEW_FIXED_CANDIDATE_FUNNEL" in text
    assert "QUALIFICATION_CARRIER_UNAVAILABLE" in text
    assert text.count("/usr/bin/env -i \\") == 2
    assert text.count("/bin/bash --noprofile --norc <<'") == 2
    assert "PATH=/home/clawd/miniconda3/envs/claw/bin:/usr/bin:/bin" in text
    assert "GIT_NO_REPLACE_OBJECTS=1" in text
    assert text.count("PYTHONPYCACHEPREFIX=/dev/null") >= 7
    assert text.count('assert sys.pycache_prefix == "/dev/null"') == 2
    assert text.count('b"__pycache__" in lower.split(b"/")') == 2
    assert text.count('test "${#commit_line[@]}" -eq 2') == 2
    assert text.count('test "${commit_line[1]}" = "$B30"') == 2
    assert (
        text.count(
            'AUTHORIZED_M30_PREP_SHA="${AUTHORIZED_M30_PREP_SHA:'
            '?authorization must name exact reviewed prep commit}"'
        )
        == 4
    )
    assert 'test ! -e "$M30_CAMPAIGN_DIR" && test ! -L' in text
    assert 'test -d "$M30_CAMPAIGN_DIR" && test ! -L' in text
    assert text.count('"/usr/bin/git",') == 2
    assert text.count('"ls-files",') == 2
    assert (
        text.count(
            "scion/docs/engineering/module-debt/"
            "v04-large-file-modularization-plan-20260629.md"
        )
        == 2
    )
    assert text.count('allowed_prefix = b"scion/docs/planning/v0.5/"') == 2
    assert text.count("\nm30_tree_gate\n") == 3
    assert text.count("\nm30_postrun_tree_gate\n") == 2
    assert text.count("\nm30_postrun_origin_gate\n") == 2
    assert "m30_tree_gate\nset +e\n(\ncd /\nenv -i \\" in text
    assert (
        "M30_EXPECTATIONS_SHA256="
        "4141167ecd1dfca46299940716f4e81ccaba26682240fd7e991a08615662ed57"
    ) in text
    audit_command = 'M30_AUDIT_STDOUT="$(\n  cd /\n  env -i \\'
    assert audit_command in text
    assert text.index(
        "m30_postrun_tree_gate\nm30_postrun_origin_gate\nset +e"
    ) < text.index(audit_command)
    assert text.index("M30_AUDIT_EXIT=$?") < text.index(
        "m30_postrun_tree_gate\nm30_postrun_origin_gate\nif test"
    )
    for process_pattern in (
        "run_.*candidate.*[.]py",
        "run_cvrp_controlled_e2e[.]py",
        r"\S*/solver[.]py",
        _fixture()["campaign_label"],
    ):
        assert process_pattern in text
    for module_name in (
        "scion.core.campaign",
        "scion.core.explore_step.pipeline",
        "scion.core.resource_envelope",
        "scion.problem.bridge",
        "scion.problem.loader",
        "scion.problems.cvrp.adapter",
        "scion.runtime.runner",
    ):
        assert f'"{module_name}"' in text
    assert "ResourceEnvelope(provider_call_cap=60, outer_hardwall_sec=28000)" in text
    assert "0|20|21|22|124" in text
