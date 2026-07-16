"""Problem-neutral postrun acceptance check ports."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import tempfile
from typing import Any, Mapping

from scion.core.execution_outcome import ExecutionOutcome
from scion.core.fixed_candidate_replay import (
    materialize_candidate_workspace,
    resolve_candidate_base_workspace,
)
from scion.core.formal_candidate_artifacts import (
    render_full_file_replacement_diff,
)
from scion.postrun.handoff.resume_snapshot import resume_snapshot_artifact_path


FORMAL_CANDIDATE_PATCH_SCHEMA_V3 = "scion.formal_candidate_patch_artifact.v3"

ANALYSIS_BRIEF_SCHEMA = "scion.postrun_analysis_brief.v1"
PHASE4_EVIDENCE_COVERAGE_SCHEMA = "scion.postrun_phase4_evidence_coverage.v1"
REBUILD_SCHEMA = "scion.postrun_acceptance_rebuild.v1"
PHASE4_COVERAGE_IDENTITY_FIELDS = (
    "evidence_scope",
    "prepared_only",
    "pre_campaign_completion_preflight_failed",
    "invalid_infra_only",
    "current_run_evidence",
)


@dataclass(frozen=True)
class PostrunAcceptanceCheck:
    """Legacy-compatible postrun acceptance check payload."""

    name: str
    status: str
    detail: Any = ""
    required: bool = True

    def to_payload(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "required": bool(self.required),
            "detail": self.detail,
        }


@dataclass(frozen=True)
class PostrunAcceptanceCheckBundle:
    """Ordered collection of legacy-compatible acceptance checks."""

    checks: tuple[PostrunAcceptanceCheck, ...]

    def to_payloads(self) -> dict[str, dict[str, Any]]:
        return {check.name: check.to_payload() for check in self.checks}


class PostrunArtifactAcceptancePort:
    """Build generic artifact identity and schema checks."""

    def read_json_object(self, path: Path) -> dict[str, Any]:
        return _read_json_object(path)

    def read_rebuild_manifest(self, report_dir: Path) -> dict[str, Any]:
        return _read_json_object(report_dir / "rebuild" / "rebuild_manifest.v1.json")

    def analysis_brief_path_from_manifest(
        self,
        rebuild_manifest: Mapping[str, Any],
        report_dir: Path,
    ) -> Path | None:
        return self.artifact_json_path_from_manifest(
            rebuild_manifest,
            report_dir,
            "analysis_brief",
        )

    def artifact_json_path_from_manifest(
        self,
        rebuild_manifest: Mapping[str, Any],
        report_dir: Path,
        family_name: str,
    ) -> Path | None:
        families = _mapping_or_empty(rebuild_manifest.get("families"))
        family = _mapping_or_empty(families.get(family_name))
        outputs = family.get("outputs")
        if not isinstance(outputs, list):
            return None
        for item in outputs:
            output = str(item)
            path = _manifest_output_path(output, report_dir)
            if (
                path.suffix == ".json"
                and path.is_file()
                and _manifest_output_in_family(path, report_dir, family_name)
            ):
                return path
        return None

    def summarize(
        self,
        *,
        root: Path,
        report_dir: Path,
        rebuild_manifest: Mapping[str, Any],
        inventory_source: str,
        inventory_path: Path | None,
        analysis_brief_path: Path | None,
        analysis_brief: Mapping[str, Any],
        postrun_counts: Mapping[str, Any],
    ) -> PostrunAcceptanceCheckBundle:
        manifest_identity_status, manifest_identity_detail = (
            _rebuild_manifest_identity_boundary(root, report_dir, rebuild_manifest)
        )
        outputs_status, outputs_detail = _rebuild_manifest_declared_outputs_present(
            rebuild_manifest,
            report_dir,
        )
        brief_boundary_status, brief_boundary_detail = _analysis_brief_boundary(
            analysis_brief
        )
        candidate_diff_status, candidate_diff_detail = (
            _formal_candidate_diff_integrity(root)
        )
        return PostrunAcceptanceCheckBundle(
            checks=(
                PostrunAcceptanceCheck(
                    name="inventory_loaded",
                    status="ok",
                    detail={
                        "run_root": str(root),
                        "source": inventory_source,
                        "stored_inventory_path": (
                            str(inventory_path) if inventory_path else ""
                        ),
                    },
                ),
                PostrunAcceptanceCheck(
                    name="postrun_acceptance_present",
                    status="ok" if report_dir.exists() else "failed",
                    detail=str(report_dir),
                ),
                PostrunAcceptanceCheck(
                    name="rebuild_manifest_present",
                    status="ok" if rebuild_manifest else "failed",
                    detail=_artifact_paths(report_dir / "rebuild"),
                ),
                PostrunAcceptanceCheck(
                    name="rebuild_manifest_schema",
                    status=(
                        "ok"
                        if rebuild_manifest.get("schema_version") == REBUILD_SCHEMA
                        else "failed"
                    ),
                    detail=rebuild_manifest.get("schema_version"),
                ),
                PostrunAcceptanceCheck(
                    name="rebuild_manifest_run_identity",
                    status=(
                        "ok"
                        if _payload_path_matches(
                            rebuild_manifest.get("run_root"),
                            root,
                        )
                        else "failed"
                    ),
                    detail={
                        "expected_run_root": str(root),
                        "manifest_run_root": rebuild_manifest.get("run_root"),
                    },
                ),
                PostrunAcceptanceCheck(
                    name="rebuild_manifest_identity_boundary",
                    status=manifest_identity_status,
                    detail=manifest_identity_detail,
                ),
                PostrunAcceptanceCheck(
                    name="rebuild_manifest_complete",
                    status=(
                        "ok"
                        if rebuild_manifest.get("complete") is True
                        else "failed"
                    ),
                    detail={
                        "complete": rebuild_manifest.get("complete"),
                        "families": rebuild_manifest.get("families"),
                    },
                ),
                PostrunAcceptanceCheck(
                    name="rebuild_manifest_declared_outputs_present",
                    status=outputs_status,
                    detail=outputs_detail,
                ),
                PostrunAcceptanceCheck(
                    name="analysis_brief_present",
                    status="ok" if analysis_brief else "failed",
                    detail={
                        "selected_from_rebuild_manifest": (
                            str(analysis_brief_path)
                            if analysis_brief_path
                            else ""
                        ),
                        "available_artifacts": _artifact_paths(
                            report_dir / "analysis_brief"
                        ),
                    },
                ),
                PostrunAcceptanceCheck(
                    name="analysis_brief_schema",
                    status=(
                        "ok"
                        if analysis_brief.get("schema_version")
                        == ANALYSIS_BRIEF_SCHEMA
                        else "failed"
                    ),
                    detail=analysis_brief.get("schema_version"),
                ),
                PostrunAcceptanceCheck(
                    name="analysis_brief_run_identity",
                    status=(
                        "ok"
                        if _payload_path_matches(
                            analysis_brief.get("run_root"),
                            root,
                        )
                        else "failed"
                    ),
                    detail={
                        "expected_run_root": str(root),
                        "analysis_brief_run_root": analysis_brief.get("run_root"),
                        "analysis_brief_path": (
                            str(analysis_brief_path)
                            if analysis_brief_path
                            else ""
                        ),
                    },
                ),
                PostrunAcceptanceCheck(
                    name="analysis_brief_boundary",
                    status=brief_boundary_status,
                    detail=brief_boundary_detail,
                ),
                PostrunAcceptanceCheck(
                    name="inventory_artifact_present",
                    status=(
                        "ok"
                        if _int_or_zero(postrun_counts.get("inventory")) > 0
                        else "failed"
                    ),
                    detail=dict(postrun_counts),
                ),
                PostrunAcceptanceCheck(
                    name="formal_candidate_diff_integrity",
                    status=candidate_diff_status,
                    detail=candidate_diff_detail,
                ),
            )
        )


def _formal_candidate_diff_integrity(root: Path) -> tuple[str, dict[str, Any]]:
    """Validate recorded formal-candidate diffs without mutating a workspace."""

    campaign_dir = root / "campaign"
    index_path = campaign_dir / "artifacts" / "formal_candidates" / "index.jsonl"
    disk_metadata_paths = {
        path.resolve()
        for path in index_path.parent.glob("**/candidate.patch.json")
        if path.is_file()
    }
    prepared_manifest = _read_json_object(root / "prepared_run_manifest.v1.json")
    run_status = _read_json_object(root / "run_status.json")
    snapshot_index_path = resume_snapshot_artifact_path(
        root=root,
        manifest=prepared_manifest,
        run_status=run_status,
        original_ref="artifacts/formal_candidates/index.jsonl",
    )
    snapshot_index_failures = (
        _resume_candidate_index_snapshot_integrity_failures(
            root=root,
            manifest=prepared_manifest,
            run_status=run_status,
            snapshot_index_path=snapshot_index_path,
        )
        if snapshot_index_path is not None
        else []
    )
    if snapshot_index_path is not None and not snapshot_index_failures:
        inherited_metadata_paths, inherited_index_failures = (
            _formal_candidate_index_metadata_paths(
                campaign_dir=campaign_dir,
                index_path=snapshot_index_path,
                reason_prefix="resume_candidate_index",
            )
        )
    else:
        inherited_metadata_paths = set()
        inherited_index_failures = snapshot_index_failures
    if not index_path.is_file():
        orphan_artifacts = sorted(
            str(path) for path in disk_metadata_paths - inherited_metadata_paths
        )
        failures = [
            *inherited_index_failures,
            *(
                [
                    {
                        "reason": "candidate_metadata_not_indexed",
                        "orphan_artifacts": orphan_artifacts,
                    }
                ]
                if orphan_artifacts
                else []
            ),
        ]
        return (
            "failed" if failures else "ok",
            {
                "reason": (
                    (
                        "formal_candidate_index_absent_with_unindexed_artifacts"
                        if inherited_metadata_paths
                        else "formal_candidate_index_absent_with_orphan_artifacts"
                    )
                    if orphan_artifacts
                    else (
                        "formal_candidate_index_absent_with_inherited_artifacts"
                        if inherited_metadata_paths
                        else "formal_candidate_index_absent"
                    )
                ),
                "index_path": str(index_path),
                "inherited_index_path": (
                    str(snapshot_index_path) if snapshot_index_path else ""
                ),
                "inherited_candidates": len(inherited_metadata_paths),
                "checked_candidates": 0,
                "orphan_artifacts": orphan_artifacts,
                "failures": failures,
            },
        )

    failures: list[dict[str, Any]] = list(inherited_index_failures)
    validations: list[dict[str, Any]] = []
    legacy_unbound_rows: list[dict[str, Any]] = []
    indexed_metadata_paths: set[Path] = set(inherited_metadata_paths)
    try:
        lines = index_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return "failed", {
            "reason": "formal_candidate_index_unreadable",
            "index_path": str(index_path),
            "error": str(exc),
        }

    for line_number, raw_line in enumerate(lines, start=1):
        if not raw_line.strip():
            continue
        try:
            row = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            failures.append(
                {
                    "line": line_number,
                    "reason": "invalid_index_json",
                    "error": str(exc),
                }
            )
            continue
        if not isinstance(row, Mapping):
            failures.append(
                {"line": line_number, "reason": "index_row_not_object"}
            )
            continue
        candidate_id = str(row.get("candidate_id") or "")
        if not row.get("artifact_ref") and "artifact_status" not in row:
            legacy_unbound_rows.append(
                {"line": line_number, "candidate_id": candidate_id}
            )
            continue
        metadata_path = _campaign_artifact_path(
            campaign_dir,
            row.get("artifact_ref"),
        )
        if metadata_path is not None:
            indexed_metadata_paths.add(metadata_path)
        if metadata_path is None or not metadata_path.is_file():
            failures.append(
                {
                    "candidate_id": candidate_id,
                    "reason": "candidate_metadata_missing",
                    "artifact_ref": row.get("artifact_ref"),
                }
            )
            continue
        metadata = _read_json_object(metadata_path)
        if not metadata:
            failures.append(
                {
                    "candidate_id": candidate_id,
                    "reason": "candidate_metadata_invalid",
                    "artifact_ref": row.get("artifact_ref"),
                }
            )
            continue
        patch = _mapping_or_empty(metadata.get("patch"))
        artifact_schema = str(metadata.get("schema") or "")
        replay_materialization = _mapping_or_empty(
            metadata.get("replay_materialization")
        )
        diff_ref = (
            replay_materialization.get("diff_ref")
            if artifact_schema == FORMAL_CANDIDATE_PATCH_SCHEMA_V3
            else patch.get("diff_ref")
        )
        diff_path = _campaign_artifact_path(campaign_dir, diff_ref)
        if diff_path is None or not diff_path.is_file():
            failures.append(
                {
                    "candidate_id": candidate_id,
                    "reason": "candidate_diff_missing",
                    "diff_ref": diff_ref,
                    "artifact_schema": artifact_schema,
                }
            )
            continue

        try:
            base_workspace = resolve_candidate_base_workspace(
                metadata,
                source_campaign_dir=campaign_dir,
            )
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            base_workspace = None
            failures.append(
                {
                    "candidate_id": candidate_id,
                    "reason": "candidate_diff_base_workspace_invalid",
                    "error": str(exc),
                }
            )
        v3_diff_detail: dict[str, Any] = {}
        if artifact_schema == FORMAL_CANDIDATE_PATCH_SCHEMA_V3:
            v3_diff_failures, v3_diff_detail = _v3_diff_integrity(
                campaign_dir=campaign_dir,
                candidate_id=candidate_id,
                metadata=metadata,
                base_workspace=base_workspace,
                cumulative_diff_path=diff_path,
            )
            failures.extend(v3_diff_failures)
        empty_v3_closure = (
            artifact_schema == FORMAL_CANDIDATE_PATCH_SCHEMA_V3
            and replay_materialization.get("files") == []
        )
        if empty_v3_closure:
            validation_mode = "empty_cumulative_closure"
            result_returncode = 0
            result_stderr = ""
            try:
                if diff_path.read_text(encoding="utf-8"):
                    result_returncode = 1
                    result_stderr = "empty replay closure has non-empty diff"
            except OSError as exc:
                result_returncode = 1
                result_stderr = str(exc)
        else:
            if base_workspace is not None and base_workspace.is_dir():
                command = ["git", "apply", "--check", str(diff_path)]
                cwd = base_workspace
                validation_mode = "apply_check"
            else:
                command = ["git", "apply", "--numstat", str(diff_path)]
                cwd = campaign_dir
                validation_mode = "parse_only_base_unavailable"
            try:
                result = subprocess.run(
                    command,
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=10,
                )
            except subprocess.TimeoutExpired as exc:
                failures.append(
                    {
                        "candidate_id": candidate_id,
                        "reason": "git_apply_timeout",
                        "validation_mode": validation_mode,
                        "timeout_seconds": exc.timeout,
                    }
                )
                continue
            except OSError as exc:
                failures.append(
                    {
                        "candidate_id": candidate_id,
                        "reason": "git_apply_unavailable",
                        "validation_mode": validation_mode,
                        "error": str(exc),
                    }
                )
                continue
            result_returncode = result.returncode
            result_stderr = result.stderr.strip()
        validation = {
            "candidate_id": candidate_id,
            "diff_ref": diff_ref,
            "artifact_schema": artifact_schema,
            "validation_mode": validation_mode,
            "returncode": result_returncode,
            **v3_diff_detail,
        }
        if result_returncode != 0:
            failures.append(
                {
                    **validation,
                    "reason": "candidate_diff_not_replayable",
                    "stderr": result_stderr,
                }
            )
        if artifact_schema == FORMAL_CANDIDATE_PATCH_SCHEMA_V3:
            try:
                with tempfile.TemporaryDirectory(
                    prefix="scion-postrun-formal-replay-"
                ) as temporary_dir:
                    materialize_candidate_workspace(
                        candidate={"candidate_id": candidate_id},
                        candidate_patch=metadata,
                        source_campaign_dir=campaign_dir,
                        output_dir=temporary_dir,
                        arm="postrun_acceptance",
                    )
            except (
                AssertionError,
                KeyError,
                OSError,
                RuntimeError,
                TypeError,
                ValueError,
            ) as exc:
                validation["materialization_status"] = "failed"
                failures.append(
                    {
                        "candidate_id": candidate_id,
                        "reason": "candidate_replay_materialization_invalid",
                        "artifact_schema": artifact_schema,
                        "error": str(exc),
                    }
                )
            else:
                validation["materialization_status"] = "ok"
                validation["materialization_model"] = (
                    "champion_base_plus_cumulative_replay_materialization"
                )
        validations.append(validation)

    orphan_artifacts = sorted(
        str(path) for path in disk_metadata_paths - indexed_metadata_paths
    )
    if orphan_artifacts:
        failures.append(
            {
                "reason": "candidate_metadata_not_indexed",
                "orphan_artifacts": orphan_artifacts,
            }
        )

    status = "ok" if validations and not failures else "failed"
    if not validations and not failures:
        status = "ok"
    return status, {
        "index_path": str(index_path),
        "inherited_index_path": (
            str(snapshot_index_path) if snapshot_index_path else ""
        ),
        "inherited_candidates": len(inherited_metadata_paths),
        "checked_candidates": len(validations),
        "legacy_unbound_rows": legacy_unbound_rows,
        "orphan_artifacts": orphan_artifacts,
        "validations": validations,
        "failures": failures,
    }


def _formal_candidate_index_metadata_paths(
    *,
    campaign_dir: Path,
    index_path: Path,
    reason_prefix: str,
) -> tuple[set[Path], list[dict[str, Any]]]:
    """Resolve metadata refs from a lineage index without counting it as current."""

    paths: set[Path] = set()
    failures: list[dict[str, Any]] = []
    try:
        lines = index_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return paths, [
            {
                "reason": f"{reason_prefix}_unreadable",
                "index_path": str(index_path),
                "error": str(exc),
            }
        ]
    for line_number, raw_line in enumerate(lines, start=1):
        if not raw_line.strip():
            continue
        try:
            row = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            failures.append(
                {
                    "reason": f"{reason_prefix}_invalid_json",
                    "index_path": str(index_path),
                    "line": line_number,
                    "error": str(exc),
                }
            )
            continue
        if not isinstance(row, Mapping):
            failures.append(
                {
                    "reason": f"{reason_prefix}_row_not_object",
                    "index_path": str(index_path),
                    "line": line_number,
                }
            )
            continue
        artifact_ref = row.get("artifact_ref")
        artifact_status = str(row.get("artifact_status") or "").strip()
        if not artifact_ref:
            if not artifact_status or artifact_status == "omitted":
                continue
            failures.append(
                {
                    "reason": f"{reason_prefix}_artifact_ref_missing",
                    "index_path": str(index_path),
                    "line": line_number,
                    "artifact_status": artifact_status,
                }
            )
            continue
        metadata_path = _campaign_artifact_path(campaign_dir, artifact_ref)
        if metadata_path is None:
            failures.append(
                {
                    "reason": f"{reason_prefix}_artifact_ref_invalid",
                    "index_path": str(index_path),
                    "line": line_number,
                    "artifact_ref": artifact_ref,
                }
            )
            continue
        if not metadata_path.is_file():
            failures.append(
                {
                    "reason": f"{reason_prefix}_metadata_missing",
                    "index_path": str(index_path),
                    "line": line_number,
                    "artifact_ref": artifact_ref,
                }
            )
            continue
        paths.add(metadata_path)
    return paths, failures


def _resume_candidate_index_snapshot_integrity_failures(
    *,
    root: Path,
    manifest: Mapping[str, Any],
    run_status: Mapping[str, Any],
    snapshot_index_path: Path,
) -> list[dict[str, Any]]:
    """Bind inherited refs to the immutable index quarantined by the launcher."""

    manifest_ref = str(manifest.get("resume_snapshot_ref") or "").strip()
    if not manifest_ref:
        manifest_ref = str(run_status.get("resume_snapshot_ref") or "").strip()
    snapshot_manifest_path = (root / manifest_ref).resolve()
    try:
        snapshot_manifest_path.relative_to(root.resolve())
    except ValueError:
        return [
            {
                "reason": "resume_candidate_index_snapshot_integrity_mismatch",
                "failures": ["resume_snapshot_manifest_outside_run_root"],
            }
        ]
    snapshot_manifest = _read_json_object(snapshot_manifest_path)
    item = next(
        (
            dict(value)
            for value in snapshot_manifest.get("terminal_artifacts") or []
            if isinstance(value, Mapping)
            and value.get("original_ref")
            == "artifacts/formal_candidates/index.jsonl"
        ),
        {},
    )
    expected_ref = (
        "resume_snapshot/campaign/artifacts/formal_candidates/index.jsonl"
    )
    actual_ref = snapshot_index_path.relative_to(root.resolve()).as_posix()
    failures: list[str] = []
    if actual_ref != expected_ref or str(item.get("snapshot_ref") or "") != expected_ref:
        failures.append("snapshot_ref_mismatch")
    try:
        expected_size = int(item.get("size_bytes"))
    except (TypeError, ValueError):
        expected_size = -1
    try:
        actual_bytes = snapshot_index_path.read_bytes()
    except OSError:
        actual_bytes = b""
        failures.append("snapshot_index_unreadable")
    else:
        if expected_size != len(actual_bytes):
            failures.append("snapshot_size_mismatch")
        expected_sha256 = str(item.get("sha256") or "")
        if expected_sha256 != sha256(actual_bytes).hexdigest():
            failures.append("snapshot_sha256_mismatch")
    if not failures:
        return []
    return [
        {
            "reason": "resume_candidate_index_snapshot_integrity_mismatch",
            "snapshot_manifest_path": str(snapshot_manifest_path),
            "snapshot_index_path": str(snapshot_index_path),
            "failures": failures,
        }
    ]


def _v3_diff_integrity(
    *,
    campaign_dir: Path,
    candidate_id: str,
    metadata: Mapping[str, Any],
    base_workspace: Path | None,
    cumulative_diff_path: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Bind both stored v3 diffs to their validated full-file entries."""

    patch = _mapping_or_empty(metadata.get("patch"))
    materialization = _mapping_or_empty(metadata.get("replay_materialization"))
    proposal_diff_ref = patch.get("diff_ref")
    proposal_diff_path = _campaign_artifact_path(
        campaign_dir,
        proposal_diff_ref,
    )
    detail = {
        "proposal_diff_ref": proposal_diff_ref,
        "proposal_diff_status": "failed",
        "cumulative_diff_status": "failed",
    }
    failures: list[dict[str, Any]] = []
    if base_workspace is None or not base_workspace.is_dir():
        failures.append(
            {
                "candidate_id": candidate_id,
                "reason": "candidate_diff_base_workspace_missing",
            }
        )
        return failures, detail
    if proposal_diff_path is None or not proposal_diff_path.is_file():
        failures.append(
            {
                "candidate_id": candidate_id,
                "reason": "proposal_diff_missing",
                "diff_ref": proposal_diff_ref,
            }
        )
    else:
        proposal_files = patch.get("files")
        try:
            expected_proposal = render_full_file_replacement_diff(
                proposal_files if isinstance(proposal_files, list) else (),
                base_workspace=base_workspace,
            )
            actual_proposal = proposal_diff_path.read_text(encoding="utf-8")
        except (OSError, TypeError, ValueError) as exc:
            failures.append(
                {
                    "candidate_id": candidate_id,
                    "reason": "proposal_diff_validation_failed",
                    "error": str(exc),
                }
            )
        else:
            if actual_proposal != expected_proposal:
                failures.append(
                    {
                        "candidate_id": candidate_id,
                        "reason": "proposal_diff_content_mismatch",
                        "diff_ref": proposal_diff_ref,
                    }
                )
            else:
                detail["proposal_diff_status"] = "ok"

    materialization_files = materialization.get("files")
    try:
        expected_cumulative = render_full_file_replacement_diff(
            materialization_files
            if isinstance(materialization_files, list)
            else (),
            base_workspace=base_workspace,
        )
        actual_cumulative = cumulative_diff_path.read_text(encoding="utf-8")
    except (OSError, TypeError, ValueError) as exc:
        failures.append(
            {
                "candidate_id": candidate_id,
                "reason": "candidate_diff_validation_failed",
                "error": str(exc),
            }
        )
    else:
        if actual_cumulative != expected_cumulative:
            failures.append(
                {
                    "candidate_id": candidate_id,
                    "reason": "candidate_diff_content_mismatch",
                    "diff_ref": materialization.get("diff_ref"),
                }
            )
        else:
            detail["cumulative_diff_status"] = "ok"
    return failures, detail


