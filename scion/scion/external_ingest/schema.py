"""Manifest schema for external proposal/workspace ingestion.

The manifest is tainted input. It is only used to construct Scion-native
proposal objects and audit metadata; Contract/verification/protocol layers
remain authoritative.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from scion.core.models import (
    HypothesisProposal,
    MechanismChange,
    PatchFileChange,
)
from scion.core.paths import normalize_relative_patch_path


class _StrictBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExternalMechanismChange(_StrictBase):
    id: str
    change_type: Literal["add", "modify", "replace", "remove", "integrate"]


class ExternalHypothesis(_StrictBase):
    hypothesis_text: str
    change_locus: str
    action: Literal["modify", "create_new", "remove"]
    target_file: str | None = None
    predicted_direction: Literal["improve", "tradeoff", "exploratory"] = "exploratory"
    target_weakness: str = ""
    expected_effect: str = ""
    target_objectives: list[str] = Field(default_factory=list)
    protected_objectives: list[str] = Field(default_factory=list)
    objective_tradeoff_policy: str = ""
    no_op_condition: str = ""
    risk_to_higher_priority: str = ""
    target_runtime_effect: str | None = None
    complexity_claim: str | None = None
    runtime_budget_strategy: str | None = None
    expected_telemetry: dict[str, Any] = Field(default_factory=dict)
    novelty_signature: dict[str, Any] = Field(default_factory=dict)
    mechanism_changes: list[ExternalMechanismChange] = Field(default_factory=list)

    def to_proposal(self) -> HypothesisProposal:
        return HypothesisProposal(
            hypothesis_text=self.hypothesis_text,
            change_locus=self.change_locus,
            action=self.action,
            target_file=self.target_file,
            predicted_direction=self.predicted_direction,
            target_weakness=self.target_weakness,
            expected_effect=self.expected_effect,
            target_objectives=tuple(self.target_objectives),
            protected_objectives=tuple(self.protected_objectives),
            objective_tradeoff_policy=self.objective_tradeoff_policy,
            no_op_condition=self.no_op_condition,
            risk_to_higher_priority=self.risk_to_higher_priority,
            target_runtime_effect=self.target_runtime_effect,
            complexity_claim=self.complexity_claim,
            runtime_budget_strategy=self.runtime_budget_strategy,
            expected_telemetry=dict(self.expected_telemetry),
            novelty_signature=dict(self.novelty_signature),
            mechanism_changes=tuple(
                MechanismChange(id=change.id, change_type=change.change_type)
                for change in self.mechanism_changes
            ),
        )


class ExternalInlineFileChange(_StrictBase):
    file_path: str
    action: Literal["modify", "create", "delete"]
    content_after: str | None = None
    test_hint: str | None = None

    @model_validator(mode="after")
    def validate_path_and_content(self) -> "ExternalInlineFileChange":
        normalize_relative_patch_path(self.file_path)
        if self.action != "delete" and self.content_after in (None, ""):
            raise ValueError("inline content_after is required unless action=delete")
        return self

    def to_patch_change(self) -> PatchFileChange:
        return PatchFileChange(
            file_path=normalize_relative_patch_path(self.file_path),
            action=self.action,
            code_content="" if self.action == "delete" else str(self.content_after),
            test_hint=self.test_hint,
        )


class ExternalPatchSource(_StrictBase):
    type: Literal["workspace", "unified_diff", "inline"]
    workspace_path: str | None = None
    patch_path: str | None = None
    changed_files: list[str] = Field(default_factory=list)
    inline_changes: list[ExternalInlineFileChange] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_source_shape(self) -> "ExternalPatchSource":
        if self.type == "workspace" and not self.workspace_path:
            raise ValueError("source.workspace_path is required when type=workspace")
        if self.type == "unified_diff" and not self.patch_path:
            raise ValueError("source.patch_path is required when type=unified_diff")
        if self.type == "inline" and not self.inline_changes:
            raise ValueError("source.inline_changes is required when type=inline")
        if self.type in {"workspace", "unified_diff"} and not self.changed_files:
            raise ValueError(
                "source.changed_files is required for workspace/unified_diff sources"
            )

        normalized = [normalize_relative_patch_path(path) for path in self.changed_files]
        duplicates = sorted({path for path in normalized if normalized.count(path) > 1})
        if duplicates:
            raise ValueError(
                "source.changed_files must not contain duplicates: "
                + ", ".join(duplicates)
            )
        object.__setattr__(self, "changed_files", normalized)
        return self


class ExternalBaseLineage(_StrictBase):
    champion_id: str
    workspace_path: str | None = None
    branch_id: str | None = None
    lineage_id: str | None = None
    branch_name: str | None = None
    code_hash: str | None = None


class ExternalProvenance(_StrictBase):
    external_agent: str
    run_id: str
    source_uri: str | None = None
    artifact_uri: str | None = None
    notes: dict[str, Any] = Field(default_factory=dict)


class ExternalBoundaryDigest(_StrictBase):
    objective_digest: str
    constraint_digest: str
    problem_spec_digest: str | None = None
    protocol_digest: str | None = None
    split_manifest_digest: str | None = None


class ExternalProposalManifest(_StrictBase):
    schema_version: Literal["scion.external_proposal.v1"] = "scion.external_proposal.v1"
    hypothesis: ExternalHypothesis
    source: ExternalPatchSource
    base_champion: ExternalBaseLineage
    provenance: ExternalProvenance
    declared_boundary: ExternalBoundaryDigest
    manifest_notes: dict[str, Any] = Field(default_factory=dict)


def load_external_manifest(path: str | Path) -> ExternalProposalManifest:
    manifest_path = Path(path).expanduser().resolve(strict=True)
    with open(manifest_path, encoding="utf-8") as f:
        if manifest_path.suffix.lower() == ".json":
            import json

            data = json.load(f)
        else:
            data = yaml.safe_load(f)
    return ExternalProposalManifest.model_validate(data)


__all__ = [
    "ExternalBaseLineage",
    "ExternalBoundaryDigest",
    "ExternalHypothesis",
    "ExternalInlineFileChange",
    "ExternalMechanismChange",
    "ExternalPatchSource",
    "ExternalProposalManifest",
    "ExternalProvenance",
    "load_external_manifest",
]
