"""Report-only proposal trajectory manifest artifacts.

Current statistics are derived only from durable direct proposal-attempt
transitions and formal-candidate artifacts. Historical agentic indexes are
reported as unsupported and never mixed into current counts.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scion.core.proposal_trajectory_attempts import (
    PROPOSAL_ATTEMPT_DB_REF,
    read_proposal_attempt_transitions,
)

SCHEMA_VERSION = "scion.proposal_trajectory_manifest.v1"
COMPARISON_SCHEMA_VERSION = "scion.proposal_trajectory_comparison.v1"
DEFAULT_MANIFEST_FILENAME = "proposal_trajectory_manifest.v1.json"
DEFAULT_COMPARISON_FILENAME = "proposal_trajectory_comparison.v1.json"
OBSERVED_CONTROL_ARMS = {"on", "record_only"}
_CONTROL_PAIR_KEY_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")

_GUARDRAILS: dict[str, bool] = {
    "report_only": True,
    "decision_features_excluded": True,
    "comparison_is_decision_input": False,
    "campaign_state_mutated": False,
    "scheduler_state_mutated": False,
    "promotion_state_mutated": False,
    "raw_prompt_excluded": True,
    "raw_response_excluded": True,
    "patch_body_excluded": True,
}

_FORMAL_CANDIDATE_INDEX_REF = "artifacts/formal_candidates/index.jsonl"


def build_proposal_trajectory_manifest(
    campaign_dir: str | Path,
    *,
    observed_control_arm: str,
    control_pair_key: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build the direct-only durable proposal trajectory manifest."""

    arm = str(observed_control_arm or "").strip()
    if arm not in OBSERVED_CONTROL_ARMS:
        raise ValueError(
            "observed_control_arm must be one of: "
            + ", ".join(sorted(OBSERVED_CONTROL_ARMS))
        )
    campaign_path = Path(campaign_dir).expanduser().resolve()
    formal_index_path = campaign_path / "artifacts" / "formal_candidates" / "index.jsonl"
    formal_rows, formal_index_status = _read_formal_candidate_index(formal_index_path)
    formal_join_index = _FormalCandidateJoinIndex(formal_rows)
    inventory = read_proposal_attempt_transitions(
        campaign_path / PROPOSAL_ATTEMPT_DB_REF
    )
    attempts = [
        _attempt_fingerprint(item, formal_join_index=formal_join_index)
        for item in inventory["attempts"]
    ]
    stats = inventory["stats"]
    joined = sum(
        1 for item in attempts
        if _mapping(item.get("proposal_fingerprint")).get("formal_candidate_ref")
    )
    missing_joins = [
        {
            "attempt_id": _clean_str(item.get("attempt_id")),
            "branch_id": _clean_str(item.get("branch_id")),
            "reason": _clean_str(
                _mapping(item.get("replayability")).get(
                    "formal_candidate_join_status"
                )
            ),
        }
        for item in attempts
        if not _mapping(item.get("proposal_fingerprint")).get(
            "formal_candidate_ref"
        )
    ]
    unsupported: list[dict[str, Any]] = []
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": "proposal_trajectory_manifest",
        "generated_at": generated_at or _utc_now_iso(),
        "campaign_dir": str(campaign_path),
        "observed_control_arm": arm,
        "control_pair_key": _sanitize_control_pair_key(control_pair_key),
        **_GUARDRAILS,
        "source_indexes": {
            "formal_candidate_index_ref": (
                _FORMAL_CANDIDATE_INDEX_REF if formal_index_path.exists() else ""
            ),
            "formal_candidate_index_status": formal_index_status,
            "proposal_attempt_db_ref": (
                PROPOSAL_ATTEMPT_DB_REF
                if stats.get("source_status") != "missing" else ""
            ),
            "proposal_attempt_db_status": stats.get("source_status"),
            "unsupported_historical": unsupported,
        },
        "counts": {
            "attempt_count": len(attempts),
            "proposal_trajectory_count": len(attempts),
            "proposal_attempt_transition_count": stats.get("valid_row_count", 0),
            "proposal_attempt_invalid_row_count": stats.get("invalid_row_count", 0),
            "formal_candidate_count": len(formal_rows),
            "formal_candidate_replayable_count": len(
                formal_join_index.replayable_rows
            ),
            "formal_candidate_joined_attempt_count": joined,
            "zero_evaluated_attempt_count": sum(
                1 for item in attempts
                if not _mapping(item.get("proposal_fingerprint")).get(
                    "formal_candidate_ref"
                )
            ),
        },
        "coverage": {
            "attempts_with_formal_candidate": joined,
            "missing_joins": missing_joins,
            "missing_join_count": len(missing_joins),
            "formal_candidate_join_basis_counts": dict(
                sorted(formal_join_index.join_basis_counts.items())
            ),
            "proposal_attempt_invalid_rows": stats.get("invalid_row_count", 0),
        },
        "proposal_attempt_inventory": stats,
        "call_kind_counts": dict(
            sorted(
                Counter(
                    _clean_str(item.get("terminal_phase"))
                    for item in inventory["attempts"]
                    if _clean_str(item.get("terminal_phase"))
                ).items()
            )
        ),
        "proposal_distributions": _proposal_distributions(attempts),
        "attempts": attempts,
    }