def _campaign_artifact_path(campaign_dir: Path, ref: Any) -> Path | None:
    text = str(ref or "").strip()
    if not text:
        return None
    candidate = Path(text)
    if not candidate.is_absolute():
        candidate = campaign_dir / candidate
    try:
        resolved = candidate.resolve()
        resolved.relative_to(campaign_dir.resolve())
    except (OSError, ValueError):
        return None
    return resolved


class PostrunEvidenceConsistencyAcceptancePort:
    """Build generic evidence and contract consistency checks."""

    def summarize(
        self,
        *,
        analysis_brief: Mapping[str, Any],
        inventory: Mapping[str, Any],
    ) -> PostrunAcceptanceCheckBundle:
        postrun_reports = _mapping_or_empty(inventory.get("postrun_reports"))
        postrun_counts = _mapping_or_empty(postrun_reports.get("counts"))
        phase4_status, phase4_detail = _phase4_evidence_coverage_actionability(
            analysis_brief,
            inventory,
        )
        contract_status, contract_detail = _prepared_contract_consistency(
            analysis_brief,
            inventory,
        )
        outcome_status, outcome_detail = _execution_outcome_integrity(
            analysis_brief,
            inventory,
        )
        return PostrunAcceptanceCheckBundle(
            checks=(
                PostrunAcceptanceCheck(
                    name="phase4_evidence_coverage_actionability",
                    status=phase4_status,
                    detail=phase4_detail,
                ),
                PostrunAcceptanceCheck(
                    name="analysis_brief_prepared_contract_consistency",
                    status=contract_status,
                    detail=contract_detail,
                ),
                PostrunAcceptanceCheck(
                    name="execution_outcome_integrity",
                    status=outcome_status,
                    detail=outcome_detail,
                ),
                PostrunAcceptanceCheck(
                    name="current_run_report_families_present",
                    status=(
                        "ok"
                        if all(
                            _int_or_zero(postrun_counts.get(name)) > 0
                            for name in (
                                "summaries",
                                "failures",
                                "manifests",
                            )
                        )
                        else "failed"
                    ),
                    detail=dict(postrun_counts),
                ),
            )
        )


