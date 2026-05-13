"""ContractGate: static validation of HypothesisProposal and PatchProposal."""
from __future__ import annotations

import ast
import hashlib
import json
import re
import time
from typing import Any, List, Optional

from scion.config.problem import ProblemSpec
from scion.core.operator_interface import parse_execute_signature
from scion.core.path_match import normalize_relative_glob_pattern, segment_glob_match
from scion.core.paths import normalize_relative_patch_path
from scion.core.models import (
    CheckResult,
    ContractResult,
    HypothesisProposal,
    HypothesisRecord,
    PatchProposal,
)
from scion.contract.surface_interface import check_surface_interface
from scion.problem.spec import SUPPORTED_RESEARCH_SURFACE_KINDS

# Sensitive API calls that are forbidden in operator code
_SENSITIVE_APIS = frozenset(
    {
        "subprocess",
        "socket",
        "eval",
        "exec",
    }
)

# os.* calls that are forbidden
_SENSITIVE_OS_ATTRS = frozenset({"system", "popen", "execve", "execvp", "execv"})

_STATIC_UNKNOWN = object()


# Non-rng random source calls that bypass the operator's rng parameter
_NON_RNG_RANDOM_PATTERNS = frozenset(
    {
        ("uuid", "uuid4"),
        ("uuid", "uuid1"),
        ("random", "random"),
        ("random", "randint"),
        ("random", "choice"),
        ("random", "sample"),
        ("random", "shuffle"),
        ("random", "uniform"),
        ("random", "randrange"),
        ("os", "urandom"),
        ("secrets", "token_bytes"),
        ("secrets", "token_hex"),
        ("secrets", "token_urlsafe"),
    }
)

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

_DIRECT_SIGNATURE_FIELDS = frozenset(
    {
        "predicted_direction",
        "target_objectives",
        "protected_objectives",
    }
)
_WEAK_SIGNATURE_FIELDS = frozenset({"predicted_direction"})
_NONEMPTY_SEQUENCE_SIGNATURE_FIELDS = frozenset(
    {
        "selected_components",
        "deep_components_selected",
    }
)
_MAX_GENERIC_SIGNATURE_ITEMS = 16
_MAX_GENERIC_SIGNATURE_STRING = 120
_SIGNATURE_FIELD_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")

_PREDICTED_DIRECTIONS = frozenset({"improve", "tradeoff", "exploratory"})
_MAX_OBJECTIVE_SIGNATURE_ITEMS = 16


