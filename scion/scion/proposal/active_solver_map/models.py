"""Problem-generic active solver map schema for APS context tools."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class _FrozenSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EntrypointCall(_FrozenSchema):
    target_id: str = ""
    evidence: tuple[str, ...] = ()


class ActiveSolverEntrypoint(_FrozenSchema):
    id: str = ""
    file_path: str = ""
    symbol: str = ""
    summary: str = ""
    calls: tuple[EntrypointCall, ...] = ()


class EditableFileRef(_FrozenSchema):
    file_path: str = ""
    role: str = ""
    digest: str = ""
    read_budget_hint: int = Field(default=0, ge=0)


class OperatorRef(_FrozenSchema):
    id: str = ""
    symbol: str = ""
    file_path: str = ""
    order: int | None = None
    role: str = ""
    summary: str = ""
    mechanism_tags: tuple[str, ...] = ()
    telemetry_ids: tuple[str, ...] = ()


class OperatorRegistry(_FrozenSchema):
    registry_id: str = ""
    owner_file: str = ""
    owner_symbol: str = ""
    registry_kind: str = "custom"
    operators: tuple[OperatorRef, ...] = ()


class SchedulerIntegration(_FrozenSchema):
    integration_id: str = ""
    file_path: str = ""
    symbol: str = ""
    phase: str = ""
    summary: str = ""
    calls: tuple[str, ...] = ()
    guard_conditions: tuple[str, ...] = ()
    state_variables: tuple[str, ...] = ()
    telemetry_events: tuple[str, ...] = ()


class AlgorithmSliceRef(_FrozenSchema):
    slice_id: str = ""
    file_path: str = ""
    symbols: tuple[str, ...] = ()
    purpose: str = ""
    exposure_level: Literal["summary", "signature", "body", "excerpt"] = "summary"
    source_digest: str = ""
    token_estimate: int = Field(default=0, ge=0)
    redaction_reason: str | None = None


class TelemetryField(_FrozenSchema):
    field: str = ""
    role: Literal["activation", "activity", "effect", "budget", "safety", "debug"] = (
        "debug"
    )
    mechanism_id_template: str | None = None
    declared_by: str = ""


class KnownMechanismFact(_FrozenSchema):
    fact_id: str = ""
    claim: str = ""
    evidence: tuple[str, ...] = ()
    provenance: Literal["adapter", "provider", "screening_memory", "contract"] = (
        "provider"
    )


class SourcePolicy(_FrozenSchema):
    max_total_tokens: int = Field(default=0, ge=0)
    max_body_tokens_per_tool_call: int = Field(default=0, ge=0)
    allowed_files_digest: str = ""
    redaction_policy: str = "provider_declared"


class ActiveSolverMap(_FrozenSchema):
    surface: str = ""
    subject_id: str = ""
    snapshot_digest: str = ""
    entrypoints: tuple[ActiveSolverEntrypoint, ...] = ()
    editable_files: tuple[EditableFileRef, ...] = ()
    operator_registries: tuple[OperatorRegistry, ...] = ()
    scheduler_integrations: tuple[SchedulerIntegration, ...] = ()
    algorithm_slices: tuple[AlgorithmSliceRef, ...] = ()
    telemetry_fields: tuple[TelemetryField, ...] = ()
    known_mechanism_facts: tuple[KnownMechanismFact, ...] = ()
    source_policy: SourcePolicy = Field(default_factory=SourcePolicy)


class IntegrationPoint(_FrozenSchema):
    file_path: str = ""
    symbol: str = ""
    insert_policy: str = ""
    required_telemetry_pattern: str | None = None


class OperatorRegistryReadResult(_FrozenSchema):
    registry_id: str = ""
    surface: str = ""
    subject_id: str = ""
    snapshot_digest: str = ""
    owner_file: str = ""
    owner_symbol: str = ""
    registry_kind: str = "custom"
    operators: tuple[OperatorRef, ...] = ()
    integration_points: tuple[IntegrationPoint, ...] = ()


class SourcePolicyReceipt(_FrozenSchema):
    allowed: bool = False
    reason: str = ""
    remaining_budget: int = Field(default=0, ge=0)


class AlgorithmSliceReadResult(_FrozenSchema):
    slice_id: str = ""
    surface: str = ""
    subject_id: str = ""
    snapshot_digest: str = ""
    file_path: str = ""
    symbols: tuple[str, ...] = ()
    slice_kind: str = "symbol_excerpt"
    content: str = ""
    content_digest: str = ""
    line_start: int | None = None
    line_end: int | None = None
    token_estimate: int = Field(default=0, ge=0)
    why_visible: str = ""
    source_policy_receipt: SourcePolicyReceipt = Field(
        default_factory=SourcePolicyReceipt
    )
    truncated: bool = False
    max_chars: int | None = Field(default=None, ge=0)


class ReadReceipt(_FrozenSchema):
    tool_name: str = ""
    surface: str = ""
    subject_id: str = ""
    target_id: str = ""
    snapshot_digest: str = ""
    digest: str = ""
    content_digest: str | None = None
    available: bool = True


class UnavailableReason(_FrozenSchema):
    reason: str = ""
    provider_hook: str = ""
    status: Literal["unavailable"] = "unavailable"


def model_payload(value: BaseModel | dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return dict(value)


__all__ = [
    "ActiveSolverEntrypoint",
    "ActiveSolverMap",
    "AlgorithmSliceReadResult",
    "AlgorithmSliceRef",
    "EditableFileRef",
    "EntrypointCall",
    "IntegrationPoint",
    "KnownMechanismFact",
    "OperatorRef",
    "OperatorRegistry",
    "OperatorRegistryReadResult",
    "ReadReceipt",
    "SchedulerIntegration",
    "SourcePolicy",
    "SourcePolicyReceipt",
    "TelemetryField",
    "UnavailableReason",
    "model_payload",
]