def _execution_outcome_integrity(
    analysis_brief: Mapping[str, Any],
    inventory: Mapping[str, Any],
) -> tuple[str, dict[str, Any]]:
    outcomes = _mapping_or_empty(inventory.get("execution_outcomes"))
    brief_outcomes = _mapping_or_empty(analysis_brief.get("execution_outcomes"))
    counts = _mapping_or_empty(outcomes.get("execution_outcome_counts"))
    allowed = {outcome.value for outcome in ExecutionOutcome}
    failures: list[str] = []
    invalid_keys = sorted(str(key) for key in counts if str(key) not in allowed)
    if invalid_keys:
        failures.append("invalid_execution_outcome_members")
    normalized_counts = {
        key: _int_or_zero(counts.get(key)) for key in sorted(allowed)
    }
    evaluated = _int_or_zero(outcomes.get("evaluated_count"))
    non_evaluated = _int_or_zero(outcomes.get("non_evaluated_count"))
    unknown = _int_or_zero(outcomes.get("unknown_outcome_count"))
    if evaluated != normalized_counts[ExecutionOutcome.EVALUATED.value]:
        failures.append("evaluated_count_mismatch")
    if non_evaluated != sum(normalized_counts.values()) - evaluated:
        failures.append("non_evaluated_count_mismatch")
    total = _int_or_zero(outcomes.get("total_outcome_subject_count"))
    if total != evaluated + non_evaluated + unknown:
        failures.append("total_outcome_subject_count_mismatch")

    step_invariants = _mapping_or_empty(outcomes.get("step_invariants"))
    if step_invariants.get("status") == "invalid":
        failures.append("step_outcome_invariants_invalid")
    if outcomes.get("summary_step_counts_comparable") is True and outcomes.get(
        "summary_step_counts_consistent"
    ) is not True:
        failures.append("summary_step_outcome_counts_mismatch")
    if outcomes.get("summary_lineage_counts_comparable") is True and outcomes.get(
        "summary_lineage_counts_consistent"
    ) is not True:
        failures.append("summary_lineage_outcome_counts_mismatch")
    lineage = _mapping_or_empty(outcomes.get("lineage"))
    if _int_or_zero(lineage.get("invalid_outcome_count")) > 0:
        failures.append("lineage_invalid_execution_outcome")
    if lineage.get("decision_outcome_consistency_status") == "invalid":
        failures.append("decision_row_requires_evaluated_outcome")

    eligibility = _mapping_or_empty(
        outcomes.get("research_conclusion_eligibility")
    )
    if evaluated == 0 and non_evaluated > 0:
        if eligibility.get("eligible") is not False or eligibility.get(
            "algorithm_conclusions_allowed"
        ) is not False:
            failures.append("zero_evaluated_conclusion_eligibility_invalid")
    elif evaluated > 0 and eligibility.get("eligible") is not True:
        failures.append("evaluated_conclusion_eligibility_invalid")
    elif evaluated == 0 and non_evaluated == 0 and eligibility.get(
        "eligible"
    ) is not None:
        failures.append("historical_missing_outcome_not_unknown")

    if evaluated + non_evaluated > 0 and not brief_outcomes:
        failures.append("analysis_brief_execution_outcomes_missing")
    elif brief_outcomes and dict(brief_outcomes) != dict(outcomes):
        failures.append("analysis_brief_outcome_projection_mismatch")
    return ("ok" if not failures else "failed"), {
        "failures": failures,
        "execution_outcome_counts": normalized_counts,
        "evaluated_count": evaluated,
        "non_evaluated_count": non_evaluated,
        "unknown_outcome_count": unknown,
        "research_conclusion_eligibility": dict(eligibility),
        "step_invariants": dict(step_invariants),
        "lineage": dict(lineage),
        "historical_missing_outcome_policy": "unknown_not_negative",
    }


