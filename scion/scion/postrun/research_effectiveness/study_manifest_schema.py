"""Strict pure manifest schema for the private M32 config-subset join."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .study_manifest_controls_schema import (
    _canonical_json_bytes,
    _freeze_json,
    _normalize_controls_unsafe,
    _NormalizedStudyControls,
    _validate_code_limits,
    _validate_resource,
)

_MANIFEST_SCHEMA_VERSION = "scion.initial_screening_study_manifest.config_subset.v1"
_JOIN_SCHEMA_VERSION = "scion.initial_screening_study_manifest_join.config_subset.v1"
_SCOPE = "CONFIG_SUBSET_ONLY"
_ERROR = "STUDY_CONFIG_SUBSET_JOIN_INVALID"
_MANIFEST_MAX_BYTES = 16 << 20
_HISTORY_UNAVAILABLE = "HISTORY_REPLAY_BASIS_UNAVAILABLE"
_TREATMENTS = frozenset({"K1", "K2"})
_PROBLEM_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,127}$")
_JOIN_LIMITATIONS = (
    "SCIENTIFIC_ENDPOINTS_NOT_EVALUATED",
    "PROBLEM_SPEC_UNVERIFIED",
    "PROBLEM_ADAPTER_UNVERIFIED",
    "RESEARCH_INPUT_UNVERIFIED",
    "RUNTIME_RESEARCH_HISTORY_CONSUMPTION_UNVERIFIED",
    "VERIFICATION_CONFIG_AND_RUNTIME_UNVERIFIED",
    "PROVIDER_REQUEST_POLICY_UNVERIFIED",
    "REMOTE_PROVIDER_BACKEND_IDENTITY_UNVERIFIED",
    "SOURCE_CARRIER_UNVERIFIED",
    "B0_CONTENT_UNVERIFIED",
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


class _StudyManifestSchemaError(ValueError):
    """Fixed, body-free failure at the private manifest schema boundary."""


@dataclass(frozen=True, repr=False)
class _NormalizedLoadedHistory:
    """One manifest-owned available or typed-unavailable replay basis."""

    available: bool
    files: tuple[str, ...]

    def __repr__(self) -> str:
        return "_NormalizedLoadedHistory(<redacted>)"

    __str__ = __repr__


@dataclass(frozen=True, repr=False)
class _NormalizedStudyArm:
    """One ordered manifest arm with complete declared S2c1 controls."""

    treatment: str
    campaign_id: str
    root_path: str
    declared_controls: _NormalizedStudyControls

    def __repr__(self) -> str:
        return "_NormalizedStudyArm(<redacted>)"

    __str__ = __repr__


@dataclass(frozen=True, repr=False)
class _NormalizedStudyBlock:
    """One ordered two-arm block and its shared replay declaration."""

    block_ordinal: int
    loaded_history: _NormalizedLoadedHistory
    arms: tuple[_NormalizedStudyArm, _NormalizedStudyArm]

    def __repr__(self) -> str:
        return "_NormalizedStudyBlock(<redacted>)"

    __str__ = __repr__


@dataclass(frozen=True, repr=False)
class _NormalizedStudyManifest:
    """One exact-five, immutable, validation-only manifest projection."""

    problem_id: str
    blocks: tuple[
        _NormalizedStudyBlock,
        _NormalizedStudyBlock,
        _NormalizedStudyBlock,
        _NormalizedStudyBlock,
        _NormalizedStudyBlock,
    ]

    def __repr__(self) -> str:
        return "_NormalizedStudyManifest(<redacted>)"

    __str__ = __repr__


@dataclass(frozen=True, repr=False)
class _StudyExpectationFacts:
    """Private identity-bearing manifest facts, never an output projection."""

    problem_id: str
    expected_initial_case_count: int
    expected_initial_pair_count: int
    a_cap: int
    p_cap: int
    max_hypothesis_candidates: int
    case_refs: tuple[str, ...]
    seeds: tuple[int, ...]
    equivalence_band: float

    def __repr__(self) -> str:
        return "_StudyExpectationFacts(<redacted>)"

    __str__ = __repr__


def _normalize_study_manifest(value: Any) -> _NormalizedStudyManifest:
    """Normalize one strict exact-five manifest without retaining aliases."""

    failed = False
    result: _NormalizedStudyManifest | None = None
    try:
        result = _normalize_study_manifest_unsafe(value)
    except Exception:  # noqa: BLE001 - sanitize the private schema boundary
        failed = True
    if failed or result is None:
        raise _StudyManifestSchemaError(_ERROR)
    return result


def _normalize_root_controls(value: Any) -> _NormalizedStudyControls:
    """Normalize one complete root controls payload at a fixed error boundary."""

    failed = False
    result: _NormalizedStudyControls | None = None
    try:
        result = _normalize_controls_unsafe(value)
    except Exception:  # noqa: BLE001 - sanitize the private schema boundary
        failed = True
    if failed or result is None:
        raise _StudyManifestSchemaError(_ERROR)
    return result


def _validate_root_control_join(
    arm: _NormalizedStudyArm,
    root_controls: _NormalizedStudyControls,
    code_limits: Any,
    resource_envelope: Any,
) -> _NormalizedStudyControls:
    """Join one arm declaration to its root and two independent subsets."""

    failed = False
    result: _NormalizedStudyControls | None = None
    try:
        result = _validate_root_control_join_unsafe(
            arm,
            root_controls,
            code_limits,
            resource_envelope,
        )
    except Exception:  # noqa: BLE001 - sanitize the private schema boundary
        failed = True
    if failed or result is None:
        raise _StudyManifestSchemaError(_ERROR)
    return result


def _derive_expectation(
    problem_id: str,
    controls: _NormalizedStudyControls,
) -> _StudyExpectationFacts:
    """Derive private identity-bearing inputs for the S2a expectation."""

    failed = False
    result: _StudyExpectationFacts | None = None
    try:
        if type(controls) is not _NormalizedStudyControls:
            raise TypeError
        result = _StudyExpectationFacts(
            problem_id=_identity_token(problem_id),
            expected_initial_case_count=len(controls.case_refs),
            expected_initial_pair_count=len(controls.case_refs) * len(controls.seeds),
            a_cap=controls.a_cap,
            p_cap=controls.p_cap,
            max_hypothesis_candidates=controls.k,
            case_refs=controls.case_refs,
            seeds=controls.seeds,
            equivalence_band=controls.equivalence_band,
        )
    except Exception:  # noqa: BLE001 - sanitize the private schema boundary
        failed = True
    if failed or result is None:
        raise _StudyManifestSchemaError(_ERROR)
    return result


def _config_subset_join_result() -> dict[str, Any]:
    """Return the sole validation-success payload authorized by this layer."""

    return {
        "schema_version": _JOIN_SCHEMA_VERSION,
        "status": "CONFIG_SUBSET_JOINED",
        "validated_scope": _SCOPE,
        "blocks_checked": 5,
        "arms_checked": 10,
        "limitations": list(_JOIN_LIMITATIONS),
    }


def _normalize_study_manifest_unsafe(value: Any) -> _NormalizedStudyManifest:
    _canonical_json_bytes(value, max_bytes=_MANIFEST_MAX_BYTES)
    manifest = _exact_dict(
        value,
        {"schema_version", "scope", "problem_id", "blocks"},
    )
    if (
        manifest["schema_version"] != _MANIFEST_SCHEMA_VERSION
        or manifest["scope"] != _SCOPE
    ):
        raise ValueError
    problem_id = _identity_token(manifest["problem_id"])
    raw_blocks = _exact_list(manifest["blocks"])
    if len(raw_blocks) != 5:
        raise ValueError
    blocks = tuple(
        _normalize_block(raw_block, ordinal)
        for ordinal, raw_block in enumerate(raw_blocks, start=1)
    )
    roots = tuple(arm.root_path for block in blocks for arm in block.arms)
    campaigns = tuple(arm.campaign_id for block in blocks for arm in block.arms)
    if len(set(campaigns)) != 10:
        raise ValueError
    _validate_separate_relative_roots(roots)
    _validate_declared_control_set(blocks)
    first_k1 = sum(block.arms[0].treatment == "K1" for block in blocks)
    if first_k1 not in {2, 3}:
        raise ValueError
    return _NormalizedStudyManifest(
        problem_id=problem_id,
        blocks=blocks,  # type: ignore[arg-type]
    )


def _validate_root_control_join_unsafe(
    arm: _NormalizedStudyArm,
    root_controls: _NormalizedStudyControls,
    code_limits: Any,
    resource_envelope: Any,
) -> _NormalizedStudyControls:
    if (
        type(arm) is not _NormalizedStudyArm
        or type(root_controls) is not _NormalizedStudyControls
        or arm.declared_controls.frozen != root_controls.frozen
        or arm.declared_controls.canonical_bytes != root_controls.canonical_bytes
    ):
        raise TypeError
    normalized_limits = _validate_code_limits(code_limits)
    normalized_resource = _validate_resource(resource_envelope)
    if (
        _freeze_json(normalized_limits) != root_controls.code_research_limits
        or _freeze_json(normalized_resource) != root_controls.resource_envelope
    ):
        raise ValueError
    return root_controls


def _normalize_block(value: Any, ordinal: int) -> _NormalizedStudyBlock:
    block = _exact_dict(value, {"block_ordinal", "loaded_history", "arms"})
    if type(block["block_ordinal"]) is not int or block["block_ordinal"] != ordinal:
        raise ValueError
    history = _normalize_history_spec(block["loaded_history"])
    raw_arms = _exact_list(block["arms"])
    if len(raw_arms) != 2:
        raise ValueError
    arms = tuple(_normalize_arm(raw_arm) for raw_arm in raw_arms)
    if {arm.treatment for arm in arms} != _TREATMENTS:
        raise ValueError
    for arm in arms:
        expected_k = 1 if arm.treatment == "K1" else 2
        if arm.declared_controls.k != expected_k:
            raise ValueError
    return _NormalizedStudyBlock(
        block_ordinal=ordinal,
        loaded_history=history,
        arms=arms,  # type: ignore[arg-type]
    )


def _normalize_history_spec(value: Any) -> _NormalizedLoadedHistory:
    if type(value) is not dict:
        raise TypeError
    availability = value.get("availability")
    if availability == "available":
        history = _exact_dict(value, {"availability", "files"})
        raw_files = _exact_list(history["files"])
        if len(raw_files) > 16:
            raise ValueError
        files = tuple(_relative_token(item, suffix=".jsonl") for item in raw_files)
        if len(files) != len(set(files)):
            raise ValueError
        return _NormalizedLoadedHistory(available=True, files=files)
    if availability == "unavailable":
        history = _exact_dict(value, {"availability", "reason"})
        if history["reason"] != _HISTORY_UNAVAILABLE:
            raise ValueError
        return _NormalizedLoadedHistory(available=False, files=())
    raise ValueError


def _normalize_arm(value: Any) -> _NormalizedStudyArm:
    arm = _exact_dict(
        value,
        {"treatment", "campaign_id", "root_path", "declared_controls"},
    )
    treatment = arm["treatment"]
    if type(treatment) is not str or treatment not in _TREATMENTS:
        raise ValueError
    return _NormalizedStudyArm(
        treatment=treatment,
        campaign_id=_campaign_id(arm["campaign_id"]),
        root_path=_relative_token(arm["root_path"]),
        declared_controls=_normalize_controls_unsafe(arm["declared_controls"]),
    )


def _validate_declared_control_set(
    blocks: tuple[_NormalizedStudyBlock, ...],
) -> None:
    controls = tuple(arm.declared_controls for block in blocks for arm in block.arms)
    for block in blocks:
        if block.arms[0].declared_controls.pair_key != (
            block.arms[1].declared_controls.pair_key
        ):
            raise ValueError
    if any(
        control.cross_block_key != controls[0].cross_block_key for control in controls
    ):
        raise ValueError
    observed_cells: set[tuple[str, int]] = set()
    for block in blocks:
        cells = set(block.arms[0].declared_controls.development_cells)
        if not cells or observed_cells.intersection(cells):
            raise ValueError
        observed_cells.update(cells)


def _exact_dict(value: Any, fields: set[str] | frozenset[str]) -> dict[str, Any]:
    if type(value) is not dict or set(value) != fields:
        raise TypeError
    return value


def _exact_list(value: Any) -> list[Any]:
    if type(value) is not list:
        raise TypeError
    return value


def _relative_token(value: Any, *, suffix: str | None = None) -> str:
    if type(value) is not str or not value or "\x00" in value or "\\" in value:
        raise TypeError
    encoded = value.encode("utf-8")
    parts = value.split("/")
    if (
        value.startswith("/")
        or len(encoded) > 4096
        or len(parts) > 128
        or any(
            part in {"", ".", ".."} or len(part.encode("utf-8")) > 255 for part in parts
        )
        or (suffix is not None and not value.endswith(suffix))
    ):
        raise ValueError
    return value


def _identity_token(value: Any) -> str:
    if type(value) is not str or _PROBLEM_ID_RE.fullmatch(value) is None:
        raise ValueError
    return value


def _campaign_id(value: Any) -> str:
    if (
        type(value) is not str
        or not value
        or value != value.strip()
        or len(value) > 256
        or not value.isprintable()
    ):
        raise ValueError
    return value


def _validate_separate_relative_roots(roots: tuple[str, ...]) -> None:
    if len(roots) != 10 or len(set(roots)) != 10:
        raise ValueError
    parts = tuple(tuple(root.split("/")) for root in roots)
    for index, left in enumerate(parts):
        for right in parts[index + 1 :]:
            common = min(len(left), len(right))
            if left[:common] == right[:common]:
                raise ValueError


__all__: tuple[str, ...] = ()
