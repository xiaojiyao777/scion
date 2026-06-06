"""Branch-local repeated contract failure routing signals."""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from scion.core.branch_hygiene import record_branch_lifecycle_policy_block
from scion.core.models import Branch, HypothesisProposal, mechanism_changes


REPEATED_CONTRACT_FAILURE_CODE = "REPEATED_CONTRACT_FAILURE"
REPEATED_CONTRACT_REROUTE_REASON = "repeated_contract_signature_reroute"
REPEATED_CONTRACT_THRESHOLD = 2
CONTRACT_PREVIEW_FAILURE_SIGNATURE_SCHEMA_VERSION = (
    "contract-preview-failure-signature.v1"
)

_UNKNOWN = "unknown"
_SAFE_TOKEN_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,127}$")
_CONTRACT_CODE_RE = re.compile(r"\bC\d+[A-Za-z0-9_]*\b")
_SNAKE_CODE_RE = re.compile(r"\b[a-z][a-z0-9]+(?:_[a-z0-9]+){2,}\b")
_GENERIC_CODES = frozenset(
    {
        "agent_quality_blocked",
        "agentic_proposal",
        "code_generation_failed",
        "contract_boundary_failure",
        "contract_preview_failed",
        "hypothesis_contract",
        "patch_contract",
        "schema_or_target_preview_failed",
        "self_check",
    }
)
_CONTRACT_HINTS = (
    "contract",
    "self_check",
    "preview",
    "algorithm_smoke_failure",
)


@dataclass(frozen=True)
class ContractFailureSignature:
    """Safe identity for a branch-local contract failure loop."""

    target_file: str
    mechanism_ids: tuple[str, ...]
    contract_check: str
    failure_category: str
    selected_surface: str

    @property
    def key(self) -> str:
        mechanisms = "+".join(self.mechanism_ids) if self.mechanism_ids else _UNKNOWN
        return "|".join(
            (
                f"target={self.target_file or _UNKNOWN}",
                f"mechanism={mechanisms}",
                f"check={self.contract_check or _UNKNOWN}",
                f"category={self.failure_category or _UNKNOWN}",
                f"surface={self.selected_surface or _UNKNOWN}",
            )
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "target_file": self.target_file or _UNKNOWN,
            "mechanism_ids": list(self.mechanism_ids),
            "contract_check": self.contract_check or _UNKNOWN,
            "failure_category": self.failure_category or _UNKNOWN,
            "selected_surface": self.selected_surface or _UNKNOWN,
        }


@dataclass(frozen=True)
class RepeatedContractRecord:
    signature: ContractFailureSignature | None
    count: int = 0
    threshold: int = REPEATED_CONTRACT_THRESHOLD
    threshold_reached: bool = False
    failure_code: str = REPEATED_CONTRACT_FAILURE_CODE

    @property
    def signature_key(self) -> str:
        return self.signature.key if self.signature is not None else ""


def extract_contract_failure_signature(
    failure_detail: str | None,
    hypothesis: HypothesisProposal | None,
    session_ref: Mapping[str, Any] | None,
    *,
    failure_stage: str | None = None,
) -> ContractFailureSignature | None:
    """Return a structured signature without retaining free-form detail text."""
    primary = _primary_failure(session_ref)
    target_file = _safe_path(
        getattr(hypothesis, "target_file", None)
        or _mapping_value(primary, "target_file")
        or _mapping_value(session_ref, "target_file")
    )
    mechanism_ids = _mechanism_ids(hypothesis)
    selected_surface = _safe_token(
        getattr(hypothesis, "change_locus", None)
        or _mapping_value(primary, "selected_surface")
        or _nested_value(session_ref, ("rejection_constraint", "selected_surface")),
        default=_UNKNOWN,
    )
    failure_category = _safe_token(
        _mapping_value(primary, "category")
        or _mapping_value(session_ref, "failure_category")
        or _infer_failure_category(failure_detail, failure_stage),
        default=_UNKNOWN,
    )
    contract_check = _safe_token(
        _first_present(
            _mapping_value(primary, "code"),
            _mapping_value(primary, "check"),
            _mapping_value(session_ref, "failure_code"),
            _first_sequence_item(_mapping_value(session_ref, "contract_preview_codes")),
            _first_sequence_item(_mapping_value(primary, "contract_preview_codes")),
            _contract_check_from_detail(failure_detail),
        ),
        default="generic_contract_failure",
    )

    if not _looks_contract_related(
        failure_stage=failure_stage,
        failure_detail=failure_detail,
        failure_category=failure_category,
        contract_check=contract_check,
    ):
        return None

    return ContractFailureSignature(
        target_file=target_file,
        mechanism_ids=mechanism_ids,
        contract_check=contract_check,
        failure_category=failure_category,
        selected_surface=selected_surface,
    )


