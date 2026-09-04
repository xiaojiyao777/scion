"""Ordinary, provider-safe cross-campaign research history."""

from __future__ import annotations

import json
import logging
import math
import os
import re
import tempfile
from collections.abc import Mapping, Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any

from scion.core.execution_outcome import (
    PROVIDER_TRANSIENT_RETRIES_EXHAUSTED,
    ExecutionOutcome,
)
from scion.core.models import ExperimentStage, StepRecord, patch_file_changes
from scion.core.paths import normalize_relative_patch_path
from scion.core.research_input import is_sensitive_research_key
from scion.core.selected_hypothesis_basis import (
    normalize_selected_hypothesis_research_basis,
)

RESEARCH_HISTORY_SCHEMA = "scion.research_history.step.v1"
MAX_RESEARCH_HISTORY_FILES = 64
MAX_RESEARCH_HISTORY_RECORDS = 1024
MAX_RESEARCH_HISTORY_LINE_BYTES = 1 * 1024 * 1024
MAX_RESEARCH_HISTORY_FILE_BYTES = 32 * 1024 * 1024
MAX_RESEARCH_HISTORY_TOTAL_BYTES = 64 * 1024 * 1024
MAX_RESEARCH_HISTORY_DEPTH = 24

logger = logging.getLogger(__name__)


class _ResearchHistoryLineTooLarge(ValueError):
    """A policy-size rejection that the campaign-local writer may skip."""

_TOP = frozenset(
    {
        "schema_version",
        "problem_id",
        "hypothesis",
        "selected_hypothesis_research_basis",
        "patch",
        "outcome",
        "protocol",
        "decision",
    }
)
_TOP_REQUIRED = _TOP - {"selected_hypothesis_research_basis"}
_HYPOTHESIS = frozenset(
    {
        "text",
        "change_locus",
        "action",
        "target_file",
        "predicted_direction",
        "target_weakness",
        "expected_effect",
        "suggested_weight",
    }
)
_PATCH_CHANGE = frozenset({"file_path", "action", "source"})
_OUTCOME_REQUIRED = frozenset({"outcome", "stage", "reason_code"})
_OUTCOME = _OUTCOME_REQUIRED | {"severity", "checks"}
_CHECK = frozenset({"name", "passed", "severity"})
_DECISION = frozenset(
    {
        "value",
        "reason_codes",
        "engine_reason_codes",
        "diagnostic_reason_codes",
        "bypass_reason_codes",
    }
)
_TOKEN = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,127}$")
_FORBIDDEN_KEY = re.compile(
    r"(^|_)(private|raw|validation|frozen|holdout|bks)($|_)"
    r"|(^|_)(decision_features|raw_metrics|raw_pair|raw_calibration)($|_)"
)
_OPEN_FORBIDDEN = frozenset(
    {
        "detail",
        "details",
        "path",
        "paths",
        "case",
        "cases",
        "seed",
        "seed_set",
        "branch_id",
        "campaign_id",
        "artifact_ref",
        "artifact_refs",
        "timestamp",
        "id",
        "ids",
    }
)
_OPEN_COMPONENTS = frozenset(
    {"detail", "details", "path", "paths", "seed", "seeds", "identity", "identities"}
)
_HELD_OUT = frozenset({"validation", "frozen"})
_OPERATIONAL_HISTORY_STAGES = frozenset(
    {
        "reconcile_source",
        "reconcile_apply",
        "candidate_disposition",
    }
)
_OPERATIONAL_HISTORY_REASON_CODES = frozenset(
    {
        PROVIDER_TRANSIENT_RETRIES_EXHAUSTED,
        "PROVIDER_CALL_BLOCKED_INFRA",
        "PROVIDER_BALANCE_EXHAUSTED",
        "PROVIDER_CALL_CAP_EXHAUSTED",
        "PROPOSAL_CONTEXT_INVALID",
        "PROPOSAL_UNEXPECTED_FAILURE",
        "PROPOSAL_RESPONSE_INVALID",
        "HYPOTHESIS_PROPOSAL_INVALID",
        "HYPOTHESIS_RESEARCH_TRANSCRIPT_EXHAUSTED",
        "HYPOTHESIS_RESEARCH_TURN_CAP_EXHAUSTED",
        "HYPOTHESIS_RESEARCH_RESULT_CAP_EXHAUSTED",
        "PATCH_PROPOSAL_INVALID",
        "PATCH_DRAFT_DUPLICATE_FILE",
        "CODE_RESEARCH_ABANDONED",
        "CODE_RESEARCH_TRANSCRIPT_EXHAUSTED",
        "CODE_RESEARCH_TURN_CAP_EXHAUSTED",
        "CODE_RESEARCH_RESULT_CAP_EXHAUSTED",
    }
)
_CASE_FEEDBACK_PATH = re.compile(
    r"^\$\.protocol\.evidence\.case_outcomes\.case_feedback\[\d+\]$"
)
_CANONICAL_CASE_FEEDBACK_SEED_FIELDS = frozenset({"seed_pattern", "seed_consistency"})


