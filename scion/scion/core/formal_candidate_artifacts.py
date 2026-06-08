"""Canonical patch artifacts for formally screened candidates."""
from __future__ import annotations

import difflib
import hashlib
import json
import logging
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from scion.core.evidence_recording.replay_identity import (
    formal_replay_identity_payload,
    stable_patch_digest,
)
from scion.core.models import (
    Branch,
    CanaryResult,
    ContractResult,
    Decision,
    HypothesisProposal,
    HypothesisRecord,
    PatchFileChange,
    PatchProposal,
    ProtocolResult,
    VerificationResult,
    patch_file_changes,
)
from scion.core.paths import normalize_relative_patch_path
from scion.core.public_refs import public_artifact_ref

logger = logging.getLogger(__name__)


class FormalCandidatePatchArtifactRecorder:
    """Persist replayable patch/diff artifacts outside branch workspace cleanup."""

    schema = "scion.formal_candidate_patch_artifact.v1"

    def __init__(
        self,
        campaign_dir: str | Path,
        *,
        protocol_version: str | None = None,
        problem_spec_hash: str | None = None,
        split_manifest_hash: str | None = None,
        seed_ledger_hash: str | None = None,
    ) -> None:
        self.campaign_dir = Path(campaign_dir)
        self.artifact_dir = self.campaign_dir / "artifacts" / "formal_candidates"
        self.protocol_version = protocol_version
        self.problem_spec_hash = problem_spec_hash
        self.split_manifest_hash = split_manifest_hash
        self.seed_ledger_hash = seed_ledger_hash

    def record(
        self,
        *,
        branch: Branch,
        hypothesis: HypothesisProposal,
        h_record: HypothesisRecord,
        patch: PatchProposal | None,
        protocol_result: ProtocolResult | None,
        canary_result: CanaryResult,
        contract_result: ContractResult,
        verification_result: VerificationResult,
        decision: Decision,
        decision_reason_codes: Iterable[str] | None = None,
        workspace: str | None = None,
        base_workspace: str | None = None,
    ) -> str | None:
        """Write one canonical patch artifact and return its public metadata ref."""
        if patch is None or protocol_result is None:
            return None
        if not (
            contract_result.passed
            and verification_result.passed
            and canary_result.passed
        ):
            return None
        stage = _stage_value(protocol_result)
        if stage != "screening":
            return None

        changes = patch_file_changes(patch)
        patch_digest = _patch_digest(changes)
        candidate_id = _candidate_id(
            branch_id=branch.branch_id,
            hypothesis_id=h_record.hypothesis_id,
            stage=stage,
            patch_digest=patch_digest,
        )
        dest = (
            self.artifact_dir
            / _safe_path_part(branch.branch_id[:8] or "branch")
            / f"{stage}-{_safe_path_part(h_record.hypothesis_id or 'hypothesis')}-{candidate_id}"
        )
        metadata_path = dest / "candidate.patch.json"
        diff_path = dest / "candidate.diff"
        if metadata_path.exists() and diff_path.exists():
            return public_artifact_ref(metadata_path, base_dir=self.campaign_dir)

        dest.mkdir(parents=True, exist_ok=True)
        diff_text = _render_candidate_diff(
            changes,
            base_workspace=base_workspace,
        )
        diff_path.write_text(diff_text, encoding="utf-8")
        raw_metrics_ref = public_artifact_ref(
            protocol_result.raw_metrics_ref,
            base_dir=self.campaign_dir,
            kind="metrics",
        )
        selected_surface = (
            getattr(protocol_result, "selected_surface", None)
            or hypothesis.change_locus
            or ""
        )
        replay_identity = formal_replay_identity_payload(
            problem_spec_hash=self.problem_spec_hash,
            split_manifest_hash=self.split_manifest_hash,
            seed_ledger_hash=self.seed_ledger_hash,
            patch_digest=patch_digest,
            selected_surface=selected_surface,
            protocol_version=self.protocol_version,
            raw_metrics_ref=raw_metrics_ref,
            code_hash=getattr(branch, "current_code_hash", None),
        )
        metadata = {
            "schema": self.schema,
            "created_at": datetime.now().isoformat(),
            "candidate_id": candidate_id,
            "campaign_artifact_kind": "formal_screening_candidate_patch",
            "branch_id": branch.branch_id,
            "lineage_id": getattr(branch, "lineage_id", None) or branch.branch_id,
            "hypothesis_id": h_record.hypothesis_id,
            "experiment_ref": raw_metrics_ref,
            "stage": stage,
            "decision": decision.value,
            "decision_reason_codes": list(decision_reason_codes or ()),
            "branch_code_status": str(
                getattr(branch, "branch_code_status", "") or ""
            ),
            "target_files": [change.file_path for change in changes],
            "base": {
                "base_champion_id": branch.base_champion_id,
                "base_champion_hash": branch.base_champion_hash,
                "last_clean_code_hash": getattr(branch, "last_clean_code_hash", None),
                "base_workspace_ref": public_artifact_ref(
                    base_workspace,
                    base_dir=self.campaign_dir,
                ),
            },
            "current": {
                "current_code_hash": getattr(branch, "current_code_hash", None),
                "workspace_ref": public_artifact_ref(
                    workspace,
                    base_dir=self.campaign_dir,
                ),
            },
            "gates": {
                "contract_passed": contract_result.passed,
                "verification_passed": verification_result.passed,
                "canary_passed": canary_result.passed,
            },
            "patch": {
                "patch_digest": patch_digest,
                "representation": "full_file_replacement",
                "diff_ref": public_artifact_ref(
                    diff_path,
                    base_dir=self.campaign_dir,
                ),
                "files": [
                    _change_payload(
                        change,
                        workspace=workspace,
                        base_workspace=base_workspace,
                    )
                    for change in changes
                ],
            },
            "replay_identity": replay_identity,
            "replay_metadata": {
                "raw_metrics_ref": raw_metrics_ref,
                "selected_surface": selected_surface,
                "replay_identity_ref": "candidate.patch.json#/replay_identity",
                "replay_identity_status": replay_identity["identity_status"],
                "patch_model": (
                    "code_content is canonical full-file candidate content; "
                    "base/current hashes and diff support audit replay"
                ),
            },
            "hypothesis": {
                "change_locus": h_record.change_locus,
                "action": h_record.action,
                "target_file": h_record.target_file,
            },
        }
        metadata_path.write_text(
            json.dumps(_jsonable(metadata), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        _append_index(
            self.artifact_dir / "index.jsonl",
            {
                "schema": self.schema,
                "candidate_id": candidate_id,
                "branch_id": branch.branch_id,
                "hypothesis_id": h_record.hypothesis_id,
                "stage": stage,
                "branch_code_status": metadata["branch_code_status"],
                "patch_digest": patch_digest,
                "artifact_ref": public_artifact_ref(
                    metadata_path,
                    base_dir=self.campaign_dir,
                ),
                "diff_ref": public_artifact_ref(diff_path, base_dir=self.campaign_dir),
            },
        )
        return public_artifact_ref(metadata_path, base_dir=self.campaign_dir)


def _stage_value(protocol_result: ProtocolResult) -> str:
    stage = getattr(protocol_result, "stage", "")
    return str(getattr(stage, "value", stage) or "")


def _candidate_id(
    *,
    branch_id: str,
    hypothesis_id: str,
    stage: str,
    patch_digest: str,
) -> str:
    raw = json.dumps(
        {
            "branch_id": branch_id,
            "hypothesis_id": hypothesis_id,
            "stage": stage,
            "patch_digest": patch_digest,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _patch_digest(changes: Iterable[PatchFileChange]) -> str:
    return stable_patch_digest(changes)


def _change_payload(
    change: PatchFileChange,
    *,
    workspace: str | None,
    base_workspace: str | None,
) -> dict[str, Any]:
    code = change.code_content or ""
    payload = {
        "file_path": normalize_relative_patch_path(change.file_path),
        "action": change.action,
        "code_sha256": hashlib.sha256(code.encode("utf-8")).hexdigest(),
        "code_content": code,
    }
    current_hash = _workspace_file_sha256(workspace, change.file_path)
    if current_hash:
        payload["workspace_current_sha256"] = current_hash
    base_hash = _workspace_file_sha256(base_workspace, change.file_path)
    if base_hash:
        payload["base_sha256"] = base_hash
    return payload


def _render_candidate_diff(
    changes: Iterable[PatchFileChange],
    *,
    base_workspace: str | None,
) -> str:
    chunks: list[str] = []
    for change in changes:
        file_rel = normalize_relative_patch_path(change.file_path)
        old_lines = _base_lines(base_workspace, file_rel)
        if old_lines is None and change.action == "modify":
            chunks.append(
                f"# scion-diff-note: base content unavailable for {file_rel}; "
                "candidate.patch.json contains canonical full-file content.\n"
            )
            old_lines = []
        if change.action == "create":
            old_lines = []
        new_lines = [] if change.action == "delete" else _split_keepends(
            change.code_content or ""
        )
        fromfile = "/dev/null" if change.action == "create" else f"a/{file_rel}"
        tofile = "/dev/null" if change.action == "delete" else f"b/{file_rel}"
        chunks.extend(
            difflib.unified_diff(
                old_lines or [],
                new_lines,
                fromfile=fromfile,
                tofile=tofile,
                lineterm="",
            )
        )
        chunks.append("")
    return "\n".join(chunks).rstrip() + "\n"


def _base_lines(base_workspace: str | None, file_rel: str) -> list[str] | None:
    if not base_workspace:
        return None
    base = Path(base_workspace)
    try:
        target = (base / file_rel).resolve()
        target.relative_to(base.resolve())
    except Exception:
        return None
    if not target.is_file():
        return None
    return _split_keepends(target.read_text(encoding="utf-8"))


def _split_keepends(text: str) -> list[str]:
    return text.splitlines(keepends=True)


def _workspace_file_sha256(workspace: str | None, file_path: str) -> str | None:
    if not workspace:
        return None
    try:
        base = Path(workspace).resolve()
        target = (base / normalize_relative_patch_path(file_path)).resolve()
        target.relative_to(base)
    except Exception:
        return None
    if not target.is_file():
        return None
    try:
        return hashlib.sha256(target.read_bytes()).hexdigest()
    except Exception:
        return None


def _safe_path_part(value: str) -> str:
    cleaned = "".join(
        char if char.isalnum() or char in {"-", "_", "."} else "-"
        for char in str(value)
    ).strip(".-")
    return cleaned[:80] or "candidate"


def _append_index(index_path: Path, payload: dict[str, Any]) -> None:
    index_path.parent.mkdir(parents=True, exist_ok=True)
    with index_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(_jsonable(payload), sort_keys=True) + "\n")


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value
