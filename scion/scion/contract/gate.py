"""ContractGate: static validation of HypothesisProposal and PatchProposal."""
from __future__ import annotations

import ast
import hashlib
import json
import time
import weakref
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, List, Mapping

from scion.config.problem import ProblemSpec
from scion.core.operator_interface import parse_execute_signature
from scion.core.path_match import normalize_relative_glob_pattern
from scion.core.paths import normalize_relative_patch_path
from scion.core.models import (
    CheckResult,
    ContractResult,
    HypothesisProposal,
    HypothesisRecord,
    PatchProposal,
    patch_file_changes,
)
from scion.contract.checks.solver_design_integration import (
    check_solver_design_integration,
)
from scion.contract.capability_owner import (
    ContractProblemCapabilities,
    resolve_contract_problem_capabilities,
)
from scion.contract.checks.identity import check_surface_instance_identity
from scion.contract.checks.randomness import check_non_rng_random
from scion.contract.checks.security import (
    check_import_whitelist,
    check_sensitive_api,
)
from scion.contract.checks.targeting import (
    check_file_whitelist,
    check_frozen_files,
    check_patch_action_target,
)
from scion.contract.hypothesis_checks import (
    check_action_target,
    check_change_locus,
    check_governance_constraints,
    check_hypothesis_schema,
)
from scion.contract.patch_graph import PatchSetGraph
from scion.contract.result_payload import (
    build_result as _build_result,
    check_result as _cr,
    prefix_checks as _prefix_checks,
)
from scion.contract.surface_access import SurfaceAccess
from scion.contract.surface_interface import check_surface_interface
from scion.contract.patch_paths import matches_config_pattern
from scion.problem.spec import SUPPORTED_RESEARCH_SURFACE_KINDS
from scion.proposal import hypothesis_generation_authority as _generation
from scion.problem.providers import (
    active_subject_policy_matches_path,
)


_HYPOTHESIS_CONTRACT_PROTOCOL_GENERATION = "hypothesis-contract.v1"
_HYPOTHESIS_PROPOSAL_KEYS = frozenset(
    {
        "hypothesis_text",
        "change_locus",
        "action",
        "target_file",
        "predicted_direction",
        "target_weakness",
        "expected_effect",
        "suggested_weight",
    }
)


class HypothesisContractUnknownError(RuntimeError):
    """An unexpected failure occurred after the exact result was claimed."""


@dataclass(frozen=True, slots=True)
class _FrozenResearchSurface:
    name: str
    kind: str
    target_files: tuple[str, ...]
    create_new_allowed: bool
    modify_allowed: bool
    remove_allowed: bool
    contract_visible: bool


@dataclass(frozen=True, slots=True)
class _FrozenHypothesisContractConfig:
    operator_categories: tuple[str, ...]
    research_surfaces: tuple[_FrozenResearchSurface, ...]
    canonical_json: bytes
    digest: str
    protocol_generation: str = _HYPOTHESIS_CONTRACT_PROTOCOL_GENERATION


@dataclass(frozen=True, slots=True)
class _DetachedGovernanceEnvelope:
    primitive: dict[str, Any]

    def to_primitive(self) -> dict[str, Any]:
        return self.primitive


def _canonical_json_bytes(value: object, *, label: str) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, RecursionError, UnicodeEncodeError) as exc:
        raise ValueError(f"{label} cannot be canonically encoded") from exc


