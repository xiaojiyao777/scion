"""Strict pure schema for the private M32 ProblemSpec manifest join."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .study_manifest_controls_schema import _canonical_json_bytes
from .study_manifest_problem_spec_declaration_schema import (
    _normalize_declared_problem_spec,
    _NormalizedDeclaredProblemSpec,
)
from .study_manifest_provider_policy_schema import (
    _normalize_study_manifest_provider_policy,
    _NormalizedStudyManifestProviderPolicy,
)

_MANIFEST_SCHEMA_VERSION = (
    "scion.initial_screening_study_manifest."
    "config_subset_and_requested_provider_policy_and_problem_spec_declaration.v3"
)
_JOIN_SCHEMA_VERSION = (
    "scion.initial_screening_study_manifest_join."
    "config_subset_and_requested_provider_policy_and_problem_spec_declaration.v3"
)
_SCOPE = "CONFIG_SUBSET_AND_REQUESTED_PROVIDER_POLICY_AND_PROBLEM_SPEC_DECLARATION_ONLY"
_STATUS = (
    "CONFIG_SUBSET_AND_REQUESTED_PROVIDER_POLICY_AND_PROBLEM_SPEC_DECLARATION_JOINED"
)
_ERROR = (
    "STUDY_CONFIG_SUBSET_AND_REQUESTED_PROVIDER_POLICY_AND_"
    "PROBLEM_SPEC_DECLARATION_JOIN_INVALID"
)
_MANIFEST_MAX_BYTES = 16 << 20
_V2_MANIFEST_SCHEMA_VERSION = (
    "scion.initial_screening_study_manifest."
    "config_subset_and_requested_provider_policy.v2"
)
_V2_SCOPE = "CONFIG_SUBSET_AND_REQUESTED_PROVIDER_POLICY_ONLY"
_JOIN_LIMITATIONS = (
    "SCIENTIFIC_ENDPOINTS_NOT_EVALUATED",
    "PROBLEM_ADAPTER_UNVERIFIED",
    "RESEARCH_INPUT_UNVERIFIED",
    "RUNTIME_RESEARCH_HISTORY_CONSUMPTION_UNVERIFIED",
    "VERIFICATION_CONFIG_AND_RUNTIME_UNVERIFIED",
    "PROVIDER_CREDENTIAL_AND_ACCOUNT_IDENTITY_UNVERIFIED",
    "PROVIDER_PROCESS_NETWORK_TLS_ENVIRONMENT_UNVERIFIED",
    "REMOTE_PROVIDER_BACKEND_IDENTITY_UNVERIFIED",
    "PROVIDER_REQUEST_CODE_CONSTANTS_UNVERIFIED",
    "PROVIDER_TIMEOUT_AND_SDK_RETRY_ENFORCEMENT_UNVERIFIED",
    "LLM_CLIENT_LIFETIME_FRESHNESS_UNVERIFIED",
    "SOURCE_CARRIER_UNVERIFIED",
    "B0_CONTENT_UNVERIFIED",
    "STUDY_MANIFEST_UNVERIFIED",
    "MANIFEST_GIT_AND_PREOUTCOME_TIMING_UNVERIFIED",
    "POPULATION_FRESHNESS_UNVERIFIED",
    "ACTUAL_ARM_ROOT_LAUNCH_ORDER_UNVERIFIED",
    "EXTERNAL_HARDWALL_ENFORCEMENT_UNVERIFIED",
    "PROTOCOL_RUNNER_BACKEND_AND_RUNTIME_ENFORCEMENT_UNVERIFIED",
    "PROTOCOL_CODE_CONSTANTS_UNVERIFIED",
    "ROOT_LIFETIME_FRESHNESS_UNVERIFIED",
    "MATCHED_RESULT_UNAUTHORIZED",
    "LIVE_EXECUTION_UNAUTHORIZED",
    "STUDY_GO_UNAUTHORIZED",
)


class _StudyManifestProblemSpecSchemaError(ValueError):
    """Fixed, body-free failure at the private v3 schema boundary."""


@dataclass(frozen=True, repr=False)
class _NormalizedStudyManifestProblemSpec:
    """One v3 manifest split into frozen v2 and ProblemSpec authorities."""

    base_manifest: _NormalizedStudyManifestProviderPolicy
    declared_problem_spec: _NormalizedDeclaredProblemSpec

    def __repr__(self) -> str:
        return "_NormalizedStudyManifestProblemSpec(<redacted>)"

    __str__ = __repr__


def _normalize_study_manifest_problem_spec(
    value: Any,
) -> _NormalizedStudyManifestProblemSpec:
    """Normalize one strict v3 manifest without widening v1 or v2."""

    failed = False
    result: _NormalizedStudyManifestProblemSpec | None = None
    try:
        result = _normalize_study_manifest_problem_spec_unsafe(value)
    except Exception:  # noqa: BLE001 - sanitize the private schema boundary
        failed = True
    if failed or result is None:
        raise _StudyManifestProblemSpecSchemaError(_ERROR)
    return result


def _config_provider_problem_spec_join_result() -> dict[str, Any]:
    """Return the sole validation-success payload authorized by v3."""

    return {
        "schema_version": _JOIN_SCHEMA_VERSION,
        "status": _STATUS,
        "validated_scope": _SCOPE,
        "blocks_checked": 5,
        "arms_checked": 10,
        "limitations": list(_JOIN_LIMITATIONS),
    }


def _normalize_study_manifest_problem_spec_unsafe(
    value: Any,
) -> _NormalizedStudyManifestProblemSpec:
    _canonical_json_bytes(value, max_bytes=_MANIFEST_MAX_BYTES)
    manifest = _exact_dict(
        value,
        {
            "schema_version",
            "scope",
            "problem_id",
            "declared_provider_policy",
            "declared_problem_spec",
            "blocks",
        },
    )
    if (
        manifest["schema_version"] != _MANIFEST_SCHEMA_VERSION
        or manifest["scope"] != _SCOPE
    ):
        raise ValueError
    problem_spec = _normalize_declared_problem_spec(manifest["declared_problem_spec"])
    base_manifest = _normalize_study_manifest_provider_policy(
        {
            "schema_version": _V2_MANIFEST_SCHEMA_VERSION,
            "scope": _V2_SCOPE,
            "problem_id": manifest["problem_id"],
            "declared_provider_policy": manifest["declared_provider_policy"],
            "blocks": manifest["blocks"],
        }
    )
    if base_manifest.base_manifest.problem_id != problem_spec.problem_id:
        raise ValueError
    return _NormalizedStudyManifestProblemSpec(
        base_manifest=base_manifest,
        declared_problem_spec=problem_spec,
    )


def _exact_dict(value: Any, fields: set[str]) -> dict[str, Any]:
    if type(value) is not dict or any(type(key) is not str for key in value):
        raise TypeError
    if set(value) != fields:
        raise ValueError
    return value


__all__: tuple[str, ...] = ()