class ContractGate:
    """Static gate that validates proposals before any code is executed."""

    SUPPORTED_SEMANTIC_SIGNATURE_FIELDS = _DIRECT_SIGNATURE_FIELDS

    def __init__(
        self,
        problem_spec: ProblemSpec,
        *,
        operator_execute_signature: str | None = None,
    ) -> None:
        self._spec = problem_spec
        self._operator_signature = parse_execute_signature(operator_execute_signature)

    @classmethod
    def supports_semantic_signature_field(cls, field: str) -> bool:
        """Return whether ContractGate can normalize a declared novelty field."""
        name = str(field).strip()
        return name in cls.SUPPORTED_SEMANTIC_SIGNATURE_FIELDS or bool(
            _SIGNATURE_FIELD_RE.fullmatch(name)
        )

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

        checks.append(self._c4_file_whitelist(patch))
        checks.append(self._c5_frozen_files(patch))
        checks.append(self._c4b_patch_action_target(patch, contract_hypothesis))
        # Short-circuit: no point running AST checks on a file we already rejected
        if not all(check.passed for check in checks[-3:]):
            return _build_result(checks)

        checks.append(self._c6_ast_syntax(patch))
        if not checks[-1].passed:
            return _build_result(checks)

        checks.append(
            self._c7_interface_signature(
                patch,
                selected_surface=selected_surface_name,
            )
        )
        checks.append(self._c8_import_whitelist(patch))
        checks.append(self._c9_sensitive_api(patch))
        checks.append(
            self._c9d_surface_instance_identity(
                patch,
                selected_surface=selected_surface_name,
            )
        )
        checks.append(self._c9b_non_rng_random(patch))
        checks.append(
            self._c9c_complexity_bound(
                patch,
                selected_surface=selected_surface_name,
            )
        )

        return _build_result(checks)

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
            objective_error = self._objective_list_schema_error(h)
            if objective_error is not None:
                passed = False
                detail = objective_error

        return _cr("C1_schema", passed, "heavy", detail, t0)

    # ------------------------------------------------------------------
    # C2: change_locus must be a known research locus
    # ------------------------------------------------------------------

    def _c2_change_locus(self, h: HypothesisProposal) -> CheckResult:
        t0 = time.monotonic_ns()
        categories = self._spec.operator_categories
        passed = h.change_locus in categories
        if passed:
            surface = self._surface_by_name(h.change_locus)
            kind_error = self._surface_kind_error(surface)
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

        surface = self._surface_by_name(h.change_locus)
        if surface is not None:
            kind_error = self._surface_kind_error(surface)
            if kind_error is not None:
                return _cr("C3_action_target", False, "heavy", kind_error, t0)
            if not self._surface_action_allowed(surface, h.action):
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
            elif surface is not None and not self._target_matches_surface(
                h.target_file,
                surface,
            ):
                passed = False
                detail = (
                    f"target_file '{h.target_file}' is not in target files "
                    f"{self._surface_target_files(surface)}"
                )
        elif h.action == "create_new":
            # create_new should NOT have a target_file pointing to an existing operator
            # (no hard rule in the spec, so we just require the action is known)
            if (
                h.target_file
                and surface is not None
                and not self._target_matches_surface(h.target_file, surface)
            ):
                passed = False
                detail = (
                    f"target_file '{h.target_file}' is not in target files "
                    f"{self._surface_target_files(surface)}"
                )

        return _cr("C3_action_target", passed, "heavy", detail, t0)

    # ------------------------------------------------------------------
    # C4: file whitelist — file_path must match an editable pattern
    # ------------------------------------------------------------------

    def _c4_file_whitelist(self, patch: PatchProposal) -> CheckResult:
        t0 = time.monotonic_ns()
        try:
            file_rel = normalize_relative_patch_path(patch.file_path)
        except ValueError as exc:
            return _cr("C4_file_whitelist", False, "heavy", str(exc), t0)

        editable = self._spec.search_space.editable
        passed = any(_matches_config_pattern(file_rel, pat) for pat in editable)
        detail = (
            "file in whitelist"
            if passed
            else f"'{file_rel}' not in editable patterns {editable}"
        )
        return _cr("C4_file_whitelist", passed, "heavy", detail, t0)

    # ------------------------------------------------------------------
    # C5: frozen files — file_path must NOT match any frozen pattern
    # ------------------------------------------------------------------

    def _c5_frozen_files(self, patch: PatchProposal) -> CheckResult:
        t0 = time.monotonic_ns()
        try:
            file_rel = normalize_relative_patch_path(patch.file_path)
        except ValueError as exc:
            return _cr("C5_frozen_files", False, "heavy", str(exc), t0)

        frozen = self._spec.search_space.frozen
        violated = [pat for pat in frozen if _matches_config_pattern(file_rel, pat)]
        passed = len(violated) == 0
        detail = "not frozen" if passed else f"'{file_rel}' matches frozen patterns {violated}"
        return _cr("C5_frozen_files", passed, "heavy", detail, t0)

    # ------------------------------------------------------------------
    # C4b: patch action/target must match approved hypothesis and surface.
    # ------------------------------------------------------------------

    def _c4b_patch_action_target(
        self,
        patch: PatchProposal,
        hypothesis: HypothesisProposal | HypothesisRecord | None,
    ) -> CheckResult:
        t0 = time.monotonic_ns()
        try:
            file_rel = normalize_relative_patch_path(patch.file_path)
        except ValueError as exc:
            return _cr("C4b_patch_action_target", False, "heavy", str(exc), t0)

        expected_patch_action = None
        surface = None
        if hypothesis is not None:
            expected_patch_action = _patch_action_for_hypothesis_action(
                hypothesis.action
            )
            if expected_patch_action is None:
                return _cr(
                    "C4b_patch_action_target",
                    False,
                    "heavy",
                    f"hypothesis action '{hypothesis.action}' has no patch action mapping",
                    t0,
                )
            if patch.action != expected_patch_action:
                return _cr(
                    "C4b_patch_action_target",
                    False,
                    "heavy",
                    f"patch action '{patch.action}' does not match approved "
                    f"hypothesis action '{hypothesis.action}'",
                    t0,
                )

            target_file = getattr(hypothesis, "target_file", None)
            if target_file:
                try:
                    target_rel = normalize_relative_patch_path(target_file)
                except ValueError as exc:
                    return _cr("C4b_patch_action_target", False, "heavy", str(exc), t0)
                if file_rel != target_rel:
                    return _cr(
                        "C4b_patch_action_target",
                        False,
                        "heavy",
                        f"patch file_path '{file_rel}' does not match approved "
                        f"hypothesis target_file '{target_rel}'",
                        t0,
                    )
            selected_name = self._selected_surface_name(hypothesis)
            surface = self._surface_by_name(selected_name or "")
            if selected_name and self._research_surfaces() and surface is None:
                return _cr(
                    "C4b_patch_action_target",
                    False,
                    "heavy",
                    f"selected research surface '{selected_name}' is not declared "
                    "in problem_spec.research_surfaces",
                    t0,
                )
            if surface is None:
                surface = self._surface_for_hypothesis(hypothesis)

        if surface is None:
            surface = self._surface_for_patch_path(file_rel)

        if surface is not None:
            kind_error = self._surface_kind_error(surface)
            if kind_error is not None:
                return _cr("C4b_patch_action_target", False, "heavy", kind_error, t0)
            surface_action = _hypothesis_action_for_patch_action(patch.action)
            if surface_action is None:
                return _cr(
                    "C4b_patch_action_target",
                    False,
                    "heavy",
                    f"patch action '{patch.action}' is not valid",
                    t0,
                )
            if not self._surface_action_allowed(surface, surface_action):
                return _cr(
                    "C4b_patch_action_target",
                    False,
                    "heavy",
                    f"patch action '{patch.action}' maps to surface action "
                    f"'{surface_action}', which is not allowed for research "
                    f"surface '{getattr(surface, 'name', '<unknown>')}'",
                    t0,
                )
            if not self._target_matches_surface(file_rel, surface):
                return _cr(
                    "C4b_patch_action_target",
                    False,
                    "heavy",
                    f"patch file_path '{file_rel}' is not in target files "
                    f"{self._surface_target_files(surface)}",
                    t0,
                )

        return _cr("C4b_patch_action_target", True, "heavy", "patch action-target ok", t0)

    # ------------------------------------------------------------------
    # C6: AST syntax check
    # ------------------------------------------------------------------

    def _c6_ast_syntax(self, patch: PatchProposal) -> CheckResult:
        t0 = time.monotonic_ns()
        if patch.action == "delete":
            return _cr("C6_ast_syntax", True, "light", "delete action — no syntax check", t0)
        try:
            ast.parse(patch.code_content)
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

    def _c7_policy_interface(
        self,
        tree: ast.AST,
        surface: Any,
        start_ns: int,
    ) -> CheckResult:
        classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        if classes:
            return _cr(
                "C7_interface",
                False,
                "light",
                f"policy surface must use module-level functions, found classes {classes}",
                start_ns,
            )

        required = tuple(self._surface_required_functions(surface))
        declared_signatures = self._surface_function_signatures(surface)
        required_names = _dedupe_preserving_order(
            list(required) + list(declared_signatures)
        )
        if not required_names:
            return _cr(
                "C7_interface",
                True,
                "light",
                "policy surface has no required functions declared — skipped",
                start_ns,
            )

        functions = {
            node.name: node
            for node in getattr(tree, "body", [])
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        missing = [name for name in required_names if name not in functions]
        if missing:
            return _cr(
                "C7_interface",
                False,
                "light",
                f"missing required functions {missing}",
                start_ns,
            )

        signature_error = self._declared_signature_error(
            functions, declared_signatures
        )
        if signature_error is not None:
            return _cr("C7_interface", False, "light", signature_error, start_ns)

        return_error = self._declared_return_value_error(functions, surface)
        if return_error is not None:
            return _cr("C7_interface", False, "light", return_error, start_ns)

        return_detail = self._declared_return_value_detail(functions, surface)
        detail = "policy interface ok"
        if return_detail:
            detail = f"{detail}; {return_detail}"
        return _cr("C7_interface", True, "light", detail, start_ns)

    def _c7_module_function_interface(
        self,
        tree: ast.AST,
        surface: Any,
        start_ns: int,
    ) -> CheckResult:
        required = tuple(self._surface_required_functions(surface))
        declared_signatures = self._surface_function_signatures(surface)
        required_names = _dedupe_preserving_order(
            list(required) + list(declared_signatures)
        )
        if not required_names:
            return _cr(
                "C7_interface",
                True,
                "light",
                f"{getattr(surface, 'kind', 'surface')} surface has no required "
                "functions declared — skipped",
                start_ns,
            )

        functions = {
            node.name: node
            for node in getattr(tree, "body", [])
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        missing = [name for name in required_names if name not in functions]
        if missing:
            return _cr(
                "C7_interface",
                False,
                "light",
                f"missing required functions {missing}",
                start_ns,
            )
        signature_error = self._declared_signature_error(
            functions, declared_signatures
        )
        if signature_error is not None:
            return _cr("C7_interface", False, "light", signature_error, start_ns)
        return_error = self._declared_return_value_error(functions, surface)
        if return_error is not None:
            return _cr("C7_interface", False, "light", return_error, start_ns)

        return_detail = self._declared_return_value_detail(functions, surface)
        detail = "surface interface ok"
        if return_detail:
            detail = f"{detail}; {return_detail}"
        return _cr("C7_interface", True, "light", detail, start_ns)

    # ------------------------------------------------------------------
    # C8: Import whitelist
    # ------------------------------------------------------------------

    def _c8_import_whitelist(self, patch: PatchProposal) -> CheckResult:
        t0 = time.monotonic_ns()
        if patch.action == "delete":
            return _cr("C8_import_whitelist", True, "heavy", "delete action — no import check", t0)

        whitelist = set(self._spec.search_space.import_whitelist)

        try:
            tree = ast.parse(patch.code_content)
        except SyntaxError:
            return _cr("C8_import_whitelist", False, "heavy", "unparseable code", t0)

        violations: List[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if not _in_whitelist(top, whitelist):
                        violations.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    top = node.module.split(".")[0]
                    if not _in_whitelist(top, whitelist):
                        violations.append(node.module)

        passed = len(violations) == 0
        detail = "imports ok" if passed else f"non-whitelisted imports: {violations}"
        return _cr("C8_import_whitelist", passed, "heavy", detail, t0)

    # ------------------------------------------------------------------
    # C9: Sensitive API detection
    # ------------------------------------------------------------------

    def _c9_sensitive_api(self, patch: PatchProposal) -> CheckResult:
        t0 = time.monotonic_ns()
        if patch.action == "delete":
            return _cr("C9_sensitive_api", True, "heavy", "delete action — no API check", t0)

        try:
            tree = ast.parse(patch.code_content)
        except SyntaxError:
            return _cr("C9_sensitive_api", False, "heavy", "unparseable code", t0)

        violations: List[str] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            func = node.func

            # Direct call: eval(...), exec(...), subprocess(...), open(...)
            if isinstance(func, ast.Name):
                if func.id in _SENSITIVE_APIS:
                    violations.append(func.id)
                elif func.id == "open":
                    violations.append("open(...)")

            # Attribute call: os.system(...), subprocess.Popen(...),
            # socket.socket(...), Path(...).read_text(), path.open(), etc.
            elif isinstance(func, ast.Attribute):
                obj_name: Optional[str] = None
                if isinstance(func.value, ast.Name):
                    obj_name = func.value.id

                if obj_name == "os" and func.attr in _SENSITIVE_OS_ATTRS:
                    violations.append(f"os.{func.attr}")
                elif obj_name in _SENSITIVE_APIS:
                    violations.append(f"{obj_name}.{func.attr}")
                elif func.attr in {"open", "read_text", "read_bytes"}:
                    violations.append(f"*.{func.attr}(...)")

        passed = len(violations) == 0
        detail = "no sensitive APIs" if passed else f"sensitive APIs detected: {violations}"
        return _cr("C9_sensitive_api", passed, "heavy", detail, t0)

    # ------------------------------------------------------------------
    # C9d: Surface policy/config code must not branch on case identity.
    # ------------------------------------------------------------------

    def _c9d_surface_instance_identity(
        self,
        patch: PatchProposal,
        *,
        selected_surface: str | None = None,
    ) -> CheckResult:
        t0 = time.monotonic_ns()
        if patch.action == "delete":
            return _cr(
                "C9d_surface_instance_identity",
                True,
                "heavy",
                "delete action — no instance identity check",
                t0,
            )

        try:
            file_rel = normalize_relative_patch_path(patch.file_path)
        except ValueError as exc:
            return _cr("C9d_surface_instance_identity", False, "heavy", str(exc), t0)

        surface, surface_error = self._surface_for_patch_selection(
            file_rel,
            selected_surface=selected_surface,
        )
        if surface_error is not None:
            return _cr(
                "C9d_surface_instance_identity",
                False,
                "heavy",
                surface_error,
                t0,
            )
        if not self._surface_disallows_instance_name(surface):
            return _cr(
                "C9d_surface_instance_identity",
                True,
                "heavy",
                "surface does not restrict instance.name",
                t0,
            )

        try:
            tree = ast.parse(patch.code_content)
        except SyntaxError:
            return _cr(
                "C9d_surface_instance_identity",
                False,
                "heavy",
                "unparseable code",
                t0,
            )

        violations: list[str] = []
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and node.attr == "name"
                and isinstance(node.value, ast.Name)
                and node.value.id == "instance"
            ):
                violations.append("instance.name")
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in {"getattr", "hasattr"}
                and len(node.args) >= 2
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id == "instance"
                and isinstance(node.args[1], ast.Constant)
                and node.args[1].value == "name"
            ):
                violations.append(f"{node.func.id}(instance, 'name')")

        if not violations:
            return _cr(
                "C9d_surface_instance_identity",
                True,
                "heavy",
                "no instance identity access",
                t0,
            )
        surface_name = getattr(surface, "name", "<unknown>")
        return _cr(
            "C9d_surface_instance_identity",
            False,
            "heavy",
            f"case-specific instance identity access is forbidden for research "
            f"surface '{surface_name}': {violations}",
            t0,
        )

    # ------------------------------------------------------------------
    # C9b: Non-rng random source detection
    # ------------------------------------------------------------------

    def _c9b_non_rng_random(self, patch: PatchProposal) -> CheckResult:
        t0 = time.monotonic_ns()
        if patch.action == "delete":
            return _cr("C9b_non_rng_random", True, "heavy", "delete action — no randomness check", t0)

        try:
            tree = ast.parse(patch.code_content)
        except SyntaxError:
            return _cr("C9b_non_rng_random", False, "heavy", "unparseable code", t0)

        # Build a set of dangerous bare names from import-from statements and alias mappings
        # e.g. `from random import choice` → dangerous_names = {"choice"}
        # e.g. `import random as r` → module_aliases = {"r": "random"}
        dangerous_names: set[str] = set()
        module_aliases: dict[str, str] = {}  # alias → canonical module name

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    local_name = alias.asname if alias.asname else alias.name
                    if (module, alias.name) in _NON_RNG_RANDOM_PATTERNS:
                        dangerous_names.add(local_name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.asname:
                        module_aliases[alias.asname] = alias.name

        violations: List[str] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Name):
                # Bare-name call: `choice(...)` from `from random import choice`
                if func.id in dangerous_names:
                    violations.append(f"{func.id}(...)")
            elif isinstance(func, ast.Attribute):
                obj_name: Optional[str] = None
                if isinstance(func.value, ast.Name):
                    obj_name = func.value.id
                if obj_name is None:
                    continue
                # Skip rng.* calls — the operator's rng parameter
                if obj_name == "rng":
                    continue
                # Resolve alias (e.g. `r` → `random`)
                resolved = module_aliases.get(obj_name, obj_name)
                if (resolved, func.attr) in _NON_RNG_RANDOM_PATTERNS:
                    violations.append(f"{obj_name}.{func.attr}")

        passed = len(violations) == 0
        detail = "no non-rng random sources" if passed else f"non-rng random sources detected: {violations}"
        return _cr("C9b_non_rng_random", passed, "heavy", detail, t0)

    # ------------------------------------------------------------------
    # C9c: Complexity bound for generated neighborhood enumeration.
    # ------------------------------------------------------------------

    def _c9c_complexity_bound(
        self,
        patch: PatchProposal,
        *,
        selected_surface: str | None = None,
    ) -> CheckResult:
        """Reject high-order or variable-size combinations in operator code.

        Production instances can contain 100+ vehicles in one region. An LLM
        operator that enumerates combinations of size 3/4 or a variable-size
        loop over combinations can explode inside the VNS pool loop. Pairwise
        combinations with a constant k<=2 are allowed; broader neighborhoods
        must be implemented via capped top-k candidate lists or sampling.
        """
        t0 = time.monotonic_ns()
        if patch.action == "delete":
            return _cr("C9c_complexity_bound", True, "heavy", "delete action — no complexity check", t0)

        try:
            tree = ast.parse(patch.code_content)
        except SyntaxError:
            return _cr("C9c_complexity_bound", False, "heavy", "unparseable code", t0)

        scale_names, surface_error = self._complexity_scale_terms_for_patch(
            patch,
            selected_surface=selected_surface,
        )
        if surface_error is not None:
            return _cr("C9c_complexity_bound", False, "heavy", surface_error, t0)
        itertools_aliases = _collect_itertools_aliases(tree)
        violations: List[str] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            call_kind = _itertools_call_kind(node, itertools_aliases)
            if call_kind == "combinations":
                if len(node.args) < 2:
                    continue
                k_arg = node.args[1]
                if isinstance(k_arg, ast.Constant) and isinstance(k_arg.value, int):
                    if k_arg.value <= 2:
                        continue
                    violations.append(f"combinations(..., {k_arg.value})")
                else:
                    violations.append("combinations(..., variable_k)")
            elif call_kind == "permutations":
                violations.append("permutations(...)")
            elif call_kind == "product":
                scale_args = sum(
                    1 for arg in node.args
                    if _is_problem_scale_expr(arg, scale_names)
                )
                repeat_scale = _constant_int_kwarg(node, "repeat")
                if scale_args >= 2 or (scale_args == 1 and repeat_scale is not None and repeat_scale > 1):
                    violations.append("product(... problem-scale iterables ...)")

        for node in ast.walk(tree):
            if isinstance(node, ast.While) and not _is_bounded_while(
                node,
                scale_names,
            ):
                violations.append("uncapped while loop")

        loop_guard = _ProblemScaleLoopGuard(scale_names)
        loop_guard.visit(tree)
        violations.extend(loop_guard.violations)

        if not violations:
            return _cr("C9c_complexity_bound", True, "heavy", "complexity ok", t0)
        return _cr(
            "C9c_complexity_bound",
            False,
            "heavy",
            "unbounded/high-order/high-risk enumeration detected: "
            f"{violations}. Use capped top-k candidate lists or sampling.",
            t0,
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
        t0 = time.monotonic_ns()
        novelty_error = self._novelty_strategy_error(h)
        if novelty_error is not None:
            return _cr("C10_novelty", False, "light", novelty_error, t0)
        semantic_identity_error = self._semantic_signature_identity_error(h)
        if semantic_identity_error is not None:
            return _cr("C10_novelty", False, "light", semantic_identity_error, t0)
        key = self._novelty_key(h)
        for existing in active_hypotheses + blacklist:
            # Rejected hypotheses only block if they come from the same champion version;
            # a champion upgrade opens the door to retry previously rejected modify paths.
            if existing.status == "rejected":
                if existing.base_champion_version != current_champion_version:
                    continue
            duplicate_key = self._duplicate_novelty_key(
                h,
                existing,
                candidate_key=key,
            )
            if duplicate_key is not None:
                return _cr(
                    "C10_novelty",
                    False,
                    "light",
                    self._duplicate_novelty_detail(h, existing, duplicate_key),
                    t0,
                )
        return _cr("C10_novelty", True, "light", "novel", t0)

    def _duplicate_novelty_detail(
        self,
        h: HypothesisProposal,
        existing: HypothesisRecord,
        duplicate_key: tuple[Any, ...],
    ) -> str:
        base = f"duplicate of existing hypothesis (key={duplicate_key})"
        if not self._uses_same_semantic_modify_surface(h, existing):
            return base
        surface = self._surface_for_hypothesis(h)
        fields = self._surface_signature_fields(surface)
        candidate_missing = self._missing_semantic_signature_fields(h, surface)
        existing_missing = self._missing_semantic_signature_fields(existing, surface)
        if candidate_missing or existing_missing:
            parts = [
                "semantic_signature surface lacks usable structured identity; "
                "C10 fell back to target-file identity"
            ]
            if candidate_missing:
                parts.append(
                    "candidate missing novelty_signature fields: "
                    + ", ".join(candidate_missing)
                )
            if existing_missing:
                parts.append(
                    "existing hypothesis missing novelty_signature fields: "
                    + ", ".join(existing_missing)
                )
            return base + "; " + "; ".join(parts)
        if len(duplicate_key) >= 4 and duplicate_key[2] == "semantic_signature":
            return (
                base
                + "; duplicate structured novelty_signature for declared fields: "
                + ", ".join(fields)
            )
        return base

    def _duplicate_novelty_key(
        self,
        h: HypothesisProposal,
        existing: HypothesisRecord,
        *,
        candidate_key: tuple[Any, ...],
    ) -> tuple[Any, ...] | None:
        if self._uses_same_semantic_modify_surface(h, existing):
            surface = self._surface_for_hypothesis(h)
            candidate_semantic = self._semantic_signature_key(h, surface)
            existing_semantic = self._semantic_signature_key(existing, surface)
            if candidate_semantic is None:
                strict_key = self._strict_novelty_key(h)
                if strict_key == self._strict_novelty_key(existing):
                    return strict_key
                return None
            if existing_semantic is None:
                return None
            if candidate_semantic == existing_semantic:
                return (
                    h.change_locus,
                    h.action,
                    "semantic_signature",
                    candidate_semantic,
                )
            return None

        existing_key = self._novelty_key(existing)
        if candidate_key == existing_key:
            return candidate_key
        return None

    def _uses_same_semantic_modify_surface(
        self,
        h: HypothesisProposal,
        existing: HypothesisRecord,
    ) -> bool:
        if h.action != "modify" or existing.action != "modify":
            return False
        if h.change_locus != existing.change_locus:
            return False
        surface = self._surface_for_hypothesis(h)
        return self._surface_novelty_strategy(surface) == "semantic_signature"

    def _novelty_key(self, h: HypothesisProposal | HypothesisRecord) -> tuple[Any, ...]:
        strict_key = self._strict_novelty_key(h)
        # create_new has no reliable singleton file identity, so keep intent in the key.
        if h.action == "create_new":
            return (
                h.change_locus,
                h.action,
                h.target_file,
                (h.hypothesis_text or "")[:50],
            )

        # Singleton surfaces can opt into semantic novelty: distinct policy/config/
        # portfolio hypotheses against one file pass only when declared structured
        # signature fields are available. Free-text rationale is intentionally
        # excluded; unavailable fields fall back to strict target-file identity.
        if h.action == "modify":
            surface = self._surface_for_hypothesis(h)
            if self._surface_novelty_strategy(surface) == "semantic_signature":
                semantic_key = self._semantic_signature_key(h, surface)
                if semantic_key is not None:
                    return (h.change_locus, h.action, "semantic_signature", semantic_key)
                return strict_key

        # Ordinary modify/remove remains strict by locus/action/target file.
        return strict_key

    @staticmethod
    def _strict_novelty_key(h: HypothesisProposal | HypothesisRecord) -> tuple[Any, ...]:
        return (h.change_locus, h.action, h.target_file)

    def _novelty_strategy_error(
        self,
        h: HypothesisProposal | HypothesisRecord,
    ) -> str | None:
        surface = self._surface_for_hypothesis(h)
        strategy = self._surface_novelty_strategy(surface)
        if strategy in ("", "target_file", "semantic_signature"):
            return None
        return (
            f"unsupported novelty.strategy '{strategy}' for research surface "
            f"'{h.change_locus}'"
        )

    def _semantic_signature_identity_error(
        self,
        h: HypothesisProposal | HypothesisRecord,
    ) -> str | None:
        if h.action != "modify":
            return None
        surface = self._surface_for_hypothesis(h)
        if self._surface_novelty_strategy(surface) != "semantic_signature":
            return None
        fields = self._surface_signature_fields(surface)
        if not fields:
            return (
                "semantic_signature surface "
                f"'{h.change_locus}' declares no usable novelty.signature_fields"
            )
        missing = self._missing_semantic_signature_fields(h, surface)
        if missing:
            return (
                "semantic_signature surface "
                f"'{h.change_locus}' requires usable structured "
                "novelty_signature identity; candidate missing or invalid "
                "novelty_signature fields: "
                + ", ".join(missing)
            )
        if self._semantic_signature_key(h, surface) is None:
            return (
                "semantic_signature surface "
                f"'{h.change_locus}' requires at least one strong structured "
                "identity field beyond weak defaults such as predicted_direction"
            )
        return None

    def _surface_for_hypothesis(
        self,
        h: HypothesisProposal | HypothesisRecord,
    ) -> Any | None:
        surface = self._surface_by_name(h.change_locus)
        if surface is not None:
            return surface
        if h.target_file:
            return self._surface_for_patch_path(h.target_file)
        return None

    def _semantic_signature_key(
        self,
        h: HypothesisProposal | HypothesisRecord,
        surface: Any | None,
    ) -> str | None:
        fields = self._surface_signature_fields(surface)
        if not fields:
            return None
        parts: list[str] = []
        sufficient = False
        for field in fields:
            normalized = self._normalize_signature_field(field, h)
            if normalized is None:
                return None
            if field not in _WEAK_SIGNATURE_FIELDS:
                sufficient = True
            parts.append(f"{field}:{normalized}")
        if not parts or not sufficient:
            return None
        normalized = "|".join(parts)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]

    def _missing_semantic_signature_fields(
        self,
        h: HypothesisProposal | HypothesisRecord,
        surface: Any | None,
    ) -> list[str]:
        missing: list[str] = []
        for field in self._surface_signature_fields(surface):
            if self._normalize_signature_field(field, h) is None:
                missing.append(field)
        return missing

    def _normalize_signature_field(
        self,
        field: str,
        h: HypothesisProposal | HypothesisRecord,
    ) -> str | None:
        if field in _DIRECT_SIGNATURE_FIELDS:
            if not hasattr(h, field):
                return None
            return self._normalize_structured_signature_value(field, getattr(h, field))
        if not _SIGNATURE_FIELD_RE.fullmatch(field):
            return None
        values = getattr(h, "novelty_signature", None)
        if not isinstance(values, dict) or field not in values:
            return None
        if field in _NONEMPTY_SEQUENCE_SIGNATURE_FIELDS:
            return _normalize_nonempty_signature_sequence(values[field])
        return _normalize_generic_signature_value(values[field])

    def _normalize_structured_signature_value(
        self,
        field: str,
        value: Any,
    ) -> str | None:
        if field == "predicted_direction":
            if not isinstance(value, str):
                return None
            direction = value.strip()
            return direction if direction in _PREDICTED_DIRECTIONS else None
        if field in ("target_objectives", "protected_objectives"):
            return self._normalize_objective_signature_value(value)
        return None

    def _normalize_objective_signature_value(self, value: Any) -> str | None:
        objective_names = self._objective_metric_names()
        if not objective_names:
            return None
        if not isinstance(value, (list, tuple, set)):
            return None
        if len(value) > min(_MAX_OBJECTIVE_SIGNATURE_ITEMS, len(objective_names)):
            return None

        items: list[str] = []
        for item in value:
            if not isinstance(item, str):
                return None
            name = item.strip()
            if not name or name not in objective_names:
                return None
            items.append(name)
        if not items:
            return None
        return ",".join(sorted(set(items)))

    def _objective_list_schema_error(self, h: HypothesisProposal) -> str | None:
        objective_names = self._objective_metric_names()
        for field in ("target_objectives", "protected_objectives"):
            value = getattr(h, field)
            if value in (None, ()):
                continue
            if not isinstance(value, (list, tuple, set)):
                return f"{field} must be a list of objective metric names"
            if len(value) > _MAX_OBJECTIVE_SIGNATURE_ITEMS:
                return (
                    f"{field} has too many entries; max "
                    f"{_MAX_OBJECTIVE_SIGNATURE_ITEMS}"
                )
            seen: set[str] = set()
            for item in value:
                if not isinstance(item, str) or not item.strip():
                    return f"{field} must contain non-empty objective metric names"
                name = item.strip()
                seen.add(name)
                if objective_names and name not in objective_names:
                    allowed = ", ".join(sorted(objective_names))
                    return (
                        f"{field} contains unknown objective '{name}', "
                        f"expected one of: {allowed}"
                    )
            if objective_names and len(seen) > len(objective_names):
                return f"{field} has too many distinct objective names"
        return None

    def _objective_metric_names(self) -> frozenset[str]:
        specs = getattr(self._spec, "objectives", None)
        if specs is None:
            specs = getattr(self._spec, "metric_specs", None)
        names: set[str] = set()
        for spec in specs or ():
            name = getattr(spec, "name", None)
            if isinstance(name, str) and name.strip():
                names.add(name.strip())
        return frozenset(names)

    def _research_surfaces(self) -> list[Any]:
        return list(getattr(self._spec, "research_surfaces", []) or [])

    def _surface_by_name(self, name: str) -> Any | None:
        for surface in self._research_surfaces():
            if getattr(surface, "name", None) == name:
                return surface
        return None

    def _surface_kind_error(self, surface: Any | None) -> str | None:
        if surface is None:
            return None
        kind = str(getattr(surface, "kind", "") or "").strip()
        if kind in SUPPORTED_RESEARCH_SURFACE_KINDS:
            return None
        allowed = ", ".join(sorted(SUPPORTED_RESEARCH_SURFACE_KINDS))
        return (
            f"unsupported research surface kind '{kind}' for surface "
            f"'{getattr(surface, 'name', '<unknown>')}', expected one of: {allowed}"
        )

    def _surface_for_patch_path(self, file_rel: str) -> Any | None:
        for surface in self._research_surfaces():
            if self._target_matches_surface(file_rel, surface):
                return surface
        return None

    def _surface_for_patch_selection(
        self,
        file_rel: str,
        *,
        selected_surface: str | None,
    ) -> tuple[Any | None, str | None]:
        surfaces = self._research_surfaces()
        selected = str(selected_surface or "").strip()
        if not selected or not surfaces:
            return self._surface_for_patch_path(file_rel), None

        surface = self._surface_by_name(selected)
        if surface is None:
            return (
                None,
                f"selected research surface '{selected}' is not declared "
                "in problem_spec.research_surfaces",
            )
        if not self._target_matches_surface(file_rel, surface):
            return (
                None,
                f"patch file_path '{file_rel}' is not in target files "
                f"{self._surface_target_files(surface)} for selected research "
                f"surface '{selected}'",
            )
        return surface, None

    def _target_matches_surface(self, file_rel: str, surface: Any) -> bool:
        try:
            normalized = normalize_relative_patch_path(file_rel)
        except ValueError:
            return False
        target_files = self._surface_target_files(surface)
        return any(
            _matches_config_pattern(normalized, str(pattern).lstrip("/"))
            for pattern in target_files
        )

    @staticmethod
    def _surface_targets(surface: Any | None) -> Any | None:
        if surface is None:
            return None
        return getattr(surface, "targets", None)

    def _surface_target_files(self, surface: Any | None) -> list[str]:
        targets = self._surface_targets(surface)
        if targets is not None:
            files = getattr(targets, "files", None)
            if files is not None:
                return [str(path) for path in files]
        return [str(path) for path in (getattr(surface, "target_files", []) or [])]

    def _surface_action_allowed(self, surface: Any | None, action: str) -> bool:
        attr = {
            "create_new": "create_new_allowed",
            "modify": "modify_allowed",
            "remove": "remove_allowed",
        }.get(action)
        if attr is None:
            return False
        targets = self._surface_targets(surface)
        if targets is not None and hasattr(targets, attr):
            return bool(getattr(targets, attr))
        return bool(getattr(surface, attr, True))

    def _surface_required_functions(self, surface: Any | None) -> list[str]:
        interface = getattr(surface, "interface", None) if surface is not None else None
        if interface is not None:
            required = getattr(interface, "required_functions", None)
            if required is not None:
                return [str(name) for name in required]
        return [str(name) for name in (getattr(surface, "required_functions", []) or [])]

    def _surface_function_signatures(
        self,
        surface: Any | None,
    ) -> dict[str, list[str]]:
        interface = getattr(surface, "interface", None) if surface is not None else None
        signatures = (
            getattr(interface, "function_signatures", None)
            if interface is not None
            else None
        )
        if not isinstance(signatures, dict):
            return {}
        normalized: dict[str, list[str]] = {}
        for raw_name, raw_args in signatures.items():
            name = str(raw_name).strip()
            if not name:
                continue
            if isinstance(raw_args, str):
                args = [arg.strip() for arg in raw_args.split(",") if arg.strip()]
            else:
                try:
                    args = [str(arg).strip() for arg in raw_args if str(arg).strip()]
                except TypeError:
                    args = []
            normalized[name] = args
        return normalized

    @staticmethod
    def _surface_return_values(surface: Any | None) -> dict[str, Any]:
        interface = getattr(surface, "interface", None) if surface is not None else None
        values = (
            getattr(interface, "return_values", None)
            if interface is not None
            else None
        )
        return values if isinstance(values, dict) else {}

    @staticmethod
    def _declared_signature_error(
        functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
        declared_signatures: dict[str, list[str]],
    ) -> str | None:
        for name, expected_args in declared_signatures.items():
            node = functions.get(name)
            if node is None:
                continue
            actual_args = [
                arg.arg
                for arg in [*node.args.posonlyargs, *node.args.args]
            ]
            if actual_args[: len(expected_args)] != expected_args:
                return (
                    f"function '{name}' positional parameters {actual_args} do "
                    f"not match declared prefix {expected_args}"
                )
            required_count = len(actual_args) - len(node.args.defaults)
            if required_count > len(expected_args):
                extra = actual_args[len(expected_args) : required_count]
                return (
                    f"function '{name}' declares extra required positional "
                    f"parameters {extra}"
                )
        return None

    def _declared_return_value_error(
        self,
        functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
        surface: Any | None,
    ) -> str | None:
        for name, spec in self._surface_return_values(surface).items():
            node = functions.get(str(name))
            if node is None:
                continue
            for return_node in [
                item for item in ast.walk(node) if isinstance(item, ast.Return)
            ]:
                value = _static_literal_value(return_node.value)
                if value is _STATIC_UNKNOWN:
                    if not bool(getattr(spec, "allow_static_unknown", True)):
                        return (
                            f"function '{name}' return value is not statically "
                            "decidable"
                        )
                    continue
                error = _return_value_contract_error(str(name), value, spec)
                if error is not None:
                    return error
        return None

    def _declared_return_value_detail(
        self,
        functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
        surface: Any | None,
    ) -> str:
        warnings: list[str] = []
        for name, spec in self._surface_return_values(surface).items():
            node = functions.get(str(name))
            if node is None:
                continue
            has_unknown = any(
                _static_literal_value(return_node.value) is _STATIC_UNKNOWN
                for return_node in ast.walk(node)
                if isinstance(return_node, ast.Return)
            )
            if has_unknown and bool(getattr(spec, "allow_static_unknown", True)):
                warnings.append(f"{name} has return paths not statically checked")
        if not warnings:
            return ""
        return "return-value warnings: " + "; ".join(warnings)

    def _surface_novelty_strategy(self, surface: Any | None) -> str:
        novelty = getattr(surface, "novelty", None) if surface is not None else None
        strategy = getattr(novelty, "strategy", "") if novelty is not None else ""
        return str(strategy or "")

    def _surface_signature_fields(self, surface: Any | None) -> list[str]:
        novelty = getattr(surface, "novelty", None) if surface is not None else None
        fields = getattr(novelty, "signature_fields", None) if novelty is not None else None
        normalized: list[str] = []
        for field in fields or []:
            value = str(field).strip()
            if value:
                normalized.append(value)
        return normalized

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
        surface, surface_error = self._surface_for_patch_selection(
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
        targets = self._surface_targets(surface)
        return bool(getattr(targets, "singleton", False)) or bool(
            getattr(surface, "singleton", False)
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cr(
    name: str,
    passed: bool,
    severity: str,
    detail: str,
    start_ns: int,
) -> CheckResult:
    elapsed_ms = int((time.monotonic_ns() - start_ns) / 1_000_000)
    return CheckResult(
        name=name,
        passed=passed,
        severity=severity,  # type: ignore[arg-type]
        detail=detail,
        elapsed_ms=elapsed_ms,
    )


def _static_literal_value(node: ast.AST | None) -> Any:
    if node is None:
        return None
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        pass
    if isinstance(node, ast.Name):
        if node.id == "True":
            return True
        if node.id == "False":
            return False
        if node.id == "None":
            return None
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        operand = _static_literal_value(node.operand)
        if isinstance(operand, bool) or not isinstance(operand, (int, float)):
            return _STATIC_UNKNOWN
        return +operand if isinstance(node.op, ast.UAdd) else -operand
    return _STATIC_UNKNOWN


def _return_value_contract_error(name: str, value: Any, spec: Any) -> str | None:
    value_type = str(getattr(spec, "value_type", "any") or "any")
    if not _return_value_type_matches(value, value_type):
        return (
            f"function '{name}' returns {type(value).__name__}, expected "
            f"{value_type}"
        )

    allowed_literals = list(getattr(spec, "allowed_literals", []) or [])
    if allowed_literals:
        if isinstance(value, (list, tuple, set, frozenset)):
            bad = [item for item in value if item not in allowed_literals]
            if bad:
                return (
                    f"function '{name}' returns values outside declared "
                    f"allowed_literals: {bad}"
                )
        elif value not in allowed_literals:
            return (
                f"function '{name}' returns {value!r}, expected one of "
                f"{allowed_literals}"
            )

    numeric_range = getattr(spec, "numeric_range", None)
    if numeric_range is not None and isinstance(value, (int, float)) and not isinstance(value, bool):
        lo, hi = float(numeric_range[0]), float(numeric_range[1])
        numeric = float(value)
        if numeric < lo or numeric > hi:
            return (
                f"function '{name}' returns {numeric!r} outside declared "
                f"range [{lo}, {hi}]"
            )

    if isinstance(value, dict):
        allowed_keys = [str(item) for item in (getattr(spec, "allowed_keys", []) or [])]
        if allowed_keys:
            bad_keys = [key for key in value if str(key) not in allowed_keys]
            if bad_keys:
                return (
                    f"function '{name}' returns keys outside declared "
                    f"allowed_keys: {bad_keys}"
                )
        required_keys = [str(item) for item in (getattr(spec, "required_keys", []) or [])]
        if required_keys:
            missing = [key for key in required_keys if key not in {str(k) for k in value}]
            if missing:
                return f"function '{name}' is missing declared required keys: {missing}"
        value_range = getattr(spec, "value_numeric_range", None)
        if value_range is not None:
            lo, hi = float(value_range[0]), float(value_range[1])
            for key, item in value.items():
                if isinstance(item, bool) or not isinstance(item, (int, float)):
                    return (
                        f"function '{name}' returns non-numeric value for key "
                        f"{key!r}: {item!r}"
                    )
                numeric = float(item)
                if numeric < lo or numeric > hi:
                    return (
                        f"function '{name}' returns value {numeric!r} for key "
                        f"{key!r} outside declared range [{lo}, {hi}]"
                    )
    return None


def _return_value_type_matches(value: Any, value_type: str) -> bool:
    if value_type == "any":
        return True
    if value_type == "str":
        return isinstance(value, str)
    if value_type == "bool":
        return isinstance(value, bool)
    if value_type == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if value_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if value_type == "sequence":
        return isinstance(value, (list, tuple, set, frozenset)) and not isinstance(value, str)
    if value_type == "mapping":
        return isinstance(value, dict)
    return True


def _dedupe_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in seen:
            seen.add(text)
            deduped.append(text)
    return deduped


def _normalize_nonempty_signature_sequence(value: Any) -> str | None:
    if not isinstance(value, (list, tuple, set, frozenset)) or not value:
        return None
    items: list[str] = []
    for item in value:
        token = _normalize_text_token(item, max_length=_MAX_GENERIC_SIGNATURE_STRING)
        if token is None:
            return None
        items.append(token)
    if not items:
        return None
    if isinstance(value, (set, frozenset)):
        items = sorted(items)
    return json.dumps(items, separators=(",", ":"), ensure_ascii=True)


def _normalize_generic_signature_value(value: Any, *, depth: int = 0) -> str | None:
    if depth > 3:
        return None
    if value is None:
        return None
    if depth == 0 and value is False:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            return None
        return f"{value:.6g}"
    if isinstance(value, str):
        return _normalize_text_token(value, max_length=_MAX_GENERIC_SIGNATURE_STRING)
    if isinstance(value, (list, tuple, set, frozenset)):
        if not value:
            return None
        if len(value) > _MAX_GENERIC_SIGNATURE_ITEMS:
            return None
        items = [
            _normalize_generic_signature_value(item, depth=depth + 1)
            for item in value
        ]
        if any(item is None for item in items):
            return None
        if isinstance(value, (set, frozenset)):
            items = sorted(items)  # type: ignore[arg-type]
        return json.dumps(items, separators=(",", ":"), ensure_ascii=True)
    if isinstance(value, dict):
        if not value:
            return None
        if len(value) > _MAX_GENERIC_SIGNATURE_ITEMS:
            return None
        normalized: dict[str, str] = {}
        for raw_key, raw_item in value.items():
            key = _normalize_text_token(raw_key, max_length=64)
            item = _normalize_generic_signature_value(raw_item, depth=depth + 1)
            if key is None or item is None:
                return None
            normalized[key] = item
        return json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return None


def _normalize_text_token(value: Any, *, max_length: int) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.strip().casefold().split())
    if not text or len(text) > max_length:
        return None
    return text


def _build_result(checks: List[CheckResult]) -> ContractResult:
    """Aggregate checks into ContractResult."""
    first_failure: Optional[str] = None
    for c in checks:
        if not c.passed:
            first_failure = f"{c.name}: {c.detail}"
            break
    return ContractResult(
        passed=first_failure is None,
        checks=tuple(checks),
        failure_reason=first_failure,
    )


def _matches_config_pattern(file_rel: str, pattern: str) -> bool:
    try:
        normalized_pattern = normalize_relative_glob_pattern(pattern)
    except ValueError:
        return False
    return segment_glob_match(file_rel, normalized_pattern)


def _patch_action_for_hypothesis_action(action: str) -> str | None:
    return {
        "modify": "modify",
        "create_new": "create",
        "remove": "delete",
    }.get(action)


def _hypothesis_action_for_patch_action(action: str) -> str | None:
    return {
        "modify": "modify",
        "create": "create_new",
        "delete": "remove",
    }.get(action)


def _in_whitelist(module_top: str, whitelist: set) -> bool:
    """Return True if module_top is explicitly allowed."""
    return module_top in whitelist


def _collect_itertools_aliases(tree: ast.AST) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "itertools":
            for alias in node.names:
                if alias.name in {"combinations", "permutations", "product"}:
                    aliases[alias.asname or alias.name] = alias.name
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "itertools":
                    aliases[alias.asname or alias.name] = "itertools"
    return aliases


def _itertools_call_kind(call_node: ast.Call, aliases: dict[str, str]) -> str | None:
    func = call_node.func
    if isinstance(func, ast.Name):
        return aliases.get(func.id)
    if isinstance(func, ast.Attribute):
        if func.attr not in {"combinations", "permutations", "product"}:
            return None
        if isinstance(func.value, ast.Name):
            resolved = aliases.get(func.value.id)
            if resolved == "itertools":
                return func.attr
        return None
    return None


def _constant_int_kwarg(call_node: ast.Call, name: str) -> int | None:
    for kw in call_node.keywords:
        if kw.arg == name and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, int):
            return kw.value.value
    return None


def _is_problem_scale_expr(node: ast.AST, scale_names: frozenset[str]) -> bool:
    if not scale_names:
        return False
    if isinstance(node, ast.Name):
        return node.id in scale_names
    if isinstance(node, ast.Attribute):
        return node.attr in scale_names or _is_problem_scale_expr(node.value, scale_names)
    if isinstance(node, ast.Subscript):
        return _is_problem_scale_expr(node.value, scale_names)
    if isinstance(node, ast.Call):
        return any(_is_problem_scale_expr(arg, scale_names) for arg in node.args)
    return False


def _is_bounded_while(node: ast.While, scale_names: frozenset[str]) -> bool:
    if isinstance(node.test, ast.Constant) and node.test.value is True:
        return _while_body_has_bounded_break(node)
    if isinstance(node.test, ast.BoolOp):
        return any(
            _compare_has_small_constant(value)
            or _compare_has_incrementing_counter_guard(value, node, scale_names)
            or _compare_has_runtime_guard(value)
            or _condition_collection_is_shrunk(value, node)
            for value in node.test.values
        ) or _while_body_has_bounded_break(node)
    if isinstance(node.test, ast.Compare):
        return (
            _compare_has_small_constant(node.test)
            or _compare_has_incrementing_counter_guard(node.test, node, scale_names)
            or _compare_has_runtime_guard(node.test)
        ) or _while_body_has_bounded_break(node)
    return (
        _condition_collection_is_shrunk(node.test, node)
        or _while_body_has_bounded_break(node)
    )


def _condition_collection_is_shrunk(test: ast.AST, node: ast.While) -> bool:
    names = _condition_collection_names(test)
    if not names:
        return False
    return any(_body_shrinks_collection(node.body, name) for name in names)


def _condition_collection_names(test: ast.AST) -> set[str]:
    if isinstance(test, ast.Name):
        return {test.id}
    if isinstance(test, ast.UnaryOp):
        return _condition_collection_names(test.operand)
    if isinstance(test, ast.BoolOp):
        names: set[str] = set()
        for value in test.values:
            names.update(_condition_collection_names(value))
        return names
    if isinstance(test, ast.Call) and isinstance(test.func, ast.Name):
        if test.func.id == "len" and test.args and isinstance(test.args[0], ast.Name):
            return {test.args[0].id}
    return set()


def _body_shrinks_collection(body: list[ast.stmt], name: str) -> bool:
    shrink_methods = {"remove", "discard", "pop", "clear"}
    for child in ast.walk(ast.Module(body=body, type_ignores=[])):
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
            if (
                isinstance(child.func.value, ast.Name)
                and child.func.value.id == name
                and child.func.attr in shrink_methods
            ):
                return True
        if isinstance(child, ast.AugAssign) and isinstance(child.target, ast.Name):
            if child.target.id == name and isinstance(child.op, (ast.Sub, ast.BitAnd)):
                return True
    return False


def _compare_has_incrementing_counter_guard(
    test: ast.AST,
    node: ast.While,
    scale_names: frozenset[str],
) -> bool:
    if not isinstance(test, ast.Compare):
        return False
    expressions = [test.left, *test.comparators]
    for index, expr in enumerate(expressions):
        if not isinstance(expr, ast.Name):
            continue
        if not _body_increments_counter(node.body, expr.id):
            continue
        other_exprs = [
            other
            for other_index, other in enumerate(expressions)
            if other_index != index
        ]
        if any(_is_bounded_limit_expr(other, scale_names) for other in other_exprs):
            return True
    return False


def _compare_has_runtime_guard(node: ast.AST) -> bool:
    return isinstance(node, ast.Compare) and _mentions_runtime_guard(node)


def _body_increments_counter(body: list[ast.stmt], name: str) -> bool:
    for child in ast.walk(ast.Module(body=body, type_ignores=[])):
        if isinstance(child, ast.AugAssign) and isinstance(child.target, ast.Name):
            if child.target.id == name and isinstance(child.op, (ast.Add, ast.Sub)):
                return True
        if isinstance(child, ast.Assign):
            if not any(
                isinstance(target, ast.Name) and target.id == name
                for target in child.targets
            ):
                continue
            if _expr_references_name(child.value, name):
                return True
    return False


def _is_bounded_limit_expr(expr: ast.AST, scale_names: frozenset[str]) -> bool:
    if _is_small_constant(expr):
        return True
    if isinstance(expr, ast.Name):
        lowered = expr.id.lower()
        return (
            expr.id.isupper()
            or "max" in lowered
            or "limit" in lowered
            or "cap" in lowered
            or "round" in lowered
            or "iter" in lowered
            or "strength" in lowered
        )
    if isinstance(expr, ast.Attribute):
        return expr.attr in scale_names or expr.attr in {
            "customer_count",
            "route_count",
        }
    if isinstance(expr, ast.Call):
        if isinstance(expr.func, ast.Name) and expr.func.id in {"len", "min", "max"}:
            return True
        return any(_is_bounded_limit_expr(arg, scale_names) for arg in expr.args)
    if isinstance(expr, ast.BinOp):
        return _is_bounded_limit_expr(expr.left, scale_names) or _is_bounded_limit_expr(
            expr.right,
            scale_names,
        )
    return False


def _while_body_has_bounded_break(node: ast.While) -> bool:
    for child in ast.walk(ast.Module(body=node.body, type_ignores=[])):
        if not isinstance(child, ast.If):
            continue
        if not _contains_break(child.body):
            continue
        if _compare_has_small_constant(child.test) or _mentions_runtime_guard(child.test):
            return True
    return False


def _contains_break(body: list[ast.stmt]) -> bool:
    return any(isinstance(child, ast.Break) for stmt in body for child in ast.walk(stmt))


def _mentions_runtime_guard(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Attribute) and child.attr in {
            "remaining_time",
            "elapsed_ms",
        }:
            return True
        if isinstance(child, ast.Name) and child.id in {
            "remaining_time",
            "elapsed_ms",
        }:
            return True
    return False


def _expr_references_name(node: ast.AST, name: str) -> bool:
    return any(
        isinstance(child, ast.Name) and child.id == name
        for child in ast.walk(node)
    )


def _compare_has_small_constant(node: ast.AST) -> bool:
    if not isinstance(node, ast.Compare):
        return False
    comparators = [node.left, *node.comparators]
    return any(_is_small_constant(expr) for expr in comparators)


def _is_small_constant(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Constant)
        and isinstance(node.value, int)
        and 0 <= node.value <= 1000
    )


class _ProblemScaleLoopGuard(ast.NodeVisitor):
    def __init__(self, scale_names: frozenset[str]) -> None:
        self._scale_names = scale_names
        self._depth = 0
        self.violations: List[str] = []

    def visit_For(self, node: ast.For) -> None:
        is_scale = _is_problem_scale_expr(node.iter, self._scale_names)
        if is_scale:
            self._depth += 1
            if self._depth >= 3:
                self.violations.append("three-level problem-scale nested loops")
        self.generic_visit(node)
        if is_scale:
            self._depth -= 1