def _freeze_hypothesis_contract_config(
    problem_spec: ProblemSpec,
) -> _FrozenHypothesisContractConfig:
    raw_categories = getattr(problem_spec, "operator_categories", ())
    if type(raw_categories) not in (list, tuple) or any(
        type(value) is not str or not value or value != value.strip()
        for value in raw_categories
    ):
        raise TypeError(
            "hypothesis contract operator_categories must be exact nonempty strings"
        )
    categories = tuple(raw_categories)
    raw_surfaces = getattr(problem_spec, "research_surfaces", []) or []
    if type(raw_surfaces) not in (list, tuple):
        raise TypeError("hypothesis contract research_surfaces must be a sequence")

    def _has(raw: object, name: str) -> bool:
        return name in raw if isinstance(raw, Mapping) else hasattr(raw, name)

    def _get(raw: object, name: str, default: object = None) -> object:
        return raw.get(name, default) if isinstance(raw, Mapping) else getattr(
            raw,
            name,
            default,
        )

    surfaces: list[_FrozenResearchSurface] = []
    for raw in raw_surfaces:
        if not isinstance(raw, Mapping) and not hasattr(raw, "name"):
            raise TypeError(
                "hypothesis contract research surface must be an object or mapping"
            )
        name = _get(raw, "name", "")
        kind = _get(raw, "kind", "")
        if (
            type(name) is not str
            or not name
            or name != name.strip()
            or type(kind) is not str
            or not kind
            or kind != kind.strip()
        ):
            raise TypeError(
                "hypothesis contract research surface name/kind must be exact text"
            )
        contract_visible = not isinstance(raw, Mapping)
        targets = _get(raw, "targets", None)
        if targets is not None and not isinstance(targets, Mapping) and not hasattr(
            targets,
            "files",
        ):
            raise TypeError(
                "hypothesis contract research surface targets must be an object"
            )
        # SurfaceAccess is the public Contract behavior we must freeze, not
        # reinterpret.  It reads only attributes: a mapping surface is not a
        # visible C2/C3 surface, and a mapping-valued ``targets`` member falls
        # back to the legacy surface-level fields.
        effective_targets = (
            targets
            if contract_visible
            and targets is not None
            and not isinstance(targets, Mapping)
            else None
        )
        files = (
            getattr(effective_targets, "files", None)
            if effective_targets is not None
            else None
        )
        if files is None:
            files = _get(raw, "target_files", []) or []
        if type(files) not in (list, tuple):
            raise TypeError(
                "hypothesis contract target files must be a sequence"
            )
        normalized_files: list[str] = []
        for path in files:
            # Match the legacy leading-slash compatibility, but reject every
            # other ambiguous/invalid glob at composition.  The frozen digest
            # therefore binds matching semantics, not caller spelling.
            if type(path) is not str:
                raise ValueError(
                    f"invalid hypothesis contract target pattern {path!r}"
                )
            text = path
            try:
                normalized_files.append(
                    normalize_relative_glob_pattern(text.lstrip("/"))
                )
            except ValueError as exc:
                raise ValueError(
                    f"invalid hypothesis contract target pattern {text!r}"
                ) from exc
        action_values: dict[str, bool] = {}
        for attr in (
            "create_new_allowed",
            "modify_allowed",
            "remove_allowed",
        ):
            if effective_targets is not None and hasattr(effective_targets, attr):
                action = getattr(effective_targets, attr)
            elif _has(raw, attr):
                action = _get(raw, attr)
            else:
                # Preserve the existing fallback semantics: an absent action
                # flag does not invent a new Contract rejection.
                action = True
            action_values[attr] = bool(action)
        surfaces.append(
            _FrozenResearchSurface(
                name=name,
                kind=kind,
                target_files=tuple(normalized_files),
                create_new_allowed=action_values["create_new_allowed"],
                modify_allowed=action_values["modify_allowed"],
                remove_allowed=action_values["remove_allowed"],
                contract_visible=contract_visible,
            )
        )
    payload = {
        "operator_categories": list(categories),
        "protocol_generation": _HYPOTHESIS_CONTRACT_PROTOCOL_GENERATION,
        "research_surfaces": [
            {
                "name": surface.name,
                "kind": surface.kind,
                "target_files": list(surface.target_files),
                "create_new_allowed": surface.create_new_allowed,
                "modify_allowed": surface.modify_allowed,
                "remove_allowed": surface.remove_allowed,
                "contract_visible": surface.contract_visible,
            }
            for surface in surfaces
        ],
        "schema_version": "frozen-hypothesis-contract-config.v1",
    }
    canonical = _canonical_json_bytes(payload, label="hypothesis contract config")
    return _FrozenHypothesisContractConfig(
        operator_categories=categories,
        research_surfaces=tuple(surfaces),
        canonical_json=canonical,
        digest=hashlib.sha256(canonical).hexdigest(),
    )


