"""Helpers for code-generation context assembly."""
from __future__ import annotations

from enum import Enum
from typing import Any, Mapping, Optional, Sequence

from scion.core.candidate_disposition import (
    CandidateDisposition,
    CandidateDispositionError,
    CandidateDispositionMapper,
)
from scion.core.models import (
    Branch,
    ChampionState,
    DecisionOutcome,
    StepRecord,
    patch_file_changes,
)
from scion.proposal.context.surfaces import _find_research_surface
from scion.proposal.edit_protocol.source_discovery import source_digest_for_content

from .io import (
    _list_champion_operator_files,
    _list_champion_surface_files,
    _read_champion_operators,
    _read_solver_design_context_artifact,
    _read_surface_file,
)


DURABLE_BRANCH_CREATED_FILES_KEY = "verified_branch_created_files"
DURABLE_BRANCH_TOUCHED_FILES_KEY = "verified_branch_touched_files"


def _branch_steps(
    branch: Branch,
    steps: Sequence[StepRecord],
) -> tuple[StepRecord, ...]:
    return tuple(step for step in steps if step.branch_id == branch.branch_id)


def _verified_branch_steps(
    branch: Branch,
    steps: Sequence[StepRecord],
) -> tuple[StepRecord, ...]:
    """Return only patch facts that reached the durable verified workspace."""

    return tuple(
        step
        for step in _branch_steps(branch, steps)
        if step.verification_passed
        and step.patch is not None
        and _step_can_own_branch_source(step)
    )


def _step_can_own_branch_source(step: StepRecord) -> bool:
    """Accept branch source only for an explicit code-retaining disposition."""

    if step.decision is None or step.decision_features_snapshot is None:
        return False
    try:
        plan = CandidateDispositionMapper.map(
            DecisionOutcome(
                decision=step.decision,
                reason_codes=tuple(step.decision_reason_codes or ()),
                features_snapshot=step.decision_features_snapshot,
            )
        )
    except (CandidateDispositionError, TypeError):
        return False
    return plan.disposition in {
        CandidateDisposition.PROVISIONAL_HEAD,
        CandidateDisposition.EXACT_REUSE,
        CandidateDisposition.PROMOTE_EXACT,
    }


def _clean_history_path(value: Any) -> str:
    text = str(value or "").strip().replace("\\", "/").lstrip("/")
    if not text or any(part in {"", ".", ".."} for part in text.split("/")):
        return ""
    return text


def _append_unique_path(paths: list[str], value: Any) -> None:
    path = _clean_history_path(value)
    if path and path not in paths:
        paths.append(path)


def branch_created_files(
    branch: Branch | None,
    steps: Sequence[StepRecord] | None,
) -> tuple[str, ...]:
    """Return every file created on the durable branch history."""

    if branch is None:
        return ()
    summary = dict(getattr(branch, "branch_evidence_summary", {}) or {})
    durable = summary.get(DURABLE_BRANCH_CREATED_FILES_KEY, [])
    if not isinstance(durable, list):
        raise ValueError("durable branch created-file history is invalid")
    files: list[str] = []
    for path in durable:
        _append_unique_path(files, path)
    for step in _verified_branch_steps(branch, steps or ()):
        hypothesis = getattr(step, "hypothesis", None)
        if getattr(hypothesis, "action", None) == "create_new":
            _append_unique_path(files, getattr(hypothesis, "target_file", ""))
        patch = getattr(step, "patch", None)
        if patch is None:
            continue
        for change in patch_file_changes(patch):
            if getattr(change, "action", None) == "create":
                _append_unique_path(files, getattr(change, "file_path", ""))
    return tuple(files)


def branch_touched_files(
    branch: Branch | None,
    steps: Sequence[StepRecord] | None,
) -> tuple[str, ...]:
    """Return every file touched on the durable branch history."""

    if branch is None:
        return ()
    summary = dict(getattr(branch, "branch_evidence_summary", {}) or {})
    durable = summary.get(DURABLE_BRANCH_TOUCHED_FILES_KEY, [])
    if not isinstance(durable, list):
        raise ValueError("durable branch touched-file history is invalid")
    files: list[str] = []
    for path in durable:
        _append_unique_path(files, path)
    for step in _verified_branch_steps(branch, steps or ()):
        hypothesis = getattr(step, "hypothesis", None)
        _append_unique_path(files, getattr(hypothesis, "target_file", ""))
        patch = getattr(step, "patch", None)
        if patch is None:
            continue
        for change in patch_file_changes(patch):
            _append_unique_path(files, getattr(change, "file_path", ""))
    return tuple(files)


