"""Build fixed-candidate replay manifests from formal candidate artifacts."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from scion.core.evidence_recording.replay_identity import (
    formal_replay_identity_missing_keys,
)


SCHEMA_VERSION = "scion.fixed_candidate_replay_manifest.v1"
DEFAULT_MANIFEST_FILENAME = "fixed_candidate_replay_manifest.v1.json"
REPLAY_ARMS = ["on", "record_only"]


def build_fixed_candidate_replay_manifest(
    source: str | Path,
    *,
    source_arm: str,
    comparison_id: str,
    max_candidates: int | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Return a deterministic manifest for fixed-candidate governance replay.

    The builder only reads ``formal_candidates/index.jsonl`` and referenced
    ``candidate.patch.json`` files. It never materializes workspaces, runs
    protocol replay, or mutates campaign state.
    """

    if max_candidates is not None and max_candidates < 0:
        raise ValueError("max_candidates must be non-negative")
    index_path, source_campaign_dir = resolve_formal_candidate_index(source)
    rows = _read_index_rows(index_path)

    candidates: list[dict[str, Any]] = []
    omitted_rows: list[dict[str, Any]] = []
    for row_index, row in enumerate(rows):
        row_reasons = _row_omission_reasons(row)
        artifact_ref = _clean_str(row.get("artifact_ref"))
        metadata_path = _resolve_artifact_path(
            artifact_ref,
            campaign_dir=source_campaign_dir,
            index_dir=index_path.parent,
        )
        metadata: Mapping[str, Any] | None = None

        if not row_reasons:
            if metadata_path is None:
                row_reasons.append("missing_artifact_ref")
            elif not metadata_path.is_file():
                row_reasons.append("candidate_patch_missing")
            else:
                try:
                    loaded = json.loads(metadata_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    row_reasons.append("candidate_patch_unreadable")
                else:
                    if not isinstance(loaded, Mapping):
                        row_reasons.append("candidate_patch_invalid")
                    else:
                        metadata = loaded
                        row_reasons.extend(_metadata_omission_reasons(metadata))

        if row_reasons:
            omitted_rows.append(_omitted_row(row_index, row, row_reasons))
            continue

        assert metadata is not None
        if max_candidates is not None and len(candidates) >= max_candidates:
            omitted_rows.append(
                _omitted_row(row_index, row, ["max_candidates_exceeded"])
            )
            continue
        candidates.append(
            _candidate_manifest_entry(
                row_index=row_index,
                row=row,
                metadata=metadata,
                artifact_ref=artifact_ref,
            )
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "comparison_id": comparison_id,
        "source_campaign_dir": str(source_campaign_dir),
        "source_arm": source_arm,
        "generated_at": generated_at or _utc_now_iso(),
        "candidate_count": len(candidates),
        "causal_candidate_pairing": bool(candidates),
        "replay_arms": list(REPLAY_ARMS),
        "candidates": candidates,
        "omitted_rows": omitted_rows,
    }


def write_fixed_candidate_replay_manifest(
    source: str | Path,
    *,
    source_arm: str,
    comparison_id: str,
    output_path: str | Path | None = None,
    max_candidates: int | None = None,
) -> Path:
    """Build and write a fixed-candidate replay manifest JSON artifact."""

    index_path, _ = resolve_formal_candidate_index(source)
    destination = (
        Path(output_path)
        if output_path is not None
        else index_path.parent / DEFAULT_MANIFEST_FILENAME
    )
    manifest = build_fixed_candidate_replay_manifest(
        source,
        source_arm=source_arm,
        comparison_id=comparison_id,
        max_candidates=max_candidates,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(_manifest_json(manifest), encoding="utf-8")
    return destination


def resolve_formal_candidate_index(source: str | Path) -> tuple[Path, Path]:
    """Resolve a campaign directory or formal candidate index path."""

    source_path = Path(source).expanduser().resolve()
    if source_path.is_dir():
        campaign_dir = source_path
        index_path = campaign_dir / "artifacts" / "formal_candidates" / "index.jsonl"
    else:
        index_path = source_path
        if index_path.name != "index.jsonl":
            raise ValueError(
                "source must be a campaign directory or formal_candidates/index.jsonl"
            )
        campaign_dir = _infer_campaign_dir_from_index(index_path)
    if not index_path.is_file():
        raise FileNotFoundError(f"formal candidate index not found: {index_path}")
    return index_path, campaign_dir


def _infer_campaign_dir_from_index(index_path: Path) -> Path:
    parts = index_path.parts
    if len(parts) >= 3 and parts[-3:-1] == ("artifacts", "formal_candidates"):
        return index_path.parents[2]
    return index_path.parent


def _read_index_rows(index_path: Path) -> list[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    with index_path.open(encoding="utf-8") as fh:
        for line_number, line in enumerate(fh, start=1):
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
                    f"formal candidate index line {line_number} is not a JSON object"
                )
            rows.append(row)
    return rows


def _row_omission_reasons(row: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    if _clean_str(row.get("artifact_status")) != "recorded":
        if _clean_str(row.get("artifact_status")) == "omitted":
            reasons.append(
                _clean_str(row.get("artifact_omitted_reason"))
                or "artifact_omitted"
            )
        else:
            reasons.append("artifact_not_recorded")
    if _clean_str(row.get("stage")) != "screening":
        reasons.append("non_screening_stage")
    if not _clean_str(row.get("artifact_ref")):
        reasons.append("missing_artifact_ref")
    if _clean_str(row.get("replay_identity_status")) != "complete":
        reasons.append("replay_identity_not_complete")
    missing_keys = _string_list(row.get("missing_replay_identity_keys"))
    if missing_keys:
        reasons.append("missing_replay_identity_keys")
    return _dedupe(reasons)


def _metadata_omission_reasons(metadata: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    if _clean_str(metadata.get("stage")) != "screening":
        reasons.append("candidate_patch_non_screening_stage")
    replay_identity = metadata.get("replay_identity")
    if not isinstance(replay_identity, Mapping):
        reasons.append("candidate_patch_missing_replay_identity")
        return reasons
    identity_status = _clean_str(
        replay_identity.get("identity_status") or replay_identity.get("status")
    )
    if identity_status != "complete":
        reasons.append("candidate_patch_replay_identity_not_complete")
    if formal_replay_identity_missing_keys(replay_identity):
        reasons.append("candidate_patch_missing_replay_identity_keys")
    return _dedupe(reasons)


def _candidate_manifest_entry(
    *,
    row_index: int,
    row: Mapping[str, Any],
    metadata: Mapping[str, Any],
    artifact_ref: str,
) -> dict[str, Any]:
    replay_identity = metadata.get("replay_identity")
    assert isinstance(replay_identity, Mapping)
    patch = metadata.get("patch") if isinstance(metadata.get("patch"), Mapping) else {}
    base = metadata.get("base") if isinstance(metadata.get("base"), Mapping) else {}
    replay_metadata = (
        metadata.get("replay_metadata")
        if isinstance(metadata.get("replay_metadata"), Mapping)
        else {}
    )
    patch_digest = _clean_str(
        replay_identity.get("patch_digest")
        or replay_identity.get("patch_hash")
        or patch.get("patch_digest")
        or row.get("patch_digest")
    )
    raw_metrics_ref = _clean_str(
        replay_identity.get("raw_metrics_ref")
        or replay_metadata.get("raw_metrics_ref")
        or metadata.get("experiment_ref")
    )
    return {
        "candidate_order_index": row_index,
        "candidate_id": _clean_str(
            metadata.get("candidate_id") or row.get("candidate_id")
        ),
        "branch_id": _clean_str(metadata.get("branch_id") or row.get("branch_id")),
        "lineage_id": _clean_str(metadata.get("lineage_id")),
        "hypothesis_id": _clean_str(
            metadata.get("hypothesis_id") or row.get("hypothesis_id")
        ),
        "stage": _clean_str(metadata.get("stage") or row.get("stage")),
        "artifact_ref": artifact_ref,
        "target_files": _target_files(metadata),
        "selected_surface": _clean_str(
            replay_identity.get("selected_surface")
            or replay_metadata.get("selected_surface")
        ),
        "patch_digest": patch_digest,
        "patch_hash": _clean_str(replay_identity.get("patch_hash") or patch_digest),
        "code_hash": _clean_str(replay_identity.get("code_hash")),
        "base_champion_id": _clean_str(base.get("base_champion_id")),
        "base_champion_hash": _clean_str(base.get("base_champion_hash")),
        "problem_spec_hash": _clean_str(replay_identity.get("problem_spec_hash")),
        "split_manifest_hash": _clean_str(replay_identity.get("split_manifest_hash")),
        "seed_ledger_hash": _clean_str(replay_identity.get("seed_ledger_hash")),
        "protocol_version": _clean_str(replay_identity.get("protocol_version")),
        "raw_metrics_ref": raw_metrics_ref,
        "source_raw_metrics_ref": raw_metrics_ref,
        "decision": _clean_str(metadata.get("decision")),
        "decision_reason_codes": _string_list(metadata.get("decision_reason_codes")),
        "audit_flags": {
            "decision_features_excluded": True,
            "proposal_text_excluded": True,
            "replay_materialized_from_artifact": True,
        },
    }


def _target_files(metadata: Mapping[str, Any]) -> list[str]:
    files = _string_list(metadata.get("target_files"))
    if files:
        return files
    patch = metadata.get("patch")
    if not isinstance(patch, Mapping):
        return []
    changes = patch.get("files")
    if not isinstance(changes, list):
        return []
    return [
        _clean_str(item.get("file_path"))
        for item in changes
        if isinstance(item, Mapping) and _clean_str(item.get("file_path"))
    ]


def _omitted_row(
    row_index: int,
    row: Mapping[str, Any],
    reasons: list[str],
) -> dict[str, Any]:
    return {
        "candidate_order_index": row_index,
        "candidate_id": _clean_str(row.get("candidate_id")),
        "branch_id": _clean_str(row.get("branch_id")),
        "hypothesis_id": _clean_str(row.get("hypothesis_id")),
        "stage": _clean_str(row.get("stage")),
        "artifact_ref": _clean_str(row.get("artifact_ref")),
        "artifact_status": _clean_str(row.get("artifact_status")),
        "replay_identity_status": _clean_str(row.get("replay_identity_status")),
        "missing_replay_identity_keys": _string_list(
            row.get("missing_replay_identity_keys")
        ),
        "reasons": _dedupe(reasons),
    }


def _resolve_artifact_path(
    artifact_ref: str,
    *,
    campaign_dir: Path,
    index_dir: Path,
) -> Path | None:
    ref = artifact_ref.split("#", 1)[0].strip()
    if not ref:
        return None
    path = Path(ref).expanduser()
    if path.is_absolute():
        return path
    campaign_candidate = campaign_dir / path
    if campaign_candidate.exists():
        return campaign_candidate
    index_candidate = index_dir / path
    if index_candidate.exists():
        return index_candidate
    return campaign_candidate


def _manifest_json(manifest: Mapping[str, Any]) -> str:
    return json.dumps(manifest, indent=2, sort_keys=True) + "\n"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _clean_str(value: Any) -> str:
    return str(value or "").strip()


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, (list, tuple, set)):
        return [_clean_str(item) for item in value if _clean_str(item)]
    return []


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


__all__ = [
    "DEFAULT_MANIFEST_FILENAME",
    "REPLAY_ARMS",
    "SCHEMA_VERSION",
    "build_fixed_candidate_replay_manifest",
    "resolve_formal_candidate_index",
    "write_fixed_candidate_replay_manifest",
]
