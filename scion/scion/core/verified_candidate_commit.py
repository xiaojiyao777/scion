"""Durable ownership record for a verified candidate before formal evaluation."""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Protocol

from scion.core.evidence_recording.replay_identity import stable_patch_digest
from scion.core.models import (
    Branch,
    HypothesisProposal,
    HypothesisRecord,
    PatchFileChange,
    PatchProposal,
    patch_file_changes,
)

VERIFIED_CANDIDATE_COMMIT_SCHEMA = "verified-candidate-commit.v1"
VERIFIED_CANDIDATE_COMMIT_REF_SCHEMA = "verified-candidate-commit-ref.v1"
VERIFIED_CANDIDATE_COMMIT_SUMMARY_KEY = "verified_candidate_commit"


class CandidateIdentityMaterializer(Protocol):
    def compute_code_hash(self, workspace: str) -> str: ...

    def compute_snapshot_hash(self, workspace: str) -> str: ...


@dataclass(frozen=True)
class VerifiedCandidateCommit:
    artifact_ref: str
    artifact_sha256: str
    branch_id: str
    hypothesis_id: str
    verified_code_hash: str
    executable_snapshot_hash: str
    patch_digest: str
    patch: PatchProposal
    commit_kind: str
    lineage_id: str
    base_code_hash: str
    hypothesis_change_locus: str
    hypothesis_action: str
    hypothesis_target_file: str
    hypothesis_text: str
    hypothesis_predicted_direction: str
    hypothesis_suggested_weight: float | None