def branch_current_file_sources(
    branch: Branch | None,
    steps: Sequence[StepRecord] | None,
) -> dict[str, str]:
    """Reconstruct current branch-owned sources from all durable patch facts."""

    if branch is None:
        return {}
    sources: dict[str, str] = {}
    for step in _verified_branch_steps(branch, steps or ()):
        patch = getattr(step, "patch", None)
        if patch is None:
            continue
        for change in patch_file_changes(patch):
            path = _clean_history_path(getattr(change, "file_path", ""))
            action = str(getattr(change, "action", "") or "")
            if not path:
                continue
            if action == "delete":
                sources.pop(path, None)
                continue
            content = getattr(change, "code_content", None)
            if action in {"create", "modify"} and isinstance(content, str):
                sources[path] = content
    return sources


def _read_champion_research_code(
    champion: ChampionState,
    *,
    research_surfaces: list[Any],
    include_operator_files: bool = True,
    excluded_paths: Sequence[str] = (),
) -> str:
    """Render hypothesis-facing champion research source."""

    excluded: set[str] = set()
    for path in excluded_paths:
        cleaned = _clean_history_path(path)
        if cleaned:
            excluded.add(cleaned)
    sections = (
        [_read_champion_operators(champion, excluded_paths=tuple(sorted(excluded)))]
        if include_operator_files
        else []
    )
    sections.extend(
        _read_surface_file(champion, path, label="research surface")
        for path in _list_champion_surface_files(
            champion, research_surfaces=research_surfaces
        )
        if path not in excluded
    )
    return "\n\n".join(section for section in sections if section)


def _branch_current_context_paths(
    branch_created_files: Sequence[str],
    branch_touched_files: Sequence[str],
) -> tuple[str, ...]:
    paths: list[str] = []
    for collection in (branch_created_files, branch_touched_files):
        for item in collection or ():
            if not str(item or "").strip():
                continue
            rel = _normalize_ledger_path(item)
            if rel and rel not in paths:
                paths.append(rel)
    return tuple(paths)


SOURCE_LEDGER_KEY = "proposal_source_ledger"


class SourceLedgerOwner(str, Enum):
    """The single full-content ownership role for one ledger path."""

    APPROVED_TARGET = "approved_target"
    BRANCH_CURRENT_INTEGRATION = "branch_current_integration"
    BRANCH_HELPER = "branch_helper"
    CHAMPION_API_SUPPORT = "champion_api_support"


_LEDGER_KEYS = frozenset({
    "schema_version", "approved_target", "entries", "views", "target_api_guidance",
})
_ENTRY_KEYS = frozenset({
    "path", "content", "digest", "owner", "provenance", "visibility", "reason",
})
_VIEW_KEYS = frozenset({
    "champion_research", "reference", "api_reference", "integration_full",
    "integration_summary", "branch_current", "required_full",
})
_PROVENANCE_VALUES = frozenset({
    "branch_history_current",
    "branch_workspace",
    "champion_snapshot",
    "champion_snapshot_fallback",
    "missing_current_source",
    "new_file_placeholder",
})
_VISIBILITY_VALUES = frozenset({
    "full_current",
    "new_file_placeholder",
    "not_visible",
})
_OWNER_PRIORITY = {
    SourceLedgerOwner.APPROVED_TARGET.value: 0,
    SourceLedgerOwner.BRANCH_CURRENT_INTEGRATION.value: 1,
    SourceLedgerOwner.BRANCH_HELPER.value: 2,
    SourceLedgerOwner.CHAMPION_API_SUPPORT.value: 3,
}
_PROVENANCE_PRIORITY = {
    "branch_history_current": 0,
    "branch_workspace": 1,
    "champion_snapshot": 2,
    "champion_snapshot_fallback": 3,
    "new_file_placeholder": 4,
    "missing_current_source": 5,
}


def _normalize_ledger_path(value: Any) -> str:
    raw = str(value or "").replace("\\", "/")
    path = raw.lstrip("/")
    if (
        not path
        or raw.startswith("/")
        or path.split("/", 1)[0].endswith(":")
        or any(part in {"", ".", ".."} for part in path.split("/"))
    ):
        raise ValueError(f"invalid source ledger path: {raw}")
    return path


