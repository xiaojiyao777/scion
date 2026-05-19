"""ContractGate: static validation of HypothesisProposal and PatchProposal."""
from __future__ import annotations

import ast
import time
from pathlib import Path
from typing import Any, Callable, List, Optional

from scion.config.problem import ProblemSpec
from scion.core.operator_interface import parse_execute_signature
from scion.core.paths import normalize_relative_patch_path
from scion.core.models import (
    CheckResult,
    ContractResult,
    HypothesisProposal,
    HypothesisRecord,
    PatchProposal,
    mechanism_changes,
    patch_file_changes,
)
from scion.contract.checks.solver_design_integration import (
    check_solver_design_integration,
)
from scion.contract.checks.complexity import check_complexity_bound
from scion.contract.checks.identity import check_surface_instance_identity
from scion.contract.checks.novelty import NoveltyChecker
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
from scion.contract.patch_graph import PatchSetGraph
from scion.contract.result_payload import (
    build_result as _build_result,
    check_result as _cr,
    prefix_checks as _prefix_checks,
)
from scion.contract.schema import (
    DIRECT_SIGNATURE_FIELDS as _DIRECT_SIGNATURE_FIELDS,
    PREDICTED_DIRECTIONS as _PREDICTED_DIRECTIONS,
    mechanism_changes_schema_error as _mechanism_changes_schema_error,
    objective_list_schema_error as _objective_list_schema_error,
    objective_metric_names as _objective_metric_names,
    supports_semantic_signature_field as _supports_semantic_signature_field,
)
from scion.contract.surface_access import SurfaceAccess
from scion.contract.surface_interface import check_surface_interface
from scion.contract.telemetry import (
    mechanism_id_matches_declaration as _mechanism_id_matches_declaration,
    surface_mechanism_telemetry_declarations as _surface_mechanism_telemetry_declarations,
)
from scion.runtime.telemetry_guard import validate_expected_telemetry_contract

# Legacy fallback for pre-research_surfaces-v2 problem specs.  New v2 surfaces
# should declare bounds.complexity_scale_terms instead of relying on these names.
_LEGACY_PROBLEM_SCALE_NAMES = frozenset(
    {
        "routes",
        "route",
        "customers",
        "customer_ids",
        "nodes",
        "node_ids",
        "orders",
        "vehicles",
        "vehicle_ids",
    }
)