def record_contract_failure_attempt(
    branch: Branch | None,
    failure_detail: str | None,
    hypothesis: HypothesisProposal | None,
    session_ref: Mapping[str, Any] | None,
    *,
    failure_stage: str | None = None,
    threshold: int = REPEATED_CONTRACT_THRESHOLD,
    now: datetime | None = None,
) -> RepeatedContractRecord:
    """Record one branch-local contract failure and mark reroute at threshold."""
    if branch is None:
        return RepeatedContractRecord(None, threshold=threshold)
    signature = extract_contract_failure_signature(
        failure_detail,
        hypothesis,
        session_ref,
        failure_stage=failure_stage,
    )
    if signature is None:
        return RepeatedContractRecord(None, threshold=threshold)

    timestamp = (now or datetime.now()).isoformat()
    summary = dict(getattr(branch, "branch_evidence_summary", {}) or {})
    repeated = dict(summary.get("repeated_contract_failures") or {})
    records = _records_by_key(repeated.get("records"))
    prior = dict(records.get(signature.key) or {})
    count = max(0, int(prior.get("count", 0) or 0)) + 1
    threshold_reached = count >= max(1, int(threshold))
    record = {
        "signature_key": signature.key,
        "signature": signature.as_dict(),
        "count": count,
        "first_seen_at": prior.get("first_seen_at") or timestamp,
        "last_seen_at": timestamp,
        "threshold": threshold,
        "threshold_reached": threshold_reached,
    }
    records[signature.key] = record
    repeated.update(
        {
            "schema_version": "repeated-contract-failures.v1",
            "threshold": threshold,
            "last_signature_key": signature.key,
            "last_signature": signature.as_dict(),
            "reroute_recommended": threshold_reached,
            "reason_code": (
                REPEATED_CONTRACT_FAILURE_CODE if threshold_reached else None
            ),
            "records": _bounded_records(records.values()),
        }
    )
    summary["repeated_contract_failures"] = _drop_empty(repeated)
    branch.branch_evidence_summary = summary
    branch.updated_at = now or datetime.now()

    if threshold_reached:
        mark_repeated_contract_reroute(
            branch,
            signature,
            count=count,
            threshold=threshold,
            now=now,
        )

    return RepeatedContractRecord(
        signature,
        count=count,
        threshold=threshold,
        threshold_reached=threshold_reached,
    )


def contract_preview_failure_signature_feedback(
    branch: Branch | None,
) -> dict[str, Any]:
    """Return proposal-visible hard negative feedback for the latest signature."""
    if branch is None:
        return {}
    summary = getattr(branch, "branch_evidence_summary", {}) or {}
    if not isinstance(summary, Mapping):
        return {}
    repeated = summary.get("repeated_contract_failures")
    if not isinstance(repeated, Mapping):
        return {}
    signature = repeated.get("last_signature")
    if not isinstance(signature, Mapping):
        return {}
    signature_key = str(repeated.get("last_signature_key") or "").strip()
    records = _records_by_key(repeated.get("records"))
    record = dict(records.get(signature_key) or {})
    count = _safe_int(
        record.get("count"),
        default=max(1, _safe_int(repeated.get("count"))),
    )
    threshold = _safe_int(
        record.get("threshold"),
        default=_safe_int(
            repeated.get("threshold"),
            default=REPEATED_CONTRACT_THRESHOLD,
        ),
    )
    threshold_reached = bool(
        record.get("threshold_reached")
        or repeated.get("reroute_recommended")
        or (count >= max(1, threshold))
    )
    target_file = _safe_path(signature.get("target_file"))
    contract_check = _safe_token(
        signature.get("contract_check"),
        default="generic_contract_failure",
    )
    failure_category = _safe_token(
        signature.get("failure_category"),
        default="contract_boundary_failure",
    )
    selected_surface = _safe_token(
        signature.get("selected_surface"),
        default=_UNKNOWN,
    )
    mechanism_ids = _string_sequence(signature.get("mechanism_ids"))
    digest_payload = {
        "target_file": target_file,
        "mechanism_ids": mechanism_ids,
        "contract_check": contract_check,
        "failure_category": failure_category,
        "selected_surface": selected_surface,
    }
    failure_digest = _stable_digest(digest_payload)
    return _drop_empty(
        {
            "schema_version": CONTRACT_PREVIEW_FAILURE_SIGNATURE_SCHEMA_VERSION,
            "source": "branch.repeated_contract_failures",
            "feedback_class": "hard_negative",
            "failure_digest": failure_digest,
            "signature_key_digest": _stable_digest(signature_key),
            "check_id": contract_check,
            "category_id": failure_category,
            "contract_check": contract_check,
            "failure_category": failure_category,
            "target_file": target_file,
            "target_path": target_file,
            "selected_surface": selected_surface,
            "mechanism_ids": list(mechanism_ids),
            "count": count,
            "signature_count": count,
            "threshold": threshold,
            "threshold_reached": threshold_reached,
            "recent_branch_ids": _recent_branch_ids(branch),
            "recent_failure_digests": _recent_failure_digests(records.values()),
            "proposal_visibility_only": True,
            "decision_features_excluded": True,
            "ordinary_retry_allowed": False,
            "required_next_step": (
                "reselect_target_or_clean_branch"
                if threshold_reached
                else "repair_same_signature_or_reselect_target"
            ),
            "same_signature_retry_policy": "force_repair_or_reselect",
            "forbidden_write_pattern": {
                "pattern_id": "same_target_check_mechanism_signature",
                "target_file": target_file,
                "check_id": contract_check,
                "category_id": failure_category,
                "mechanism_ids": list(mechanism_ids),
            },
        }
    )


