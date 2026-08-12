"""Canonical patch artifacts for formally screened candidates."""

from __future__ import annotations

import difflib
import hashlib
import json
import logging
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from scion.core.evidence_recording.replay_identity import (
    formal_replay_identity_missing_keys,
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

    legacy_schema = "scion.formal_candidate_patch_artifact.v2"
    cumulative_schema = "scion.formal_candidate_patch_artifact.v3"

    def __init__(
        self,
        campaign_dir: str | Path,
        *,
        protocol_version: str | None = None,
        problem_spec_hash: str | None = None,
        split_manifest_hash: str | None = None,
        seed_ledger_hash: str | None = None,
        identity_manifest_for: Callable[[str], Mapping[str, Any]] | None = None,
    ) -> None:
        self.campaign_dir = Path(campaign_dir)
        self.artifact_dir = self.campaign_dir / "artifacts" / "formal_candidates"
        self.protocol_version = protocol_version
        self.problem_spec_hash = problem_spec_hash
        self.split_manifest_hash = split_manifest_hash
        self.seed_ledger_hash = seed_ledger_hash
        self.identity_manifest_for = identity_manifest_for
        # Direct/unit callers without a problem-owned materializer retain the
        # exact v2 artifact contract. Production composition supplies the
        # identity callback and therefore records cumulative v3 replay closure.
        self.schema = (
            self.cumulative_schema
            if identity_manifest_for is not None
            else self.legacy_schema
        )

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
        proposal_attempt_ref: Mapping[str, Any] | None = None,
    ) -> str | None:
        """Write one canonical patch artifact and return its public metadata ref."""
        if protocol_result is None:
            return None
        stage = _stage_value(protocol_result)
        if stage != "screening" or getattr(protocol_result, "stats", None) is None:
            return None
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
        proposal_changes = patch_file_changes(patch) if patch is not None else ()
        proposal_paths = {
            normalize_relative_patch_path(change.file_path)
            for change in proposal_changes
        }
        proposal_patch_digest = (
            _patch_digest(proposal_changes) if patch is not None else ""
        )
        replay_materialization: dict[str, Any] | None = None
        formal_gates_passed = (
            contract_result.passed
            and verification_result.passed
            and canary_result.passed
        )
        if (
            self.schema == self.cumulative_schema
            and patch is not None
            and formal_gates_passed
        ):
            replay_materialization = self._build_replay_materialization(
                branch=branch,
                proposal_changes=proposal_changes,
                workspace=workspace,
                base_workspace=base_workspace,
            )
            changes = tuple(replay_materialization.pop("_changes"))
            activation_files = list(replay_materialization["activation_files"])
            inherited_files = list(replay_materialization["inherited_files"])
            patch_digest = str(replay_materialization["patch_digest"])
        elif self.schema == self.cumulative_schema:
            # Omitted candidates keep current-attempt identity only; they have
            # no replay artifact and therefore require no cumulative closure.
            changes = proposal_changes
            activation_files = []
            inherited_files = []
            patch_digest = proposal_patch_digest
        else:
            changes = _changes_with_activation_files(
                proposal_changes,
                workspace=workspace,
                base_workspace=base_workspace,
            )
            activation_files = _activation_file_paths(proposal_changes, changes)
            inherited_files = []
            patch_digest = _patch_digest(changes) if patch is not None else ""
        replay_identity = (
            formal_replay_identity_payload(
                problem_spec_hash=self.problem_spec_hash,
                split_manifest_hash=self.split_manifest_hash,
                seed_ledger_hash=self.seed_ledger_hash,
                patch_digest=patch_digest,
                selected_surface=selected_surface,
                protocol_version=self.protocol_version,
                raw_metrics_ref=raw_metrics_ref,
                code_hash=getattr(branch, "current_code_hash", None),
            )
            if patch is not None
            else None
        )
        missing_replay_identity_keys = formal_replay_identity_missing_keys(
            replay_identity
        )
        omitted_reasons = _artifact_omitted_reasons(
            patch=patch,
            contract_result=contract_result,
            verification_result=verification_result,
            canary_result=canary_result,
            missing_replay_identity_keys=missing_replay_identity_keys,
        )
        candidate_id = _candidate_id(
            branch_id=branch.branch_id,
            hypothesis_id=h_record.hypothesis_id,
            stage=stage,
            raw_metrics_ref=raw_metrics_ref,
            patch_digest=patch_digest
            or _omitted_candidate_digest(
                branch=branch,
                h_record=h_record,
                stage=stage,
                raw_metrics_ref=raw_metrics_ref,
                omitted_reasons=omitted_reasons,
            ),
        )
        proposal_attempt_fields = _proposal_attempt_join_fields(
            proposal_attempt_ref,
            hypothesis_id=h_record.hypothesis_id,
        )
        if omitted_reasons:
            self._record_omitted(
                branch=branch,
                h_record=h_record,
                stage=stage,
                candidate_id=candidate_id,
                patch_digest=patch_digest,
                raw_metrics_ref=raw_metrics_ref,
                selected_surface=selected_surface,
                replay_identity=replay_identity,
                missing_replay_identity_keys=missing_replay_identity_keys,
                omitted_reasons=omitted_reasons,
                decision=decision,
                decision_reason_codes=decision_reason_codes,
                proposal_attempt_fields=proposal_attempt_fields,
            )
            return None
        assert patch is not None
        assert replay_identity is not None
        if not formal_gates_passed:
            return None
        dest = (
            self.artifact_dir
            / _safe_path_part(branch.branch_id[:8] or "branch")
            / f"{stage}-{_safe_path_part(h_record.hypothesis_id or 'hypothesis')}-{candidate_id}"
        )
        metadata_path = dest / "candidate.patch.json"
        diff_path = dest / "candidate.diff"
        proposal_diff_path = dest / "proposal.diff"
        artifact_ref = public_artifact_ref(metadata_path, base_dir=self.campaign_dir)
        diff_text = _render_candidate_diff(
            changes,
            base_workspace=base_workspace,
        )
        proposal_diff_text = (
            _render_candidate_diff(
                proposal_changes,
                base_workspace=base_workspace,
            )
            if self.schema == self.cumulative_schema
            else None
        )
        patch_files = [
            _change_payload(
                change,
                workspace=workspace,
                base_workspace=base_workspace,
            )
            for change in (
                proposal_changes if self.schema == self.cumulative_schema else changes
            )
        ]
        proposal_target_files = [
            normalize_relative_patch_path(change.file_path)
            for change in proposal_changes
        ]
        metadata = {
            "schema": self.schema,
            "created_at": datetime.now().isoformat(),
            "candidate_id": candidate_id,
            "campaign_artifact_kind": "formal_screening_candidate_patch",
            "branch_id": branch.branch_id,
            "lineage_id": getattr(branch, "lineage_id", None) or branch.branch_id,
            "hypothesis_id": h_record.hypothesis_id,
            **proposal_attempt_fields,
            "experiment_ref": raw_metrics_ref,
            "stage": stage,
            "decision": decision.value,
            "decision_reason_codes": list(decision_reason_codes or ()),
            "branch_code_status": str(getattr(branch, "branch_code_status", "") or ""),
            "target_files": [
                normalize_relative_patch_path(change.file_path) for change in changes
            ],
            "proposal_target_files": proposal_target_files,
            "activation_files": activation_files,
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
                "patch_digest": (
                    proposal_patch_digest
                    if self.schema == self.cumulative_schema
                    else patch_digest
                ),
                "representation": "full_file_replacement",
                "normalization_events": [
                    dict(item)
                    for item in tuple(patch.repair_attribution or ())
                    if isinstance(item, Mapping)
                ],
                "diff_ref": public_artifact_ref(
                    proposal_diff_path
                    if self.schema == self.cumulative_schema
                    else diff_path,
                    base_dir=self.campaign_dir,
                ),
                "files": patch_files,
            },
            "replay_identity": replay_identity,
            "replay_metadata": {
                "raw_metrics_ref": raw_metrics_ref,
                "selected_surface": selected_surface,
                "replay_identity_ref": "candidate.patch.json#/replay_identity",
                "replay_identity_status": replay_identity["identity_status"],
                "patch_model": (
                    (
                        "patch is the current proposal attempt; "
                        "replay_materialization is the cumulative full-file "
                        "closure from the declared champion base"
                    )
                    if self.schema == self.cumulative_schema
                    else (
                        "code_content is canonical full-file candidate content; "
                        "base/current hashes and diff support audit replay; "
                        "activation_files are runtime-owned support files required "
                        "to materialize the executed candidate workspace"
                    )
                ),
                "formal_replay_identity_ref": (
                    f"{artifact_ref}#/replay_identity" if artifact_ref else ""
                ),
            },
            "hypothesis": {
                "change_locus": h_record.change_locus,
                "action": h_record.action,
                "target_file": h_record.target_file,
            },
        }
        if self.schema == self.cumulative_schema:
            assert replay_materialization is not None
            materialized_proposal_files = sorted(
                proposal_paths.intersection(metadata["target_files"])
            )
            metadata.update(
                {
                    "proposal_patch_digest": proposal_patch_digest,
                    "formal_patch_digest": patch_digest,
                    "parent_hypothesis_id": h_record.parent_hypothesis_id,
                    "inherited_files": inherited_files,
                    "candidate_attribution_scope": {
                        "schema_version": ("formal-candidate-attribution-scope.v1"),
                        "scope": (
                            "cumulative_branch_candidate_from_declared_champion_base"
                        ),
                        "proposal_target_files": proposal_target_files,
                        "materialized_proposal_files": materialized_proposal_files,
                        "inherited_files": inherited_files,
                        "activation_files": activation_files,
                    },
                    "replay_materialization": {
                        **replay_materialization,
                        "diff_ref": public_artifact_ref(
                            diff_path,
                            base_dir=self.campaign_dir,
                        ),
                    },
                }
            )
        index_payload = {
            "schema": self.schema,
            "candidate_id": candidate_id,
            "branch_id": branch.branch_id,
            "hypothesis_id": h_record.hypothesis_id,
            **proposal_attempt_fields,
            "stage": stage,
            "branch_code_status": metadata["branch_code_status"],
            "patch_digest": patch_digest,
            **(
                {
                    "proposal_patch_digest": proposal_patch_digest,
                    "formal_patch_digest": patch_digest,
                    "parent_hypothesis_id": h_record.parent_hypothesis_id,
                }
                if self.schema == self.cumulative_schema
                else {}
            ),
            "artifact_ref": artifact_ref,
            "diff_ref": public_artifact_ref(diff_path, base_dir=self.campaign_dir),
            "artifact_status": "recorded",
            "replay_identity_status": replay_identity["identity_status"],
            "missing_replay_identity_keys": [],
        }
        if metadata_path.exists():
            _validate_existing_artifact_metadata(metadata_path, expected=metadata)
            _restore_or_validate_artifact_text(diff_path, diff_text)
            if proposal_diff_text is not None:
                _restore_or_validate_artifact_text(
                    proposal_diff_path,
                    proposal_diff_text,
                )
            _append_index(
                self.artifact_dir / "index.jsonl",
                index_payload,
            )
            _attach_formal_candidate_summary(
                branch,
                artifact_ref=artifact_ref,
                stage=stage,
                raw_metrics_ref=raw_metrics_ref,
                selected_surface=selected_surface,
                replay_identity=replay_identity,
                patch_digest=patch_digest,
            )
            return artifact_ref

        dest.mkdir(parents=True, exist_ok=True)
        diff_path.write_text(diff_text, encoding="utf-8")
        if proposal_diff_text is not None:
            proposal_diff_path.write_text(proposal_diff_text, encoding="utf-8")
        metadata_path.write_text(
            json.dumps(_jsonable(metadata), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        _append_index(
            self.artifact_dir / "index.jsonl",
            index_payload,
        )
        _attach_formal_candidate_summary(
            branch,
            artifact_ref=artifact_ref,
            stage=stage,
            raw_metrics_ref=raw_metrics_ref,
            selected_surface=selected_surface,
            replay_identity=replay_identity,
            patch_digest=patch_digest,
        )
        return artifact_ref

    def _build_replay_materialization(
        self,
        *,
        branch: Branch,
        proposal_changes: tuple[PatchFileChange, ...],
        workspace: str | None,
        base_workspace: str | None,
    ) -> dict[str, Any]:
        """Build the complete candidate delta from the declared champion.

        Path selection is deliberately delegated to the problem-owned
        WorkspaceMaterializer callback. Comparing those two exact identity
        manifests captures prior verified branch work, newly created files,
        deletions, and reverts without consulting proposal history.
        """

        if self.identity_manifest_for is None:
            raise ValueError("v3 replay materialization requires an identity callback")
        if not workspace or not base_workspace:
            raise ValueError(
                "v3 replay materialization requires base/current workspaces"
            )

        base_manifest = _validated_identity_manifest(
            self.identity_manifest_for(base_workspace),
            workspace=base_workspace,
        )
        current_manifest = _validated_identity_manifest(
            self.identity_manifest_for(workspace),
            workspace=workspace,
        )
        branch_code_hash = str(getattr(branch, "current_code_hash", None) or "")
        current_code_hash = str(current_manifest["code_hash"])
        if not branch_code_hash or current_code_hash != branch_code_hash:
            raise ValueError(
                "formal replay identity does not match branch.current_code_hash: "
                f"computed={current_code_hash} branch={branch_code_hash or 'missing'}"
            )

        identity_changes = _identity_manifest_changes(
            base_manifest,
            current_manifest,
            workspace=workspace,
        )
        identity_paths = {
            normalize_relative_patch_path(change.file_path)
            for change in identity_changes
        }
        changes = _changes_with_activation_files(
            identity_changes,
            workspace=workspace,
            base_workspace=base_workspace,
        )
        activation_files = sorted(
            normalize_relative_patch_path(change.file_path)
            for change in changes
            if normalize_relative_patch_path(change.file_path) not in identity_paths
        )
        proposal_paths = {
            normalize_relative_patch_path(change.file_path)
            for change in proposal_changes
        }
        inherited_files = sorted(identity_paths - proposal_paths)
        files = []
        for change in changes:
            path = normalize_relative_patch_path(change.file_path)
            candidate_scope = (
                "runtime_activation"
                if path in activation_files
                else "current_proposal"
                if path in proposal_paths
                else "inherited_verified"
            )
            files.append(
                _change_payload(
                    change,
                    workspace=workspace,
                    base_workspace=base_workspace,
                    candidate_scope=candidate_scope,
                )
            )
        return {
            "schema_version": "scion.replay_materialization.v1",
            "representation": "cumulative_full_file_replacement",
            "base_identity_manifest": base_manifest,
            "candidate_identity_manifest": current_manifest,
            "patch_digest": _patch_digest(changes),
            "files": files,
            "activation_files": activation_files,
            "inherited_files": inherited_files,
            "_changes": changes,
        }

    def _record_omitted(
        self,
        *,
        branch: Branch,
        h_record: HypothesisRecord,
        stage: str,
        candidate_id: str,
        patch_digest: str,
        raw_metrics_ref: str | None,
        selected_surface: str,
        replay_identity: dict[str, Any] | None,
        missing_replay_identity_keys: list[str],
        omitted_reasons: list[str],
        decision: Decision,
        decision_reason_codes: Iterable[str] | None,
        proposal_attempt_fields: Mapping[str, str],
    ) -> None:
        primary_reason = omitted_reasons[0] if omitted_reasons else "unknown"
        payload = {
            "schema": self.schema,
            "created_at": datetime.now().isoformat(),
            "candidate_id": candidate_id,
            "campaign_artifact_kind": "formal_screening_candidate_patch",
            "artifact_status": "omitted",
            "artifact_omitted": True,
            "artifact_omitted_reason": primary_reason,
            "artifact_omitted_reasons": list(omitted_reasons),
            "non_replayable_reason": f"formal_candidate_artifact_omitted:{primary_reason}",
            "branch_id": branch.branch_id,
            "lineage_id": getattr(branch, "lineage_id", None) or branch.branch_id,
            "hypothesis_id": h_record.hypothesis_id,
            **proposal_attempt_fields,
            "stage": stage,
            "decision": decision.value,
            "decision_reason_codes": list(decision_reason_codes or ()),
            "branch_code_status": str(getattr(branch, "branch_code_status", "") or ""),
            "patch_digest": patch_digest,
            "raw_metrics_ref": raw_metrics_ref,
            "selected_surface": selected_surface,
            "replay_identity_status": (
                replay_identity.get("identity_status")
                if isinstance(replay_identity, dict)
                else "missing"
            ),
            "missing_replay_identity_keys": list(missing_replay_identity_keys),
            "artifact_ref": None,
            "diff_ref": None,
        }
        _append_index(self.artifact_dir / "index.jsonl", payload)
        _attach_formal_candidate_omission_summary(
            branch,
            stage=stage,
            raw_metrics_ref=raw_metrics_ref,
            selected_surface=selected_surface,
            replay_identity=replay_identity,
            patch_digest=patch_digest,
            omitted_reasons=omitted_reasons,
            missing_replay_identity_keys=missing_replay_identity_keys,
        )


def _stage_value(protocol_result: ProtocolResult) -> str:
    stage = getattr(protocol_result, "stage", "")
    return str(getattr(stage, "value", stage) or "")


def _proposal_attempt_join_fields(
    proposal_attempt_ref: Mapping[str, Any] | None,
    *,
    hypothesis_id: str,
) -> dict[str, str]:
    """Keep provider-call identity out of scientific candidate artifacts.

    A formal candidate is identified by its exact patch and problem-owned
    replay inputs.  Provider attempt, continuation, and transition identifiers
    describe transport bookkeeping, not the candidate's scientific identity.
    The arguments remain temporarily accepted while older callers migrate to
    the smaller proposal-call API.
    """

    del proposal_attempt_ref, hypothesis_id
    return {}


def _changes_with_activation_files(
    changes: Iterable[PatchFileChange],
    *,
    workspace: str | None,
    base_workspace: str | None,
) -> tuple[PatchFileChange, ...]:
    result = list(changes)
    existing = {
        normalize_relative_patch_path(change.file_path)
        for change in result
        if change.file_path
    }
    for activation_file in ("registry.yaml",):
        if activation_file in existing:
            continue
        extra = _activation_file_change(
            activation_file,
            workspace=workspace,
            base_workspace=base_workspace,
        )
        if extra is not None:
            result.append(extra)
    return tuple(result)


def _activation_file_change(
    file_rel: str,
    *,
    workspace: str | None,
    base_workspace: str | None,
) -> PatchFileChange | None:
    if not workspace:
        return None
    workspace_path = Path(workspace) / file_rel
    if not workspace_path.is_file():
        return None
    base_path = Path(base_workspace) / file_rel if base_workspace else None
    try:
        code = workspace_path.read_text(encoding="utf-8")
        base_code = (
            base_path.read_text(encoding="utf-8")
            if base_path is not None and base_path.is_file()
            else None
        )
    except OSError:
        return None
    if base_code == code:
        return None
    return PatchFileChange(
        file_path=file_rel,
        action="modify" if base_code is not None else "create",
        code_content=code,
        test_hint="runtime activation support file",
    )


def _activation_file_paths(
    proposal_changes: Iterable[PatchFileChange],
    artifact_changes: Iterable[PatchFileChange],
) -> list[str]:
    proposal_paths = {
        normalize_relative_patch_path(change.file_path)
        for change in proposal_changes
        if change.file_path
    }
    activation_paths = []
    for change in artifact_changes:
        path = normalize_relative_patch_path(change.file_path)
        if path and path not in proposal_paths:
            activation_paths.append(path)
    return sorted(dict.fromkeys(activation_paths))


def _artifact_omitted_reasons(
    *,
    patch: PatchProposal | None,
    contract_result: ContractResult,
    verification_result: VerificationResult,
    canary_result: CanaryResult,
    missing_replay_identity_keys: list[str],
) -> list[str]:
    reasons: list[str] = []
    if patch is None:
        reasons.append("missing_patch")
    if not contract_result.passed:
        reasons.append("contract_failed")
    if not verification_result.passed:
        reasons.append("verification_failed")
    if not canary_result.passed:
        reasons.append("canary_failed")
    if missing_replay_identity_keys:
        reasons.append("missing_replay_identity")
    return list(dict.fromkeys(reasons))


def _omitted_candidate_digest(
    *,
    branch: Branch,
    h_record: HypothesisRecord,
    stage: str,
    raw_metrics_ref: str | None,
    omitted_reasons: Iterable[str],
) -> str:
    raw = json.dumps(
        {
            "branch_id": branch.branch_id,
            "hypothesis_id": h_record.hypothesis_id,
            "stage": stage,
            "raw_metrics_ref": raw_metrics_ref,
            "artifact_omitted_reasons": list(omitted_reasons),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _attach_formal_candidate_summary(
    branch: Branch,
    *,
    artifact_ref: str | None,
    stage: str,
    raw_metrics_ref: str | None,
    selected_surface: str,
    replay_identity: dict[str, Any],
    patch_digest: str,
) -> None:
    summary = dict(getattr(branch, "branch_evidence_summary", {}) or {})
    if artifact_ref:
        summary["formal_candidate_patch_artifact_ref"] = artifact_ref
        summary["formal_replay_identity_ref"] = f"{artifact_ref}#/replay_identity"
    summary["formal_candidate_artifact_status"] = "recorded"
    summary["formal_candidate_artifact_omitted"] = False
    summary.pop("artifact_omitted_reason", None)
    summary.pop("artifact_omitted_reasons", None)
    summary.pop("non_replayable_reason", None)
    summary.pop("non_replayable", None)
    summary["protocol_stage"] = stage
    summary["stage"] = stage
    summary["raw_metrics_ref"] = raw_metrics_ref
    summary["selected_surface"] = selected_surface
    summary["patch_digest"] = patch_digest
    summary["patch_hash"] = patch_digest
    summary["replay_identity"] = replay_identity
    summary["formal_replay_identity"] = replay_identity
    code_hash = str(replay_identity.get("code_hash") or "").strip()
    if code_hash and code_hash != "unknown":
        summary["candidate_code_hash"] = code_hash
        summary["code_hash"] = code_hash
        summary["current_code_hash"] = code_hash
    summary["replay_metadata"] = {
        "schema_version": "formal_candidate_replay_metadata.v1",
        "raw_metrics_ref": raw_metrics_ref,
        "selected_surface": selected_surface,
        "replay_identity_status": replay_identity["identity_status"],
        "replay_identity_ref": (
            f"{artifact_ref}#/replay_identity" if artifact_ref else ""
        ),
        "decision_features_excluded": True,
    }
    summary["formal_candidate_artifact_report"] = {
        "schema_version": "formal_candidate_artifact_report.v1",
        "artifact_status": "recorded",
        "artifact_ref": artifact_ref,
        "replay_identity_status": replay_identity["identity_status"],
        "missing_replay_identity_keys": [],
    }
    branch.branch_evidence_summary = summary


def _attach_formal_candidate_omission_summary(
    branch: Branch,
    *,
    stage: str,
    raw_metrics_ref: str | None,
    selected_surface: str,
    replay_identity: dict[str, Any] | None,
    patch_digest: str,
    omitted_reasons: list[str],
    missing_replay_identity_keys: list[str],
) -> None:
    primary_reason = omitted_reasons[0] if omitted_reasons else "unknown"
    summary = dict(getattr(branch, "branch_evidence_summary", {}) or {})
    summary["formal_candidate_artifact_status"] = "omitted"
    summary["formal_candidate_artifact_omitted"] = True
    summary["artifact_omitted_reason"] = primary_reason
    summary["artifact_omitted_reasons"] = list(omitted_reasons)
    summary["non_replayable"] = True
    summary["non_replayable_reason"] = (
        f"formal_candidate_artifact_omitted:{primary_reason}"
    )
    summary["protocol_stage"] = stage
    summary["stage"] = stage
    summary["raw_metrics_ref"] = raw_metrics_ref
    summary["selected_surface"] = selected_surface
    if patch_digest:
        summary["patch_digest"] = patch_digest
        summary["patch_hash"] = patch_digest
    if replay_identity is not None:
        summary["replay_identity"] = replay_identity
        summary["formal_replay_identity"] = replay_identity
        code_hash = str(replay_identity.get("code_hash") or "").strip()
        if code_hash and code_hash != "unknown":
            summary["candidate_code_hash"] = code_hash
            summary["code_hash"] = code_hash
            summary["current_code_hash"] = code_hash
    summary["formal_candidate_artifact_report"] = {
        "schema_version": "formal_candidate_artifact_report.v1",
        "artifact_status": "omitted",
        "artifact_omitted_reason": primary_reason,
        "artifact_omitted_reasons": list(omitted_reasons),
        "non_replayable_reason": summary["non_replayable_reason"],
        "replay_identity_status": (
            replay_identity.get("identity_status")
            if isinstance(replay_identity, dict)
            else "missing"
        ),
        "missing_replay_identity_keys": list(missing_replay_identity_keys),
    }
    branch.branch_evidence_summary = summary


def _candidate_id(
    *,
    branch_id: str,
    hypothesis_id: str,
    stage: str,
    raw_metrics_ref: str | None,
    patch_digest: str,
) -> str:
    raw = json.dumps(
        {
            "branch_id": branch_id,
            "hypothesis_id": hypothesis_id,
            "stage": stage,
            "raw_metrics_ref": raw_metrics_ref,
            "patch_digest": patch_digest,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _patch_digest(changes: Iterable[PatchFileChange]) -> str:
    return stable_patch_digest(changes)


def _validated_identity_manifest(
    manifest: Mapping[str, Any],
    *,
    workspace: str,
) -> dict[str, Any]:
    if manifest.get("schema_version") != "scion.editable_identity_manifest.v1":
        raise ValueError("unsupported editable identity manifest")
    raw_files = manifest.get("files")
    code_hash = str(manifest.get("code_hash") or "")
    if not isinstance(raw_files, list) or not _is_sha256(code_hash):
        raise ValueError("invalid editable identity manifest")

    entries: list[dict[str, str]] = []
    seen: set[str] = set()
    workspace_path = Path(workspace).resolve()
    digest = hashlib.sha256()
    for raw in raw_files:
        if not isinstance(raw, Mapping):
            raise ValueError("invalid editable identity manifest file entry")
        file_path = normalize_relative_patch_path(str(raw.get("file_path") or ""))
        expected_sha = str(raw.get("sha256") or "")
        if file_path in seen or not _is_sha256(expected_sha):
            raise ValueError(f"invalid editable identity file entry: {file_path}")
        seen.add(file_path)
        content = _workspace_file_bytes(workspace_path, file_path)
        actual_sha = hashlib.sha256(content).hexdigest()
        if actual_sha != expected_sha:
            raise ValueError(f"editable identity file digest mismatch: {file_path}")
        entries.append({"file_path": file_path, "sha256": expected_sha})

    entries.sort(key=lambda item: item["file_path"])
    for entry in entries:
        content = _workspace_file_bytes(workspace_path, entry["file_path"])
        digest.update(entry["file_path"].encode())
        digest.update(content)
    if digest.hexdigest() != code_hash:
        raise ValueError("editable identity manifest code_hash mismatch")
    return {
        "schema_version": "scion.editable_identity_manifest.v1",
        "files": entries,
        "code_hash": code_hash,
    }


def _identity_manifest_changes(
    base_manifest: Mapping[str, Any],
    current_manifest: Mapping[str, Any],
    *,
    workspace: str,
) -> tuple[PatchFileChange, ...]:
    base_by_path = {
        str(item["file_path"]): str(item["sha256"]) for item in base_manifest["files"]
    }
    current_by_path = {
        str(item["file_path"]): str(item["sha256"])
        for item in current_manifest["files"]
    }
    workspace_path = Path(workspace).resolve()
    changes: list[PatchFileChange] = []
    for file_path in sorted(base_by_path.keys() | current_by_path.keys()):
        base_sha = base_by_path.get(file_path)
        current_sha = current_by_path.get(file_path)
        if base_sha == current_sha:
            continue
        if current_sha is None:
            action = "delete"
            code_content = ""
        else:
            action = "create" if base_sha is None else "modify"
            raw_content = _workspace_file_bytes(workspace_path, file_path)
            try:
                code_content = raw_content.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError(
                    f"editable replay file is not UTF-8 text: {file_path}"
                ) from exc
        changes.append(
            PatchFileChange(
                file_path=file_path,
                action=action,
                code_content=code_content,
                test_hint="cumulative formal replay materialization",
            )
        )
    return tuple(changes)


def _workspace_file_bytes(workspace: Path, file_path: str) -> bytes:
    target = (workspace / normalize_relative_patch_path(file_path)).resolve()
    try:
        target.relative_to(workspace)
    except ValueError as exc:
        raise ValueError(f"identity file escapes workspace: {file_path}") from exc
    if not target.is_file():
        raise ValueError(f"editable identity file is missing: {file_path}")
    return target.read_bytes()


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _change_payload(
    change: PatchFileChange,
    *,
    workspace: str | None,
    base_workspace: str | None,
    candidate_scope: str | None = None,
) -> dict[str, Any]:
    code = change.code_content or ""
    base_hash = _workspace_file_sha256(base_workspace, change.file_path)
    payload = {
        "file_path": normalize_relative_patch_path(change.file_path),
        "action": change.action,
        "code_sha256": hashlib.sha256(code.encode("utf-8")).hexdigest(),
        "code_content": code,
    }
    if candidate_scope is not None:
        payload["candidate_attribution"] = {
            "schema_version": "formal-file-candidate-attribution.v1",
            "scope": candidate_scope,
        }
    current_hash = _workspace_file_sha256(workspace, change.file_path)
    if current_hash:
        payload["workspace_current_sha256"] = current_hash
    if base_hash:
        payload["base_sha256"] = base_hash
    return payload


def render_full_file_replacement_diff(
    files: Iterable[Mapping[str, Any]],
    *,
    base_workspace: str | Path,
) -> str:
    """Render the canonical diff represented by full-file artifact entries."""

    changes: list[PatchFileChange] = []
    for entry in files:
        if not isinstance(entry, Mapping):
            raise ValueError("formal artifact file entry must be an object")
        file_path = normalize_relative_patch_path(str(entry.get("file_path") or ""))
        action = str(entry.get("action") or "").strip()
        if action not in {"create", "modify", "delete"}:
            raise ValueError(f"invalid formal artifact action: {file_path}")
        if "code_content" not in entry:
            raise ValueError(f"formal artifact content missing: {file_path}")
        changes.append(
            PatchFileChange(
                file_path=file_path,
                action=action,
                code_content=str(entry.get("code_content") or ""),
            )
        )
    return _render_candidate_diff(
        changes,
        base_workspace=str(base_workspace),
    )


def _validate_existing_artifact_metadata(
    metadata_path: Path,
    *,
    expected: Mapping[str, Any],
) -> None:
    try:
        existing = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("existing formal candidate metadata is unreadable") from exc
    if not isinstance(existing, Mapping):
        raise ValueError("existing formal candidate metadata is invalid")
    comparable_existing = _without_legacy_source_attribution(existing)
    comparable_expected = _without_legacy_source_attribution(expected)
    comparable_expected["created_at"] = existing.get("created_at")
    if comparable_existing != comparable_expected:
        raise ValueError("existing formal candidate metadata conflicts with record")


def _without_legacy_source_attribution(
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    """Ignore only the retired per-file source-ledger field when rereading."""

    comparable = _jsonable(metadata)
    for section_name in ("patch", "replay_materialization"):
        section = comparable.get(section_name)
        if not isinstance(section, dict):
            continue
        files = section.get("files")
        if not isinstance(files, list):
            continue
        for file_entry in files:
            if isinstance(file_entry, dict):
                file_entry.pop("source_attribution", None)
    return comparable


def _restore_or_validate_artifact_text(path: Path, expected: str) -> None:
    if not path.exists():
        path.write_text(expected, encoding="utf-8")
        return
    try:
        actual = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(
            f"formal candidate artifact is unreadable: {path.name}"
        ) from exc
    if actual != expected:
        raise ValueError(f"formal candidate artifact content mismatch: {path.name}")


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
        new_lines = (
            []
            if change.action == "delete"
            else _split_keepends(change.code_content or "")
        )
        fromfile = "/dev/null" if change.action == "create" else f"a/{file_rel}"
        tofile = "/dev/null" if change.action == "delete" else f"b/{file_rel}"
        chunks.extend(
            _render_unified_diff(
                old_lines or [],
                new_lines,
                fromfile=fromfile,
                tofile=tofile,
            )
        )
    return "".join(chunks)


def _render_unified_diff(
    old_lines: list[str],
    new_lines: list[str],
    *,
    fromfile: str,
    tofile: str,
) -> list[str]:
    """Render a git-parseable diff while preserving missing final newlines."""

    rendered: list[str] = []
    for line in difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=fromfile,
        tofile=tofile,
        lineterm="\n",
    ):
        if line.endswith("\n"):
            rendered.append(line)
            continue
        rendered.append(f"{line}\n\\ No newline at end of file\n")
    return rendered


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
    candidate_id = str(payload.get("candidate_id") or "")
    artifact_status = str(payload.get("artifact_status") or "")
    omitted_reason = str(payload.get("artifact_omitted_reason") or "")
    artifact_ref = str(payload.get("artifact_ref") or "")
    if candidate_id and index_path.exists():
        try:
            for line in index_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                existing = json.loads(line)
                if not isinstance(existing, dict):
                    continue
                if (
                    str(existing.get("candidate_id") or "") == candidate_id
                    and str(existing.get("artifact_status") or "") == artifact_status
                    and str(existing.get("artifact_omitted_reason") or "")
                    == omitted_reason
                    and str(existing.get("artifact_ref") or "") == artifact_ref
                ):
                    return
        except (OSError, json.JSONDecodeError):
            pass
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