class VerifiedCandidateCommitRecorder:
    """Write and validate the pre-formal verified-candidate commit record."""

    def __init__(self, campaign_dir: str | os.PathLike[str]) -> None:
        self.campaign_dir = Path(campaign_dir).resolve()
        self.artifact_dir = (
            self.campaign_dir / "artifacts" / "verified_candidate_commits"
        )

    def record(
        self,
        *,
        branch: Branch,
        hypothesis: HypothesisProposal,
        h_record: HypothesisRecord,
        patch: PatchProposal,
        workspace: str,
        base_code_hash: str | None,
        materializer: CandidateIdentityMaterializer,
        commit_kind: str = "explore",
    ) -> str:
        """Atomically prepare ownership before candidate workspace promotion."""

        verified_code_hash = str(branch.current_code_hash or "")
        if not verified_code_hash:
            raise RuntimeError(
                f"Branch {branch.branch_id}: verified candidate hash is unavailable"
            )
        actual_code_hash = materializer.compute_code_hash(workspace)
        if actual_code_hash != verified_code_hash:
            raise RuntimeError(
                f"Branch {branch.branch_id}: verified candidate code identity mismatch"
            )
        executable_snapshot_hash = materializer.compute_snapshot_hash(workspace)
        changes = patch_file_changes(patch)
        patch_digest = stable_patch_digest(changes)
        if commit_kind not in {"explore", "reconcile"}:
            raise ValueError("verified candidate commit_kind is invalid")
        payload = {
            "schema_version": VERIFIED_CANDIDATE_COMMIT_SCHEMA,
            "created_at": datetime.now().isoformat(),
            "branch_id": branch.branch_id,
            "lineage_id": branch.lineage_id or branch.branch_id,
            "hypothesis_id": h_record.hypothesis_id,
            "base_code_hash": base_code_hash,
            "verified_code_hash": verified_code_hash,
            "executable_snapshot_hash": executable_snapshot_hash,
            "patch_digest": patch_digest,
            "promotion_status": "prepared",
            "evaluation_status": "pending",
            "commit_kind": commit_kind,
            "hypothesis": {
                "change_locus": hypothesis.change_locus,
                "action": hypothesis.action,
                "target_file": hypothesis.target_file,
                "hypothesis_text": hypothesis.hypothesis_text,
                "predicted_direction": hypothesis.predicted_direction,
                "suggested_weight": hypothesis.suggested_weight,
            },
            "patch": {
                "representation": "full_file_replacement",
                "files": [
                    {
                        "file_path": change.file_path,
                        "action": change.action,
                        "code_content": change.code_content,
                        "test_hint": change.test_hint,
                    }
                    for change in changes
                ],
                "repair_attribution": [
                    dict(item)
                    for item in tuple(patch.repair_attribution or ())
                    if isinstance(item, Mapping)
                ],
            },
        }
        artifact_bytes = (
            json.dumps(payload, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        artifact_sha256 = hashlib.sha256(artifact_bytes).hexdigest()
        # The same hypothesis can be reconciled more than once.  A content-
        # addressed ref keeps the previously persisted commit immutable if a
        # later reconcile is rolled back before its branch state is committed.
        artifact_path = (
            self.artifact_dir
            / _safe_component(branch.branch_id)
            / (
                f"{_safe_component(h_record.hypothesis_id)}-"
                f"{artifact_sha256}.json"
            )
        )
        _atomic_write(artifact_path, artifact_bytes)
        artifact_ref = artifact_path.relative_to(self.campaign_dir).as_posix()
        summary = dict(branch.branch_evidence_summary or {})
        summary[VERIFIED_CANDIDATE_COMMIT_SUMMARY_KEY] = {
            "schema_version": VERIFIED_CANDIDATE_COMMIT_REF_SCHEMA,
            "artifact_schema": VERIFIED_CANDIDATE_COMMIT_SCHEMA,
            "artifact_ref": artifact_ref,
            "artifact_sha256": artifact_sha256,
            "hypothesis_id": h_record.hypothesis_id,
            "verified_code_hash": verified_code_hash,
            "executable_snapshot_hash": executable_snapshot_hash,
            "patch_digest": patch_digest,
            "promotion_status": "prepared",
            "evaluation_status": "pending",
            "commit_kind": commit_kind,
        }
        branch.branch_evidence_summary = summary
        return artifact_ref

    def mark_promotion_committed(self, branch: Branch) -> None:
        marker = _verified_candidate_marker(branch)
        marker["promotion_status"] = "committed"
        summary = dict(branch.branch_evidence_summary or {})
        summary[VERIFIED_CANDIDATE_COMMIT_SUMMARY_KEY] = marker
        branch.branch_evidence_summary = summary

    def load_and_validate(
        self,
        *,
        branch: Branch,
        workspace: str,
        materializer: CandidateIdentityMaterializer,
    ) -> VerifiedCandidateCommit | None:
        """Validate a persisted commit ref and the physical executable identity."""

        summary = branch.branch_evidence_summary or {}
        marker = summary.get(VERIFIED_CANDIDATE_COMMIT_SUMMARY_KEY)
        if marker is None:
            return None
        if not isinstance(marker, Mapping):
            raise RuntimeError(
                f"Branch {branch.branch_id}: verified candidate commit ref is invalid"
            )
        _require_equal(
            marker.get("schema_version"),
            VERIFIED_CANDIDATE_COMMIT_REF_SCHEMA,
            branch.branch_id,
            "commit ref schema",
        )
        _require_equal(
            marker.get("artifact_schema"),
            VERIFIED_CANDIDATE_COMMIT_SCHEMA,
            branch.branch_id,
            "commit artifact schema",
        )
        artifact_path = self._resolve_artifact(marker.get("artifact_ref"))
        try:
            artifact_bytes = artifact_path.read_bytes()
        except OSError as exc:
            raise RuntimeError(
                f"Branch {branch.branch_id}: verified candidate commit artifact "
                "is unavailable"
            ) from exc
        artifact_sha256 = hashlib.sha256(artifact_bytes).hexdigest()
        _require_equal(
            artifact_sha256,
            marker.get("artifact_sha256"),
            branch.branch_id,
            "commit artifact digest",
        )
        try:
            payload = json.loads(artifact_bytes)
        except (TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                f"Branch {branch.branch_id}: verified candidate commit artifact "
                "is invalid"
            ) from exc
        if not isinstance(payload, Mapping):
            raise RuntimeError(
                f"Branch {branch.branch_id}: verified candidate commit artifact "
                "is invalid"
            )
        _require_equal(
            payload.get("schema_version"),
            VERIFIED_CANDIDATE_COMMIT_SCHEMA,
            branch.branch_id,
            "commit schema",
        )
        _require_equal(
            payload.get("branch_id"),
            branch.branch_id,
            branch.branch_id,
            "commit branch ownership",
        )
        expected_lineage_id = branch.lineage_id or branch.branch_id
        _require_equal(
            payload.get("lineage_id"),
            expected_lineage_id,
            branch.branch_id,
            "commit lineage ownership",
        )
        _require_equal(
            payload.get("promotion_status"),
            "prepared",
            branch.branch_id,
            "artifact promotion status",
        )
        _require_equal(
            payload.get("evaluation_status"),
            "pending",
            branch.branch_id,
            "artifact evaluation status",
        )
        for key in (
            "hypothesis_id",
            "verified_code_hash",
            "executable_snapshot_hash",
            "patch_digest",
            "commit_kind",
        ):
            _require_equal(
                payload.get(key),
                marker.get(key),
                branch.branch_id,
                f"commit {key}",
            )
        if marker.get("promotion_status") not in {"prepared", "committed"}:
            raise RuntimeError(
                f"Branch {branch.branch_id}: verified candidate promotion status mismatch"
            )
        if marker.get("evaluation_status") not in {"pending", "completed"}:
            raise RuntimeError(
                f"Branch {branch.branch_id}: verified candidate evaluation status mismatch"
            )
        verified_code_hash = str(payload.get("verified_code_hash") or "")
        if (
            not verified_code_hash
            or branch.current_code_hash != verified_code_hash
            or branch.last_clean_code_hash != verified_code_hash
        ):
            raise RuntimeError(
                f"Branch {branch.branch_id}: verified candidate commit code "
                "identity mismatch"
            )
        commit_kind = str(payload.get("commit_kind") or "")
        if commit_kind not in {"explore", "reconcile"}:
            raise RuntimeError(
                f"Branch {branch.branch_id}: verified candidate commit kind mismatch"
            )
        base_code_hash = str(payload.get("base_code_hash") or "")
        if not base_code_hash:
            raise RuntimeError(
                f"Branch {branch.branch_id}: verified candidate base identity mismatch"
            )
        if (
            commit_kind == "reconcile"
            and base_code_hash != branch.base_champion_hash
        ):
            raise RuntimeError(
                f"Branch {branch.branch_id}: verified candidate reconcile base mismatch"
            )
        hypothesis_payload = payload.get("hypothesis")
        if not isinstance(hypothesis_payload, Mapping):
            raise RuntimeError(
                f"Branch {branch.branch_id}: verified candidate hypothesis ownership mismatch"
            )
        hypothesis_change_locus = str(
            hypothesis_payload.get("change_locus") or ""
        )
        hypothesis_action = str(hypothesis_payload.get("action") or "")
        hypothesis_target_file = str(
            hypothesis_payload.get("target_file") or ""
        )
        hypothesis_text = str(hypothesis_payload.get("hypothesis_text") or "")
        hypothesis_predicted_direction = str(
            hypothesis_payload.get("predicted_direction") or ""
        )
        suggested_weight_raw = hypothesis_payload.get("suggested_weight")
        if suggested_weight_raw is not None and (
            isinstance(suggested_weight_raw, bool)
            or not isinstance(suggested_weight_raw, (int, float))
        ):
            raise RuntimeError(
                f"Branch {branch.branch_id}: verified candidate hypothesis ownership mismatch"
            )
        hypothesis_suggested_weight = (
            float(suggested_weight_raw)
            if suggested_weight_raw is not None
            else None
        )
        if not all(
            (
                hypothesis_change_locus,
                hypothesis_action,
                hypothesis_target_file,
                hypothesis_text,
                hypothesis_predicted_direction,
            )
        ):
            raise RuntimeError(
                f"Branch {branch.branch_id}: verified candidate hypothesis ownership mismatch"
            )
        if materializer.compute_code_hash(workspace) != verified_code_hash:
            raise RuntimeError(
                f"Branch {branch.branch_id}: verified candidate commit physical "
                "code mismatch"
            )
        executable_snapshot_hash = str(payload.get("executable_snapshot_hash") or "")
        if materializer.compute_snapshot_hash(workspace) != executable_snapshot_hash:
            raise RuntimeError(
                f"Branch {branch.branch_id}: verified candidate executable "
                "identity mismatch"
            )
        patch = _patch_from_payload(payload, branch.branch_id)
        patch_digest = stable_patch_digest(patch_file_changes(patch))
        _require_equal(
            patch_digest,
            payload.get("patch_digest"),
            branch.branch_id,
            "commit patch digest",
        )
        return VerifiedCandidateCommit(
            artifact_ref=artifact_path.relative_to(self.campaign_dir).as_posix(),
            artifact_sha256=artifact_sha256,
            branch_id=branch.branch_id,
            hypothesis_id=str(payload.get("hypothesis_id") or ""),
            verified_code_hash=verified_code_hash,
            executable_snapshot_hash=executable_snapshot_hash,
            patch_digest=patch_digest,
            patch=patch,
            commit_kind=commit_kind,
            lineage_id=expected_lineage_id,
            base_code_hash=base_code_hash,
            hypothesis_change_locus=hypothesis_change_locus,
            hypothesis_action=hypothesis_action,
            hypothesis_target_file=hypothesis_target_file,
            hypothesis_text=hypothesis_text,
            hypothesis_predicted_direction=hypothesis_predicted_direction,
            hypothesis_suggested_weight=hypothesis_suggested_weight,
        )

    def _resolve_artifact(self, ref: Any) -> Path:
        text = str(ref or "").strip()
        if not text:
            raise RuntimeError("verified candidate commit artifact ref is missing")
        path = Path(text)
        resolved = (
            path.resolve()
            if path.is_absolute()
            else (self.campaign_dir / path).resolve()
        )
        try:
            resolved.relative_to(self.campaign_dir)
        except ValueError as exc:
            raise RuntimeError(
                "verified candidate commit artifact ref escapes campaign root"
            ) from exc
        return resolved


def _patch_from_payload(payload: Mapping[str, Any], branch_id: str) -> PatchProposal:
    patch_payload = payload.get("patch")
    files = patch_payload.get("files") if isinstance(patch_payload, Mapping) else None
    if not isinstance(files, list) or not files:
        raise RuntimeError(f"Branch {branch_id}: verified candidate patch is invalid")
    changes: list[PatchFileChange] = []
    for item in files:
        if not isinstance(item, Mapping):
            raise RuntimeError(
                f"Branch {branch_id}: verified candidate patch is invalid"
            )
        file_path = str(item.get("file_path") or "").strip()
        action = str(item.get("action") or "").strip()
        code_content = item.get("code_content")
        if (
            not file_path
            or action not in {"modify", "create", "delete"}
            or not isinstance(code_content, str)
        ):
            raise RuntimeError(
                f"Branch {branch_id}: verified candidate patch is invalid"
            )
        changes.append(
            PatchFileChange(
                file_path=file_path,
                action=action,  # type: ignore[arg-type]
                code_content=code_content,
                test_hint=(
                    str(item["test_hint"])
                    if item.get("test_hint") is not None
                    else None
                ),
            )
        )
    primary, *additional = changes
    repair_attribution = ()
    if isinstance(patch_payload, Mapping):
        raw_attribution = patch_payload.get("repair_attribution")
        if isinstance(raw_attribution, list):
            repair_attribution = tuple(
                dict(item) for item in raw_attribution if isinstance(item, Mapping)
            )
    return PatchProposal(
        file_path=primary.file_path,
        action=primary.action,
        code_content=primary.code_content,
        test_hint=primary.test_hint,
        additional_changes=tuple(additional),
        repair_attribution=repair_attribution,
    )


def verified_candidate_pending_evaluation(branch: Branch) -> bool:
    marker = (branch.branch_evidence_summary or {}).get(
        VERIFIED_CANDIDATE_COMMIT_SUMMARY_KEY
    )
    return (
        isinstance(marker, Mapping)
        and marker.get("promotion_status") == "committed"
        and marker.get("evaluation_status") == "pending"
    )


def verified_candidate_commit_kind(branch: Branch) -> str | None:
    marker = (branch.branch_evidence_summary or {}).get(
        VERIFIED_CANDIDATE_COMMIT_SUMMARY_KEY
    )
    if not isinstance(marker, Mapping):
        return None
    commit_kind = str(marker.get("commit_kind") or "")
    return commit_kind if commit_kind in {"explore", "reconcile"} else None


def mark_verified_candidate_evaluation_completed(branch: Branch) -> bool:
    marker = (branch.branch_evidence_summary or {}).get(
        VERIFIED_CANDIDATE_COMMIT_SUMMARY_KEY
    )
    if not isinstance(marker, Mapping) or marker.get("evaluation_status") != "pending":
        return False
    updated = dict(marker)
    updated["evaluation_status"] = "completed"
    summary = dict(branch.branch_evidence_summary or {})
    summary[VERIFIED_CANDIDATE_COMMIT_SUMMARY_KEY] = updated
    branch.branch_evidence_summary = summary
    return True


def discard_prepared_verified_candidate_commit(branch: Branch) -> None:
    summary = dict(branch.branch_evidence_summary or {})
    marker = summary.get(VERIFIED_CANDIDATE_COMMIT_SUMMARY_KEY)
    if isinstance(marker, Mapping) and marker.get("promotion_status") == "prepared":
        summary.pop(VERIFIED_CANDIDATE_COMMIT_SUMMARY_KEY, None)
        branch.branch_evidence_summary = summary


def _verified_candidate_marker(branch: Branch) -> dict[str, Any]:
    marker = (branch.branch_evidence_summary or {}).get(
        VERIFIED_CANDIDATE_COMMIT_SUMMARY_KEY
    )
    if not isinstance(marker, Mapping):
        raise RuntimeError(
            f"Branch {branch.branch_id}: verified candidate commit ref is unavailable"
        )
    return dict(marker)


def _require_equal(actual: Any, expected: Any, branch_id: str, label: str) -> None:
    if not isinstance(actual, str) or not actual or actual != expected:
        raise RuntimeError(f"Branch {branch_id}: verified candidate {label} mismatch")


def _safe_component(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]", "_", str(value or ""))
    return cleaned or hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:16]


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.tmp-{uuid.uuid4().hex}"
    try:
        with temporary.open("wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            try:
                existing = path.read_bytes()
            except OSError as exc:
                raise RuntimeError(
                    "verified candidate artifact exists but is unreadable"
                ) from exc
            if existing != content:
                raise RuntimeError(
                    "verified candidate artifact is immutable"
                )
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
