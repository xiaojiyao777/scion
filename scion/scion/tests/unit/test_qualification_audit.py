"""Synthetic-only tests for the generic postrun qualification auditor."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

import scion.postrun.handoff as handoff_module
import scion.postrun.handoff.qualification_audit as qualification_audit_module
from scion.cli.app import app
from scion.postrun.handoff import (
    QUALIFIED_TOKEN,
    UNAVAILABLE_TOKEN,
    QualificationAuditUnavailable,
    audit_qualification_campaign,
    load_qualification_audit_expectation,
)
from scion.runtime.workspace import WorkspaceMaterializer


@dataclass(frozen=True)
class SyntheticCampaign:
    campaign: Path
    repository: Path
    revision: str
    expectations: Path

    @property
    def candidate(self) -> Path:
        return self.campaign / "candidate_workspaces" / "candidate-ready"


def _json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_history(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )


def _read_history(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def _git(repository: Path, *arguments: str) -> str:
    return subprocess.check_output(
        ["git", *arguments], cwd=repository, text=True
    ).strip()


def _commit(repository: Path, message: str) -> str:
    subprocess.run(["git", "add", "pkg"], cwd=repository, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=synthetic",
            "-c",
            "user.email=synthetic@example.invalid",
            "commit",
            "-qm",
            message,
        ],
        cwd=repository,
        check=True,
    )
    return _git(repository, "rev-parse", "HEAD")


def _synthetic_root(tmp_path: Path) -> SyntheticCampaign:
    repository = tmp_path / "repo"
    source = repository / "pkg"
    (source / "policies").mkdir(parents=True)
    _json(
        source / "problem.yaml",
        {
            "name": "generic_demo",
            "operator_categories": ["generic"],
            "search_space": {
                "editable": ["policies/*.py"],
                "frozen": ["policies/frozen.py"],
                "import_whitelist": [],
            },
        },
    )
    (source / "policies" / "baseline.py").write_text("VALUE = 0\n", encoding="utf-8")
    (source / "policies" / "frozen.py").write_text("LOCKED = True\n", encoding="utf-8")
    (source / "opaque").mkdir()
    (source / "opaque" / "payload.bin").write_bytes(b"opaque synthetic bytes\x00\xff")
    (source / "module.py").write_text("UNCHANGED = 7\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
    revision = _commit(repository, "synthetic source")

    campaign = tmp_path / "campaign"
    candidate = campaign / "candidate_workspaces" / "candidate-ready"
    candidate.parent.mkdir(parents=True)
    shutil.copytree(source, candidate)
    (candidate / "policies" / "baseline.py").write_text("VALUE = 1\n", encoding="utf-8")
    materializer = WorkspaceMaterializer(
        str(tmp_path / "hashing"),
        frozen_patterns=frozenset({"policies/frozen.py"}),
        editable_patterns=["policies/*.py"],
    )
    code_hash = materializer.compute_code_hash(str(candidate))
    historical = candidate.parent / "candidate-historical"
    shutil.copytree(source, historical)
    (historical / "policies" / "baseline.py").write_text(
        "VALUE = 2\n", encoding="utf-8"
    )
    expectations = tmp_path / "expectations.json"
    _json(
        expectations,
        {
            "schema_version": "scion.qualification_audit_expectation.v1",
            "base_revision": revision,
            "source": {
                "prefix": "pkg",
                "file_count": 5,
                "hash_spec_path": "problem.yaml",
                "ignored_directory_names": ["__pycache__", ".pytest_cache"],
                "ignored_suffixes": [".pyc"],
            },
            "qualification": {
                "limits": {
                    "max_proposal_attempts": 7,
                    "max_verified_candidate_chains": 5,
                    "max_formal_screening_stages": 5,
                },
                "formal_stage": "screening",
                "required_action": "modify",
                "stop_reason": "synthetic_boundary_reached",
                "ready_disposition": "synthetic_postrun_audit_ready",
                "protocol_stages": ["screening", "review", "sealed"],
                "forbidden_stages": ["review", "sealed"],
                "zero_metrics": ["constraint_debt"],
            },
            "screening": [
                {
                    "case_ids": ["alpha", "beta"],
                    "seed_set": [7, 9],
                    "valid_pairs": 4,
                    "gate_outcome": "expand",
                    "decision": "expand_screening",
                    "require_contract_verification": True,
                },
                {
                    "case_ids": ["alpha", "beta", "gamma"],
                    "seed_set": [7, 9, 11],
                    "valid_pairs": 9,
                    "gate_outcome": "pass",
                    "decision": "queue_validate",
                    "require_contract_verification": False,
                },
            ],
        },
    )
    _write_artifacts(campaign, code_hash)
    _make_readonly(candidate)
    _make_readonly(historical)
    (campaign / "scion.db").chmod(0o444)
    return SyntheticCampaign(campaign, repository, revision, expectations)


def _summary_protocol(
    cases: list[str], seeds: list[int], pairs: int, gate: str
) -> dict[str, Any]:
    return {
        "stage": "screening",
        "case_ids": cases,
        "seed_set": seeds,
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
                "metric_name": "constraint_debt",
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
        "selected_surface": "generic_surface",
    }


def _history_protocol(gate: str) -> dict[str, Any]:
    return {
        "candidate_composition": {
            "attribution_scope": "cumulative_branch_candidate",
            "protocol_comparison_scope": "candidate_vs_champion",
            "evaluation_candidate": "branch_state_after_current_step_patch",
            "current_step_change_scope": "incremental_patch",
            "incremental_effect_isolated": False,
            "current_step": {"target_files": ["policies/baseline.py"]},
        },
        "evidence": {
            "stage": "screening",
            "protocol_outcome": {"gate_outcome": gate, "reason_codes": []},
            "case_outcomes": {"case_feedback": []},
        },
    }


def _history_hypothesis(
    *, text: str = "synthetic candidate", target: str = "policies/baseline.py"
) -> dict[str, Any]:
    return {
        "text": text,
        "change_locus": "generic_surface",
        "action": "modify",
        "target_file": target,
        "predicted_direction": "exploratory",
        "target_weakness": "synthetic weakness",
        "expected_effect": "synthetic effect",
        "suggested_weight": None,
    }


def _summary_hypothesis(
    *, text: str = "synthetic candidate", target: str = "policies/baseline.py"
) -> dict[str, Any]:
    hypothesis = _history_hypothesis(text=text, target=target)
    return {
        key: hypothesis[key]
        for key in ("text", "action", "change_locus", "target_file")
    }


def _history_record(
    gate: str,
    decision: str,
    *,
    text: str = "synthetic candidate",
    source: str = "VALUE = 1\n",
) -> dict[str, Any]:
    return {
        "schema_version": "scion.research_history.step.v1",
        "problem_id": "generic_demo",
        "hypothesis": _history_hypothesis(text=text),
        "patch": {
            "changes": [
                {
                    "file_path": "policies/baseline.py",
                    "action": "modify",
                    "source": source,
                }
            ]
        },
        "outcome": {
            "outcome": "evaluated",
            "stage": "screening",
            "reason_code": "EVALUATION_COMPLETED",
        },
        "protocol": _history_protocol(gate),
        "decision": {
            "value": decision,
            "reason_codes": [],
            "engine_reason_codes": [],
            "diagnostic_reason_codes": [],
            "bypass_reason_codes": [],
        },
    }


def _branch_row(
    branch_id: str,
    state: str,
    current_code_hash: str | None,
) -> dict[str, Any]:
    return {
        "id": branch_id,
        "state": state,
        "base_champion_id": "synthetic-champion",
        "current_code_hash": current_code_hash,
        "weight_revision": 0,
        "direction": None,
        "failure_codes": [],
        "created_at": "2026-08-24T00:00:00",
        "updated_at": "2026-08-24T00:00:01",
    }


def _write_artifacts(campaign: Path, code_hash: str) -> None:
    run = {
        "status": "completed",
        "evaluated_rounds": 4,
        "scheduled_calls": 7,
        "formal_screened_candidates": 4,
        "stop_reason": "synthetic_boundary_reached",
        "run_validity": {"valid": True, "status": "valid", "reason": "valid"},
        "protocol_stage_counts": {"screening": 4, "review": 0, "sealed": 0},
        "unknown_outcome_count": 0,
        "execution_outcome_counts": {
            "evaluated": 6,
            "research_rejected": 1,
            "not_evaluated": 0,
            "blocked_infra": 0,
            "resource_exhausted": 0,
            "interrupted": 0,
        },
        "last_execution_outcome": {
            "outcome": "evaluated",
            "reason_code": "EVALUATION_COMPLETED",
            "stage": "screening",
        },
        "qualification": {
            "mode": "qualification_only",
            "limits": {
                "max_proposal_attempts": 7,
                "max_verified_candidate_chains": 5,
                "max_formal_screening_stages": 5,
            },
            "proposal_attempts": 5,
            "verified_candidate_chains": 4,
            "formal_screening_stages": 4,
            "initial_screening_stages": 3,
            "expanded_screening_stages": 1,
            "disposition": "synthetic_postrun_audit_ready",
        },
    }
    outcome = {
        "outcome": "evaluated",
        "reason_code": "EVALUATION_COMPLETED",
        "detail": "",
        "provenance": {"stage": "screening"},
    }
    negative_protocol = _summary_protocol(["alpha", "beta"], [7, 9], 4, "fail")
    negative_protocol.update(
        valid_pairs=3,
        failed_pairs=1,
        candidate_failed_pairs=1,
    )
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
        {
            "branch_id": "negative",
            "hypothesis": _summary_hypothesis(text="negative candidate"),
            "protocol_result": None,
            "decision": "abandon",
            "contract_passed": True,
            "verification_passed": True,
            "failure_stage": "canary",
            "canary_result": {
                "passed": False,
                "failure_category": "candidate_failure",
            },
            "execution_outcome": {
                "outcome": "evaluated",
                "reason_code": "EVALUATION_COMPLETED",
                "detail": "",
                "provenance": {"stage": "screening"},
            },
        },
        {
            "branch_id": "expanded-negative",
            "hypothesis": _summary_hypothesis(text="expanded failure candidate"),
            "protocol_result": _summary_protocol(
                ["alpha", "beta"], [7, 9], 4, "expand"
            ),
            "decision": "expand_screening",
            "contract_passed": True,
            "verification_passed": True,
            "canary_result": {"passed": True},
            "execution_outcome": outcome,
        },
        {
            "branch_id": "expanded-negative",
            "hypothesis": _summary_hypothesis(text="expanded failure candidate"),
            "protocol_result": None,
            "decision": "abandon",
            "contract_passed": None,
            "verification_passed": None,
            "failure_stage": "canary",
            "canary_result": {
                "passed": False,
                "failure_category": "candidate_failure",
            },
            "execution_outcome": {
                "outcome": "evaluated",
                "reason_code": "EVALUATION_COMPLETED",
                "detail": "",
                "provenance": {"stage": "screening"},
            },
        },
        {
            "branch_id": "sibling",
            "hypothesis": _summary_hypothesis(text="sibling candidate"),
            "protocol_result": negative_protocol,
            "decision": "continue_explore",
            "contract_passed": True,
            "verification_passed": True,
            "canary_result": {"passed": True},
            "execution_outcome": outcome,
        },
        {
            "branch_id": "ready",
            "hypothesis": _summary_hypothesis(),
            "protocol_result": _summary_protocol(
                ["alpha", "beta"], [7, 9], 4, "expand"
            ),
            "decision": "expand_screening",
            "contract_passed": True,
            "verification_passed": True,
            "canary_result": {"passed": True},
            "execution_outcome": outcome,
        },
        {
            "branch_id": "ready",
            "hypothesis": _summary_hypothesis(),
            "protocol_result": _summary_protocol(
                ["alpha", "beta", "gamma"], [7, 9, 11], 9, "pass"
            ),
            "decision": "queue_validate",
            "contract_passed": None,
            "verification_passed": None,
            "canary_result": {"passed": True},
            "execution_outcome": outcome,
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
            "problem_id": "generic_demo",
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
        {
            **_history_record(
                "unused",
                "abandon",
                text="negative candidate",
                source="VALUE = -1\n",
            ),
            "outcome": {
                "outcome": "evaluated",
                "stage": "canary",
                "reason_code": "EVALUATION_COMPLETED",
            },
            "protocol": None,
        },
        _history_record(
            "expand",
            "expand_screening",
            text="expanded failure candidate",
            source="VALUE = 3\n",
        ),
        {
            **_history_record(
                "unused",
                "abandon",
                text="expanded failure candidate",
                source="VALUE = 3\n",
            ),
            "outcome": {
                "outcome": "evaluated",
                "stage": "canary",
                "reason_code": "EVALUATION_COMPLETED",
            },
            "protocol": None,
        },
        _history_record(
            "fail",
            "continue_explore",
            text="sibling candidate",
            source="VALUE = 2\n",
        ),
        _history_record("expand", "expand_screening"),
        _history_record("pass", "queue_validate"),
    ]
    branches = [
        _branch_row("negative", "parked_lineage", None),
        _branch_row("expanded-negative", "parked_lineage", None),
        _branch_row("sibling", "parked_lineage", None),
        _branch_row("ready", "ready_validate", code_hash),
    ]
    _json(
        campaign / "status.json",
        {
            "campaign_mode": "qualification_only",
            "n_experiments": 4,
            "screened_experiments": 4,
            "n_steps": 7,
            "total_rounds": 7,
            "n_active_branches": 1,
            "active_slots": {
                "used": 1,
                "max": 4,
                "available": 3,
                "branch_ids": ["ready"],
            },
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
    _json(
        campaign / "campaign_summary.json",
        {
            "campaign_mode": "qualification_only",
            "n_experiments": 4,
            "screened_experiments": 4,
            "n_steps": 7,
            "total_rounds": 7,
            "n_active_branches": 1,
            "active_slots": {
                "used": 1,
                "max": 4,
                "available": 3,
                "branch_ids": ["ready"],
            },
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
            ),
            (
                "experiment",
                "negative",
                "b" * 64,
                "modify",
                "policies/baseline.py",
                "negative candidate",
                "passed",
                "passed",
                "failed",
                "",
                "abandon",
            ),
            (
                "experiment",
                "expanded-negative",
                "d" * 64,
                "modify",
                "policies/baseline.py",
                "expanded failure candidate",
                "passed",
                "passed",
                "passed",
                "screening",
                "expand_screening",
            ),
            (
                "experiment",
                "expanded-negative",
                "d" * 64,
                "modify",
                "policies/baseline.py",
                "expanded failure candidate",
                "not_run",
                "not_run",
                "failed",
                "",
                "abandon",
            ),
            (
                "experiment",
                "sibling",
                "c" * 64,
                "modify",
                "policies/baseline.py",
                "sibling candidate",
                "passed",
                "passed",
                "passed",
                "screening",
                "continue_explore",
            ),
            (
                "experiment",
                "ready",
                code_hash,
                "modify",
                "policies/baseline.py",
                "synthetic candidate",
                "passed",
                "passed",
                "passed",
                "screening",
                "expand_screening",
            ),
            (
                "experiment",
                "ready",
                code_hash,
                "modify",
                "policies/baseline.py",
                "synthetic candidate",
                "not_run",
                "not_run",
                "passed",
                "screening",
                "queue_validate",
            ),
        )
        for row in rows:
            connection.execute(
                "INSERT INTO experiment_events "
                "(event_kind, branch_id, code_hash, patch_action, patch_file, "
                "hypothesis_text, contract_result, verification_result, "
                "canary_result, stage, decision) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                row,
            )
        connection.execute(
            "UPDATE experiment_events SET decision_reason = '[]' "
            "WHERE event_kind = 'experiment'"
        )
        connection.execute(
            "UPDATE experiment_events SET execution_outcome = 'research_rejected', "
            "execution_outcome_reason_code = 'SYNTHETIC_ABSTAINED' WHERE rowid = 1"
        )


def _make_readonly(root: Path) -> None:
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        path.chmod(0o555 if path.is_dir() else 0o444)
    root.chmod(0o555)


def _audit(fixture: SyntheticCampaign, *, revision: str | None = None) -> str:
    return audit_qualification_campaign(
        fixture.campaign,
        expectation=load_qualification_audit_expectation(fixture.expectations),
        repository=fixture.repository,
        base_revision=fixture.revision if revision is None else revision,
    )


def _mutate_json(path: Path, mutate: Any) -> None:
    value = _read_json(path)
    mutate(value)
    _json(path, value)


def _mutate_both_run_results(fixture: SyntheticCampaign, mutate: Any) -> None:
    for name in ("status.json", "campaign_summary.json"):
        _mutate_json(
            fixture.campaign / name,
            lambda value: mutate(value["run_result"]),
        )


def _sync_active_slots(value: dict[str, Any]) -> None:
    active_ids = [
        branch["id"]
        for branch in value["branches"]
        if branch["state"] in {"explore", "ready_validate"}
    ]
    maximum = value["active_slots"]["max"]
    value["n_active_branches"] = len(active_ids)
    value["active_slots"] = {
        "used": len(active_ids),
        "max": maximum,
        "available": maximum - len(active_ids),
        "branch_ids": active_ids,
    }


def _set_patch_target(fixture: SyntheticCampaign, target: str, source: str) -> None:
    history_path = fixture.campaign / "research_history.jsonl"
    records = _read_history(history_path)
    for record in records[-2:]:
        record["hypothesis"]["target_file"] = target
        record["patch"]["changes"][0]["file_path"] = target
        record["patch"]["changes"][0]["source"] = source
        record["protocol"]["candidate_composition"]["current_step"]["target_files"] = [
            target
        ]
    _write_history(history_path, records)
    _mutate_json(
        fixture.campaign / "campaign_summary.json",
        lambda value: [
            step["hypothesis"].update(target_file=target)
            for step in value["steps"][-2:]
        ],
    )


def _database_update(
    fixture: SyntheticCampaign,
    statement: str,
    parameters: tuple[Any, ...] = (),
) -> None:
    database = fixture.campaign / "scion.db"
    database.chmod(0o644)
    with sqlite3.connect(database) as connection:
        connection.execute(statement, parameters)
    database.chmod(0o444)


def _database_swap_rows(fixture: SyntheticCampaign, first: int, second: int) -> None:
    database = fixture.campaign / "scion.db"
    database.chmod(0o644)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE experiment_events SET rowid = -1 WHERE rowid = ?", (first,)
        )
        connection.execute(
            "UPDATE experiment_events SET rowid = ? WHERE rowid = ?",
            (first, second),
        )
        connection.execute(
            "UPDATE experiment_events SET rowid = ? WHERE rowid = -1",
            (second,),
        )
    database.chmod(0o444)


def _replace_expanded_negative_dispatch_with_formal(
    fixture: SyntheticCampaign,
    *,
    gate: str,
    decision: str,
    candidate_failure: bool = False,
    runtime_guard_code: str | None = None,
) -> None:
    def replace_step(value: dict[str, Any]) -> None:
        protocol = _summary_protocol(
            ["alpha", "beta", "gamma"],
            [7, 9, 11],
            9,
            gate,
        )
        if candidate_failure:
            protocol.update(
                valid_pairs=8,
                failed_pairs=1,
                candidate_failed_pairs=1,
            )
        value["steps"][3].update(
            protocol_result=protocol,
            decision=decision,
            failure_stage=None,
            canary_result={"passed": True},
        )
        if runtime_guard_code is not None:
            value["steps"][3]["decision_reason_codes"] = [runtime_guard_code]
            protocol["decision_reason_codes"] = [runtime_guard_code]

    _mutate_json(fixture.campaign / "campaign_summary.json", replace_step)
    history_path = fixture.campaign / "research_history.jsonl"
    records = _read_history(history_path)
    records[3] = _history_record(
        gate,
        decision,
        text="expanded failure candidate",
        source="VALUE = 3\n",
    )
    if runtime_guard_code is not None:
        records[3]["decision"]["reason_codes"] = [runtime_guard_code]
    _write_history(history_path, records)
    _database_update(
        fixture,
        "UPDATE experiment_events SET canary_result = 'passed', "
        "stage = 'screening', decision = ?, decision_reason = ? WHERE rowid = 4",
        (decision, json.dumps([runtime_guard_code] if runtime_guard_code else [])),
    )

    def update_run(run: dict[str, Any]) -> None:
        run["evaluated_rounds"] = 5
        run["formal_screened_candidates"] = 5
        run["protocol_stage_counts"]["screening"] = 5
        run["qualification"]["formal_screening_stages"] = 5
        run["qualification"]["expanded_screening_stages"] = 2

    _mutate_both_run_results(fixture, update_run)
    for name in ("status.json", "campaign_summary.json"):
        _mutate_json(
            fixture.campaign / name,
            lambda value: value.update(n_experiments=5, screened_experiments=5),
        )


def _set_preformal_decision(
    fixture: SyntheticCampaign,
    decision: str,
) -> None:
    _mutate_json(
        fixture.campaign / "campaign_summary.json",
        lambda value: value["steps"][0].update(decision=decision),
    )
    history_path = fixture.campaign / "research_history.jsonl"
    records = _read_history(history_path)
    records[0]["decision"] = {
        "value": decision,
        "reason_codes": [],
        "engine_reason_codes": [],
        "diagnostic_reason_codes": [],
        "bypass_reason_codes": [],
    }
    _write_history(history_path, records)
    _database_update(
        fixture,
        "UPDATE experiment_events SET event_kind = 'experiment', decision = ? "
        "WHERE rowid = 1",
        (decision,),
    )


def _apply_mutation(fixture: SyntheticCampaign, mutation: str) -> str | None:
    candidate = fixture.candidate
    if mutation == "base_mismatch":
        return fixture.revision[:-1] + ("0" if fixture.revision[-1] != "0" else "1")
    if mutation == "base_noncommit":
        blob = _git(fixture.repository, "rev-parse", "HEAD:pkg/module.py")
        _mutate_json(
            fixture.expectations,
            lambda value: value.update(base_revision=blob),
        )
        return blob
    if mutation == "prefix_missing":
        _mutate_json(
            fixture.expectations,
            lambda value: value["source"].update(prefix="pkg/missing"),
        )
    elif mutation == "source_count":
        _mutate_json(
            fixture.expectations,
            lambda value: value["source"].update(file_count=6),
        )
    elif mutation == "prefix_noncanonical":
        _mutate_json(
            fixture.expectations,
            lambda value: value["source"].update(prefix="pkg/../pkg"),
        )
    elif mutation == "screening_cartesian_schema":
        _mutate_json(
            fixture.expectations,
            lambda value: value["screening"][0].update(valid_pairs=3),
        )
    elif mutation == "candidate_root_writable":
        candidate.chmod(0o755)
    elif mutation == "candidate_nested_writable":
        (candidate / "module.py").chmod(0o644)
    elif mutation == "ignored_symlink":
        candidate.chmod(0o755)
        (candidate / "__pycache__").symlink_to(candidate / "policies")
        candidate.chmod(0o555)
    elif mutation == "ignored_nonregular":
        candidate.chmod(0o755)
        path = candidate / "cache.pyc"
        os.mkfifo(path, mode=0o444)
        path.chmod(0o444)
        candidate.chmod(0o555)
    elif mutation == "baseline_bytes":
        (fixture.repository / "pkg" / "module.py").write_text(
            "UNCHANGED = 8\n", encoding="utf-8"
        )
        revision = _commit(fixture.repository, "mutated baseline")
        _mutate_json(
            fixture.expectations,
            lambda value: value.update(base_revision=revision),
        )
        return revision
    elif mutation == "candidate_bytes":
        path = candidate / "module.py"
        path.chmod(0o644)
        path.write_text("UNCHANGED = 8\n", encoding="utf-8")
        path.chmod(0o444)
    elif mutation == "candidate_source_set":
        candidate.chmod(0o755)
        (candidate / "extra.txt").write_text("extra\n", encoding="utf-8")
        (candidate / "extra.txt").chmod(0o444)
        candidate.chmod(0o555)
    elif mutation == "duplicate_artifact_key":
        path = fixture.campaign / "status.json"
        raw = path.read_text(encoding="utf-8")
        path.write_text(raw.replace("{", '{"n_steps": 2,', 1), encoding="utf-8")
    elif mutation == "duplicate_zero_metric":
        _mutate_json(
            fixture.campaign / "campaign_summary.json",
            lambda value: value["steps"][5]["protocol_result"]["metric_stats"].append(
                dict(value["steps"][5]["protocol_result"]["metric_stats"][0])
            ),
        )
    elif mutation == "nonzero_metric":
        _mutate_json(
            fixture.campaign / "campaign_summary.json",
            lambda value: value["steps"][5]["protocol_result"]["metric_stats"][
                0
            ].update(median_delta=1),
        )
    elif mutation == "branch_projection":
        _mutate_json(
            fixture.campaign / "campaign_summary.json",
            lambda value: value["branches"][0].update(state="archived"),
        )
    elif mutation == "ready_hash_missing":
        for name in ("status.json", "campaign_summary.json"):
            _mutate_json(
                fixture.campaign / name,
                lambda value: value["branches"][-1].update(current_code_hash=None),
            )
    elif mutation == "ready_hash_malformed":
        for name in ("status.json", "campaign_summary.json"):
            _mutate_json(
                fixture.campaign / name,
                lambda value: value["branches"][-1].update(
                    current_code_hash="not-a-digest"
                ),
            )
    elif mutation == "parked_hash_retained":
        for name in ("status.json", "campaign_summary.json"):
            _mutate_json(
                fixture.campaign / name,
                lambda value: value["branches"][0].update(current_code_hash="b" * 64),
            )
    elif mutation == "explore_hash_retained":
        for name in ("status.json", "campaign_summary.json"):

            def add_hashed_explore(value: dict[str, Any]) -> None:
                value["branches"].append(
                    _branch_row("hashed-explore", "explore", "e" * 64)
                )
                _sync_active_slots(value)

            _mutate_json(fixture.campaign / name, add_hashed_explore)
    elif mutation == "branch_row_shape":
        for name in ("status.json", "campaign_summary.json"):
            _mutate_json(
                fixture.campaign / name,
                lambda value: value["branches"][0].pop("direction"),
            )
    elif mutation == "campaign_mode_tamper":
        for name in ("status.json", "campaign_summary.json"):
            _mutate_json(
                fixture.campaign / name,
                lambda value: value.update(campaign_mode="ordinary"),
            )
    elif mutation == "n_experiments_tamper":
        for name in ("status.json", "campaign_summary.json"):
            _mutate_json(
                fixture.campaign / name,
                lambda value: value.update(n_experiments=3),
            )
    elif mutation == "screened_experiments_tamper":
        for name in ("status.json", "campaign_summary.json"):
            _mutate_json(
                fixture.campaign / name,
                lambda value: value.update(screened_experiments=3),
            )
    elif mutation == "active_slots_tamper":
        for name in ("status.json", "campaign_summary.json"):
            _mutate_json(
                fixture.campaign / name,
                lambda value: value["active_slots"].update(
                    used=0,
                    available=4,
                    branch_ids=[],
                ),
            )
    elif mutation == "total_rounds":
        for name in ("status.json", "campaign_summary.json"):
            _mutate_json(
                fixture.campaign / name,
                lambda value: value.update(total_rounds=8),
            )
    elif mutation == "missing_round":
        _mutate_json(
            fixture.campaign / "campaign_summary.json",
            lambda value: value["steps"][2].pop("round"),
        )
    elif mutation == "out_of_order_round":
        _mutate_json(
            fixture.campaign / "campaign_summary.json",
            lambda value: value["steps"][2].update(round=2),
        )
    elif mutation == "scheduled_calls":
        _mutate_both_run_results(
            fixture,
            lambda run: run.update(scheduled_calls=6),
        )
    elif mutation == "evaluated_rounds":
        _mutate_both_run_results(
            fixture,
            lambda run: run.update(evaluated_rounds=3),
        )
    elif mutation == "formal_screened_candidates":
        _mutate_both_run_results(
            fixture,
            lambda run: run.update(formal_screened_candidates=3),
        )
    elif mutation == "execution_outcome_counts":
        _mutate_both_run_results(
            fixture,
            lambda run: run["execution_outcome_counts"].update(evaluated=5),
        )
    elif mutation == "last_execution_outcome":
        _mutate_both_run_results(
            fixture,
            lambda run: run["last_execution_outcome"].update(reason_code="TAMPERED"),
        )
    elif mutation == "last_result_shape":
        _mutate_json(
            fixture.campaign / "status.json",
            lambda value: value["last_result"].update(action=""),
        )
    elif mutation == "formal_counts":

        def mutate(run: dict[str, Any]) -> None:
            run["protocol_stage_counts"]["screening"] = 5
            run["qualification"]["formal_screening_stages"] = 5
            run["qualification"]["initial_screening_stages"] = 4

        _mutate_both_run_results(fixture, mutate)
    elif mutation == "proposal_attempts_tamper":
        _mutate_both_run_results(
            fixture,
            lambda run: run["qualification"].update(proposal_attempts=3),
        )
    elif mutation == "verified_chains_tamper":
        _mutate_both_run_results(
            fixture,
            lambda run: run["qualification"].update(verified_candidate_chains=2),
        )
    elif mutation == "formal_shape_tamper":
        _mutate_json(
            fixture.campaign / "campaign_summary.json",
            lambda value: value["steps"][4].update(verification_passed=None),
        )
    elif mutation == "verified_branch_duplicate":
        _mutate_json(
            fixture.campaign / "campaign_summary.json",
            lambda value: value["steps"][4].update(branch_id="negative"),
        )
    elif mutation == "retired_negative_branch_reused":
        _mutate_json(
            fixture.campaign / "campaign_summary.json",
            lambda value: value["steps"][4].update(branch_id="negative"),
        )
        _database_update(
            fixture,
            "UPDATE experiment_events SET branch_id = 'negative' WHERE rowid = 5",
        )
        _mutate_both_run_results(
            fixture,
            lambda run: run["qualification"].update(verified_candidate_chains=3),
        )
        for name in ("status.json", "campaign_summary.json"):

            def retire_sibling(value: dict[str, Any]) -> None:
                value["branches"][2].update(state="explore")
                _sync_active_slots(value)

            _mutate_json(fixture.campaign / name, retire_sibling)
    elif mutation == "orphan_formal_expansion":
        _mutate_json(
            fixture.campaign / "campaign_summary.json",
            lambda value: value["steps"][4].update(
                contract_passed=None,
                verification_passed=None,
            ),
        )

        def mutate_orphan(run: dict[str, Any]) -> None:
            run["qualification"]["verified_candidate_chains"] = 3
            run["qualification"]["initial_screening_stages"] = 2
            run["qualification"]["expanded_screening_stages"] = 2

        _mutate_both_run_results(fixture, mutate_orphan)
    elif mutation == "interleaved_expansion_dispatch":

        def swap_steps(value: dict[str, Any]) -> None:
            value["steps"][3], value["steps"][4] = (
                value["steps"][4],
                value["steps"][3],
            )
            value["steps"][3]["round"] = 4
            value["steps"][4]["round"] = 5

        _mutate_json(fixture.campaign / "campaign_summary.json", swap_steps)
        history_path = fixture.campaign / "research_history.jsonl"
        records = _read_history(history_path)
        records[3], records[4] = records[4], records[3]
        _write_history(history_path, records)
        _database_swap_rows(fixture, 4, 5)
    elif mutation == "expansion_candidate_mismatch":
        history_path = fixture.campaign / "research_history.jsonl"
        records = _read_history(history_path)
        records[3]["patch"]["changes"][0]["source"] = "VALUE = 4\n"
        _write_history(history_path, records)
    elif mutation == "null_h_expansion_dispatch":

        def replace_dispatch(value: dict[str, Any]) -> None:
            value["steps"][3].update(
                hypothesis=None,
                protocol_result=None,
                decision=None,
                contract_passed=None,
                verification_passed=None,
                failure_stage="proposal_hypothesis",
                canary_result=None,
                execution_outcome={
                    "outcome": "research_rejected",
                    "reason_code": "SYNTHETIC_ABSTAINED",
                    "detail": "",
                    "provenance": {"stage": "proposal_hypothesis"},
                },
            )

        _mutate_json(fixture.campaign / "campaign_summary.json", replace_dispatch)
        history_path = fixture.campaign / "research_history.jsonl"
        records = _read_history(history_path)
        records[3] = {
            "schema_version": "scion.research_history.step.v1",
            "problem_id": "generic_demo",
            "hypothesis": None,
            "patch": None,
            "outcome": {
                "outcome": "research_rejected",
                "stage": "proposal_hypothesis",
                "reason_code": "SYNTHETIC_ABSTAINED",
            },
            "protocol": None,
            "decision": None,
        }
        _write_history(history_path, records)
        _database_update(
            fixture,
            "UPDATE experiment_events SET "
            "event_kind = 'proposal_execution_outcome', code_hash = NULL, "
            "patch_action = NULL, patch_file = NULL, hypothesis_text = NULL, "
            "contract_result = NULL, verification_result = NULL, "
            "canary_result = NULL, stage = 'proposal_hypothesis', "
            "decision = NULL, execution_outcome = 'research_rejected', "
            "execution_outcome_reason_code = 'SYNTHETIC_ABSTAINED' "
            "WHERE rowid = 4",
        )

        def update_outcomes(run: dict[str, Any]) -> None:
            run["execution_outcome_counts"]["evaluated"] = 5
            run["execution_outcome_counts"]["research_rejected"] = 2

        _mutate_both_run_results(fixture, update_outcomes)
    elif mutation == "wrong_formal_population":
        _mutate_json(
            fixture.campaign / "campaign_summary.json",
            lambda value: value["steps"][4]["protocol_result"].update(
                case_ids=["heldout-alpha", "heldout-beta"]
            ),
        )
    elif mutation == "formal_pair_accounting":
        _mutate_json(
            fixture.campaign / "campaign_summary.json",
            lambda value: value["steps"][4]["protocol_result"].update(valid_pairs=4),
        )
    elif mutation == "formal_gate_decision_mismatch":
        _mutate_json(
            fixture.campaign / "campaign_summary.json",
            lambda value: value["steps"][4]["protocol_result"].update(
                gate_outcome="pass"
            ),
        )
        history_path = fixture.campaign / "research_history.jsonl"
        records = _read_history(history_path)
        records[4]["protocol"]["evidence"]["protocol_outcome"]["gate_outcome"] = "pass"
        _write_history(history_path, records)
    elif mutation == "other_qualifier":
        _replace_expanded_negative_dispatch_with_formal(
            fixture,
            gate="pass",
            decision="queue_validate",
        )
    elif mutation == "formal_abandon_without_safety":
        _replace_expanded_negative_dispatch_with_formal(
            fixture,
            gate="pass",
            decision="abandon",
        )
    elif mutation == "runtime_guard_reason_mismatch":
        _replace_expanded_negative_dispatch_with_formal(
            fixture,
            gate="pass",
            decision="abandon",
            runtime_guard_code="RUNTIME_GUARD_FAILED",
        )
        history_path = fixture.campaign / "research_history.jsonl"
        records = _read_history(history_path)
        records[3]["decision"]["reason_codes"] = []
        _write_history(history_path, records)
    elif mutation == "formal_decision_reason_mismatch":
        history_path = fixture.campaign / "research_history.jsonl"
        records = _read_history(history_path)
        records[4]["decision"]["reason_codes"] = ["SYNTHETIC_MISMATCH"]
        _write_history(history_path, records)
    elif mutation == "lineage_decision_reason_mismatch":
        _database_update(
            fixture,
            "UPDATE experiment_events SET decision_reason = ? WHERE rowid = 5",
            (json.dumps(["SYNTHETIC_MISMATCH"]),),
        )
    elif mutation == "synchronized_runtime_guard_without_lineage":
        _replace_expanded_negative_dispatch_with_formal(
            fixture,
            gate="pass",
            decision="abandon",
            runtime_guard_code="RUNTIME_GUARD_FAILED",
        )
        _database_update(
            fixture,
            "UPDATE experiment_events SET decision_reason = '[]' WHERE rowid = 4",
        )
    elif mutation == "lineage_verified_branch_mismatch":
        _database_update(
            fixture,
            "UPDATE experiment_events SET branch_id = 'mismatched' WHERE rowid = 5",
        )
    elif mutation == "extra_protocol_count":
        _mutate_both_run_results(
            fixture,
            lambda run: run["protocol_stage_counts"].update(unexpected=0),
        )
    elif mutation == "forbidden_summary_stage":
        _mutate_json(
            fixture.campaign / "campaign_summary.json",
            lambda value: value["steps"][4]["protocol_result"].update(stage="review"),
        )
    elif mutation == "unknown_protocol_stage":
        _mutate_json(
            fixture.campaign / "campaign_summary.json",
            lambda value: value["steps"][4]["protocol_result"].update(stage="mystery"),
        )
    elif mutation == "forbidden_lineage_stage":
        _database_update(
            fixture,
            "UPDATE experiment_events SET stage = 'review' WHERE rowid = 6",
        )
    elif mutation == "forbidden_history_evidence_stage":
        history_path = fixture.campaign / "research_history.jsonl"
        records = _read_history(history_path)
        records[5]["protocol"]["evidence"]["stage"] = "review"
        _write_history(history_path, records)
    elif mutation == "preformal_forbidden_stage":
        _mutate_json(
            fixture.campaign / "campaign_summary.json",
            lambda value: value["steps"][0]["execution_outcome"]["provenance"].update(
                stage="validation"
            ),
        )
        history_path = fixture.campaign / "research_history.jsonl"
        records = _read_history(history_path)
        records[0]["outcome"]["stage"] = "validation"
        _write_history(history_path, records)
        _database_update(
            fixture,
            "UPDATE experiment_events SET stage = 'validation' WHERE rowid = 1",
        )
    elif mutation == "malformed_summary_stage":
        _mutate_json(
            fixture.campaign / "campaign_summary.json",
            lambda value: value["steps"][0]["execution_outcome"]["provenance"].update(
                stage={"name": "proposal_hypothesis"}
            ),
        )
    elif mutation == "summary_mystery_stage":
        _mutate_json(
            fixture.campaign / "campaign_summary.json",
            lambda value: value["steps"][0]["execution_outcome"]["provenance"].update(
                stage="mystery"
            ),
        )
    elif mutation == "preformal_mystery_all_faces":

        def mutate_summary(value: dict[str, Any]) -> None:
            value["steps"][0].update(failure_stage="mystery")
            value["steps"][0]["execution_outcome"]["provenance"]["stage"] = "mystery"

        _mutate_json(fixture.campaign / "campaign_summary.json", mutate_summary)
        history_path = fixture.campaign / "research_history.jsonl"
        records = _read_history(history_path)
        records[0]["outcome"]["stage"] = "mystery"
        _write_history(history_path, records)
        _database_update(
            fixture,
            "UPDATE experiment_events SET stage = 'mystery' WHERE rowid = 1",
        )
    elif mutation == "delete_preformal_lineage":
        _database_update(
            fixture,
            "DELETE FROM experiment_events WHERE rowid = 1",
        )
    elif mutation == "append_mystery_lineage":
        _database_update(
            fixture,
            "INSERT INTO experiment_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "mystery_event",
                "mystery-branch",
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                "mystery",
                None,
                None,
                "research_rejected",
                "SYNTHETIC_ABSTAINED",
            ),
        )
    elif mutation == "preformal_event_kind_mystery":
        _database_update(
            fixture,
            "UPDATE experiment_events SET event_kind = 'mystery' WHERE rowid = 1",
        )
    elif mutation == "preformal_lineage_branch_mismatch":
        _database_update(
            fixture,
            "UPDATE experiment_events SET branch_id = 'mismatched' WHERE rowid = 1",
        )
    elif mutation == "preformal_lineage_outcome_mismatch":
        _database_update(
            fixture,
            "UPDATE experiment_events SET execution_outcome = 'evaluated' "
            "WHERE rowid = 1",
        )
    elif mutation == "preformal_history_reason_mismatch":
        history_path = fixture.campaign / "research_history.jsonl"
        records = _read_history(history_path)
        records[0]["outcome"]["reason_code"] = "SYNTHETIC_MISMATCH"
        _write_history(history_path, records)
    elif mutation == "preformal_summary_canary":
        _mutate_json(
            fixture.campaign / "campaign_summary.json",
            lambda value: value["steps"][0].update(canary_result={"passed": True}),
        )
    elif mutation == "preformal_lineage_candidate_evidence":
        _database_update(
            fixture,
            "UPDATE experiment_events SET code_hash = ?, "
            "contract_result = 'passed', verification_result = 'passed', "
            "canary_result = 'passed' WHERE rowid = 1",
            ("e" * 64,),
        )
    elif mutation == "nondecision_summary_evaluated":
        _mutate_json(
            fixture.campaign / "campaign_summary.json",
            lambda value: value["steps"][0].update(
                execution_outcome={
                    "outcome": "evaluated",
                    "reason_code": "EVALUATION_COMPLETED",
                    "detail": "",
                    "provenance": {"stage": "proposal_hypothesis"},
                }
            ),
        )

        def mutate_counts(run: dict[str, Any]) -> None:
            run["execution_outcome_counts"].update(
                evaluated=7,
                research_rejected=0,
            )

        _mutate_both_run_results(fixture, mutate_counts)
    elif mutation == "synchronized_forbidden_outcome":
        reason_code = "SYNTHETIC_BLOCKED"
        _mutate_json(
            fixture.campaign / "campaign_summary.json",
            lambda value: value["steps"][0].update(
                execution_outcome={
                    "outcome": "blocked_infra",
                    "reason_code": reason_code,
                    "detail": "",
                    "provenance": {"stage": "proposal_hypothesis"},
                }
            ),
        )
        history_path = fixture.campaign / "research_history.jsonl"
        records = _read_history(history_path)
        records[0]["outcome"].update(
            outcome="blocked_infra",
            reason_code=reason_code,
        )
        _write_history(history_path, records)
        _database_update(
            fixture,
            "UPDATE experiment_events SET execution_outcome = 'blocked_infra', "
            "execution_outcome_reason_code = ? WHERE rowid = 1",
            (reason_code,),
        )

        def mutate_counts(run: dict[str, Any]) -> None:
            run["execution_outcome_counts"].update(
                research_rejected=0,
                blocked_infra=1,
            )

        _mutate_both_run_results(fixture, mutate_counts)
    elif mutation == "lineage_canary":
        _database_update(
            fixture,
            "UPDATE experiment_events SET canary_result = 'failed' WHERE rowid = 6",
        )
    elif mutation == "lineage_hash":
        _database_update(
            fixture,
            "UPDATE experiment_events SET code_hash = '0000000000000000000000000000000000000000000000000000000000000000' WHERE rowid = 6",
        )
    elif mutation == "patch_uneditable":
        _set_patch_target(fixture, "module.py", "UNCHANGED = 8\n")
    elif mutation == "patch_frozen":
        _set_patch_target(fixture, "policies/frozen.py", "LOCKED = False\n")
    elif mutation == "hypothesis_target_mismatch":
        history_path = fixture.campaign / "research_history.jsonl"
        records = _read_history(history_path)
        for record in records[-2:]:
            record["hypothesis"]["target_file"] = "policies/frozen.py"
        _write_history(history_path, records)
        _mutate_json(
            fixture.campaign / "campaign_summary.json",
            lambda value: [
                step["hypothesis"].update(target_file="policies/frozen.py")
                for step in value["steps"][-2:]
            ],
        )
    elif mutation == "summary_outcome":
        _mutate_json(
            fixture.campaign / "campaign_summary.json",
            lambda value: value["steps"][5]["execution_outcome"].update(
                outcome="research_rejected"
            ),
        )
    elif mutation == "expanded_contract_tamper":
        _mutate_json(
            fixture.campaign / "campaign_summary.json",
            lambda value: value["steps"][6].update(contract_passed=False),
        )
    elif mutation == "history_outcome":
        history_path = fixture.campaign / "research_history.jsonl"
        records = _read_history(history_path)
        records[5]["outcome"].update(
            outcome="research_rejected", reason_code="SYNTHETIC_REJECTED"
        )
        _write_history(history_path, records)
    elif mutation == "historical_ignored_symlink":
        historical = candidate.parent / "candidate-historical"
        historical.chmod(0o755)
        (historical / "__pycache__").symlink_to(historical / "policies")
        historical.chmod(0o555)
    else:  # pragma: no cover - mutation names are a closed test table
        raise AssertionError(mutation)
    return None


def test_generic_auditor_reads_synthetic_git_and_sqlite_read_only(
    tmp_path: Path,
) -> None:
    fixture = _synthetic_root(tmp_path)
    database = fixture.campaign / "scion.db"
    before = database.stat().st_mtime_ns

    assert _audit(fixture) == QUALIFIED_TOKEN
    assert database.stat().st_mtime_ns == before


@pytest.mark.parametrize(
    ("gate", "decision"),
    (
        ("fail", "continue_explore"),
        ("expand", "expand_screening"),
    ),
)
def test_nonready_expanded_formal_negative_remains_legal(
    tmp_path: Path,
    gate: str,
    decision: str,
) -> None:
    fixture = _synthetic_root(tmp_path)
    _replace_expanded_negative_dispatch_with_formal(
        fixture,
        gate=gate,
        decision=decision,
    )

    assert _audit(fixture) == QUALIFIED_TOKEN


def test_formal_abandon_with_candidate_failure_evidence_remains_legal(
    tmp_path: Path,
) -> None:
    fixture = _synthetic_root(tmp_path)
    _replace_expanded_negative_dispatch_with_formal(
        fixture,
        gate="pass",
        decision="abandon",
        candidate_failure=True,
    )

    assert _audit(fixture) == QUALIFIED_TOKEN


@pytest.mark.parametrize(
    "reason_code",
    ("RUNTIME_GUARD_FAILED", "RUNTIME_GUARD_TIMEOUT"),
)
def test_formal_abandon_with_runtime_guard_evidence_remains_legal(
    tmp_path: Path,
    reason_code: str,
) -> None:
    fixture = _synthetic_root(tmp_path)
    _replace_expanded_negative_dispatch_with_formal(
        fixture,
        gate="pass",
        decision="abandon",
        runtime_guard_code=reason_code,
    )

    assert _audit(fixture) == QUALIFIED_TOKEN


@pytest.mark.parametrize(
    "decision",
    ("expand_validation", "queue_frozen", "promote"),
)
def test_preformal_heldout_decision_fails_closed(
    tmp_path: Path,
    decision: str,
) -> None:
    fixture = _synthetic_root(tmp_path)
    _set_preformal_decision(fixture, decision)

    with pytest.raises(QualificationAuditUnavailable) as raised:
        _audit(fixture)

    assert str(raised.value) == UNAVAILABLE_TOKEN


def test_artifact_authority_api_is_not_exported() -> None:
    assert "audit_qualification_artifacts" not in handoff_module.__all__
    assert not hasattr(handoff_module, "audit_qualification_artifacts")


@pytest.mark.parametrize(
    "boundary", ("status", "stop_reason", "disposition", "ready_branch")
)
def test_terminal_boundary_precedes_source_materialization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    boundary: str,
) -> None:
    fixture = _synthetic_root(tmp_path)

    if boundary == "ready_branch":
        for name in ("status.json", "campaign_summary.json"):
            _mutate_json(
                fixture.campaign / name,
                lambda value: value["branches"][-1].update(state="abandoned"),
            )
    else:

        def mutate(run: dict[str, Any]) -> None:
            if boundary == "status":
                run["status"] = "running"
            elif boundary == "stop_reason":
                run["stop_reason"] = "wrong_boundary"
            else:
                run["qualification"]["disposition"] = "not_ready"

        _mutate_both_run_results(fixture, mutate)
    materialization_calls = 0

    def forbidden_materialization(**_kwargs: Any) -> None:
        nonlocal materialization_calls
        materialization_calls += 1

    monkeypatch.setattr(
        qualification_audit_module,
        "_materialize_tracked_source",
        forbidden_materialization,
    )

    with pytest.raises(QualificationAuditUnavailable):
        _audit(fixture)

    assert materialization_calls == 0


def test_unknown_protocol_stage_precedes_source_materialization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _synthetic_root(tmp_path)
    _mutate_json(
        fixture.campaign / "campaign_summary.json",
        lambda value: value["steps"][4]["protocol_result"].update(stage="mystery"),
    )
    materialization_calls = 0

    def forbidden_materialization(**_kwargs: Any) -> None:
        nonlocal materialization_calls
        materialization_calls += 1

    monkeypatch.setattr(
        qualification_audit_module,
        "_materialize_tracked_source",
        forbidden_materialization,
    )

    with pytest.raises(QualificationAuditUnavailable):
        _audit(fixture)

    assert materialization_calls == 0


@pytest.mark.parametrize(
    "mutation",
    (
        "summary_mystery_stage",
        "preformal_mystery_all_faces",
        "delete_preformal_lineage",
        "append_mystery_lineage",
        "preformal_event_kind_mystery",
        "preformal_lineage_branch_mismatch",
        "preformal_lineage_outcome_mismatch",
        "preformal_history_reason_mismatch",
        "preformal_summary_canary",
        "preformal_lineage_candidate_evidence",
        "nondecision_summary_evaluated",
    ),
)
def test_durable_ledger_tamper_precedes_source_materialization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    fixture = _synthetic_root(tmp_path)
    _apply_mutation(fixture, mutation)
    materialization_calls = 0

    def forbidden_materialization(**_kwargs: Any) -> None:
        nonlocal materialization_calls
        materialization_calls += 1

    monkeypatch.setattr(
        qualification_audit_module,
        "_materialize_tracked_source",
        forbidden_materialization,
    )

    with pytest.raises(QualificationAuditUnavailable):
        _audit(fixture)

    assert materialization_calls == 0


@pytest.mark.parametrize(
    "outcome",
    ("blocked_infra", "resource_exhausted", "not_evaluated"),
)
def test_preformal_history_outcome_must_match_summary(
    tmp_path: Path,
    outcome: str,
) -> None:
    fixture = _synthetic_root(tmp_path)
    history_path = fixture.campaign / "research_history.jsonl"
    records = _read_history(history_path)
    records[0]["outcome"]["outcome"] = outcome
    _write_history(history_path, records)

    with pytest.raises(QualificationAuditUnavailable) as raised:
        _audit(fixture)

    assert str(raised.value) == UNAVAILABLE_TOKEN


@pytest.mark.parametrize(
    "outcome",
    ("blocked_infra", "resource_exhausted", "interrupted", "not_evaluated"),
)
def test_completed_positive_rejects_synchronized_nonvalid_outcome(
    tmp_path: Path,
    outcome: str,
) -> None:
    fixture = _synthetic_root(tmp_path)
    reason_code = f"SYNTHETIC_{outcome.upper()}"
    _mutate_json(
        fixture.campaign / "campaign_summary.json",
        lambda value: value["steps"][0].update(
            execution_outcome={
                "outcome": outcome,
                "reason_code": reason_code,
                "detail": "",
                "provenance": {"stage": "proposal_hypothesis"},
            }
        ),
    )
    history_path = fixture.campaign / "research_history.jsonl"
    records = _read_history(history_path)
    records[0]["outcome"].update(outcome=outcome, reason_code=reason_code)
    _write_history(history_path, records)
    _database_update(
        fixture,
        "UPDATE experiment_events SET execution_outcome = ?, "
        "execution_outcome_reason_code = ? WHERE rowid = 1",
        (outcome, reason_code),
    )

    def mutate_counts(run: dict[str, Any]) -> None:
        run["execution_outcome_counts"].update(
            research_rejected=0,
            **{outcome: 1},
        )

    _mutate_both_run_results(fixture, mutate_counts)

    with pytest.raises(QualificationAuditUnavailable) as raised:
        _audit(fixture)

    assert str(raised.value) == UNAVAILABLE_TOKEN


@pytest.mark.parametrize(
    "state",
    ("explore",),
)
def test_terminal_boundary_allows_legal_extra_nonready_branch(
    tmp_path: Path, state: str
) -> None:
    fixture = _synthetic_root(tmp_path)
    branch_id = f"legal-extra-{state}"
    _mutate_json(
        fixture.campaign / "campaign_summary.json",
        lambda value: value["steps"][0].update(branch_id=branch_id),
    )
    _database_update(
        fixture,
        "UPDATE experiment_events SET branch_id = ? WHERE rowid = 1",
        (branch_id,),
    )
    for name in ("status.json", "campaign_summary.json"):

        def add_branch(value: dict[str, Any]) -> None:
            value["branches"].append(_branch_row(branch_id, state, None))
            _sync_active_slots(value)

        _mutate_json(
            fixture.campaign / name,
            add_branch,
        )

    assert _audit(fixture) == QUALIFIED_TOKEN


def test_terminal_boundary_rejects_empty_explore_branch(tmp_path: Path) -> None:
    fixture = _synthetic_root(tmp_path)
    for name in ("status.json", "campaign_summary.json"):

        def add_branch(value: dict[str, Any]) -> None:
            value["branches"].append(_branch_row("empty-explore", "explore", None))
            _sync_active_slots(value)

        _mutate_json(fixture.campaign / name, add_branch)

    with pytest.raises(QualificationAuditUnavailable) as raised:
        _audit(fixture)

    assert str(raised.value) == UNAVAILABLE_TOKEN


@pytest.mark.parametrize(
    "state",
    (
        "ready_validate",
        "new",
        "abandoned",
        "explore_expand",
        "validating",
        "validating_expand",
        "ready_frozen",
        "frozen_testing",
        "promoted",
        "stale",
        "stale_weight_update",
        "blocked_infra",
        "unknown_state",
    ),
)
def test_terminal_boundary_rejects_duplicate_ready_or_forbidden_branch_state(
    tmp_path: Path, state: str
) -> None:
    fixture = _synthetic_root(tmp_path)
    for name in ("status.json", "campaign_summary.json"):

        def add_branch(value: dict[str, Any]) -> None:
            value["branches"].append(
                _branch_row(f"forbidden-extra-{state}", state, "f" * 64)
            )
            _sync_active_slots(value)

        _mutate_json(
            fixture.campaign / name,
            add_branch,
        )

    with pytest.raises(QualificationAuditUnavailable) as raised:
        _audit(fixture)

    assert str(raised.value) == UNAVAILABLE_TOKEN


@pytest.mark.parametrize(
    "mutation",
    (
        "base_mismatch",
        "base_noncommit",
        "prefix_missing",
        "source_count",
        "prefix_noncanonical",
        "screening_cartesian_schema",
        "candidate_root_writable",
        "candidate_nested_writable",
        "ignored_symlink",
        "ignored_nonregular",
        "baseline_bytes",
        "candidate_bytes",
        "candidate_source_set",
        "duplicate_artifact_key",
        "duplicate_zero_metric",
        "nonzero_metric",
        "branch_projection",
        "ready_hash_missing",
        "ready_hash_malformed",
        "parked_hash_retained",
        "explore_hash_retained",
        "branch_row_shape",
        "campaign_mode_tamper",
        "n_experiments_tamper",
        "screened_experiments_tamper",
        "active_slots_tamper",
        "total_rounds",
        "missing_round",
        "out_of_order_round",
        "scheduled_calls",
        "evaluated_rounds",
        "formal_screened_candidates",
        "execution_outcome_counts",
        "last_execution_outcome",
        "last_result_shape",
        "formal_counts",
        "proposal_attempts_tamper",
        "verified_chains_tamper",
        "formal_shape_tamper",
        "verified_branch_duplicate",
        "retired_negative_branch_reused",
        "orphan_formal_expansion",
        "interleaved_expansion_dispatch",
        "expansion_candidate_mismatch",
        "null_h_expansion_dispatch",
        "wrong_formal_population",
        "formal_pair_accounting",
        "formal_gate_decision_mismatch",
        "other_qualifier",
        "formal_abandon_without_safety",
        "runtime_guard_reason_mismatch",
        "formal_decision_reason_mismatch",
        "lineage_decision_reason_mismatch",
        "synchronized_runtime_guard_without_lineage",
        "lineage_verified_branch_mismatch",
        "extra_protocol_count",
        "forbidden_summary_stage",
        "unknown_protocol_stage",
        "forbidden_lineage_stage",
        "forbidden_history_evidence_stage",
        "preformal_forbidden_stage",
        "malformed_summary_stage",
        "summary_mystery_stage",
        "preformal_mystery_all_faces",
        "delete_preformal_lineage",
        "append_mystery_lineage",
        "preformal_event_kind_mystery",
        "preformal_lineage_branch_mismatch",
        "preformal_lineage_outcome_mismatch",
        "preformal_history_reason_mismatch",
        "nondecision_summary_evaluated",
        "synchronized_forbidden_outcome",
        "lineage_canary",
        "lineage_hash",
        "patch_uneditable",
        "patch_frozen",
        "hypothesis_target_mismatch",
        "summary_outcome",
        "expanded_contract_tamper",
        "history_outcome",
        "historical_ignored_symlink",
    ),
)
def test_mutation_classes_fail_closed(tmp_path: Path, mutation: str) -> None:
    fixture = _synthetic_root(tmp_path)
    revision = _apply_mutation(fixture, mutation)

    with pytest.raises(QualificationAuditUnavailable) as raised:
        _audit(fixture, revision=revision)

    assert str(raised.value) == UNAVAILABLE_TOKEN


def test_git_replace_ref_is_ignored(tmp_path: Path) -> None:
    fixture = _synthetic_root(tmp_path)
    original = fixture.revision
    (fixture.repository / "pkg" / "module.py").write_text(
        "UNCHANGED = 999\n", encoding="utf-8"
    )
    replacement = _commit(fixture.repository, "replacement source")
    subprocess.run(
        ["git", "replace", original, replacement],
        cwd=fixture.repository,
        check=True,
    )

    assert _audit(fixture) == QUALIFIED_TOKEN


def test_inherited_git_control_environment_is_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _synthetic_root(tmp_path)
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "redirected.git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(tmp_path / "redirected-worktree"))
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "core.repositoryformatversion")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "999")
    monkeypatch.setenv("GIT_NO_REPLACE_OBJECTS", "0")

    assert _audit(fixture) == QUALIFIED_TOKEN


def test_lineage_wal_is_read_from_private_copy_without_touching_source(
    tmp_path: Path,
) -> None:
    fixture = _synthetic_root(tmp_path)
    database = fixture.campaign / "scion.db"
    database.chmod(0o644)
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
        connection.execute("PRAGMA wal_autocheckpoint=0")
        last = connection.execute(
            "SELECT event_kind, branch_id, code_hash, patch_action, patch_file, "
            "hypothesis_text, contract_result, verification_result, canary_result, "
            "stage, decision, decision_reason, execution_outcome, "
            "execution_outcome_reason_code "
            "FROM experiment_events WHERE rowid = 7"
        ).fetchone()
        assert last is not None
        connection.execute("DELETE FROM experiment_events WHERE rowid = 7")
        connection.commit()
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        connection.execute(
            "INSERT INTO experiment_events "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            tuple(last),
        )
        connection.commit()
        bundle = tuple(Path(str(database) + suffix) for suffix in ("", "-wal", "-shm"))
        assert all(path.is_file() for path in bundle)
        before = {
            path: (
                hashlib.sha256(path.read_bytes()).hexdigest(),
                path.stat().st_mtime_ns,
            )
            for path in bundle
        }

        assert _audit(fixture) == QUALIFIED_TOKEN

        after = {
            path: (
                hashlib.sha256(path.read_bytes()).hexdigest(),
                path.stat().st_mtime_ns,
            )
            for path in bundle
        }
        assert after == before


def test_cli_success_is_the_single_qualified_token(tmp_path: Path) -> None:
    fixture = _synthetic_root(tmp_path)

    result = CliRunner().invoke(
        app,
        [
            "audit-qualification-campaign",
            str(fixture.campaign),
            "--expectations",
            str(fixture.expectations),
            "--repo-root",
            str(fixture.repository),
            "--base-commit",
            fixture.revision,
        ],
    )

    assert result.exit_code == 0
    assert result.output.strip() == QUALIFIED_TOKEN


def test_duplicate_key_expectation_fails_closed(tmp_path: Path) -> None:
    fixture = _synthetic_root(tmp_path)
    fixture.expectations.write_text(
        '{"schema_version":"x","schema_version":"y"}', encoding="utf-8"
    )

    with pytest.raises(QualificationAuditUnavailable):
        load_qualification_audit_expectation(fixture.expectations)


@pytest.mark.parametrize("failure", ("base", "artifact"))
def test_cli_has_uniform_failure_without_artifact_detail(
    tmp_path: Path, failure: str
) -> None:
    fixture = _synthetic_root(tmp_path)
    if failure == "artifact":
        (fixture.campaign / "status.json").write_text("PRIVATE BODY", encoding="utf-8")
    base = (
        fixture.revision[:-1] + ("0" if fixture.revision[-1] != "0" else "1")
        if failure == "base"
        else fixture.revision
    )
    result = CliRunner().invoke(
        app,
        [
            "audit-qualification-campaign",
            str(fixture.campaign),
            "--expectations",
            str(fixture.expectations),
            "--repo-root",
            str(fixture.repository),
            "--base-commit",
            base,
        ],
    )

    assert result.exit_code == 1
    assert result.output.strip() == UNAVAILABLE_TOKEN
    assert "PRIVATE" not in result.output