class PostrunLifecycleAcceptancePort:
    """Build generic lifecycle and wrapper-marker checks."""

    def summarize(
        self,
        inventory: Mapping[str, Any],
        analysis_brief: Mapping[str, Any],
    ) -> PostrunAcceptanceCheckBundle:
        lifecycle = _mapping_or_empty(inventory.get("lifecycle"))
        validity = _mapping_or_empty(inventory.get("validity"))
        phase4 = _mapping_or_empty(inventory.get("phase4_evidence_coverage"))
        launcher = _mapping_or_empty(inventory.get("launcher"))
        run_log_markers = _mapping_or_empty(launcher.get("run_log_markers"))
        wrapper_status, wrapper_detail = _launcher_wrapper_status_ok(inventory)
        marker_status, marker_detail = _launcher_wrapper_marker_status_ok(
            inventory
        )
        return PostrunAcceptanceCheckBundle(
            checks=(
                PostrunAcceptanceCheck(
                    name="current_run_evidence",
                    status=(
                        "ok"
                        if lifecycle.get("current_run_evidence") is True
                        and phase4.get("current_run_evidence") is True
                        else "failed"
                    ),
                    detail={
                        "lifecycle": lifecycle,
                        "phase4": {
                            "current_run_evidence": phase4.get(
                                "current_run_evidence"
                            ),
                            "evidence_scope": phase4.get("evidence_scope"),
                        },
                    },
                ),
                PostrunAcceptanceCheck(
                    name="analysis_brief_current_run_evidence",
                    status=(
                        "ok"
                        if _brief_current_run_evidence(analysis_brief)
                        else "failed"
                    ),
                    detail={
                        "lifecycle": _mapping_or_empty(
                            analysis_brief.get("lifecycle")
                        ),
                        "phase4": _mapping_or_empty(
                            analysis_brief.get("phase4_evidence_coverage")
                        ),
                    },
                ),
                PostrunAcceptanceCheck(
                    name="launcher_wrapper_status_ok",
                    status=wrapper_status,
                    detail=wrapper_detail,
                ),
                PostrunAcceptanceCheck(
                    name="launcher_wrapper_marker_status_ok",
                    status=marker_status,
                    detail=marker_detail,
                ),
                PostrunAcceptanceCheck(
                    name="not_invalid_infra_only",
                    status=(
                        "ok"
                        if validity.get("invalid_infra_only") is not True
                        and lifecycle.get("invalid_infra_only") is not True
                        else "failed"
                    ),
                    detail={"lifecycle": lifecycle, "validity": validity},
                ),
                PostrunAcceptanceCheck(
                    name="not_prepared_only",
                    status=(
                        "ok"
                        if lifecycle.get("prepared_only") is not True
                        else "failed"
                    ),
                    detail=lifecycle,
                ),
                PostrunAcceptanceCheck(
                    name="not_pre_campaign_preflight_failed",
                    status=(
                        "ok"
                        if lifecycle.get(
                            "pre_campaign_completion_preflight_failed"
                        )
                        is not True
                        else "failed"
                    ),
                    detail=lifecycle,
                ),
                PostrunAcceptanceCheck(
                    name="postrun_report_status_marker",
                    status=(
                        "ok"
                        if _int_or_zero(
                            run_log_markers.get("POSTRUN_REPORTS_EXIT_STATUS")
                        )
                        > 0
                        else "missing"
                    ),
                    detail=run_log_markers,
                    required=False,
                ),
            )
        )