def mark_repeated_contract_reroute(
    branch: Branch,
    signature: ContractFailureSignature,
    *,
    count: int,
    threshold: int = REPEATED_CONTRACT_THRESHOLD,
    now: datetime | None = None,
) -> None:
    """Attach generic reroute signals after repeated same-signature failures."""
    if REPEATED_CONTRACT_FAILURE_CODE not in branch.failure_codes:
        branch.failure_codes.append(REPEATED_CONTRACT_FAILURE_CODE)
    branch.pending_retry = False
    branch.consecutive_llm_retries = 0
    block = record_branch_lifecycle_policy_block(
        branch,
        "repeated_contract_failure: repeated_contract_signature_threshold_reached",
    )
    block.update(
        {
            "reason": REPEATED_CONTRACT_REROUTE_REASON,
            "failure_code": REPEATED_CONTRACT_FAILURE_CODE,
            "reroute_reason": REPEATED_CONTRACT_REROUTE_REASON,
            "failure_signature": signature.as_dict(),
            "signature_key": signature.key,
            "signature_count": count,
            "threshold": threshold,
            "same_hypothesis_retry": "blocked",
            "next_selection": "clean_branch_or_new_hypothesis_or_new_target",
        }
    )
    branch.last_branch_lifecycle_policy_block = block
    branch.branch_lifecycle_reroute_reason = REPEATED_CONTRACT_REROUTE_REASON
    branch.updated_at = now or datetime.now()


def _primary_failure(ref: Mapping[str, Any] | None) -> Mapping[str, Any]:
    primary = _mapping_value(ref, "primary_failure")
    return primary if isinstance(primary, Mapping) else {}


def _mapping_value(mapping: Mapping[str, Any] | None, key: str) -> Any:
    if not isinstance(mapping, Mapping):
        return None
    return mapping.get(key)


def _nested_value(mapping: Mapping[str, Any] | None, keys: tuple[str, ...]) -> Any:
    current: Any = mapping
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _mechanism_ids(hypothesis: HypothesisProposal | None) -> tuple[str, ...]:
    ids = [
        _safe_token(change.id, default="")
        for change in mechanism_changes(hypothesis) if str(change.id or "").strip()
    ]
    ids = [item for item in ids if item]
    return tuple(dict.fromkeys(ids)) or (_UNKNOWN,)


def _safe_token(value: Any, *, default: str) -> str:
    text = str(value or "").strip().strip("'\"`[](){}")
    if not text:
        return default
    text = re.split(r"[\s,;]+", text, maxsplit=1)[0]
    text = re.sub(r"[^A-Za-z0-9_.:-]+", "_", text).strip("_.:-").lower()
    if not text:
        return default
    if not text[0].isalpha():
        text = f"id_{text}"
    if len(text) > 128:
        text = text[:128].rstrip("_.:-")
    return text if _SAFE_TOKEN_RE.fullmatch(text) else default