def problem_id_from_spec(problem_spec: Any) -> str:
    spec_v1 = getattr(problem_spec, "spec_v1", None)
    value = str(
        getattr(spec_v1, "id", None)
        or getattr(problem_spec, "id", None)
        or getattr(problem_spec, "name", "")
        or ""
    ).strip()
    return _token(value, field="problem id")


class ResearchHistoryWriter:
    """Atomically maintain the visible JSONL prefix of one fresh campaign."""

    def __init__(self, campaign_dir: str | Path, *, problem_id: str) -> None:
        self.path = Path(campaign_dir) / "research_history.jsonl"
        self.problem_id = _token(problem_id, field="problem_id")
        if self.path.exists():
            raise FileExistsError(f"research history already exists: {self.path}")
        self._lines: list[bytes] = []
        self._output_stopped = False

    def append_step(self, step: StepRecord) -> None:
        if self._output_stopped:
            return
        if len(self._lines) >= MAX_RESEARCH_HISTORY_RECORDS:
            self._stop_output(
                "record limit %d reached",
                MAX_RESEARCH_HISTORY_RECORDS,
            )
            return
        try:
            record = project_research_history_step(step, problem_id=self.problem_id)
        except _ResearchHistoryLineTooLarge:
            logger.warning(
                "Skipping research history record because it exceeds the %d-byte "
                "line limit",
                MAX_RESEARCH_HISTORY_LINE_BYTES,
            )
            return
        if record is None:
            return
        line = _render(record)
        if len(line) > MAX_RESEARCH_HISTORY_LINE_BYTES:
            logger.warning(
                "Skipping research history record because it exceeds the %d-byte "
                "line limit",
                MAX_RESEARCH_HISTORY_LINE_BYTES,
            )
            return
        prefix = b"".join((*self._lines, line))
        if len(prefix) > MAX_RESEARCH_HISTORY_FILE_BYTES:
            self._stop_output(
                "file limit %d bytes would be exceeded",
                MAX_RESEARCH_HISTORY_FILE_BYTES,
            )
            return
        _write_bytes_atomically(self.path, prefix)
        self._lines.append(line)

    def _stop_output(self, reason: str, *args: object) -> None:
        self._output_stopped = True
        logger.warning(
            "Research history output stopped after %d records: " + reason,
            len(self._lines),
            *args,
        )


def project_research_history_step(
    step: StepRecord, *, problem_id: str
) -> dict[str, Any] | None:
    if _is_held_out(step) or _is_operational_rejection(step):
        return None
    return normalize_research_history_record(
        {
            "schema_version": RESEARCH_HISTORY_SCHEMA,
            "problem_id": problem_id,
            "hypothesis": _hypothesis(step),
            "selected_hypothesis_research_basis": (
                step.selected_hypothesis_research_basis
            ),
            "patch": _patch(step),
            "outcome": _outcome(step),
            "protocol": _screening_protocol(step),
            "decision": _decision(step),
        },
        expected_problem_id=problem_id,
    )


def _is_operational_rejection(step: StepRecord) -> bool:
    outcome = step.execution_outcome
    if outcome is None:
        return False
    stage = str(step.failure_stage or outcome.provenance.get("stage") or "").strip()
    return bool(
        outcome.reason_code in _OPERATIONAL_HISTORY_REASON_CODES
        or stage in _OPERATIONAL_HISTORY_STAGES
    )


