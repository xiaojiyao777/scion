"""Campaign accounting helpers for status and summary payloads."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Iterable, Mapping

from scion.core.models import StepRecord
from scion.core.public_refs import public_artifact_ref
from scion.proposal.session_trace_index import SESSION_TRACE_INDEX_NAME

logger = logging.getLogger(__name__)


def proposal_accounting_fields(
    *,
    campaign_dir: str | Path,
    steps: Iterable[StepRecord] = (),
    loop_status: Mapping[str, Any] | None = None,
    state: Mapping[str, Any] | None = None,
    round_num: int | None = None,
    screened_rounds: int | None = None,
    agentic_artifact_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Return explicit counters that disambiguate legacy proposal attempts."""
    step_list = list(steps)
    loop = loop_status if isinstance(loop_status, Mapping) else {}
    state_map = state if isinstance(state, Mapping) else {}
    request_counts = llm_request_kind_counts(campaign_dir)
    if not request_counts and isinstance(
        state_map.get("llm_request_kind_counts"),
        Mapping,
    ):
        request_counts = {
            str(kind): _first_int(value, default=0)
            for kind, value in state_map["llm_request_kind_counts"].items()
        }
    campaign_steps = _first_int(
        loop.get("campaign_steps"),
        loop.get("loop_steps"),
        state_map.get("campaign_steps"),
        state_map.get("n_steps"),
        len(step_list) if step_list else None,
        round_num,
        default=0,
    )
    screened = _first_int(
        screened_rounds,
        state_map.get("screened_rounds"),
        state_map.get("screened_experiments"),
        default=0,
    )
    quality_blocks = _first_int(
        loop.get("quality_blocks"),
        loop.get("proposal_quality_blocks_consumed"),
        state_map.get("quality_blocks"),
        default=0,
    )
    computed_agentic_sessions = agentic_session_count(
        campaign_dir=campaign_dir,
        steps=step_list,
        agentic_artifact_dir=agentic_artifact_dir,
    )
    agentic_sessions = (
        computed_agentic_sessions
        if computed_agentic_sessions > 0
        else _first_int(state_map.get("agentic_sessions"), default=0)
    )
    hypothesis_calls = _hypothesis_calls(request_counts)
    if hypothesis_calls == 0:
        hypothesis_calls = _first_int(state_map.get("hypothesis_calls"), default=0)
    code_calls = _code_calls(request_counts)
    if code_calls == 0:
        code_calls = _first_int(state_map.get("code_calls"), default=0)
    fields = {
        "campaign_steps": campaign_steps,
        "screened_rounds": screened,
        "quality_blocks": quality_blocks,
        "agentic_sessions": agentic_sessions,
        "hypothesis_calls": hypothesis_calls,
        "code_calls": code_calls,
        "llm_request_kind_counts": dict(request_counts),
    }
    trace_index = agentic_session_trace_index_artifact(
        campaign_dir=campaign_dir,
        agentic_artifact_dir=agentic_artifact_dir,
    )
    if trace_index:
        fields["agentic_session_trace_index"] = trace_index
    return fields


def llm_request_kind_counts(campaign_dir: str | Path) -> dict[str, int]:
    """Count LLM trace records by normalized request kind."""
    llm_dir = Path(campaign_dir) / "llm_traces"
    counts: dict[str, int] = {}
    if not llm_dir.exists():
        return counts
    for trace_path in sorted(llm_dir.glob("*.json")):
        try:
            payload = json.loads(trace_path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - best-effort status path
            logger.debug("failed to read llm trace accounting %s: %s", trace_path, exc)
            continue
        usage = payload.get("llm_usage")
        usage_map = usage if isinstance(usage, Mapping) else {}
        kind = _request_kind(
            payload.get("request_kind") or usage_map.get("request_kind")
        )
        if not kind:
            continue
        counts[kind] = counts.get(kind, 0) + 1
    return counts


def agentic_session_count(
    *,
    campaign_dir: str | Path,
    steps: Iterable[StepRecord] = (),
    agentic_artifact_dir: str | Path | None = None,
) -> int:
    """Count distinct agentic proposal sessions from step refs and the APS index."""
    session_ids: set[str] = set()
    anonymous_refs = 0
    for step in steps:
        ref = getattr(step, "proposal_session_ref", None)
        if not isinstance(ref, Mapping) or not ref:
            continue
        session_id = str(ref.get("session_id") or "").strip()
        if session_id:
            session_ids.add(session_id)
        else:
            anonymous_refs += 1

    for item in _agentic_index_items(
        campaign_dir=campaign_dir,
        agentic_artifact_dir=agentic_artifact_dir,
    ):
        session_id = str(item.get("session_id") or "").strip()
        if session_id:
            session_ids.add(session_id)
        elif item:
            anonymous_refs += 1
    return len(session_ids) + anonymous_refs


def _agentic_index_items(
    *,
    campaign_dir: str | Path,
    agentic_artifact_dir: str | Path | None,
) -> list[Mapping[str, Any]]:
    index_dir = (
        Path(agentic_artifact_dir)
        if agentic_artifact_dir
        else Path(campaign_dir) / "agentic_sessions"
    )
    index_path = index_dir / "agentic_session_index.json"
    if not index_path.exists():
        return []
    try:
        raw = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - best-effort status path
        logger.debug("failed to read agentic session index %s: %s", index_path, exc)
        return []
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, Mapping)]


def agentic_session_trace_index_artifact(
    *,
    campaign_dir: str | Path,
    agentic_artifact_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Return a public ref/digest summary for the compact session trace index."""
    index_dir = (
        Path(agentic_artifact_dir)
        if agentic_artifact_dir
        else Path(campaign_dir) / "agentic_sessions"
    )
    index_path = index_dir / SESSION_TRACE_INDEX_NAME
    if not index_path.exists():
        return {}
    try:
        raw_bytes = index_path.read_bytes()
        payload = json.loads(raw_bytes.decode("utf-8"))
    except Exception as exc:  # pragma: no cover - best-effort status path
        logger.debug(
            "failed to read agentic session trace index %s: %s",
            index_path,
            exc,
        )
        return {}
    if not isinstance(payload, Mapping):
        return {}
    public_ref = public_artifact_ref(
        index_path,
        base_dir=campaign_dir,
        kind="artifact",
    )
    return {
        "artifact_kind": "agentic_session_trace_index",
        "artifact_ref": public_ref or index_path.name,
        "artifact_path": public_ref or index_path.name,
        "digest": hashlib.sha256(raw_bytes).hexdigest(),
        "digest_algorithm": "sha256",
        "schema_version": str(payload.get("schema_version") or ""),
        "session_count": _first_int(payload.get("session_count"), default=0),
        "trace_count": _first_int(payload.get("trace_count"), default=0),
    }


def _hypothesis_calls(request_counts: Mapping[str, int]) -> int:
    return sum(
        int(request_counts.get(kind, 0) or 0)
        for kind in ("hypothesis", "generate_hypothesis")
    )


def _code_calls(request_counts: Mapping[str, int]) -> int:
    return sum(
        int(request_counts.get(kind, 0) or 0)
        for kind in ("code", "patch", "generate_code")
    )


def _request_kind(value: Any) -> str:
    return str(value or "").strip().lower()


def _first_int(*values: Any, default: int) -> int:
    for value in values:
        if value is None:
            continue
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            continue
    return max(0, int(default))