def _safe_path(value: Any) -> str:
    text = str(value or "").strip().replace("\\", "/")
    if not text:
        return _UNKNOWN
    parts = [
        _safe_token(part, default="")
        for part in text.split("/")
        if part not in ("", ".", "..")
    ]
    parts = [part for part in parts if part]
    if not parts:
        return _UNKNOWN
    return "/".join(parts[-6:])


def _first_present(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", (), [], {}):
            return value
    return None


def _first_sequence_item(value: Any) -> Any:
    if isinstance(value, (str, bytes)):
        return value
    if isinstance(value, Iterable):
        for item in value:
            if item not in (None, ""):
                return item
    return None


def _infer_failure_category(
    failure_detail: str | None,
    failure_stage: str | None,
) -> str:
    text = str(failure_detail or "").lower()
    if "algorithm_smoke_failure" in text:
        return "algorithm_smoke_failure"
    if "contract_boundary_failure" in text:
        return "contract_boundary_failure"
    if "schema_output_failure" in text:
        return "schema_output_failure"
    stage = _safe_token(failure_stage, default="")
    if "contract" in stage:
        return stage
    if "contract" in text:
        return "contract"
    return _UNKNOWN


def _contract_check_from_detail(failure_detail: str | None) -> str:
    text = str(failure_detail or "")
    for pattern in (_CONTRACT_CODE_RE, _SNAKE_CODE_RE):
        for match in pattern.findall(text):
            token = _safe_token(match, default="")
            if token and token not in _GENERIC_CODES:
                return token
    return ""


def _looks_contract_related(
    *,
    failure_stage: str | None,
    failure_detail: str | None,
    failure_category: str,
    contract_check: str,
) -> bool:
    stage = str(failure_stage or "").lower()
    detail = str(failure_detail or "").lower()
    category = str(failure_category or "").lower()
    if "contract" in stage:
        return True
    if any(hint in detail for hint in _CONTRACT_HINTS):
        return True
    if any(hint in category for hint in _CONTRACT_HINTS):
        return True
    return bool(re.fullmatch(r"c\d+[a-z0-9_]*", contract_check))


def _records_by_key(value: Any) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes, Mapping)):
        return records
    for item in value:
        if not isinstance(item, Mapping):
            continue
        key = str(item.get("signature_key") or "")
        if key:
            records[key] = dict(item)
    return records


def _bounded_records(records: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(
        (dict(record) for record in records),
        key=lambda item: str(item.get("last_seen_at") or ""),
    )
    return ordered[-16:]


def _drop_empty(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in payload.items()
        if value not in (None, "", (), [], {})
    }


def _safe_int(value: Any, *, default: int = 0) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return max(0, int(default))


def _string_sequence(value: Any) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)):
        items = [value]
    else:
        try:
            items = list(value)
        except TypeError:
            items = []
    safe = [
        _safe_token(item, default="")
        for item in items
        if str(item or "").strip()
    ]
    safe = [item for item in safe if item]
    return tuple(dict.fromkeys(safe)) or (_UNKNOWN,)


def _stable_digest(value: Any, *, length: int = 16) -> str:
    rendered = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()[:length]


def _recent_branch_ids(branch: Branch) -> list[str]:
    branch_id = str(getattr(branch, "branch_id", "") or "").strip()
    if not branch_id:
        return []
    return [re.sub(r"[^A-Za-z0-9_.:-]+", "_", branch_id)[:128]]


def _recent_failure_digests(records: Iterable[Mapping[str, Any]]) -> list[str]:
    ordered = sorted(
        (dict(record) for record in records if isinstance(record, Mapping)),
        key=lambda item: str(item.get("last_seen_at") or ""),
    )
    digests: list[str] = []
    for record in ordered[-4:]:
        signature = record.get("signature")
        if isinstance(signature, Mapping):
            digest = _stable_digest(signature)
        else:
            digest = _stable_digest(record.get("signature_key") or "")
        if digest not in digests:
            digests.append(digest)
    return digests


__all__ = [
    "ContractFailureSignature",
    "RepeatedContractRecord",
    "CONTRACT_PREVIEW_FAILURE_SIGNATURE_SCHEMA_VERSION",
    "REPEATED_CONTRACT_FAILURE_CODE",
    "REPEATED_CONTRACT_REROUTE_REASON",
    "REPEATED_CONTRACT_THRESHOLD",
    "contract_preview_failure_signature_feedback",
    "extract_contract_failure_signature",
    "mark_repeated_contract_reroute",
    "record_contract_failure_attempt",
]