def _brief_current_run_evidence(brief: Mapping[str, Any]) -> bool:
    lifecycle = _mapping_or_empty(brief.get("lifecycle"))
    phase4 = _mapping_or_empty(brief.get("phase4_evidence_coverage"))
    return (
        lifecycle.get("current_run_evidence") is True
        and phase4.get("current_run_evidence") is True
    )


def _launcher_wrapper_status_ok(
    inventory: Mapping[str, Any],
) -> tuple[str, dict[str, Any]]:
    launcher = _mapping_or_empty(inventory.get("launcher"))
    status_fields = _mapping_or_empty(launcher.get("status_fields"))
    failures: list[str] = []

    wrapper_exit = _int_or_none(status_fields.get("wrapper_exit_status"))
    if wrapper_exit is None:
        failures.append("wrapper_exit_status_missing")
    elif wrapper_exit != 0:
        failures.append("wrapper_exit_status_nonzero")

    campaign_exit = _int_or_none(status_fields.get("campaign_wrapper_exit_status"))
    if campaign_exit not in (None, 0):
        failures.append("campaign_wrapper_exit_status_nonzero")

    if status_fields.get("postrun_acceptance_failed") is True:
        failures.append("postrun_acceptance_failed")
    if str(status_fields.get("postrun_acceptance_status") or "").lower() == "failed":
        failures.append("postrun_acceptance_status_failed")

    for key in ("postrun_readiness_exit_status", "postrun_reports_exit_status"):
        value = _int_or_none(status_fields.get(key))
        if value not in (None, 0):
            failures.append(f"{key}_nonzero")

    return (
        "ok" if not failures else "failed",
        {
            "failures": failures,
            "status_fields": status_fields,
        },
    )