def load_research_histories(
    paths: Sequence[Path], *, expected_problem_id: str
) -> tuple[dict[str, Any], ...]:
    """Load only explicit JSONL files, preserving caller and line order."""

    expected = _token(expected_problem_id, field="expected_problem_id")
    if len(paths) > MAX_RESEARCH_HISTORY_FILES:
        raise ValueError("too many research history files")
    records: list[dict[str, Any]] = []
    total_bytes = 0
    for raw_path in paths:
        path = Path(raw_path).expanduser()
        try:
            with path.open("rb") as source:
                raw = source.read(MAX_RESEARCH_HISTORY_FILE_BYTES + 1)
        except OSError as exc:
            raise ValueError(f"cannot read research history: {path}: {exc}") from exc
        if len(raw) > MAX_RESEARCH_HISTORY_FILE_BYTES:
            raise ValueError("research history file is too large")
        total_bytes += len(raw)
        if total_bytes > MAX_RESEARCH_HISTORY_TOTAL_BYTES:
            raise ValueError("research history inputs are too large")
        if raw and not raw.endswith(b"\n"):
            raise ValueError(f"research history must end with a newline: {path}")
        for line_number, line in enumerate(raw.splitlines(keepends=True), 1):
            if not line.strip():
                raise ValueError(
                    f"research history contains blank line: {path}:{line_number}"
                )
            if len(line) > MAX_RESEARCH_HISTORY_LINE_BYTES:
                raise ValueError(
                    f"research history line is too large: {path}:{line_number}"
                )
            try:
                value = json.loads(
                    line.decode("utf-8"), object_pairs_hook=_mapping_without_duplicates
                )
            except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
                raise ValueError(
                    f"invalid research history JSON: {path}:{line_number}: {exc}"
                ) from exc
            records.append(
                normalize_research_history_record(value, expected_problem_id=expected)
            )
            if len(records) > MAX_RESEARCH_HISTORY_RECORDS:
                raise ValueError("too many research history records")
    return tuple(records)