def _decode_canonical_object(
    value: bytes,
    *,
    label: str,
) -> dict[str, Any]:
    def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        decoded: dict[str, Any] = {}
        for key, item in pairs:
            if key in decoded:
                raise ValueError(f"{label} contains duplicate key {key!r}")
            decoded[key] = item
        return decoded

    def _constant(raw: str) -> None:
        raise ValueError(f"{label} contains non-finite constant {raw!r}")

    if type(value) is not bytes or not value:
        raise ValueError(f"{label} must be exact nonempty bytes")
    try:
        decoded = json.loads(
            value.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is malformed") from exc
    if type(decoded) is not dict:
        raise ValueError(f"{label} must contain an object")
    expected = _canonical_json_bytes(decoded, label=label)
    if expected != value:
        raise ValueError(f"{label} is not canonical")
    return decoded


def _decode_hypothesis_proposal(value: bytes) -> HypothesisProposal:
    payload = _decode_canonical_object(value, label="generated hypothesis proposal")
    if frozenset(payload) != _HYPOTHESIS_PROPOSAL_KEYS:
        raise ValueError("generated hypothesis proposal has unexpected fields")
    return HypothesisProposal(**payload)


def _contract_result_digest(result: ContractResult) -> str:
    payload = {
        "checks": [
            {
                "detail": check.detail,
                "elapsed_ms": check.elapsed_ms,
                "metadata": check.metadata,
                "name": check.name,
                "passed": check.passed,
                "severity": check.severity,
            }
            for check in result.checks
        ],
        "failure_reason": result.failure_reason,
        "passed": result.passed,
        "schema_version": "hypothesis-contract-result.v1",
    }
    return hashlib.sha256(
        _canonical_json_bytes(payload, label="hypothesis contract result")
    ).hexdigest()

def _normalize_source_overrides(
    source_overrides: Mapping[str, str] | None,
) -> dict[str, str]:
    if not source_overrides:
        return {}
    normalized: dict[str, str] = {}
    for raw_path, content in source_overrides.items():
        if not isinstance(content, str):
            continue
        try:
            file_rel = normalize_relative_patch_path(str(raw_path))
        except ValueError:
            continue
        normalized[file_rel] = content
    return normalized


def _syntax_source_detail(source: str) -> str:
    lines = str(source or "").splitlines()
    if not lines:
        return "<empty>"
    return " | ".join(
        f"{index}: {line!r}"
        for index, line in enumerate(lines, start=1)
    )


class ContractGate:
    """Static gate that validates proposals before any code is executed."""

    def __init__(
        self,
        problem_spec: ProblemSpec,
        *,
        operator_execute_signature: str | None = None,
        champion_snapshot_path: str | None = None,
        champion_snapshot_provider: Callable[[], str | None] | None = None,
        source_overrides: Mapping[str, str] | None = None,
        adapter: Any = None,
    ) -> None:
        self._spec = problem_spec
        self._adapter = adapter
        self._operator_signature = parse_execute_signature(operator_execute_signature)
        self._champion_snapshot_path = champion_snapshot_path
        self._champion_snapshot_provider = champion_snapshot_provider
        self._source_overrides = _normalize_source_overrides(source_overrides)
        self._surface_access = SurfaceAccess(problem_spec)
        self.__frozen_hypothesis_config = _freeze_hypothesis_contract_config(
            problem_spec
        )
        self.__hypothesis_generation_authority: (
            _generation._AuthorityHandle | None
        ) = None
        self.__returned_hypothesis_results: weakref.WeakSet[
            _generation.GeneratedHypothesisResult
        ] = weakref.WeakSet()

    @property
    def hypothesis_contract_config_digest(self) -> str:
        return self.__frozen_hypothesis_config.digest

    @property
    def hypothesis_contract_protocol_generation(self) -> str:
        return self.__frozen_hypothesis_config.protocol_generation

    def _install_hypothesis_generation_authority(
        self,
        authority: _generation._AuthorityHandle,
    ) -> None:
        if self.__hypothesis_generation_authority is not None:
            raise _generation.HypothesisGenerationLifecycleError(
                "ContractGate generation authority is already installed"
            )
        _generation._require_authority(
            authority,
            role=_generation._AuthorityRole.CONTRACT_GATE,
            owner=self,
        )
        self.__hypothesis_generation_authority = authority

    def _require_hypothesis_generation_authority(
        self,
    ) -> _generation._AuthorityHandle:
        authority = self.__hypothesis_generation_authority
        if authority is None:
            raise _generation.InvalidHypothesisGenerationCapabilityError(
                "ContractGate generation authority is not installed"
            )
        _generation._require_authority(
            authority,
            role=_generation._AuthorityRole.CONTRACT_GATE,
            owner=self,
        )
        return authority

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate_hypothesis(
        self,
        hypothesis: HypothesisProposal,
        *,
        governance_envelope: Any | None = None,
    ) -> ContractResult:
        """Validate the provider hypothesis against host-owned boundaries."""
        checks: List[CheckResult] = []

        checks.append(
            check_governance_constraints(
                hypothesis,
                governance_envelope=governance_envelope,
            )
        )
        checks.append(self._c1_schema(hypothesis))
        checks.append(self._c2_change_locus(hypothesis))
        checks.append(self._c3_action_target(hypothesis))
        return _build_result(checks)

    def validate_generated_hypothesis(
        self,
        result: _generation.GeneratedHypothesisResult,
    ) -> (
        _generation.HypothesisContractApproval
        | _generation.HypothesisContractRejection
    ):
        """Claim and validate one exact generated result against frozen C0-C3."""

        authority = self._require_hypothesis_generation_authority()
        config = self.__frozen_hypothesis_config
        try:
            claimed = _generation._claim_generated_result_for_contract(
                authority,
                result,
                contract_config_digest=config.digest,
                contract_protocol_generation=config.protocol_generation,
            )
            hypothesis = _decode_hypothesis_proposal(
                claimed.result_projection.proposal_canonical_bytes
            )
            governance = _decode_canonical_object(
                claimed.c0_governance_json,
                label="detached C0 governance",
            )
            checks = [
                check_governance_constraints(
                    hypothesis,
                    governance_envelope=_DetachedGovernanceEnvelope(governance),
                ),
                self._frozen_c1_schema(hypothesis),
                self._frozen_c2_change_locus(hypothesis),
                self._frozen_c3_action_target(hypothesis),
            ]
            contract_result = _build_result(checks)
            digest = _contract_result_digest(contract_result)
            issuer = (
                _generation._issue_hypothesis_contract_approval
                if contract_result.passed
                else _generation._issue_hypothesis_contract_rejection
            )
            decision = issuer(
                authority,
                result,
                contract_result=contract_result,
                contract_result_digest=digest,
                contract_config_digest=config.digest,
                contract_protocol_generation=config.protocol_generation,
            )
            self.__returned_hypothesis_results.add(result)
            return decision
        except BaseException as exc:
            if result in self.__returned_hypothesis_results:
                raise
            postclaim = False
            try:
                postclaim = _generation._finish_hypothesis_contract_unknown(
                    authority,
                    result,
                )
            except BaseException as cleanup:
                if hasattr(exc, "add_note"):
                    exc.add_note(
                        "Contract claim-fault settlement also failed: "
                        f"{type(cleanup).__name__}: {cleanup}"
                    )
            if not postclaim:
                raise
            if not isinstance(exc, Exception):
                raise
            raise HypothesisContractUnknownError(
                "hypothesis contract validation failed unexpectedly after claim"
            ) from exc

    def _frozen_c1_schema(self, h: HypothesisProposal) -> CheckResult:
        t0 = time.monotonic_ns()
        passed = True
        detail = "schema ok"
        if not h.hypothesis_text or not h.hypothesis_text.strip():
            passed = False
            detail = "hypothesis_text is empty"
        elif not h.change_locus or not h.change_locus.strip():
            passed = False
            detail = "change_locus is empty"
        elif h.action not in ("modify", "create_new", "remove"):
            passed = False
            detail = f"action '{h.action}' is not valid"
        elif h.predicted_direction not in (
            "improve",
            "tradeoff",
            "exploratory",
        ):
            passed = False
            detail = "predicted_direction must be one of improve/tradeoff/exploratory"
        return _cr("C1_schema", passed, "heavy", detail, t0)

    def _frozen_surface(self, name: str) -> _FrozenResearchSurface | None:
        for surface in self.__frozen_hypothesis_config.research_surfaces:
            if surface.contract_visible and surface.name == name:
                return surface
        return None

    def _frozen_c2_change_locus(self, h: HypothesisProposal) -> CheckResult:
        t0 = time.monotonic_ns()
        categories = self.__frozen_hypothesis_config.operator_categories
        passed = h.change_locus in categories
        if passed:
            surface = self._frozen_surface(h.change_locus)
            if (
                surface is not None
                and surface.kind not in SUPPORTED_RESEARCH_SURFACE_KINDS
            ):
                allowed = ", ".join(sorted(SUPPORTED_RESEARCH_SURFACE_KINDS))
                return _cr(
                    "C2_change_locus",
                    False,
                    "heavy",
                    f"unsupported research surface kind '{surface.kind}' for "
                    f"surface '{surface.name}', expected one of: {allowed}",
                    t0,
                )
        detail = (
            "change_locus ok"
            if passed
            else f"change_locus '{h.change_locus}' not in research loci "
            f"{list(categories)}"
        )
        return _cr("C2_change_locus", passed, "heavy", detail, t0)

    @staticmethod
    def _frozen_target_matches(
        target_file: str,
        surface: _FrozenResearchSurface,
    ) -> bool:
        try:
            normalized = normalize_relative_patch_path(target_file)
        except ValueError:
            return False
        return any(
            matches_config_pattern(normalized, pattern)
            for pattern in surface.target_files
        )

    def _frozen_c3_action_target(self, h: HypothesisProposal) -> CheckResult:
        t0 = time.monotonic_ns()
        surface = self._frozen_surface(h.change_locus)
        if surface is not None:
            if surface.kind not in SUPPORTED_RESEARCH_SURFACE_KINDS:
                allowed = ", ".join(sorted(SUPPORTED_RESEARCH_SURFACE_KINDS))
                return _cr(
                    "C3_action_target",
                    False,
                    "heavy",
                    f"unsupported research surface kind '{surface.kind}' for "
                    f"surface '{surface.name}', expected one of: {allowed}",
                    t0,
                )
            allowed_action = {
                "create_new": surface.create_new_allowed,
                "modify": surface.modify_allowed,
                "remove": surface.remove_allowed,
            }.get(h.action, False)
            if not allowed_action:
                return _cr(
                    "C3_action_target",
                    False,
                    "heavy",
                    f"action='{h.action}' is not allowed for research surface "
                    f"'{h.change_locus}'",
                    t0,
                )
        passed = True
        detail = "action-target ok"
        if h.action in ("modify", "remove"):
            if not h.target_file:
                passed = False
                detail = f"action='{h.action}' requires target_file"
            elif surface is not None and not self._frozen_target_matches(
                h.target_file,
                surface,
            ):
                passed = False
                detail = (
                    f"target_file '{h.target_file}' is not in target files "
                    f"{list(surface.target_files)}"
                )
        elif (
            h.action == "create_new"
            and h.target_file
            and surface is not None
            and not self._frozen_target_matches(h.target_file, surface)
        ):
            passed = False
            detail = (
                f"target_file '{h.target_file}' is not in target files "
                f"{list(surface.target_files)}"
            )
        return _cr("C3_action_target", passed, "heavy", detail, t0)

    def validate_patch(
        self,
        patch: PatchProposal,
        hypothesis: HypothesisProposal | HypothesisRecord | None = None,
        *,
        approved_hypothesis: HypothesisProposal | HypothesisRecord | None = None,
        selected_surface: str | None = None,
        base_snapshot_path: str | None = None,
        base_file_overrides: Mapping[str, str] | None = None,
    ) -> ContractResult:
        """Validate typed patch ownership, syntax, interface, and safety."""
        checks: List[CheckResult] = []
        base_file_content = self._file_content_provider(
            base_snapshot_path,
            source_overrides=base_file_overrides,
        )
        contract_hypothesis = (
            approved_hypothesis if approved_hypothesis is not None else hypothesis
        )
        selected_surface_name = (
            self._selected_surface_name(contract_hypothesis) or selected_surface
        )
        patch_graph = PatchSetGraph.from_patch(patch)
        file_changes = patch_file_changes(patch)
        additional_change_files = tuple(change.file_path for change in file_changes[1:])
        capabilities = resolve_contract_problem_capabilities(
            problem_spec=self._spec,
            adapter=self._adapter,
            patch=patch,
            selected_surface=selected_surface_name,
        )
        for index, change in enumerate(file_changes):
            is_primary = index == 0
            change_patch = PatchProposal(
                file_path=change.file_path,
                action=change.action,
                code_content=change.code_content,
                test_hint=change.test_hint,
            )
            change_checks = self._validate_patch_file_change(
                change_patch,
                contract_hypothesis if is_primary else None,
                selected_surface=selected_surface_name,
                enforce_hypothesis_target=is_primary,
                patch_graph=patch_graph,
                base_file_content=base_file_content,
                additional_change_files=additional_change_files if is_primary else (),
                capabilities=capabilities,
            )
            if is_primary:
                checks.extend(change_checks)
            else:
                checks.extend(
                    _prefix_checks(change_checks, f"additional_changes[{index - 1}]")
                )

        if checks and all(check.passed for check in checks):
            checks.append(
                self._c9e_solver_design_integration(
                    patch,
                    selected_surface=selected_surface_name,
                    base_file_content=base_file_content,
                    capabilities=capabilities,
                )
            )

        return _build_result(checks)

    def _validate_patch_file_change(
        self,
        patch: PatchProposal,
        hypothesis: HypothesisProposal | HypothesisRecord | None,
        *,
        selected_surface: str | None,
        enforce_hypothesis_target: bool,
        patch_graph: PatchSetGraph | None,
        base_file_content: Callable[[str], str | None] | None = None,
        additional_change_files: tuple[str, ...] = (),
        capabilities: ContractProblemCapabilities,
    ) -> List[CheckResult]:
        checks: List[CheckResult] = []
        checks.append(self._c4_file_whitelist(patch))
        checks.append(self._c5_frozen_files(patch))
        checks.append(
            self._c4b_patch_action_target(
                patch,
                hypothesis,
                selected_surface=selected_surface,
                enforce_hypothesis_target=enforce_hypothesis_target,
                additional_change_files=additional_change_files,
            )
        )
        if not all(check.passed for check in checks[-3:]):
            return checks

        checks.append(self._c6_ast_syntax(patch))
        if not checks[-1].passed:
            return checks

        checks.append(
            self._c7_interface_signature(
                patch,
                selected_surface=selected_surface,
                capabilities=capabilities,
            )
        )
        checks.append(
            self._c8_import_whitelist(
                patch,
                patch_graph=patch_graph,
                base_file_content=base_file_content,
                capabilities=capabilities,
            )
        )
        checks.append(
            self._c9_sensitive_api(
                patch,
                selected_surface=selected_surface,
                capabilities=capabilities,
            )
        )
        checks.append(
            self._c9d_surface_instance_identity(
                patch,
                selected_surface=selected_surface,
                champion_file_content=base_file_content,
            )
        )
        checks.append(self._c9b_non_rng_random(patch))
        return checks

    # ------------------------------------------------------------------
    # C1: JSON Schema (pydantic already validates, check required fields)
    # ------------------------------------------------------------------

    def _c1_schema(self, h: HypothesisProposal) -> CheckResult:
        return check_hypothesis_schema(h, self._spec)

    # ------------------------------------------------------------------
    # C2: change_locus must be a known research locus
    # ------------------------------------------------------------------

    def _c2_change_locus(self, h: HypothesisProposal) -> CheckResult:
        return check_change_locus(
            h,
            problem_spec=self._spec,
            surface_access=self._surface_access,
        )

    # ------------------------------------------------------------------
    # C3: action-target consistency
    # ------------------------------------------------------------------

    def _c3_action_target(self, h: HypothesisProposal) -> CheckResult:
        return check_action_target(
            h,
            surface_access=self._surface_access,
        )

    # ------------------------------------------------------------------
    # C4: file whitelist — file_path must match an editable pattern
    # ------------------------------------------------------------------

    def _c4_file_whitelist(self, patch: PatchProposal) -> CheckResult:
        return check_file_whitelist(patch, self._spec)

    # ------------------------------------------------------------------
    # C5: frozen files — file_path must NOT match any frozen pattern
    # ------------------------------------------------------------------

    def _c5_frozen_files(self, patch: PatchProposal) -> CheckResult:
        return check_frozen_files(patch, self._spec)

    # ------------------------------------------------------------------
    # C4b: patch action/target must match approved hypothesis and surface.
    # ------------------------------------------------------------------

    def _c4b_patch_action_target(
        self,
        patch: PatchProposal,
        hypothesis: HypothesisProposal | HypothesisRecord | None,
        *,
        selected_surface: str | None = None,
        enforce_hypothesis_target: bool = True,
        additional_change_files: tuple[str, ...] = (),
    ) -> CheckResult:
        return check_patch_action_target(
            patch,
            hypothesis,
            surface_access=self._surface_access,
            selected_surface=selected_surface,
            enforce_hypothesis_target=enforce_hypothesis_target,
            additional_change_files=additional_change_files,
        )

    # ------------------------------------------------------------------
    # C6: AST syntax check
    # ------------------------------------------------------------------

    def _c6_ast_syntax(self, patch: PatchProposal) -> CheckResult:
        t0 = time.monotonic_ns()
        if patch.action == "delete":
            return _cr("C6_ast_syntax", True, "light", "delete action — no syntax check", t0)
        try:
            filename = patch.file_path or "<patch>"
            tree = ast.parse(patch.code_content, filename=filename)
            compile(tree, filename, "exec")
            return _cr("C6_ast_syntax", True, "light", "syntax ok", t0)
        except SyntaxError as e:
            detail = (
                f"SyntaxError: {e}; "
                f"source_detail={_syntax_source_detail(patch.code_content)}"
            )
            return _cr("C6_ast_syntax", False, "light", detail, t0)

    # ------------------------------------------------------------------
    # C7: Interface signature — validate the active research-surface interface.
    # ------------------------------------------------------------------

    def _c7_interface_signature(
        self,
        patch: PatchProposal,
        *,
        selected_surface: str | None = None,
        capabilities: ContractProblemCapabilities,
    ) -> CheckResult:
        return check_surface_interface(
            patch,
            problem_spec=self._spec,
            selected_surface=selected_surface,
            operator_execute_signature=self._operator_signature.display,
            active_subject_policy=capabilities.active_subject_policy,
            check_name="C7_interface",
            severity="light",
        )

    # ------------------------------------------------------------------
    # C8: Import whitelist
    # ------------------------------------------------------------------

    def _c8_import_whitelist(
        self,
        patch: PatchProposal,
        *,
        patch_graph: PatchSetGraph | None = None,
        base_file_content: Callable[[str], str | None] | None = None,
        capabilities: ContractProblemCapabilities,
    ) -> CheckResult:
        return check_import_whitelist(
            patch,
            problem_spec=self._spec,
            patch_graph=patch_graph,
            is_editable_solver_file=lambda file_rel: self._is_solver_design_patch_path(
                file_rel,
                capabilities=capabilities,
            ),
            relative_import_file_exists=(
                self._relative_import_file_exists(base_file_content)
            ),
        )

    def _relative_import_file_exists(
        self,
        base_file_content: Callable[[str], str | None] | None,
    ) -> Callable[[str], bool]:
        reader = base_file_content or self._champion_file_content

        def exists(file_rel: str) -> bool:
            return reader(file_rel) is not None

        return exists

    # ------------------------------------------------------------------
    # C9: Sensitive API detection
    # ------------------------------------------------------------------

    def _c9_sensitive_api(
        self,
        patch: PatchProposal,
        *,
        selected_surface: str | None = None,
        capabilities: ContractProblemCapabilities,
    ) -> CheckResult:
        if capabilities.active_subject_policy_error:
            return _cr(
                "C9_sensitive_api",
                False,
                "heavy",
                "active-subject sensitive-API policy unavailable: "
                f"{capabilities.active_subject_policy_error}",
                time.monotonic_ns(),
                metadata={
                    "reason_code": "active_subject_sensitive_api_policy_unavailable",
                    "surface": selected_surface,
                },
            )
        return check_sensitive_api(
            patch,
            forbidden_entrypoint_calls=self._forbidden_entrypoint_calls(
                capabilities=capabilities,
            ),
        )

    # ------------------------------------------------------------------
    # C9d: Surface policy/config code must not branch on case identity.
    # ------------------------------------------------------------------

    def _c9d_surface_instance_identity(
        self,
        patch: PatchProposal,
        *,
        selected_surface: str | None = None,
        champion_file_content: Callable[[str], str | None] | None = None,
    ) -> CheckResult:
        return check_surface_instance_identity(
            patch,
            selected_surface=selected_surface,
            surface_access=self._surface_access,
            surface_disallows_instance_name=self._surface_disallows_instance_name,
            champion_file_content=champion_file_content or self._champion_file_content,
        )

    def _champion_file_content(self, file_rel: str) -> str | None:
        return self._file_content_provider()(file_rel)

    def _file_content_provider(
        self,
        snapshot_path: str | None = None,
        *,
        source_overrides: Mapping[str, str] | None = None,
    ) -> Callable[[str], str | None]:
        root_path = str(snapshot_path or "").strip() or self._current_champion_snapshot_path()
        overrides = dict(self._source_overrides)
        overrides.update(_normalize_source_overrides(source_overrides))

        def read_file(file_rel: str) -> str | None:
            try:
                normalized = normalize_relative_patch_path(file_rel)
            except ValueError:
                normalized = str(file_rel or "").replace("\\", "/").lstrip("/")
            if normalized in overrides:
                return overrides[normalized]
            return self._file_content_from_snapshot(root_path, file_rel)

        return read_file

    @staticmethod
    def _file_content_from_snapshot(
        snapshot_path: str | None,
        file_rel: str,
    ) -> str | None:
        if not snapshot_path:
            return None
        try:
            root = Path(snapshot_path).expanduser().resolve(strict=False)
            path = (root / file_rel).resolve(strict=False)
            path.relative_to(root)
        except Exception:
            return None
        if not path.is_file():
            return None
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return None

    def _current_champion_snapshot_path(self) -> str | None:
        if self._champion_snapshot_provider is not None:
            try:
                value = self._champion_snapshot_provider()
            except Exception:
                value = None
            if value:
                return str(value)
        return self._champion_snapshot_path

    # ------------------------------------------------------------------
    # C9e: Generic surface-integration dispatch.
    # ------------------------------------------------------------------

    def _c9e_solver_design_integration(
        self,
        patch: PatchProposal,
        *,
        selected_surface: str | None = None,
        base_file_content: Callable[[str], str | None] | None = None,
        capabilities: ContractProblemCapabilities | None = None,
    ) -> CheckResult:
        t0 = time.monotonic_ns()
        if capabilities is None:
            capabilities = resolve_contract_problem_capabilities(
                problem_spec=self._spec,
                adapter=self._adapter,
                patch=patch,
                selected_surface=selected_surface,
            )
        result = check_solver_design_integration(
            patch,
            problem_spec=self._spec,
            adapter=self._adapter,
            selected_surface=selected_surface,
            champion_file_content=base_file_content or self._champion_file_content,
            provider=capabilities.contract_check_provider,
            provider_error=capabilities.contract_provider_error,
        )
        return _cr(
            "C9e_solver_design_integration",
            result.passed,
            "light",
            result.detail,
            t0,
            metadata={
                "generic_check_alias": "C9e_surface_integration",
                "surface_contract": "solver_design",
                "surface_contract_scope": "generic_first_class_surface",
            },
        )

    # ------------------------------------------------------------------
    # C9b: Non-rng random source detection
    # ------------------------------------------------------------------

    def _c9b_non_rng_random(self, patch: PatchProposal) -> CheckResult:
        return check_non_rng_random(patch)

    @staticmethod
    def _selected_surface_name(
        hypothesis: HypothesisProposal | HypothesisRecord | None,
    ) -> str | None:
        if hypothesis is None:
            return None
        name = str(getattr(hypothesis, "change_locus", "") or "").strip()
        return name or None

    def _is_solver_design_patch_path(
        self,
        file_rel: str,
        *,
        capabilities: ContractProblemCapabilities,
    ) -> bool:
        normalized = str(file_rel or "").replace("\\", "/").lstrip("/")
        if active_subject_policy_matches_path(
            capabilities.active_subject_policy,
            normalized,
        ):
            return True
        surface = self._surface_access.surface_for_patch_path(normalized)
        if surface is None:
            return False
        kind = str(getattr(surface, "kind", "") or "").strip()
        role = str(
            getattr(getattr(surface, "algorithm", None), "role", "") or ""
        )
        return kind in {"solver_design", "solver_algorithm"} or role in {
            "solver_design",
            "solver_algorithm",
        }

    def _forbidden_entrypoint_calls(
        self,
        *,
        capabilities: ContractProblemCapabilities,
    ) -> tuple[dict[str, Any], ...]:
        calls = capabilities.active_subject_policy.get("forbidden_entrypoint_calls")
        if not isinstance(calls, tuple):
            return ()
        return tuple(item for item in calls if isinstance(item, dict))

    def _surface_disallows_instance_name(self, surface: Any | None) -> bool:
        if surface is None:
            return False
        kind = str(getattr(surface, "kind", "") or "").strip()
        if kind in {
            "policy",
            "config",
            "portfolio",
            "construction",
            "acceptance_restart",
            "solver_design",
        }:
            return True
        if kind == "operator":
            return False
        targets = self._surface_access.surface_targets(surface)
        return bool(getattr(targets, "singleton", False)) or bool(
            getattr(surface, "singleton", False)
        )