def _launcher_wrapper_marker_status_ok(
    inventory: Mapping[str, Any],
) -> tuple[str, dict[str, Any]]:
    launcher = _mapping_or_empty(inventory.get("launcher"))
    run_log_markers = _mapping_or_empty(launcher.get("run_log_markers"))
    exit_markers = _mapping_or_empty(launcher.get("exit_markers"))
    failures: list[str] = []

    if _int_or_zero(run_log_markers.get("POSTRUN_STATUS_WRITE_EXIT_STATUS")) > 0:
        failures.append("postrun_status_write_exit_status_marker_present")
    if _int_or_zero(exit_markers.get("POSTRUN_ACCEPTANCE_FAILED")) > 0:
        failures.append("postrun_acceptance_failed_marker_present")
    if _int_or_zero(exit_markers.get("POSTRUN_REPORTS_EFFECTIVE_EXIT_STATUS")) > 0:
        failures.append("postrun_reports_effective_exit_status_marker_present")
    if _int_or_zero(exit_markers.get("POSTRUN_READINESS_EFFECTIVE_EXIT_STATUS")) > 0:
        failures.append("postrun_readiness_effective_exit_status_marker_present")
    if _int_or_zero(exit_markers.get("WRAPPER_EXIT_STATUS_EFFECTIVE")) > 0:
        failures.append("wrapper_exit_status_effective_marker_present")

    return (
        "ok" if not failures else "failed",
        {
            "failures": failures,
            "run_log_markers": run_log_markers,
            "exit_markers": exit_markers,
        },
    )


