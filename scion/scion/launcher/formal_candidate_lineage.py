"""Flatten trusted formal-candidate ownership across resume hops."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

FORMAL_CANDIDATE_INDEX_REF = "artifacts/formal_candidates/index.jsonl"
RESUME_PREPARATION_SCHEMA = "scion.launcher_resume_preparation.v1"
RESUME_SNAPSHOT_MANIFEST_REF = "resume_snapshot/resume_source_manifest.v1.json"
RESUME_FORMAL_CANDIDATE_INDEX_REF = (
    "resume_snapshot/campaign/artifacts/formal_candidates/index.jsonl"
)


class FormalCandidateLineageError(ValueError):
    """Raised when a resume source cannot prove candidate ownership."""


@dataclass(frozen=True)
class CandidateIndexSource:
    """One validated candidate-index layer used by a resume operation."""

    source_kind: str
    source_ref: Path
    rows: tuple[dict[str, Any], ...]
    size_bytes: int
    sha256: str


def flatten_formal_candidate_lineage(
    *,
    resume_source: Path,
    campaign_dir: Path,
    run_root: Path,
    snapshot_dir: Path,
) -> dict[str, Any] | None:
    """Write one inherited union index while leaving current live state empty."""

    inherited = _load_inherited_index(resume_source)
    copied_live_path = campaign_dir / FORMAL_CANDIDATE_INDEX_REF
    live = (
        _read_index(
            copied_live_path,
            source_kind="source_campaign_live",
            source_ref=resume_source / FORMAL_CANDIDATE_INDEX_REF,
        )
        if copied_live_path.is_file()
        else None
    )
    sources = tuple(item for item in (inherited, live) if item is not None)
    rows = _validate_and_merge_rows(
        sources=sources,
        campaign_dir=campaign_dir,
    )
    _validate_metadata_coverage(
        campaign_dir=campaign_dir,
        rows=rows,
        has_trusted_index=bool(sources),
    )
    if not sources:
        return None

    target = snapshot_dir / FORMAL_CANDIDATE_INDEX_REF
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    target.write_text(payload, encoding="utf-8")
    if copied_live_path.is_file():
        copied_live_path.unlink()
        _prune_empty_parents(copied_live_path.parent, stop_at=campaign_dir)
    stat = target.stat()
    return {
        "original_ref": FORMAL_CANDIDATE_INDEX_REF,
        "snapshot_ref": target.relative_to(run_root).as_posix(),
        "size_bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "sha256": _sha256_file(target),
        "ownership_scope": "inherited_lineage_union",
        "source_indexes": [
            {
                "source_kind": source.source_kind,
                "source_ref": str(source.source_ref),
                "row_count": len(source.rows),
                "size_bytes": source.size_bytes,
                "sha256": source.sha256,
            }
            for source in sources
        ],
        "source_row_count": sum(len(source.rows) for source in sources),
        "merged_row_count": len(rows),
    }


def _load_inherited_index(resume_source: Path) -> CandidateIndexSource | None:
    source_root = resume_source.parent.resolve()
    manifest_path = source_root / RESUME_SNAPSHOT_MANIFEST_REF
    fixed_snapshot_path = source_root / RESUME_FORMAL_CANDIDATE_INDEX_REF
    if not manifest_path.exists():
        if fixed_snapshot_path.exists():
            raise FormalCandidateLineageError(
                "resume formal candidate snapshot exists without its manifest: "
                f"{fixed_snapshot_path}"
            )
        return None
    if manifest_path.resolve() != manifest_path:
        raise FormalCandidateLineageError(
            f"resume snapshot manifest is not a fixed in-root file: {manifest_path}"
        )
    manifest = _read_json_object(manifest_path, label="resume snapshot manifest")
    if manifest.get("schema_version") != RESUME_PREPARATION_SCHEMA:
        raise FormalCandidateLineageError(
            f"resume snapshot manifest schema mismatch: {manifest_path}"
        )
    if manifest.get("current_run_canonical_terminal_artifacts_cleared") is not True:
        raise FormalCandidateLineageError(
            "resume snapshot manifest does not assert cleared current terminal state: "
            f"{manifest_path}"
        )
    source_campaign = _resolved_manifest_path(
        manifest.get("campaign_dir"),
        label="resume snapshot campaign_dir",
    )
    if source_campaign != resume_source.resolve():
        raise FormalCandidateLineageError(
            "resume snapshot manifest campaign_dir does not match resume source: "
            f"{source_campaign} != {resume_source.resolve()}"
        )

    terminal_artifacts = manifest.get("terminal_artifacts")
    if not isinstance(terminal_artifacts, list):
        raise FormalCandidateLineageError(
            f"resume snapshot terminal_artifacts is not a list: {manifest_path}"
        )
    items = [
        dict(item)
        for item in terminal_artifacts
        if isinstance(item, dict)
        and item.get("original_ref") == FORMAL_CANDIDATE_INDEX_REF
    ]
    if len(items) > 1:
        raise FormalCandidateLineageError(
            "resume snapshot manifest contains duplicate formal candidate indexes: "
            f"{manifest_path}"
        )
    if not items:
        if fixed_snapshot_path.exists():
            raise FormalCandidateLineageError(
                "resume formal candidate snapshot is not bound by its manifest: "
                f"{fixed_snapshot_path}"
            )
        return None

    item = items[0]
    snapshot_ref = str(item.get("snapshot_ref") or "").strip()
    if snapshot_ref != RESUME_FORMAL_CANDIDATE_INDEX_REF:
        raise FormalCandidateLineageError(
            "resume formal candidate snapshot_ref mismatch: "
            f"{snapshot_ref or '<missing>'}"
        )
    snapshot_path = (source_root / snapshot_ref).resolve()
    if snapshot_path != fixed_snapshot_path:
        raise FormalCandidateLineageError(
            f"resume formal candidate snapshot path is not fixed: {snapshot_path}"
        )
    if not snapshot_path.is_file():
        raise FormalCandidateLineageError(
            f"resume formal candidate snapshot is missing: {snapshot_path}"
        )
    _validate_file_identity(
        snapshot_path,
        expected_size=item.get("size_bytes"),
        expected_sha256=item.get("sha256"),
        label="resume formal candidate snapshot",
    )
    return _read_index(
        snapshot_path,
        source_kind="source_inherited_snapshot",
        source_ref=snapshot_path,
    )


def _read_index(
    path: Path,
    *,
    source_kind: str,
    source_ref: Path,
) -> CandidateIndexSource:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise FormalCandidateLineageError(
            f"unable to read formal candidate index: {path}: {exc}"
        ) from exc
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FormalCandidateLineageError(
            f"formal candidate index is not UTF-8: {path}: {exc}"
        ) from exc
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise FormalCandidateLineageError(
                "formal candidate index contains invalid JSON: "
                f"{path}:{line_number}: {exc}"
            ) from exc
        if not isinstance(row, dict):
            raise FormalCandidateLineageError(
                f"formal candidate index row is not an object: {path}:{line_number}"
            )
        rows.append(row)
    return CandidateIndexSource(
        source_kind=source_kind,
        source_ref=source_ref,
        rows=tuple(rows),
        size_bytes=len(raw),
        sha256=sha256(raw).hexdigest(),
    )


def _validate_and_merge_rows(
    *,
    sources: Iterable[CandidateIndexSource],
    campaign_dir: Path,
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    by_artifact_ref: dict[str, dict[str, Any]] = {}
    by_recorded_candidate_id: dict[str, dict[str, Any]] = {}
    by_omission_identity: dict[str, dict[str, Any]] = {}
    legacy_rows: dict[str, dict[str, Any]] = {}
    output_rows: set[str] = set()
    for source in sources:
        for line_number, row in enumerate(source.rows, start=1):
            validated = _validate_row_contract(
                row=row,
                campaign_dir=campaign_dir,
                source_ref=source.source_ref,
                line_number=line_number,
            )
            artifact_ref = str(validated.get("artifact_ref") or "")
            candidate_id = str(validated.get("candidate_id") or "").strip()
            status = str(validated.get("artifact_status") or "").strip()
            if artifact_ref:
                _bind_unique_row(
                    by_artifact_ref,
                    artifact_ref,
                    validated,
                    identity_kind="artifact_ref",
                )
                _bind_unique_row(
                    by_recorded_candidate_id,
                    candidate_id,
                    validated,
                    identity_kind="recorded candidate_id",
                )
            elif status == "omitted" and candidate_id:
                omitted_reason = str(
                    validated.get("artifact_omitted_reason") or ""
                ).strip()
                omission_identity = f"{candidate_id}:{omitted_reason}"
                _bind_unique_row(
                    by_omission_identity,
                    omission_identity,
                    validated,
                    identity_kind="omitted candidate",
                )
            elif candidate_id:
                _bind_unique_row(
                    legacy_rows,
                    candidate_id,
                    validated,
                    identity_kind="legacy candidate_id",
                )
            else:
                canonical = json.dumps(
                    validated,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                _bind_unique_row(
                    legacy_rows,
                    canonical,
                    validated,
                    identity_kind="legacy_row",
                )
            canonical_row = json.dumps(
                validated,
                sort_keys=True,
                separators=(",", ":"),
            )
            if canonical_row not in output_rows:
                output_rows.add(canonical_row)
                merged.append(validated)
    return merged


def _bind_unique_row(
    index: dict[str, dict[str, Any]],
    identity: str,
    row: dict[str, Any],
    *,
    identity_kind: str,
) -> None:
    previous = index.get(identity)
    if previous is None:
        index[identity] = row
        return
    if previous != row:
        raise FormalCandidateLineageError(
            f"conflicting formal candidate index rows for {identity_kind} {identity}"
        )


def _validate_row_contract(
    *,
    row: dict[str, Any],
    campaign_dir: Path,
    source_ref: Path,
    line_number: int,
) -> dict[str, Any]:
    validated = dict(row)
    status_present = "artifact_status" in validated
    status = str(validated.get("artifact_status") or "").strip()
    raw_ref = validated.get("artifact_ref")
    has_ref = raw_ref is not None and raw_ref != ""
    location = f"{source_ref}:{line_number}"

    if not status_present and not has_ref:
        return validated
    if status_present and status not in {"recorded", "omitted"}:
        raise FormalCandidateLineageError(
            f"formal candidate index artifact_status is invalid at {location}: "
            f"{status or '<missing>'}"
        )
    if status == "omitted":
        if has_ref:
            raise FormalCandidateLineageError(
                f"omitted formal candidate index row has artifact_ref at {location}"
            )
        validated["artifact_status"] = "omitted"
        validated["artifact_ref"] = None
        return validated
    if not has_ref:
        raise FormalCandidateLineageError(
            f"recorded formal candidate index row lacks artifact_ref at {location}"
        )
    if not isinstance(raw_ref, str):
        raise FormalCandidateLineageError(
            f"formal candidate index artifact_ref is not a string at {location}"
        )
    canonical_ref = _canonical_formal_candidate_ref(raw_ref, location=location)
    validated["artifact_ref"] = canonical_ref
    if status_present:
        validated["artifact_status"] = "recorded"
    candidate_id = str(validated.get("candidate_id") or "").strip()
    if not candidate_id:
        raise FormalCandidateLineageError(
            f"recorded formal candidate index row lacks candidate_id at {location}"
        )
    campaign_root = campaign_dir.resolve()
    metadata_path = campaign_root / canonical_ref
    if metadata_path.resolve() != metadata_path or not metadata_path.is_file():
        raise FormalCandidateLineageError(
            "formal candidate index metadata is missing or not a fixed in-root "
            f"file: {canonical_ref}"
        )
    metadata = _read_json_object(metadata_path, label="formal candidate metadata")
    for field in ("candidate_id", "branch_id", "hypothesis_id"):
        expected = str(validated.get(field) or "").strip()
        if expected and str(metadata.get(field) or "").strip() != expected:
            raise FormalCandidateLineageError(
                "formal candidate index metadata identity mismatch for "
                f"{field} at {location}: {canonical_ref}"
            )
    return validated


def _canonical_formal_candidate_ref(raw_ref: str, *, location: str) -> str:
    ref = PurePosixPath(raw_ref)
    canonical = ref.as_posix()
    if (
        not raw_ref
        or ref.is_absolute()
        or canonical != raw_ref
        or any(part in {"", ".", ".."} for part in ref.parts)
        or ref.parts[:2] != ("artifacts", "formal_candidates")
        or ref.name != "candidate.patch.json"
    ):
        raise FormalCandidateLineageError(
            f"formal candidate index artifact_ref is not canonical at {location}: "
            f"{raw_ref}"
        )
    return canonical


def _validate_metadata_coverage(
    *,
    campaign_dir: Path,
    rows: list[dict[str, Any]],
    has_trusted_index: bool,
) -> None:
    artifact_root = campaign_dir / "artifacts" / "formal_candidates"
    disk_refs = {
        path.relative_to(campaign_dir).as_posix()
        for path in artifact_root.glob("**/candidate.patch.json")
        if path.is_file()
    }
    if disk_refs and not has_trusted_index:
        raise FormalCandidateLineageError(
            "resume formal candidate artifacts exist without a trusted lineage "
            f"index: {sorted(disk_refs)}"
        )
    indexed_refs = {str(row["artifact_ref"]) for row in rows if row.get("artifact_ref")}
    if indexed_refs != disk_refs:
        raise FormalCandidateLineageError(
            "resume formal candidate metadata coverage mismatch: "
            f"unindexed={sorted(disk_refs - indexed_refs)}, "
            f"missing={sorted(indexed_refs - disk_refs)}"
        )


def _read_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FormalCandidateLineageError(
            f"unable to read {label}: {path}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise FormalCandidateLineageError(f"{label} is not a JSON object: {path}")
    return value


def _resolved_manifest_path(value: Any, *, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise FormalCandidateLineageError(f"{label} is missing")
    return Path(value).expanduser().resolve()


def _validate_file_identity(
    path: Path,
    *,
    expected_size: Any,
    expected_sha256: Any,
    label: str,
) -> None:
    try:
        size = int(expected_size)
    except (TypeError, ValueError) as exc:
        raise FormalCandidateLineageError(
            f"{label} size is invalid: {expected_size}"
        ) from exc
    actual_size = path.stat().st_size
    if size != actual_size:
        raise FormalCandidateLineageError(
            f"{label} size mismatch: expected {size}, found {actual_size}"
        )
    digest = str(expected_sha256 or "").strip()
    actual_digest = _sha256_file(path)
    if digest != actual_digest:
        raise FormalCandidateLineageError(
            f"{label} sha256 mismatch: expected {digest}, found {actual_digest}"
        )


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _prune_empty_parents(path: Path, *, stop_at: Path) -> None:
    current = path
    while current != stop_at and current.is_dir():
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent
