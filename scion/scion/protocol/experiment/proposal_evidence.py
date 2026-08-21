"""Generic dispatch for problem-owned proposal-visible mechanism evidence."""
from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from scion.core.models import PatchProposal, patch_file_changes
from scion.core.paths import normalize_relative_patch_path
from scion.problem.providers import resolve_proposal_mechanism_evidence_provider

logger = logging.getLogger(__name__)

_ENVELOPE_SCHEMA = "scion.problem_proposal_mechanism_evidence.v1"
_SUBJECT_SCHEMA = "scion.problem_proposal_subject.v1"
_MAX_SUBJECT_SOURCE_BYTES = 2_000_000


class _SubjectSourceLimitExceeded(RuntimeError):
    pass


def build_problem_proposal_subject(
    *,
    patch: PatchProposal | None,
    base_workspace: str | None,
) -> dict[str, Any]:
    """Build a domain-opaque before/after source packet for a problem provider.

    The generic layer validates paths and transports ordinary source.  It does
    not inspect symbols, infer a mechanism, or include hypothesis free text,
    object identity, hashes, receipts, or registration metadata.
    """

    if patch is None or not base_workspace:
        return {}
    root = Path(base_workspace).expanduser().resolve()
    changes: list[dict[str, Any]] = []
    source_bytes = 0
    for change in patch_file_changes(patch):
        try:
            file_path = normalize_relative_patch_path(change.file_path)
        except ValueError:
            return {}
        if file_path != change.file_path:
            return {}
        try:
            before_source = _bounded_subject_source(root, file_path)
        except _SubjectSourceLimitExceeded:
            return {}
        after_source = None if change.action == "delete" else change.code_content
        try:
            source_bytes += sum(
                len(source.encode("utf-8"))
                for source in (before_source, after_source)
                if isinstance(source, str)
            )
        except UnicodeEncodeError:
            return {}
        if source_bytes > _MAX_SUBJECT_SOURCE_BYTES:
            return {}
        changes.append(
            {
                "file_path": file_path,
                "action": change.action,
                "before_source": before_source,
                "after_source": after_source,
            }
        )
    return {
        "schema_version": _SUBJECT_SCHEMA,
        "changes": changes,
    }


def problem_proposal_mechanism_evidence(
    *,
    stage: str,
    selected_surface: str | None,
    runtime_pairs: Sequence[Mapping[str, Any]],
    proposal_subject: Mapping[str, Any] | None = None,
    runtime_pairs_complete: bool = True,
    problem_spec: Any = None,
    adapter: Any = None,
) -> dict[str, Any]:
    """Return a safe proposal-only envelope, or ``{}`` on provider absence/error."""

    if stage != "screening" or not runtime_pairs:
        return {}
    try:
        provider = resolve_proposal_mechanism_evidence_provider(
            problem_spec=problem_spec,
            adapter=adapter,
        )
        summarize = getattr(provider, "summarize_proposal_mechanism_evidence", None)
        if not callable(summarize):
            return {}
        raw = summarize(
            stage=stage,
            selected_surface=selected_surface,
            runtime_pairs=runtime_pairs,
            proposal_subject=(
                dict(proposal_subject)
                if isinstance(proposal_subject, Mapping)
                else None
            ),
            runtime_pairs_complete=bool(runtime_pairs_complete),
        )
    except Exception:
        logger.warning(
            "Problem proposal mechanism evidence provider failed; preserving formal result",
            exc_info=True,
        )
        return {}
    if not isinstance(raw, Mapping) or not raw:
        return {}
    family = _problem_family(problem_spec, adapter)
    return {
        "schema_version": _ENVELOPE_SCHEMA,
        "problem_family": family or "unknown",
        "producer": "problem_provider",
        "evidence": dict(raw),
    }


def is_proposal_mechanism_evidence_envelope(value: Any) -> bool:
    return bool(
        isinstance(value, Mapping)
        and value.get("schema_version") == _ENVELOPE_SCHEMA
        and value.get("producer") == "problem_provider"
        and isinstance(value.get("evidence"), Mapping)
    )


def _problem_family(problem_spec: Any, adapter: Any) -> str:
    adapter_spec = getattr(adapter, "spec", None) or getattr(adapter, "_spec", None)
    spec_v1 = getattr(problem_spec, "spec_v1", None)
    for owner in (adapter_spec, spec_v1, problem_spec):
        value = str(
            getattr(owner, "id", None)
            or getattr(owner, "problem_id", None)
            or getattr(owner, "name", "")
            or ""
        ).strip()
        if value:
            return value
    return ""


def _bounded_subject_source(root: Path, relative_path: str) -> str | None:
    if not root.is_dir():
        return None
    declared_source = root / relative_path
    try:
        if declared_source.is_symlink():
            return None
        source = declared_source.resolve()
        source.relative_to(root)
        if not source.is_file():
            return None
        with source.open("rb") as stream:
            payload = stream.read(_MAX_SUBJECT_SOURCE_BYTES + 1)
        if len(payload) > _MAX_SUBJECT_SOURCE_BYTES:
            raise _SubjectSourceLimitExceeded(relative_path)
        return payload.decode("utf-8")
    except (OSError, UnicodeError, ValueError):
        return None


__all__ = [
    "build_problem_proposal_subject",
    "is_proposal_mechanism_evidence_envelope",
    "problem_proposal_mechanism_evidence",
]