def provider_research_history(
    records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Return only provider-safe scientific records from prior campaigns.

    Operational proposal/provider/reconcile rows remain in their original
    campaign ledger for audit, but they are not algorithm evidence and must not
    consume H attention in later campaigns.
    """

    return [
        deepcopy(
            {
                key: value
                for key, value in record.items()
                if key not in {"schema_version", "problem_id"}
            }
        )
        for record in records
        if not _is_operational_history_record(record)
    ]


def _is_operational_history_record(record: Mapping[str, Any]) -> bool:
    outcome = record.get("outcome")
    if not isinstance(outcome, Mapping):
        return False
    stage = str(outcome.get("stage") or "").strip()
    reason_code = str(outcome.get("reason_code") or "").strip()
    return bool(
        stage in _OPERATIONAL_HISTORY_STAGES
        or reason_code in _OPERATIONAL_HISTORY_REASON_CODES
    )


def normalize_research_history_record(
    value: Any, *, expected_problem_id: str
) -> dict[str, Any]:
    record = _mapping(value, _TOP, required=_TOP_REQUIRED, path="$")
    if record["schema_version"] != RESEARCH_HISTORY_SCHEMA:
        raise ValueError("unsupported research history schema")
    expected = _token(expected_problem_id, field="expected_problem_id")
    problem_id = _token(record["problem_id"], field="problem_id")
    if problem_id != expected:
        raise ValueError(
            f"research history problem_id mismatch: expected {expected!r}, got {problem_id!r}"
        )
    normalized = {
        "schema_version": RESEARCH_HISTORY_SCHEMA,
        "problem_id": problem_id,
        "hypothesis": _normalize_hypothesis(record["hypothesis"]),
        "selected_hypothesis_research_basis": (
            normalize_selected_hypothesis_research_basis(
                record.get("selected_hypothesis_research_basis")
            )
        ),
        "patch": _normalize_patch(record["patch"]),
        "outcome": _normalize_outcome(record["outcome"]),
        "protocol": _normalize_protocol(record["protocol"]),
        "decision": _normalize_decision(record["decision"]),
    }
    _validate_record_relationships(normalized)
    _validate_safe_value(normalized, path="$", depth=0)
    if len(_render(normalized)) > MAX_RESEARCH_HISTORY_LINE_BYTES:
        raise _ResearchHistoryLineTooLarge(
            "research history record exceeds line byte limit"
        )
    return normalized


def _is_held_out(step: StepRecord) -> bool:
    stages: list[Any] = [step.failure_stage]
    if step.protocol_result is not None:
        stages.append(step.protocol_result.stage)
    if step.execution_outcome is not None:
        provenance = step.execution_outcome.provenance
        stages.extend(
            (
                provenance.get("stage"),
                provenance.get("protocol_stage"),
            )
        )
        completed_protocol = provenance.get("completed_protocol")
        if isinstance(completed_protocol, Mapping):
            stages.append(completed_protocol.get("stage"))
        interrupted_outcome = provenance.get("interrupted_outcome")
        if isinstance(interrupted_outcome, Mapping):
            interrupted_provenance = interrupted_outcome.get("provenance")
            if isinstance(interrupted_provenance, Mapping):
                stages.append(interrupted_provenance.get("stage"))
    return any(
        str(getattr(stage, "value", stage) or "").strip().lower() in _HELD_OUT
        for stage in stages
    )


def _hypothesis(step: StepRecord) -> dict[str, Any] | None:
    hypothesis = step.hypothesis
    if hypothesis is None:
        return None
    target = hypothesis.target_file
    if target is not None:
        try:
            target = normalize_relative_patch_path(target)
        except ValueError:
            target = None
    return {
        "text": hypothesis.hypothesis_text,
        "change_locus": hypothesis.change_locus,
        "action": hypothesis.action,
        "target_file": target,
        "predicted_direction": hypothesis.predicted_direction,
        "target_weakness": hypothesis.target_weakness,
        "expected_effect": hypothesis.expected_effect,
        "suggested_weight": hypothesis.suggested_weight,
    }


def _patch(step: StepRecord) -> dict[str, Any] | None:
    if step.patch is None:
        return None
    return {
        "changes": [
            {
                "file_path": normalize_relative_patch_path(change.file_path),
                "action": change.action,
                "source": change.code_content,
            }
            for change in patch_file_changes(step.patch)
        ]
    }


def _outcome(step: StepRecord) -> dict[str, Any] | None:
    outcome = step.execution_outcome
    if outcome is None:
        return None
    if step.hypothesis is None:
        return {
            "outcome": outcome.outcome.value,
            "stage": "proposal_hypothesis",
            "reason_code": outcome.reason_code,
        }
    from scion.proposal.context_manager.history_projection import (
        proposal_pre_protocol_observations,
    )

    observations = proposal_pre_protocol_observations([step])
    if observations:
        return {"outcome": outcome.outcome.value, **observations[0]["outcome"]}
    stage = (
        step.protocol_result.stage.value
        if step.protocol_result is not None
        else str(step.failure_stage or outcome.provenance.get("stage") or "unknown")
    )
    return {
        "outcome": outcome.outcome.value,
        "stage": stage,
        "reason_code": outcome.reason_code,
    }


def _screening_protocol(step: StepRecord) -> dict[str, Any] | None:
    protocol = step.protocol_result
    if protocol is None:
        return None
    if protocol.stage is not ExperimentStage.SCREENING:
        raise ValueError("research history accepts screening Protocol only")
    from scion.proposal.context_manager.history_projection import (
        normalize_proposal_screening_observation,
        proposal_screening_history,
    )
    from scion.proposal.context_manager.manager import screening_record

    projected = proposal_screening_history(
        [{**screening_record(step), "relation": "current"}]
    )[0]
    evidence = dict(projected["experiment_evidence"])
    evidence.pop("decision_outcome", None)
    return normalize_proposal_screening_observation(
        {
            "candidate_composition": dict(projected.get("candidate_composition") or {}),
            "evidence": evidence,
        }
    )


def _decision(step: StepRecord) -> dict[str, Any] | None:
    if step.decision is None:
        return None
    return {
        "value": step.decision.value,
        "reason_codes": list(step.decision_reason_codes or ()),
        "engine_reason_codes": list(step.decision_engine_reason_codes or ()),
        "diagnostic_reason_codes": list(step.diagnostic_reason_codes or ()),
        "bypass_reason_codes": list(step.bypass_reason_codes or ()),
    }


def _normalize_hypothesis(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    item = dict(_mapping(value, _HYPOTHESIS, path="$.hypothesis"))
    for field in ("text", "change_locus", "target_weakness", "expected_effect"):
        if not isinstance(item[field], str):
            raise TypeError(f"research history hypothesis {field} must be a string")
    target = item["target_file"]
    if target is not None and (
        not isinstance(target, str) or normalize_relative_patch_path(target) != target
    ):
        raise ValueError("research history target_file must be canonical or null")
    return item


def _validate_record_relationships(record: Mapping[str, Any]) -> None:
    """Reject cross-field shapes that cannot be an ordinary step."""

    if record["hypothesis"] is not None:
        _validate_hypothesis_record(record)
        return
    if record["selected_hypothesis_research_basis"] is not None:
        raise ValueError(
            "hypothesis-free research history cannot carry a selected basis"
        )
    if any(record[field] is not None for field in ("patch", "protocol", "decision")):
        raise ValueError(
            "hypothesis-free research history cannot carry patch, Protocol, "
            "or Decision data"
        )
    outcome = record["outcome"]
    if not isinstance(outcome, Mapping):
        # A malformed record is rejected as one invalid evidence value regardless
        # of which nested field has the wrong runtime shape.
        raise ValueError(  # noqa: TRY004
            "hypothesis-free research history requires an outcome"
        )
    if set(outcome) != _OUTCOME_REQUIRED:
        raise ValueError(
            "hypothesis-free research history outcome must contain only "
            "typed terminal fields"
        )
    if outcome["stage"] != "proposal_hypothesis":
        raise ValueError(
            "hypothesis-free research history must fail at proposal_hypothesis"
        )
    if outcome["outcome"] == ExecutionOutcome.EVALUATED.value:
        raise ValueError("hypothesis-free research history cannot be evaluated")


def _validate_hypothesis_record(record: Mapping[str, Any]) -> None:
    outcome = record["outcome"]
    if not isinstance(outcome, Mapping):
        raise ValueError(  # noqa: TRY004
            "research history with a hypothesis requires an outcome"
        )
    if outcome["stage"] == "proposal_hypothesis":
        raise ValueError(
            "proposal_hypothesis research history cannot carry a hypothesis"
        )

    protocol = record["protocol"]
    decision = record["decision"]
    if protocol is None and decision is not None:
        if not (
            record["patch"] is not None
            and outcome["outcome"] == ExecutionOutcome.EVALUATED.value
            and outcome["stage"] == "canary"
            and decision["value"] == "abandon"
        ):
            raise ValueError(
                "research history Protocol and Decision may be separated only "
                "for an evaluated canary abandonment with a patch"
            )
        return
    if (protocol is None) != (decision is None):
        raise ValueError(
            "research history Protocol and Decision must be present together"
        )

    evaluated = outcome["outcome"] == ExecutionOutcome.EVALUATED.value
    if evaluated != (protocol is not None):
        raise ValueError(
            "research history evaluated outcome requires Protocol and Decision"
        )
    if protocol is None:
        return
    if record["patch"] is None:
        raise ValueError("research history Protocol requires a patch")
    protocol_stage = protocol["evidence"]["stage"]
    if outcome["stage"] != protocol_stage:
        raise ValueError(
            "research history outcome stage must match Protocol evidence stage"
        )


def _normalize_patch(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    changes = _mapping(value, frozenset({"changes"}), path="$.patch")["changes"]
    if not isinstance(changes, list) or not changes:
        raise ValueError("research history patch changes must be a nonempty array")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(changes):
        change = dict(_mapping(raw, _PATCH_CHANGE, path=f"$.patch.changes[{index}]"))
        path = normalize_relative_patch_path(change["file_path"])
        if path != change["file_path"] or path in seen:
            raise ValueError(
                "research history patch paths must be unique and canonical"
            )
        if change["action"] not in {"modify", "create", "delete"} or not isinstance(
            change["source"], str
        ):
            raise ValueError("research history patch change is invalid")
        seen.add(path)
        normalized.append(change)
    return {"changes": normalized}


def _normalize_outcome(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    item = dict(_mapping(value, _OUTCOME, required=_OUTCOME_REQUIRED, path="$.outcome"))
    if item["outcome"] not in {member.value for member in ExecutionOutcome}:
        raise ValueError("research history outcome is invalid")
    stage = _token(item["stage"], field="outcome.stage")
    if stage.lower() in _HELD_OUT:
        raise ValueError("research history cannot contain held-out stages")
    _token(item["reason_code"], field="outcome.reason_code")
    if "severity" in item and item["severity"] not in {"light", "heavy"}:
        raise ValueError("research history outcome severity is invalid")
    if "checks" in item:
        if not isinstance(item["checks"], list):
            raise TypeError("research history outcome checks must be an array")
        for index, check in enumerate(item["checks"]):
            _mapping(check, _CHECK, path=f"$.outcome.checks[{index}]")
    return item


def _normalize_protocol(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    from scion.proposal.context_manager.history_projection import (
        normalize_proposal_screening_observation,
    )

    projected = normalize_proposal_screening_observation(value)
    _validate_open_keys(projected, path="$.protocol")
    return projected


def _normalize_decision(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    item = dict(_mapping(value, _DECISION, path="$.decision"))
    _token(item["value"], field="decision.value")
    for field in _DECISION - {"value"}:
        if not isinstance(item[field], list):
            raise TypeError(f"research history decision {field} must be an array")
        for token in item[field]:
            _token(token, field=f"decision.{field}")
    return item


def _mapping(
    value: Any,
    allowed: frozenset[str],
    *,
    path: str,
    required: frozenset[str] | None = None,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"research history value at {path} must be a mapping")
    keys = set(value)
    required = allowed if required is None else required
    if (
        any(not isinstance(key, str) for key in value)
        or not required <= keys <= allowed
    ):
        raise ValueError(f"research history fields at {path} do not match schema")
    return value


def _token(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or _TOKEN.fullmatch(value) is None:
        raise ValueError(f"research history {field} must be a bounded token")
    return value


def _validate_safe_value(value: Any, *, path: str, depth: int) -> None:
    if depth > MAX_RESEARCH_HISTORY_DEPTH:
        raise ValueError(f"research history exceeds maximum depth at {path}")
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"non-finite research history number at {path}")
        return
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise TypeError(f"research history key at {path} must be a string")
            normalized = re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")
            if is_sensitive_research_key(key) or _FORBIDDEN_KEY.search(normalized):
                raise ValueError(f"forbidden research history field at {path}.{key}")
            _validate_safe_value(child, path=f"{path}.{key}", depth=depth + 1)
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _validate_safe_value(child, path=f"{path}[{index}]", depth=depth + 1)
        return
    raise TypeError(f"unsupported research history value at {path}")


def _validate_open_keys(value: Any, *, path: str) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")
            components = frozenset(normalized.split("_"))
            canonical_case_feedback_seed_field = (
                normalized in _CANONICAL_CASE_FEEDBACK_SEED_FIELDS
                and _CASE_FEEDBACK_PATH.fullmatch(path) is not None
            )
            if not canonical_case_feedback_seed_field and (
                normalized in _OPEN_FORBIDDEN
                or normalized.endswith(("_id", "_ids"))
                or components & _OPEN_COMPONENTS
            ):
                raise ValueError(f"forbidden research history field at {path}.{key}")
            _validate_open_keys(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _validate_open_keys(child, path=f"{path}[{index}]")


def _mapping_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate research history JSON key: {key}")
        result[key] = value
    return result


def _render(record: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(record, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _write_bytes_atomically(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "wb", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
        ) as tmp:
            tmp_path = tmp.name
            tmp.write(content)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_path, path)
        tmp_path = None
    finally:
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except FileNotFoundError:
                pass


__all__ = [
    "MAX_RESEARCH_HISTORY_DEPTH",
    "MAX_RESEARCH_HISTORY_FILES",
    "MAX_RESEARCH_HISTORY_FILE_BYTES",
    "MAX_RESEARCH_HISTORY_LINE_BYTES",
    "MAX_RESEARCH_HISTORY_RECORDS",
    "MAX_RESEARCH_HISTORY_TOTAL_BYTES",
    "RESEARCH_HISTORY_SCHEMA",
    "ResearchHistoryWriter",
    "load_research_histories",
    "normalize_research_history_record",
    "problem_id_from_spec",
    "project_research_history_step",
    "provider_research_history",
]
