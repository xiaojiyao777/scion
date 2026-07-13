"""Host-side external proposal ingestion.

This module deliberately avoids problem semantics. It turns a tainted external
manifest plus patch/workspace into Scion-native proposals, canonical audit
artifacts, and a host-materialized candidate workspace.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import yaml

from scion.config.problem import ProblemSpec
from scion.config.split_manifest import SplitManifest
from scion.contract.gate import ContractGate
from scion.core.models import (
    ContractResult,
    HypothesisProposal,
    PatchFileChange,
    PatchProposal,
    patch_file_changes,
)
from scion.core.paths import normalize_relative_patch_path
from scion.core.research_surface_index import editable_identity_patterns
from scion.lineage.registry import LineageRegistry
from scion.runtime.workspace import WorkspaceMaterializer

from .schema import ExternalProposalManifest


@dataclass(frozen=True)
class MockSmokeResult:
    passed: bool
    detail: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class CanonicalFileAudit:
    file_path: str
    action: str
    content_after_ref: str | None
    content_after_sha256: str | None
    before_sha256: str | None
    after_sha256: str | None


@dataclass(frozen=True)
class ExternalIngestResult:
    ingest_id: str
    output_dir: str
    workspace_path: str
    audit_manifest_path: str
    canonical_diff_path: str
    result_path: str
    hypothesis: HypothesisProposal
    patch: PatchProposal
    hypothesis_contract: ContractResult
    patch_contract: ContractResult
    smoke_result: MockSmokeResult | None
    lineage_event_id: str | None

    @property
    def passed(self) -> bool:
        smoke_passed = self.smoke_result is None or self.smoke_result.passed
        return (
            self.hypothesis_contract.passed
            and self.patch_contract.passed
            and smoke_passed
        )


SmokeRunner = Callable[
    [str, PatchProposal, HypothesisProposal, ExternalProposalManifest],
    MockSmokeResult,
]


def _pattern_set(patterns: Any, *, empty_as_none: bool = True) -> frozenset[str] | None:
    normalized = frozenset(
        pattern
        for pattern in (str(value).strip() for value in (patterns or ()))
        if pattern
    )
    if normalized or not empty_as_none:
        return normalized
    return None


def _materializer_kwargs_from_problem_spec(problem_spec: Any) -> dict[str, Any]:
    search_space = getattr(problem_spec, "search_space", None)
    return {
        "frozen_patterns": _pattern_set(
            getattr(search_space, "frozen", ()),
            empty_as_none=False,
        ),
        "editable_patterns": editable_identity_patterns(problem_spec),
    }


class ExternalProposalIngestor:
    def __init__(
        self,
        *,
        problem_spec: ProblemSpec,
        output_dir: str | Path,
        base_workspace: str | Path | None = None,
        split_manifest: SplitManifest | None = None,
        selected_surface: str | None = None,
        campaign_dir: str | Path | None = None,
        record_lineage: bool = False,
    ) -> None:
        self.problem_spec = problem_spec
        self.output_dir = Path(output_dir).expanduser().resolve(strict=False)
        self.base_workspace = (
            Path(base_workspace).expanduser().resolve(strict=True)
            if base_workspace is not None
            else None
        )
        self.split_manifest = split_manifest
        self.selected_surface = selected_surface
        self.campaign_dir = (
            Path(campaign_dir).expanduser().resolve(strict=False)
            if campaign_dir is not None
            else None
        )
        self.record_lineage = record_lineage

    def ingest(
        self,
        manifest: ExternalProposalManifest,
        *,
        manifest_path: str | Path | None = None,
        smoke_runner: SmokeRunner | None = None,
    ) -> ExternalIngestResult:
        ingest_id = f"external-{uuid.uuid4().hex[:12]}"
        ingest_dir = self.output_dir / ingest_id
        ingest_dir.mkdir(parents=True, exist_ok=False)
        audit_dir = ingest_dir / "audit"
        audit_dir.mkdir()

        base_workspace = self._resolve_base_workspace(manifest)
        candidate_source = self._candidate_source_workspace(
            manifest,
            base_workspace=base_workspace,
            ingest_dir=ingest_dir,
        )
        file_audits, patch = self._build_patch_from_candidate(
            manifest,
            base_workspace=base_workspace,
            candidate_workspace=candidate_source,
            audit_dir=audit_dir,
        )
        hypothesis = manifest.hypothesis.to_proposal()

        gate = ContractGate(
            self.problem_spec,
            champion_snapshot_path=str(base_workspace),
        )
        h_result = gate.validate_hypothesis(hypothesis)
        p_result = gate.validate_patch(
            patch,
            approved_hypothesis=hypothesis,
            selected_surface=self.selected_surface,
            base_snapshot_path=str(base_workspace),
        )

        workspace_path: Path | None = None
        smoke_result: MockSmokeResult | None = None
        if h_result.passed and p_result.passed:
            workspace_path = self._materialize_host_workspace(
                ingest_id=ingest_id,
                base_workspace=base_workspace,
                patch=patch,
                ingest_dir=ingest_dir,
            )
            smoke_result = (
                smoke_runner(str(workspace_path), patch, hypothesis, manifest)
                if smoke_runner is not None
                else None
            )
        elif smoke_runner is not None:
            smoke_result = MockSmokeResult(
                passed=False,
                detail="mock smoke skipped because ContractGate failed",
                metadata={
                    "schema": "scion.external_ingest.mock_smoke.v1",
                    "workspace_materialized": False,
                },
            )
        else:
            smoke_result = None

        diff_path = audit_dir / "canonical.diff"
        audit_manifest_path = audit_dir / "external_ingest_audit.json"
        result_path = ingest_dir / "ingest_result.json"
        resolved_split_path = self._write_resolved_split_manifest(ingest_dir)
        audit_payload = self._audit_payload(
            ingest_id=ingest_id,
            manifest=manifest,
            manifest_path=manifest_path,
            base_workspace=base_workspace,
            workspace_path=workspace_path,
            patch=patch,
            file_audits=file_audits,
            diff_path=diff_path,
            resolved_split_path=resolved_split_path,
        )
        _write_json(audit_manifest_path, audit_payload)

        result_payload = {
            "schema": "scion.external_ingest.result.v1",
            "ingest_id": ingest_id,
            "passed": h_result.passed
            and p_result.passed
            and (smoke_result is None or smoke_result.passed),
            "workspace_path": str(workspace_path) if workspace_path is not None else "",
            "audit_manifest_path": str(audit_manifest_path),
            "canonical_diff_path": str(diff_path),
            "hypothesis_contract": _contract_result_payload(h_result),
            "patch_contract": _contract_result_payload(p_result),
            "smoke_result": asdict(smoke_result) if smoke_result is not None else None,
        }
        _write_json(result_path, result_payload)

        lineage_event_id = self._record_lineage_event(
            ingest_id=ingest_id,
            manifest=manifest,
            patch=patch,
            hypothesis=hypothesis,
            h_result=h_result,
            p_result=p_result,
            smoke_result=smoke_result,
            audit_payload=audit_payload,
            workspace_path=workspace_path,
        )

        return ExternalIngestResult(
            ingest_id=ingest_id,
            output_dir=str(ingest_dir),
            workspace_path=str(workspace_path) if workspace_path is not None else "",
            audit_manifest_path=str(audit_manifest_path),
            canonical_diff_path=str(diff_path),
            result_path=str(result_path),
            hypothesis=hypothesis,
            patch=patch,
            hypothesis_contract=h_result,
            patch_contract=p_result,
            smoke_result=smoke_result,
            lineage_event_id=lineage_event_id,
        )

    def _resolve_base_workspace(self, manifest: ExternalProposalManifest) -> Path:
        if self.base_workspace is not None:
            return self.base_workspace
        if manifest.base_champion.workspace_path:
            return Path(manifest.base_champion.workspace_path).expanduser().resolve(
                strict=True
            )
        return Path(self.problem_spec.root_dir).expanduser().resolve(strict=True)

    def _candidate_source_workspace(
        self,
        manifest: ExternalProposalManifest,
        *,
        base_workspace: Path,
        ingest_dir: Path,
    ) -> Path:
        source = manifest.source
        if source.type == "workspace":
            return Path(str(source.workspace_path)).expanduser().resolve(strict=True)
        if source.type == "inline":
            candidate = ingest_dir / "candidate_from_inline"
            shutil.copytree(base_workspace, candidate, symlinks=False)
            for change in source.inline_changes:
                _apply_change_to_tree(candidate, change.to_patch_change())
            return candidate
        if source.type == "unified_diff":
            candidate = ingest_dir / "candidate_from_diff"
            shutil.copytree(base_workspace, candidate, symlinks=False)
            patch_path = Path(str(source.patch_path)).expanduser().resolve(strict=True)
            completed = subprocess.run(
                ["git", "apply", "--whitespace=nowarn", str(patch_path)],
                cwd=candidate,
                text=True,
                capture_output=True,
                timeout=30,
                check=False,
            )
            if completed.returncode != 0:
                detail = completed.stderr.strip() or completed.stdout.strip()
                raise ValueError(f"git apply failed for external patch: {detail}")
            return candidate
        raise ValueError(f"unsupported source type: {source.type}")

    def _build_patch_from_candidate(
        self,
        manifest: ExternalProposalManifest,
        *,
        base_workspace: Path,
        candidate_workspace: Path,
        audit_dir: Path,
    ) -> tuple[list[CanonicalFileAudit], PatchProposal]:
        changes: list[PatchFileChange] = []
        audits: list[CanonicalFileAudit] = []
        diff_chunks: list[str] = []
        content_dir = audit_dir / "content_after"
        content_dir.mkdir()

        source_changes = (
            [change.to_patch_change() for change in manifest.source.inline_changes]
            if manifest.source.type == "inline"
            else [
                self._derive_change(
                    base_workspace=base_workspace,
                    candidate_workspace=candidate_workspace,
                    file_path=file_path,
                )
                for file_path in manifest.source.changed_files
            ]
        )

        for change in source_changes:
            file_rel = normalize_relative_patch_path(change.file_path)
            before = _read_optional_text(base_workspace, file_rel)
            after = None if change.action == "delete" else change.code_content
            if before == after:
                raise ValueError(f"changed file has no content delta: {file_rel}")
            diff_chunks.extend(_unified_diff(file_rel, before, after))
            content_after_ref: str | None = None
            after_digest: str | None = None
            if after is not None:
                content_after_path = content_dir / _safe_audit_filename(file_rel)
                content_after_path.parent.mkdir(parents=True, exist_ok=True)
                content_after_path.write_text(after, encoding="utf-8")
                content_after_ref = str(content_after_path.relative_to(audit_dir))
                after_digest = _sha256_text(after)
            audits.append(
                CanonicalFileAudit(
                    file_path=file_rel,
                    action=change.action,
                    content_after_ref=content_after_ref,
                    content_after_sha256=after_digest,
                    before_sha256=_sha256_text(before) if before is not None else None,
                    after_sha256=after_digest,
                )
            )
            changes.append(change)

        diff_path = audit_dir / "canonical.diff"
        diff_path.write_text("".join(diff_chunks), encoding="utf-8")
        if not changes:
            raise ValueError("external proposal produced no file changes")

        primary, additional = changes[0], tuple(changes[1:])
        return audits, PatchProposal(
            file_path=primary.file_path,
            action=primary.action,
            code_content=primary.code_content,
            test_hint=primary.test_hint,
            additional_changes=additional,
        )

    def _derive_change(
        self,
        *,
        base_workspace: Path,
        candidate_workspace: Path,
        file_path: str,
    ) -> PatchFileChange:
        file_rel = normalize_relative_patch_path(file_path)
        before = _read_optional_text(base_workspace, file_rel)
        after = _read_optional_text(candidate_workspace, file_rel)
        if before is None and after is None:
            raise ValueError(f"changed file not found in base or candidate: {file_rel}")
        if before is None:
            action = "create"
        elif after is None:
            action = "delete"
        else:
            action = "modify"
        return PatchFileChange(
            file_path=file_rel,
            action=action,
            code_content="" if after is None else after,
        )

    def _materialize_host_workspace(
        self,
        *,
        ingest_id: str,
        base_workspace: Path,
        patch: PatchProposal,
        ingest_dir: Path,
    ) -> Path:
        materializer = WorkspaceMaterializer(
            str(ingest_dir),
            **_materializer_kwargs_from_problem_spec(self.problem_spec),
        )
        workspace = Path(
            materializer.create_branch_workspace(ingest_id, str(base_workspace))
        )
        materializer.apply_patch(str(workspace), patch)
        scion_dir = workspace / ".scion" / "external_ingest"
        scion_dir.mkdir(parents=True, exist_ok=True)
        _write_json(
            scion_dir / "workspace_manifest.json",
            {
                "schema": "scion.external_ingest.workspace_manifest.v1",
                "ingest_id": ingest_id,
                "safe_data_roots": _resolved_safe_data_roots(self.split_manifest),
            },
        )
        return workspace

    def _write_resolved_split_manifest(self, ingest_dir: Path) -> str | None:
        if self.split_manifest is None:
            return None
        payload = self.split_manifest.model_dump()
        payload["safe_data_roots"] = _resolved_safe_data_roots(self.split_manifest)
        target = ingest_dir / "split_manifest.resolved.yaml"
        target.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        return str(target)

    def _audit_payload(
        self,
        *,
        ingest_id: str,
        manifest: ExternalProposalManifest,
        manifest_path: str | Path | None,
        base_workspace: Path,
        workspace_path: Path | None,
        patch: PatchProposal,
        file_audits: list[CanonicalFileAudit],
        diff_path: Path,
        resolved_split_path: str | None,
    ) -> dict[str, Any]:
        return {
            "schema": "scion.external_ingest.audit.v1",
            "ingest_id": ingest_id,
            "created_at": datetime.now().isoformat(),
            "manifest_path": str(manifest_path) if manifest_path is not None else None,
            "manifest_sha256": (
                _sha256_file(Path(manifest_path))
                if manifest_path is not None and Path(manifest_path).exists()
                else None
            ),
            "base_champion": manifest.base_champion.model_dump(),
            "declared_boundary": manifest.declared_boundary.model_dump(),
            "provenance": manifest.provenance.model_dump(),
            "source": manifest.source.model_dump(),
            "base_workspace": str(base_workspace),
            "base_workspace_sha256": _tree_hash(base_workspace),
            "materialized_workspace": (
                str(workspace_path) if workspace_path is not None else None
            ),
            "materialized_workspace_sha256": (
                _tree_hash(workspace_path) if workspace_path is not None else None
            ),
            "patch_sha256": _patch_digest(patch),
            "canonical_diff_ref": str(diff_path),
            "canonical_files": [asdict(item) for item in file_audits],
            "resolved_safe_data_roots": _resolved_safe_data_roots(self.split_manifest),
            "resolved_split_manifest_ref": resolved_split_path,
        }

    def _record_lineage_event(
        self,
        *,
        ingest_id: str,
        manifest: ExternalProposalManifest,
        patch: PatchProposal,
        hypothesis: HypothesisProposal,
        h_result: ContractResult,
        p_result: ContractResult,
        smoke_result: MockSmokeResult | None,
        audit_payload: dict[str, Any],
        workspace_path: Path | None,
    ) -> str | None:
        if not self.record_lineage or self.campaign_dir is None:
            return None
        self.campaign_dir.mkdir(parents=True, exist_ok=True)
        registry = LineageRegistry(str(self.campaign_dir / "scion.db"))
        branch_id = manifest.base_champion.branch_id or ingest_id
        passed = h_result.passed and p_result.passed
        event = {
            "campaign_id": str(self.campaign_dir),
            "branch_id": branch_id,
            "event_kind": "external_proposal_ingest",
            "code_hash": _tree_hash(workspace_path) if workspace_path is not None else "",
            "patch_action": patch.action,
            "patch_file": patch.file_path,
            "hypothesis_text": hypothesis.hypothesis_text,
            "contract_passed": str(passed),
            "verification_passed": "False",
            "contract_result": "passed" if passed else "failed",
            "verification_result": "skipped",
            "canary_result": (
                "passed"
                if smoke_result is not None and smoke_result.passed
                else "failed"
                if smoke_result is not None
                else "skipped"
            ),
            "stage": "external_ingest",
            "raw_metrics_ref": "",
            "decision": "",
            "audit_payload_json": json.dumps(audit_payload, sort_keys=True),
        }
        return registry.record_event(event)


def run_mock_smoke(
    workspace: str,
    patch: PatchProposal,
    hypothesis: HypothesisProposal,
    manifest: ExternalProposalManifest,
) -> MockSmokeResult:
    """A generic non-execution smoke used by tests and dry-run CLI paths."""

    root = Path(workspace).resolve(strict=True)
    missing: list[str] = []
    present_deleted: list[str] = []
    for change in patch_file_changes(patch):
        path = root / normalize_relative_patch_path(change.file_path)
        if change.action == "delete":
            if path.exists():
                present_deleted.append(change.file_path)
        elif not path.is_file():
            missing.append(change.file_path)
    passed = not missing and not present_deleted
    detail = "mock smoke observed materialized files" if passed else "mock smoke failed"
    return MockSmokeResult(
        passed=passed,
        detail=detail,
        metadata={
            "schema": "scion.external_ingest.mock_smoke.v1",
            "workspace_materialized": True,
            "hypothesis_locus": hypothesis.change_locus,
            "source_type": manifest.source.type,
            "missing_files": missing,
            "present_deleted_files": present_deleted,
        },
    )


def _apply_change_to_tree(root: Path, change: PatchFileChange) -> None:
    target = (root / normalize_relative_patch_path(change.file_path)).resolve()
    target.relative_to(root.resolve())
    if change.action == "delete":
        target.unlink(missing_ok=True)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(change.code_content, encoding="utf-8")


def _read_optional_text(root: Path, file_rel: str) -> str | None:
    path = (root / normalize_relative_patch_path(file_rel)).resolve(strict=False)
    try:
        path.relative_to(root.resolve(strict=True))
    except ValueError as exc:
        raise ValueError(f"path escapes workspace: {file_rel}") from exc
    if not path.exists():
        return None
    if not path.is_file():
        raise ValueError(f"changed path is not a file: {file_rel}")
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"changed file is not UTF-8 text: {file_rel}") from exc


def _unified_diff(file_rel: str, before: str | None, after: str | None) -> list[str]:
    before_lines = [] if before is None else before.splitlines(keepends=True)
    after_lines = [] if after is None else after.splitlines(keepends=True)
    return [
        line if line.endswith("\n") else f"{line}\n"
        for line in difflib.unified_diff(
            before_lines,
            after_lines,
            fromfile=f"base/{file_rel}",
            tofile=f"candidate/{file_rel}",
            lineterm="",
        )
    ]


def _safe_audit_filename(file_rel: str) -> Path:
    return Path(normalize_relative_patch_path(file_rel) + ".content_after")


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _patch_digest(patch: PatchProposal) -> str:
    payload = [
        {
            "file_path": change.file_path,
            "action": change.action,
            "code_content_sha256": _sha256_text(change.code_content),
        }
        for change in patch_file_changes(patch)
    ]
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel.startswith(".git/") or "/__pycache__/" in f"/{rel}/":
            continue
        digest.update(rel.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _resolved_safe_data_roots(split_manifest: SplitManifest | None) -> list[str]:
    if split_manifest is None:
        return []
    return [
        str(Path(root).expanduser().resolve(strict=False))
        for root in split_manifest.safe_data_roots
    ]


def _contract_result_payload(result: ContractResult) -> dict[str, Any]:
    return {
        "passed": result.passed,
        "failure_reason": result.failure_reason,
        "checks": [asdict(check) for check in result.checks],
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


__all__ = [
    "ExternalIngestResult",
    "ExternalProposalIngestor",
    "MockSmokeResult",
    "run_mock_smoke",
]