class ContractGate:
    """Static gate that validates proposals before any code is executed."""

    SUPPORTED_SEMANTIC_SIGNATURE_FIELDS = _DIRECT_SIGNATURE_FIELDS

    def __init__(
        self,
        problem_spec: ProblemSpec,
        *,
        operator_execute_signature: str | None = None,
        champion_snapshot_path: str | None = None,
        champion_snapshot_provider: Callable[[], str | None] | None = None,
    ) -> None:
        self._spec = problem_spec
        self._operator_signature = parse_execute_signature(operator_execute_signature)
        self._champion_snapshot_path = champion_snapshot_path
        self._champion_snapshot_provider = champion_snapshot_provider
        self._surface_access = SurfaceAccess(problem_spec)
        self._novelty_checker = NoveltyChecker(problem_spec, self._surface_access)

    @classmethod
    def supports_semantic_signature_field(cls, field: str) -> bool:
        """Return whether ContractGate can normalize a declared novelty field."""
        return _supports_semantic_signature_field(field)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate_hypothesis(
        self,
        hypothesis: HypothesisProposal,
        active_hypotheses: List[HypothesisRecord],
        blacklist: List[HypothesisRecord],
        rejected_hypotheses: Optional[List[HypothesisRecord]] = None,
        current_champion_version: int = 0,
    ) -> ContractResult:
        """Run C1, C2, C3, C10 checks on a HypothesisProposal."""
        checks: List[CheckResult] = []

        checks.append(self._c1_schema(hypothesis))
        checks.append(self._c2_change_locus(hypothesis))
        checks.append(self._c3_action_target(hypothesis))
        checks.append(self._c11_expected_telemetry(hypothesis))
        checks.append(self._c12_hypothesis_mechanism_binding(hypothesis))
        checks.append(self._c10_novelty(
            hypothesis,
            active_hypotheses,
            blacklist + (rejected_hypotheses or []),
            current_champion_version=current_champion_version,
        ))

        return _build_result(checks)

    def validate_patch(
        self,
        patch: PatchProposal,
        hypothesis: HypothesisProposal | HypothesisRecord | None = None,
        *,
        approved_hypothesis: HypothesisProposal | HypothesisRecord | None = None,
        selected_surface: str | None = None,
    ) -> ContractResult:
        """Run C4–C9 checks on a PatchProposal."""
        checks: List[CheckResult] = []
        contract_hypothesis = (
            approved_hypothesis if approved_hypothesis is not None else hypothesis
        )
        selected_surface_name = (
            self._selected_surface_name(contract_hypothesis) or selected_surface
        )
        patch_graph = PatchSetGraph.from_patch(patch)
        checks.append(
            self._c12_patch_mechanism_binding(
                patch,
                contract_hypothesis,
                selected_surface=selected_surface_name,
            )
        )
        for index, change in enumerate(patch_file_changes(patch)):
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
            )
        )
        checks.append(self._c8_import_whitelist(patch, patch_graph=patch_graph))
        checks.append(self._c9_sensitive_api(patch))
        checks.append(
            self._c9d_surface_instance_identity(
                patch,
                selected_surface=selected_surface,
            )
        )
        checks.append(self._c9b_non_rng_random(patch))
        checks.append(
            self._c9c_complexity_bound(
                patch,
                selected_surface=selected_surface,
            )
        )
        return checks

    # ------------------------------------------------------------------
    # C1: JSON Schema (pydantic already validates, check required fields)
    # ------------------------------------------------------------------

    def _c1_schema(self, h: HypothesisProposal) -> CheckResult:
        t0 = time.monotonic_ns()
        passed = True
        detail = "schema ok"

        # HypothesisProposal is already a dataclass; verify required text fields
        if not h.hypothesis_text or not h.hypothesis_text.strip():
            passed = False
            detail = "hypothesis_text is empty"
        elif not h.change_locus or not h.change_locus.strip():
            passed = False
            detail = "change_locus is empty"
        elif h.action not in ("modify", "create_new", "remove"):
            passed = False
            detail = f"action '{h.action}' is not valid"
        elif h.predicted_direction not in _PREDICTED_DIRECTIONS:
            passed = False
            detail = (
                "predicted_direction must be one of "
                "improve/tradeoff/exploratory"
            )
        else:
            objective_error = _objective_list_schema_error(
                h,
                _objective_metric_names(self._spec),
            )
            if objective_error is not None:
                passed = False
                detail = objective_error
            else:
                mechanism_error = _mechanism_changes_schema_error(h)
                if mechanism_error is not None:
                    passed = False
                    detail = mechanism_error

        return _cr("C1_schema", passed, "heavy", detail, t0)

    # ------------------------------------------------------------------
    # C2: change_locus must be a known research locus
    # ------------------------------------------------------------------

    def _c2_change_locus(self, h: HypothesisProposal) -> CheckResult:
        t0 = time.monotonic_ns()
        categories = self._spec.operator_categories
        passed = h.change_locus in categories
        if passed:
            surface = self._surface_access.surface_by_name(h.change_locus)
            kind_error = self._surface_access.surface_kind_error(surface)
            if kind_error is not None:
                return _cr("C2_change_locus", False, "heavy", kind_error, t0)
        detail = (
            "change_locus ok"
            if passed
            else f"change_locus '{h.change_locus}' not in research loci {categories}"
        )
        return _cr("C2_change_locus", passed, "heavy", detail, t0)

    # ------------------------------------------------------------------
    # C3: action-target consistency
    # ------------------------------------------------------------------

    def _c3_action_target(self, h: HypothesisProposal) -> CheckResult:
        t0 = time.monotonic_ns()
        passed = True
        detail = "action-target ok"

        surface = self._surface_access.surface_by_name(h.change_locus)
        if surface is not None:
            kind_error = self._surface_access.surface_kind_error(surface)
            if kind_error is not None:
                return _cr("C3_action_target", False, "heavy", kind_error, t0)
            if not self._surface_access.surface_action_allowed(surface, h.action):
                return _cr(
                    "C3_action_target",
                    False,
                    "heavy",
                    f"action='{h.action}' is not allowed for research surface "
                    f"'{h.change_locus}'",
                    t0,
                )

        if h.action in ("modify", "remove"):
            if not h.target_file:
                passed = False
                detail = f"action='{h.action}' requires target_file"
            elif surface is not None and not self._surface_access.target_matches_surface(
                h.target_file,
                surface,
            ):
                passed = False
                detail = (
                    f"target_file '{h.target_file}' is not in target files "
                    f"{self._surface_access.surface_target_files(surface)}"
                )
        elif h.action == "create_new":
            # create_new should NOT have a target_file pointing to an existing operator
            # (no hard rule in the spec, so we just require the action is known)
            if (
                h.target_file
                and surface is not None
                and not self._surface_access.target_matches_surface(h.target_file, surface)
            ):
                passed = False
                detail = (
                    f"target_file '{h.target_file}' is not in target files "
                    f"{self._surface_access.surface_target_files(surface)}"
                )

        return _cr("C3_action_target", passed, "heavy", detail, t0)

    # ------------------------------------------------------------------
    # C11: proposal-declared telemetry must be adapter-declared.
    # ------------------------------------------------------------------

    def _c11_expected_telemetry(self, h: HypothesisProposal) -> CheckResult:
        t0 = time.monotonic_ns()
        expected = getattr(h, "expected_telemetry", None)
        if expected in (None, "", [], (), {}):
            return _cr(
                "C11_expected_telemetry",
                True,
                "light",
                "no expected telemetry declared",
                t0,
            )
        if not isinstance(expected, dict):
            return _cr(
                "C11_expected_telemetry",
                False,
                "heavy",
                "expected_telemetry must be an object",
                t0,
            )
        try:
            declared_mechanisms = mechanism_changes(h)
        except (TypeError, AttributeError):
            declared_mechanisms = ()
        errors = validate_expected_telemetry_contract(
            problem_spec=self._spec,
            selected_surface=h.change_locus,
            expected_telemetry=expected,
            declared_mechanisms=declared_mechanisms,
        )
        if errors:
            return _cr(
                "C11_expected_telemetry",
                False,
                "heavy",
                "; ".join(errors),
                t0,
            )
        return _cr(
            "C11_expected_telemetry",
            True,
            "light",
            "expected telemetry fields declared by selected surface",
            t0,
        )

    # ------------------------------------------------------------------
    # C12: mechanism telemetry bindings must be explicit and stable.
    # ------------------------------------------------------------------

    def _c12_hypothesis_mechanism_binding(
        self,
        h: HypothesisProposal,
    ) -> CheckResult:
        t0 = time.monotonic_ns()
        schema_error = _mechanism_changes_schema_error(h)
        if schema_error is not None:
            return _cr(
                "C12_mechanism_binding",
                False,
                "heavy",
                schema_error,
                t0,
            )

        surface = self._surface_access.surface_for_hypothesis(h)
        declarations = _surface_mechanism_telemetry_declarations(surface)
        if not declarations:
            return _cr(
                "C12_mechanism_binding",
                True,
                "light",
                "surface declares no mechanism telemetry",
                t0,
            )

        changes = mechanism_changes(h)
        if not changes:
            return _cr(
                "C12_mechanism_binding",
                False,
                "heavy",
                f"research surface '{h.change_locus}' declares mechanism "
                "telemetry; hypothesis must declare mechanism_changes",
                t0,
            )

        unmatched = [
            change.id
            for change in changes
            if not _mechanism_id_matches_declaration(change.id, declarations)
        ]
        if unmatched:
            return _cr(
                "C12_mechanism_binding",
                False,
                "heavy",
                "mechanism_changes id(s) do not match declared mechanism "
                f"telemetry exact/wildcard keys: {', '.join(unmatched)}",
                t0,
            )

        return _cr(
            "C12_mechanism_binding",
            True,
            "light",
            "mechanism changes match selected surface telemetry declarations",
            t0,
        )

    def _c12_patch_mechanism_binding(
        self,
        patch: PatchProposal,
        approved_hypothesis: HypothesisProposal | HypothesisRecord | None,
        *,
        selected_surface: str | None,
    ) -> CheckResult:
        t0 = time.monotonic_ns()
        schema_error = _mechanism_changes_schema_error(patch)
        if schema_error is not None:
            return _cr(
                "C12_mechanism_binding",
                False,
                "heavy",
                schema_error,
                t0,
            )

        surface = None
        if selected_surface:
            surface = self._surface_access.surface_by_name(selected_surface)
        if surface is None and approved_hypothesis is not None:
            surface = self._surface_access.surface_for_hypothesis(approved_hypothesis)
        declarations = _surface_mechanism_telemetry_declarations(surface)
        if not declarations:
            return _cr(
                "C12_mechanism_binding",
                True,
                "light",
                "surface declares no mechanism telemetry",
                t0,
            )
        if approved_hypothesis is None:
            return _cr(
                "C12_mechanism_binding",
                True,
                "light",
                "no approved hypothesis supplied; mechanism echo skipped",
                t0,
            )

        approved_ids = {change.id for change in mechanism_changes(approved_hypothesis)}
        if not approved_ids:
            return _cr(
                "C12_mechanism_binding",
                False,
                "heavy",
                "approved hypothesis declares no mechanism_changes for a "
                "mechanism-telemetry surface",
                t0,
            )
        patch_ids = {change.id for change in mechanism_changes(patch)}
        if patch_ids != approved_ids:
            missing = sorted(approved_ids - patch_ids)
            extra = sorted(patch_ids - approved_ids)
            detail_parts: list[str] = []
            if missing:
                detail_parts.append(
                    "missing approved mechanism id(s): " + ", ".join(missing)
                )
            if extra:
                detail_parts.append(
                    "unexpected mechanism id(s): " + ", ".join(extra)
                )
            return _cr(
                "C12_mechanism_binding",
                False,
                "heavy",
                "patch mechanism_changes must echo approved hypothesis "
                "mechanism ids; " + "; ".join(detail_parts),
                t0,
            )

        return _cr(
            "C12_mechanism_binding",
            True,
            "light",
            "patch echoes approved mechanism ids",
            t0,
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
    ) -> CheckResult:
        return check_patch_action_target(
            patch,
            hypothesis,
            surface_access=self._surface_access,
            selected_surface=selected_surface,
            enforce_hypothesis_target=enforce_hypothesis_target,
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
            return _cr("C6_ast_syntax", False, "light", f"SyntaxError: {e}", t0)

    # ------------------------------------------------------------------
    # C7: Interface signature — validate the active research-surface interface.
    # ------------------------------------------------------------------

    def _c7_interface_signature(
        self,
        patch: PatchProposal,
        *,
        selected_surface: str | None = None,
    ) -> CheckResult:
        return check_surface_interface(
            patch,
            problem_spec=self._spec,
            selected_surface=selected_surface,
            operator_execute_signature=self._operator_signature.display,
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
    ) -> CheckResult:
        return check_import_whitelist(
            patch,
            problem_spec=self._spec,
            patch_graph=patch_graph,
            is_editable_solver_file=self._is_solver_design_patch_path,
        )

    # ------------------------------------------------------------------
    # C9: Sensitive API detection
    # ------------------------------------------------------------------

    def _c9_sensitive_api(self, patch: PatchProposal) -> CheckResult:
        return check_sensitive_api(patch)

    # ------------------------------------------------------------------
    # C9d: Surface policy/config code must not branch on case identity.
    # ------------------------------------------------------------------

    def _c9d_surface_instance_identity(
        self,
        patch: PatchProposal,
        *,
        selected_surface: str | None = None,
    ) -> CheckResult:
        return check_surface_instance_identity(
            patch,
            selected_surface=selected_surface,
            surface_access=self._surface_access,
            surface_disallows_instance_name=self._surface_disallows_instance_name,
            champion_file_content=self._champion_file_content,
        )

    def _champion_file_content(self, file_rel: str) -> str | None:
        champion_snapshot_path = self._current_champion_snapshot_path()
        if not champion_snapshot_path:
            return None
        try:
            root = Path(champion_snapshot_path).expanduser().resolve(strict=False)
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
    # C9e: Solver-design patches must integrate newly added helpers.
    # ------------------------------------------------------------------

    def _c9e_solver_design_integration(
        self,
        patch: PatchProposal,
        *,
        selected_surface: str | None = None,
    ) -> CheckResult:
        t0 = time.monotonic_ns()
        result = check_solver_design_integration(
            patch,
            selected_surface=selected_surface,
            selected_surface_is_solver_design=self._selected_surface_is_solver_design,
            is_solver_design_patch_path=self._is_solver_design_patch_path,
            champion_file_content=self._champion_file_content,
        )
        return _cr(
            "C9e_solver_design_integration",
            result.passed,
            "light",
            result.detail,
            t0,
        )

    # ------------------------------------------------------------------
    # C9b: Non-rng random source detection
    # ------------------------------------------------------------------

    def _c9b_non_rng_random(self, patch: PatchProposal) -> CheckResult:
        return check_non_rng_random(patch)

    # ------------------------------------------------------------------
    # C9c: Complexity bound for generated neighborhood enumeration.
    # ------------------------------------------------------------------

    def _c9c_complexity_bound(
        self,
        patch: PatchProposal,
        *,
        selected_surface: str | None = None,
    ) -> CheckResult:
        scale_names, surface_error = self._complexity_scale_terms_for_patch(
            patch,
            selected_surface=selected_surface,
        )
        return check_complexity_bound(
            patch,
            scale_names=scale_names,
            surface_error=surface_error,
        )

    # ------------------------------------------------------------------
    # C10: Novelty check
    # ------------------------------------------------------------------

    def _c10_novelty(
        self,
        h: HypothesisProposal,
        active_hypotheses: List[HypothesisRecord],
        blacklist: List[HypothesisRecord],
        current_champion_version: int = 0,
    ) -> CheckResult:
        return self._novelty_checker.check(
            h,
            active_hypotheses,
            blacklist,
            current_champion_version=current_champion_version,
        )

    def _complexity_scale_terms_for_patch(
        self,
        patch: PatchProposal,
        *,
        selected_surface: str | None = None,
    ) -> tuple[frozenset[str], str | None]:
        try:
            file_rel = normalize_relative_patch_path(patch.file_path)
        except ValueError as exc:
            return frozenset(), str(exc)
        surface, surface_error = self._surface_access.surface_for_patch_selection(
            file_rel,
            selected_surface=selected_surface,
        )
        if surface_error is not None:
            return frozenset(), surface_error
        bounds = getattr(surface, "bounds", None) if surface is not None else None
        if bounds is not None:
            terms = getattr(bounds, "complexity_scale_terms", None)
            return (
                frozenset(
                    str(term).strip()
                    for term in (terms or ())
                    if str(term).strip()
                ),
                None,
            )
        return _LEGACY_PROBLEM_SCALE_NAMES, None

    @staticmethod
    def _selected_surface_name(
        hypothesis: HypothesisProposal | HypothesisRecord | None,
    ) -> str | None:
        if hypothesis is None:
            return None
        name = str(getattr(hypothesis, "change_locus", "") or "").strip()
        return name or None

    def _selected_surface_is_solver_design(
        self,
        selected_surface: str | None,
        patch: PatchProposal,
    ) -> bool:
        selected = str(selected_surface or "").strip()
        if selected in {"solver_design", "solver_algorithm"}:
            return True
        if selected:
            surface = self._surface_access.surface_by_name(selected)
            if surface is not None:
                kind = str(getattr(surface, "kind", "") or "").strip()
                role = str(
                    getattr(getattr(surface, "algorithm", None), "role", "") or ""
                )
                if kind in {"solver_design", "solver_algorithm"}:
                    return True
                if role in {"solver_design", "solver_algorithm"}:
                    return True
        for change in patch_file_changes(patch):
            try:
                file_rel = normalize_relative_patch_path(change.file_path)
            except ValueError:
                continue
            if self._is_solver_design_patch_path(file_rel):
                return True
        return False

    def _is_solver_design_patch_path(self, file_rel: str) -> bool:
        normalized = str(file_rel or "").replace("\\", "/").lstrip("/")
        if normalized in {
            "policies/baseline_algorithm.py",
            "policies/solver_algorithm.py",
        }:
            return True
        if normalized.startswith("policies/baseline_modules/") and normalized.endswith(
            ".py"
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