def _phase4_evidence_coverage_actionability(
    brief: Mapping[str, Any],
    inventory: Mapping[str, Any],
) -> tuple[str, Any]:
    summary = _mapping_or_empty(brief.get("phase4_evidence_coverage"))
    expected = _mapping_or_empty(inventory.get("phase4_evidence_coverage"))
    failures: list[str] = []

    if summary.get("schema_version") != PHASE4_EVIDENCE_COVERAGE_SCHEMA:
        failures.append("phase4_evidence_coverage_schema_stale")
    failures.extend(_boundary_marker_failures("phase4_evidence_coverage", summary))
    if summary.get("current_run_evidence") is not True:
        failures.append("phase4_evidence_coverage_not_current_run_evidence")

    field_mismatches: list[dict[str, Any]] = []
    for field in PHASE4_COVERAGE_IDENTITY_FIELDS:
        expected_value = expected.get(field)
        actual_value = summary.get(field)
        if actual_value != expected_value:
            field_mismatches.append(
                {
                    "field": field,
                    "expected": expected_value,
                    "actual": actual_value,
                }
            )
    if field_mismatches:
        failures.append("phase4_evidence_coverage_inventory_mismatch")

    expected_requirements = _phase4_requirement_signature_map(
        expected.get("requirements")
    )
    actual_requirements = _phase4_requirement_signature_map(
        summary.get("requirements")
    )
    if actual_requirements != expected_requirements:
        failures.append("phase4_requirements_inventory_mismatch")
    unavailable_required = sorted(
        key
        for key, item in actual_requirements.items()
        if item.get("required") is True
        and item.get("applicable") is not False
        and item.get("available") is not True
    )
    if unavailable_required:
        failures.append("phase4_required_evidence_unavailable")

    expected_problem_specific = _phase4_requirement_signature_map(
        expected.get("problem_specific_requirements")
    )
    actual_problem_specific = _phase4_requirement_signature_map(
        summary.get("problem_specific_requirements")
    )
    if actual_problem_specific != expected_problem_specific:
        failures.append("phase4_problem_specific_requirements_mismatch")
    unavailable_problem_specific = sorted(
        key
        for key, item in actual_problem_specific.items()
        if item.get("available") is not True
    )
    if unavailable_problem_specific:
        failures.append("phase4_problem_specific_requirements_unavailable")

    return (
        "ok" if not failures else "failed",
        {
            "failures": failures,
            "schema_version": summary.get("schema_version"),
            "current_run_evidence": summary.get("current_run_evidence"),
            "expected_current_run_evidence": expected.get("current_run_evidence"),
            "coverage_field_mismatches": field_mismatches,
            "problem_specific_keys": sorted(actual_problem_specific),
            "expected_problem_specific_keys": sorted(expected_problem_specific),
            "problem_specific_unavailable": unavailable_problem_specific,
            "required_evidence_unavailable": unavailable_required,
        },
    )


def _phase4_requirement_signature_map(value: Any) -> dict[str, dict[str, Any]]:
    requirements = _mapping_or_empty(value)
    return {
        str(key): {
            "available": item.get("available") is True,
            "count": (
                _int_or_zero(item.get("count")) if "count" in item else None
            ),
            "source": str(item.get("source") or ""),
            "status": str(item.get("status") or ""),
            "applicable": item.get("applicable"),
            "required": item.get("required") is True,
        }
        for key, item in sorted(requirements.items())
        if isinstance(item, Mapping)
    }


def _prepared_contract_consistency(
    brief: Mapping[str, Any],
    inventory: Mapping[str, Any],
) -> tuple[str, Any]:
    brief_contract = _mapping_or_empty(brief.get("prepared_run_contract"))
    launcher = _mapping_or_empty(inventory.get("launcher"))
    inventory_contract = _mapping_or_empty(launcher.get("prepared_run_contract"))
    failures: list[str] = []
    if not brief_contract:
        failures.append("analysis_brief_prepared_contract_missing")
    if not inventory_contract:
        failures.append("inventory_prepared_contract_missing")
    for field in (
        "schema_version",
        "report_only",
        "quality_judgment",
        "decision_features_excluded",
        "manifest_present",
        "contract_complete",
        "problem_family",
        "model",
        "resume_from_campaign",
        "control_pair_key",
        "completion_preflight",
        "postrun_reports",
    ):
        if brief_contract.get(field) != inventory_contract.get(field):
            failures.append(f"prepared_contract_{field}_mismatch")
    if _mapping_or_empty(brief_contract.get("execution")) != _mapping_or_empty(
        inventory_contract.get("execution")
    ):
        failures.append("prepared_contract_execution_mismatch")
    if _mapping_or_empty(brief_contract.get("git")) != _mapping_or_empty(
        inventory_contract.get("git")
    ):
        failures.append("prepared_contract_git_mismatch")
    return (
        "ok" if not failures else "failed",
        {
            "failures": failures,
            "brief_problem_family": brief_contract.get("problem_family"),
            "inventory_problem_family": inventory_contract.get("problem_family"),
            "brief_model": brief_contract.get("model"),
            "inventory_model": inventory_contract.get("model"),
            "brief_control_pair_key": brief_contract.get("control_pair_key"),
            "inventory_control_pair_key": inventory_contract.get("control_pair_key"),
            "brief_resume_from_campaign": brief_contract.get("resume_from_campaign"),
            "inventory_resume_from_campaign": inventory_contract.get(
                "resume_from_campaign"
            ),
        },
    )


def _rebuild_manifest_identity_boundary(
    root: Path,
    report_dir: Path,
    rebuild_manifest: Mapping[str, Any],
) -> tuple[str, Any]:
    if not rebuild_manifest:
        return "failed", {"reason": "missing_rebuild_manifest", "failures": []}

    failures: list[dict[str, Any]] = []
    expected_identity = {
        "artifact_kind": "postrun_acceptance_rebuild",
        "run_root": str(root),
        "campaign_dir": str(root / "campaign"),
        "report_dir": str(report_dir),
    }
    for field, expected in expected_identity.items():
        actual = rebuild_manifest.get(field)
        matches = (
            _payload_path_matches(actual, Path(expected))
            if field in {"run_root", "campaign_dir", "report_dir"}
            else actual == expected
        )
        if not matches:
            failures.append(
                {
                    "reason": "manifest_identity_mismatch",
                    "field": field,
                    "expected": expected,
                    "actual": actual,
                }
            )

    boundary_expectations = _boundary_expectations()
    for field, expected in boundary_expectations.items():
        if rebuild_manifest.get(field) is not expected:
            failures.append(
                {
                    "reason": "manifest_boundary_flag_mismatch",
                    "field": field,
                    "expected": expected,
                    "actual": rebuild_manifest.get(field),
                }
            )

    return (
        "ok" if not failures else "failed",
        {
            "failures": failures,
            "expected_identity": expected_identity,
            "boundary_expectations": boundary_expectations,
        },
    )