def write_proposal_trajectory_manifest(
    campaign_dir: str | Path,
    *,
    observed_control_arm: str,
    control_pair_key: str | None = None,
    output_path: str | Path,
) -> Path:
    """Build and write a proposal trajectory manifest JSON artifact."""

    destination = Path(output_path).expanduser().resolve()
    manifest = build_proposal_trajectory_manifest(
        campaign_dir,
        observed_control_arm=observed_control_arm,
        control_pair_key=control_pair_key,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(_stable_json(manifest), encoding="utf-8")
    return destination


def build_proposal_trajectory_comparison(
    left: str | Path | Mapping[str, Any],
    right: str | Path | Mapping[str, Any],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Compare two report-only proposal trajectory manifests."""

    left_manifest = _load_manifest(left)
    right_manifest = _load_manifest(right)
    _validate_manifest(left_manifest, side="left")
    _validate_manifest(right_manifest, side="right")

    left_key = _manifest_control_pair_key(left_manifest, side="left")
    right_key = _manifest_control_pair_key(right_manifest, side="right")
    paired_control_key = left_key if left_key and left_key == right_key else ""
    observational_only = not bool(paired_control_key)

    comparison = {
        "schema_version": COMPARISON_SCHEMA_VERSION,
        "artifact_kind": "proposal_trajectory_comparison",
        "generated_at": generated_at or _utc_now_iso(),
        **_GUARDRAILS,
        "observational_only": observational_only,
        "llm_deterministic_replay": False,
        "control_pair_key": paired_control_key,
        "causal_replay_label": (
            "observational_only_not_causal_llm_trajectory_replay"
            if observational_only
            else "control_pair_key_matched_not_deterministic_llm_replay"
        ),
        "summary": {
            "left": _manifest_count_summary(left_manifest),
            "right": _manifest_count_summary(right_manifest),
            "delta": _count_delta(left_manifest, right_manifest),
        },
        "call_kind_counts": _paired_counter_summary(
            left_manifest.get("call_kind_counts"),
            right_manifest.get("call_kind_counts"),
        ),
        "proposal_distributions": {
            key: _paired_counter_summary(
                _mapping_at(left_manifest, "proposal_distributions", key),
                _mapping_at(right_manifest, "proposal_distributions", key),
            )
            for key in (
                "selected_surface",
                "action",
                "target_file",
                "mechanism_id",
            )
        },
        "coverage": {
            "left": _coverage_summary(left_manifest),
            "right": _coverage_summary(right_manifest),
        },
        "missing_joins": {
            "left": _missing_joins(left_manifest),
            "right": _missing_joins(right_manifest),
        },
    }
    return comparison


def write_proposal_trajectory_comparison(
    left: str | Path,
    right: str | Path,
    *,
    output_path: str | Path,
) -> Path:
    """Build and write a proposal trajectory comparison JSON artifact."""

    destination = Path(output_path).expanduser().resolve()
    comparison = build_proposal_trajectory_comparison(left, right)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(_stable_json(comparison), encoding="utf-8")
    return destination


def _attempt_fingerprint(
    attempt: Mapping[str, Any],
    *,
    formal_join_index: "_FormalCandidateJoinIndex",
) -> dict[str, Any]:
    phases = [
        dict(item)
        for item in attempt.get("phases", ())
        if isinstance(item, Mapping)
    ]
    terminal = phases[-1] if phases else {}
    formal = formal_join_index.match_attempt(
        {
            "attempt_id": _clean_str(attempt.get("attempt_id")),
            "event_id": _clean_str(terminal.get("event_id")),
            "branch_id": _clean_str(attempt.get("branch_id")),
            "hypothesis_id": _clean_str(terminal.get("hypothesis_id")),
        }
    )
    return _drop_empty(
        {
            **dict(attempt),
            "proposal_fingerprint": _drop_empty(
                {
                    "hypothesis_id": terminal.get("hypothesis_id"),
                    "hypothesis_digest": terminal.get("hypothesis_digest"),
                    "patch_digest": terminal.get("patch_digest"),
                    "formal_candidate_ref": formal.get("artifact_ref"),
                    "formal_candidate_id": formal.get("candidate_id"),
                    "formal_candidate_join_basis": formal.get("join_basis"),
                }
            ),
            "replayability": {
                "summary": "posthoc_audit_fingerprints_only_no_llm_replay",
                "formal_candidate_joined": bool(formal.get("artifact_ref")),
                "formal_candidate_join_status": (
                    "joined"
                    if formal.get("artifact_ref")
                    else formal.get("join_status", "missing")
                ),
            },
        }
    )


class _FormalCandidateJoinIndex:
    def __init__(self, rows: list[Mapping[str, Any]]) -> None:
        self.rows = rows
        self.replayable_rows = [
            row for row in rows if _is_replayable_formal_candidate_row(row)
        ]
        self.logical_rows = _logical_formal_candidate_rows(self.replayable_rows)
        self.join_basis_counts: Counter[str] = Counter()
        self._by_attempt = _index_unique(
            self.logical_rows, "proposal_attempt_id"
        )
        self._by_attempt_event = _index_unique(
            self.logical_rows, "proposal_attempt_event_id"
        )

    def match_attempt(self, attempt: Mapping[str, str]) -> dict[str, str]:
        match: Mapping[str, Any] | None = None
        basis = ""
        for candidate_basis, key, index in (
            ("proposal_attempt_id", attempt.get("attempt_id"), self._by_attempt),
            (
                "proposal_attempt_event_id",
                attempt.get("event_id"),
                self._by_attempt_event,
            ),
        ):
            if not key:
                continue
            match = index.get(str(key))
            if match is not None:
                basis = candidate_basis
                break
        if not match:
            return {"join_status": "missing_formal_candidate_join"}
        return self._matched_projection(match, basis=basis)

    def _matched_projection(
        self,
        match: Mapping[str, Any],
        *,
        basis: str,
    ) -> dict[str, str]:
        self.join_basis_counts[basis] += 1
        return {
            "candidate_id": _clean_str(match.get("candidate_id")),
            "artifact_ref": _clean_str(match.get("artifact_ref")),
            "patch_digest": _clean_str(
                match.get("patch_digest") or match.get("patch_hash")
            ),
            "join_basis": basis,
        }


def _is_replayable_formal_candidate_row(row: Mapping[str, Any]) -> bool:
    missing = row.get("missing_replay_identity_keys")
    if isinstance(missing, list) and missing:
        return False
    return (
        _clean_str(row.get("artifact_status")) == "recorded"
        and _clean_str(row.get("replay_identity_status")) == "complete"
    )


def _logical_formal_candidate_rows(
    rows: list[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    grouped: dict[str, tuple[Mapping[str, Any], int]] = {}
    order: list[str] = []
    for row_index, row in enumerate(rows):
        key = _formal_candidate_logical_key(row, row_index)
        if not key:
            continue
        existing = grouped.get(key)
        if existing is None:
            order.append(key)
            grouped[key] = (row, row_index)
            continue
        if _formal_candidate_preference_key(
            row,
            row_index,
        ) > _formal_candidate_preference_key(*existing):
            grouped[key] = (row, row_index)
    return [grouped[key][0] for key in order]


def _formal_candidate_logical_key(row: Mapping[str, Any], row_index: int) -> str:
    branch_id = _clean_str(row.get("branch_id"))
    if not branch_id:
        return ""
    for key in (
        "proposal_attempt_id",
        "proposal_attempt_event_id",
        "hypothesis_id",
        "candidate_id",
    ):
        value = _clean_str(row.get(key))
        if value:
            return _composite_key((branch_id, key, value))
    return _composite_key((branch_id, "row", str(row_index)))


def _formal_candidate_preference_key(
    row: Mapping[str, Any],
    row_index: int,
) -> tuple[int, int, int, int]:
    return (
        1 if _string_list(row.get("activation_files")) else 0,
        len(_string_list(row.get("target_files"))),
        len(_string_list(row.get("proposal_target_files"))),
        -row_index,
    )


def _read_formal_candidate_index(
    index_path: Path,
) -> tuple[list[Mapping[str, Any]], str]:
    if not index_path.exists():
        return [], "missing"
    rows: list[Mapping[str, Any]] = []
    with index_path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"invalid JSON in formal candidate index line {line_number}"
                ) from exc
            if not isinstance(row, Mapping):
                raise ValueError(
                    f"formal candidate index line {line_number} is not an object"
                )
            rows.append(row)
    return rows, "available"


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON artifact: {path}") from exc


def _load_manifest(value: str | Path | Mapping[str, Any]) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    raw = _read_json(Path(value).expanduser().resolve())
    if not isinstance(raw, Mapping):
        raise ValueError(f"manifest must be a JSON object: {value}")
    return raw


def _validate_manifest(manifest: Mapping[str, Any], *, side: str) -> None:
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"{side} manifest schema_version must be {SCHEMA_VERSION}")
    for key, expected in _GUARDRAILS.items():
        if manifest.get(key) is not expected:
            raise ValueError(f"{side} manifest guardrail mismatch: {key}")
    _manifest_control_pair_key(manifest, side=side)


def _proposal_distributions(attempts: list[Mapping[str, Any]]) -> dict[str, dict[str, int]]:
    selected_surface: Counter[str] = Counter()
    action: Counter[str] = Counter()
    target_file: Counter[str] = Counter()
    mechanism_id: Counter[str] = Counter()
    for attempt in attempts:
        proposal = _mapping(attempt.get("proposal_fingerprint"))
        selected_surface[_clean_str(proposal.get("selected_surface")) or "unknown"] += 1
        action[_clean_str(proposal.get("action")) or "unknown"] += 1
        target_file[_clean_str(proposal.get("target_file")) or "unknown"] += 1
        for mechanism in _string_list(proposal.get("mechanism_ids")):
            mechanism_id[mechanism] += 1
    return {
        "selected_surface": dict(sorted(selected_surface.items())),
        "action": dict(sorted(action.items())),
        "target_file": dict(sorted(target_file.items())),
        "mechanism_id": dict(sorted(mechanism_id.items())),
    }


def _manifest_count_summary(manifest: Mapping[str, Any]) -> dict[str, int]:
    counts = _mapping(manifest.get("counts"))
    return {
        "attempt_count": _int_or_zero(counts.get("attempt_count")),
        "proposal_trajectory_count": _int_or_zero(
            counts.get("proposal_trajectory_count")
        ),
        "formal_candidate_count": _int_or_zero(counts.get("formal_candidate_count")),
    }


def _count_delta(
    left_manifest: Mapping[str, Any],
    right_manifest: Mapping[str, Any],
) -> dict[str, int]:
    left = _manifest_count_summary(left_manifest)
    right = _manifest_count_summary(right_manifest)
    return {key: right[key] - left[key] for key in sorted(left)}


def _paired_counter_summary(left: Any, right: Any) -> dict[str, dict[str, int]]:
    left_counts = {str(key): _int_or_zero(value) for key, value in _mapping(left).items()}
    right_counts = {
        str(key): _int_or_zero(value) for key, value in _mapping(right).items()
    }
    keys = sorted(set(left_counts) | set(right_counts))
    return {
        "left": {key: left_counts.get(key, 0) for key in keys},
        "right": {key: right_counts.get(key, 0) for key in keys},
        "delta": {
            key: right_counts.get(key, 0) - left_counts.get(key, 0) for key in keys
        },
    }


def _coverage_summary(manifest: Mapping[str, Any]) -> dict[str, int]:
    coverage = _mapping(manifest.get("coverage"))
    return {
        "attempts_with_formal_candidate": _int_or_zero(
            coverage.get("attempts_with_formal_candidate")
        ),
        "proposal_attempt_invalid_rows": _int_or_zero(
            coverage.get("proposal_attempt_invalid_rows")
        ),
        "missing_join_count": _int_or_zero(coverage.get("missing_join_count")),
    }


def _missing_joins(manifest: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    coverage = _mapping(manifest.get("coverage"))
    joins = coverage.get("missing_joins")
    if not isinstance(joins, list):
        return []
    return [item for item in joins if isinstance(item, Mapping)]


def _mapping_at(manifest: Mapping[str, Any], *keys: str) -> Mapping[str, Any]:
    current: Any = manifest
    for key in keys:
        current = _mapping(current).get(key)
    return _mapping(current)


def _index_unique(
    rows: list[Mapping[str, Any]],
    key: str,
) -> dict[str, Mapping[str, Any]]:
    values: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        row_key = _clean_str(row.get(key))
        if not row_key:
            continue
        values.setdefault(row_key, []).append(row)
    return {row_key: items[0] for row_key, items in values.items() if len(items) == 1}


def _composite_key(values: Iterable[Any]) -> str:
    parts = [_clean_str(value) for value in values]
    if not all(parts):
        return ""
    return "\x1f".join(parts)


def _stable_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _manifest_control_pair_key(manifest: Mapping[str, Any], *, side: str) -> str:
    if "control_pair_key" not in manifest or manifest.get("control_pair_key") == "":
        return ""
    try:
        return _sanitize_control_pair_key(manifest.get("control_pair_key"))
    except ValueError as exc:
        raise ValueError(f"{side} manifest {exc}") from exc


def _sanitize_control_pair_key(value: Any) -> str:
    if value is None:
        return ""
    key = str(value).strip()
    if not key:
        raise ValueError("control_pair_key must be non-empty after trimming")
    if len(key) > 128:
        raise ValueError("control_pair_key must be at most 128 characters")
    if not _CONTROL_PAIR_KEY_RE.fullmatch(key):
        raise ValueError(
            "control_pair_key must contain only [A-Za-z0-9._:-] characters"
        )
    return key


def _clean_str(value: Any) -> str:
    return str(value or "").strip()


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        values: Iterable[Any] = [value]
    elif isinstance(value, Iterable) and not isinstance(value, Mapping):
        values = value
    else:
        values = []
    compact: list[str] = []
    for item in values:
        text = _clean_str(item)
        if text and text not in compact:
            compact.append(text)
    return compact


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _drop_empty(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): value
        for key, value in payload.items()
        if value not in (None, "", (), [], {})
    }


def _int_or_none(value: Any) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _int_or_zero(value: Any) -> int:
    result = _int_or_none(value)
    return result if result is not None else 0


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "COMPARISON_SCHEMA_VERSION",
    "DEFAULT_COMPARISON_FILENAME",
    "DEFAULT_MANIFEST_FILENAME",
    "SCHEMA_VERSION",
    "build_proposal_trajectory_comparison",
    "build_proposal_trajectory_manifest",
    "write_proposal_trajectory_comparison",
    "write_proposal_trajectory_manifest",
]