def _validate_canonical_ledger_path(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError(f"source ledger path must be a string: {value!r}")
    normalized = _normalize_ledger_path(value)
    if value != normalized:
        raise ValueError(f"source ledger path is not canonical: {value}")
    return normalized


def _validate_source_ledger(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _LEDGER_KEYS:
        raise ValueError("source ledger has unknown or missing keys")
    if value.get("schema_version") != "proposal-source-ledger.v2":
        raise ValueError("unsupported source ledger schema")
    if not isinstance(value.get("target_api_guidance"), str):
        raise ValueError("source ledger target_api_guidance must be a string")
    entries = value.get("entries")
    views = value.get("views")
    if not isinstance(entries, list) or not isinstance(views, Mapping) or set(views) != _VIEW_KEYS:
        raise ValueError("source ledger entries or views are invalid")
    paths: set[str] = set()
    owners: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, Mapping) or set(entry) != _ENTRY_KEYS:
            raise ValueError("source ledger entry has unknown or missing keys")
        path = _validate_canonical_ledger_path(entry.get("path"))
        if path in paths:
            raise ValueError(f"duplicate source ledger path: {path}")
        paths.add(path)
        content = entry.get("content")
        digest = entry.get("digest")
        owner = entry.get("owner")
        provenance = entry.get("provenance")
        visibility = entry.get("visibility")
        reason = entry.get("reason")
        if owner not in _OWNER_PRIORITY:
            raise ValueError(f"invalid source ledger owner: {path}")
        owners[path] = str(owner)
        if provenance not in _PROVENANCE_VALUES:
            raise ValueError(f"invalid source ledger provenance: {path}")
        if visibility not in _VISIBILITY_VALUES:
            raise ValueError(f"invalid source ledger visibility: {path}")
        if not isinstance(reason, str):
            raise ValueError(f"invalid source ledger reason: {path}")
        visible = visibility == "full_current"
        if visible and (not isinstance(content, str) or digest != source_digest_for_content(content)):
            raise ValueError(f"source ledger digest mismatch: {path}")
        if not visible and (content is not None or digest is not None):
            raise ValueError(f"non-visible source ledger entry owns content: {path}")
        if visibility == "new_file_placeholder" and provenance != "new_file_placeholder":
            raise ValueError(f"source ledger placeholder provenance mismatch: {path}")
        if visibility == "not_visible" and provenance != "missing_current_source":
            raise ValueError(f"source ledger missing provenance mismatch: {path}")
        if visible and provenance in {"missing_current_source", "new_file_placeholder"}:
            raise ValueError(f"source ledger visible provenance mismatch: {path}")
    target = _validate_canonical_ledger_path(value.get("approved_target"))
    if target not in paths:
        raise ValueError("source ledger approved target has no entry")
    if owners[target] != SourceLedgerOwner.APPROVED_TARGET.value:
        raise ValueError("source ledger approved target has invalid owner")
    if any(
        path != target and owner == SourceLedgerOwner.APPROVED_TARGET.value
        for path, owner in owners.items()
    ):
        raise ValueError("source ledger has multiple approved target owners")
    for name, members in views.items():
        if not isinstance(members, list):
            raise ValueError(f"source ledger view is invalid: {name}")
        normalized_members = [
            _validate_canonical_ledger_path(path) for path in members
        ]
        if len(normalized_members) != len(set(normalized_members)):
            raise ValueError(f"source ledger view is invalid: {name}")
        if any(path not in paths for path in normalized_members):
            raise ValueError(f"source ledger view has unknown path: {name}")
    return dict(value)


def _build_code_source_ledger(
    *,
    champion: ChampionState,
    research_surfaces: list[Any],
    change_locus: str,
    source_root: str,
    target_file: Optional[str],
    target_action: str,
    provider: Any | None,
    branch_created_files: Sequence[str] = (),
    branch_touched_files: Sequence[str] = (),
    branch_current_file_sources: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Collect one complete primitive source owner per repository path."""

    target = _normalize_ledger_path(target_file)
    branch_paths = _branch_current_context_paths(branch_created_files, branch_touched_files)
    overrides = branch_current_file_sources or {}
    entries: dict[str, dict[str, Any]] = {}
    owner_scores: dict[str, tuple[int, int]] = {}

    def add(
        rel: str,
        *,
        owner: str,
        helper: bool = False,
        target_entry: bool = False,
        champion_only: bool = False,
    ) -> None:
        path = _normalize_ledger_path(rel)
        if target_entry and path in overrides:
            artifact = {
                "source": "branch_history_current",
                "readable": True,
                "reason": "ok",
                "content": overrides[path],
            }
        else:
            artifact = _read_solver_design_context_artifact(
                path,
                source_root=(champion.code_snapshot_path if champion_only else source_root),
                champion_root=champion.code_snapshot_path,
                source_overrides=overrides,
                allow_champion_fallback=(False if helper or target_entry else path not in branch_paths),
            )
        readable = bool(artifact.get("readable"))
        if (
            readable
            and path in branch_paths
            and artifact.get("source") == "branch_workspace"
        ):
            artifact = {**artifact, "source": "branch_history_current"}
        if target_entry and target_action == "create_new" and not readable:
            provenance, visibility = "new_file_placeholder", "new_file_placeholder"
        else:
            provenance = str(artifact.get("source") or "missing_current_source")
            visibility = "full_current" if readable else "not_visible"
        content = str(artifact.get("content") or "") if readable else None
        entry = {
            "path": path,
            "content": content,
            "digest": source_digest_for_content(content) if content is not None else None,
            "owner": owner,
            "provenance": provenance,
            "visibility": visibility,
            "reason": str(artifact.get("reason") or ""),
        }
        score = (
            _OWNER_PRIORITY[owner],
            _PROVENANCE_PRIORITY.get(provenance, 99),
        )
        previous_score = owner_scores.get(path)
        if previous_score is not None and previous_score <= score:
            return
        entries[path] = entry
        owner_scores[path] = score

    add(target, owner="approved_target", target_entry=True)
    operator_paths = _list_champion_operator_files(champion)
    surface_paths = _list_champion_surface_files(
        champion, research_surfaces=research_surfaces
    )
    champion_paths = list(dict.fromkeys([*operator_paths, *surface_paths]))
    for path in champion_paths:
        add(path, owner="champion_api_support", champion_only=True)
    surface = _find_research_surface(research_surfaces, change_locus)
    reference_paths = (
        operator_paths
        if surface is None or getattr(surface, "kind", "operator") == "operator"
        else []
    )
    api_paths = list(
        dict.fromkeys(
            [
                *_solver_design_api_manifest_files(provider, fallback=(target,)),
                *surface_paths,
            ]
        )
    )
    full_paths = list(_solver_design_integration_full_files(provider, fallback=(target,)))
    summary_paths = list(_solver_design_integration_summary_files(provider))
    for path in dict.fromkeys([*api_paths]):
        add(path, owner="champion_api_support")
    for path in dict.fromkeys([*full_paths, *summary_paths]):
        add(path, owner="branch_current_integration")
    for path in branch_paths:
        add(path, owner="branch_helper", helper=True)
    ledger = {
        "schema_version": "proposal-source-ledger.v2",
        "approved_target": target,
        "entries": list(entries.values()),
        "views": {
            "champion_research": champion_paths,
            "reference": reference_paths,
            "api_reference": api_paths,
            "integration_full": full_paths,
            "integration_summary": summary_paths,
            "branch_current": list(branch_paths),
            "required_full": [],
        },
        "target_api_guidance": _solver_design_target_api_guidance(provider, target),
    }
    return _validate_source_ledger(ledger)

def _solver_design_api_manifest_files(
    provider: Any | None,
    *,
    fallback: tuple[str, ...],
) -> tuple[str, ...]:
    return _provider_string_sequence(
        provider,
        "solver_design_api_manifest_files",
        fallback=fallback,
    )


def _solver_design_integration_full_files(
    provider: Any | None,
    *,
    fallback: tuple[str, ...],
) -> tuple[str, ...]:
    return _provider_string_sequence(
        provider,
        "solver_design_integration_full_files",
        fallback=fallback,
    )


def _solver_design_integration_summary_files(
    provider: Any | None,
) -> tuple[str, ...]:
    return _provider_string_sequence(
        provider,
        "solver_design_integration_summary_files",
        fallback=(),
    )


def _solver_design_target_api_guidance(
    provider: Any | None,
    target_file: str,
) -> str:
    method = getattr(provider, "solver_design_target_api_guidance", None)
    if not callable(method):
        return ""
    return str(method(target_file) or "").strip()


def _provider_string_sequence(
    provider: Any | None,
    method_name: str,
    *,
    fallback: tuple[str, ...],
) -> tuple[str, ...]:
    method = getattr(provider, method_name, None)
    if not callable(method):
        return tuple(item for item in fallback if item)
    try:
        raw_items = method()
    except TypeError:
        raw_items = method({})
    items: list[str] = []
    for item in raw_items or ():
        if not str(item or "").strip():
            continue
        rel = _normalize_ledger_path(item)
        if rel and rel not in items:
            items.append(rel)
    if items:
        return tuple(items)
    fallback_items: list[str] = []
    for item in fallback:
        if not str(item or "").strip():
            continue
        rel = _normalize_ledger_path(item)
        if rel and rel not in fallback_items:
            fallback_items.append(rel)
    return tuple(fallback_items)