def _rebuild_manifest_declared_outputs_present(
    rebuild_manifest: Mapping[str, Any],
    report_dir: Path,
) -> tuple[str, Any]:
    if not rebuild_manifest:
        return "failed", {"reason": "missing_rebuild_manifest"}
    families = _mapping_or_empty(rebuild_manifest.get("families"))
    if not families:
        return "failed", {"reason": "missing_rebuild_manifest_families"}

    ok_families: list[str] = []
    skipped_families: list[str] = []
    missing_outputs: list[dict[str, Any]] = []
    inconsistent_outputs: list[dict[str, Any]] = []
    unexpected_outputs: list[dict[str, Any]] = []
    out_of_scope_outputs: list[dict[str, Any]] = []
    family_failures: list[dict[str, Any]] = []
    for family_name, raw_family in sorted(families.items()):
        family = _mapping_or_empty(raw_family)
        family_status = family.get("status")
        outputs = _string_items(family.get("outputs"))
        outputs_present = _mapping_or_empty(family.get("outputs_present"))
        if family_status == "skipped":
            skipped_families.append(str(family_name))
            continue
        if family_status != "ok":
            family_failures.append(
                {
                    "family": str(family_name),
                    "status": family_status,
                    "reason": "family_status_not_ok",
                }
            )
            continue
        ok_families.append(str(family_name))
        if not outputs:
            family_failures.append(
                {
                    "family": str(family_name),
                    "status": family_status,
                    "reason": "ok_family_without_outputs",
                }
            )
            continue
        declared_paths: set[Path] = set()
        for output in outputs:
            path = _manifest_output_path(output, report_dir)
            in_scope = _manifest_output_in_family(path, report_dir, str(family_name))
            if not in_scope:
                out_of_scope_outputs.append(
                    {
                        "family": str(family_name),
                        "path": str(path),
                        "manifest_output": output,
                        "expected_directory": str(report_dir / str(family_name)),
                        "reason": "manifest_output_outside_family_directory",
                    }
                )
            else:
                declared_paths.add(path.resolve())
            actual_present = path.is_file()
            manifest_present = outputs_present.get(output)
            if actual_present is False:
                missing_outputs.append(
                    {
                        "family": str(family_name),
                        "path": str(path),
                        "manifest_output": output,
                    }
                )
            if isinstance(manifest_present, bool):
                if manifest_present is not actual_present:
                    inconsistent_outputs.append(
                        {
                            "family": str(family_name),
                            "path": str(path),
                            "manifest_output": output,
                            "manifest_outputs_present": manifest_present,
                            "actual_present": actual_present,
                        }
                    )
            else:
                inconsistent_outputs.append(
                    {
                        "family": str(family_name),
                        "path": str(path),
                        "manifest_output": output,
                        "manifest_outputs_present": manifest_present,
                        "actual_present": actual_present,
                        "reason": "missing_outputs_present_entry",
                    }
                )
        family_dir = report_dir / str(family_name)
        if family_dir.is_dir():
            for path in sorted(family_dir.iterdir()):
                if not path.is_file() or path.suffix not in {".json", ".md"}:
                    continue
                if path.resolve() not in declared_paths:
                    unexpected_outputs.append(
                        {
                            "family": str(family_name),
                            "path": str(path),
                            "reason": "undeclared_generated_output",
                        }
                    )

    failures_present = bool(
        missing_outputs
        or inconsistent_outputs
        or unexpected_outputs
        or out_of_scope_outputs
        or family_failures
    )
    return (
        "failed" if failures_present else "ok",
        {
            "ok_families": ok_families,
            "skipped_families": skipped_families,
            "missing_outputs": missing_outputs,
            "inconsistent_outputs": inconsistent_outputs,
            "unexpected_outputs": unexpected_outputs,
            "out_of_scope_outputs": out_of_scope_outputs,
            "family_failures": family_failures,
        },
    )


def _analysis_brief_boundary(brief: Mapping[str, Any]) -> tuple[str, Any]:
    failures: list[str] = []
    failures.extend(_boundary_marker_failures("analysis_brief", brief))
    for mutation_field in (
        "campaign_state_mutated",
        "scheduler_state_mutated",
        "promotion_state_mutated",
    ):
        if brief.get(mutation_field) is not False:
            failures.append(f"analysis_brief_{mutation_field}_not_false")
    return (
        "ok" if not failures else "failed",
        {
            "failures": failures,
            "report_only": brief.get("report_only"),
            "quality_judgment": brief.get("quality_judgment"),
            "decision_features_excluded": brief.get("decision_features_excluded"),
            "campaign_state_mutated": brief.get("campaign_state_mutated"),
            "scheduler_state_mutated": brief.get("scheduler_state_mutated"),
            "promotion_state_mutated": brief.get("promotion_state_mutated"),
        },
    )


def _boundary_marker_failures(prefix: str, payload: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    if payload.get("report_only") is not True:
        failures.append(f"{prefix}_not_report_only")
    if payload.get("quality_judgment") is not False:
        failures.append(f"{prefix}_quality_judgment_not_false")
    if payload.get("decision_features_excluded") is not True:
        failures.append(f"{prefix}_decision_features_not_excluded")
    return failures


def _boundary_expectations() -> dict[str, bool]:
    return {
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "campaign_state_mutated": False,
        "scheduler_state_mutated": False,
        "promotion_state_mutated": False,
    }


def _manifest_output_path(value: str, report_dir: Path) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return (report_dir / path).resolve()


def _manifest_output_in_family(path: Path, report_dir: Path, family_name: str) -> bool:
    try:
        return path.resolve().parent == (report_dir / family_name).resolve()
    except OSError:
        return False


def _artifact_paths(directory: Path) -> list[str]:
    return sorted(str(path) for path in directory.glob("*.json") if path.is_file())


def _payload_path_matches(value: Any, expected: Path) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        return Path(value).expanduser().resolve() == expected
    except OSError:
        return False


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(data) if isinstance(data, Mapping) else {}


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _int_or_zero(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _int_or_none(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _string_items(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


__all__ = [
    "ANALYSIS_BRIEF_SCHEMA",
    "PHASE4_EVIDENCE_COVERAGE_SCHEMA",
    "PostrunAcceptanceCheck",
    "PostrunAcceptanceCheckBundle",
    "PostrunArtifactAcceptancePort",
    "PostrunEvidenceConsistencyAcceptancePort",
    "PostrunLifecycleAcceptancePort",
    "REBUILD_SCHEMA",
]
