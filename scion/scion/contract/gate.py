"""ContractGate: static validation of HypothesisProposal and PatchProposal."""
from __future__ import annotations

import ast
import fnmatch
import hashlib
import re
import time
from typing import Any, List, Optional

from scion.config.problem import ProblemSpec
from scion.core.operator_interface import parse_execute_signature
from scion.core.paths import normalize_relative_patch_path
from scion.core.models import (
    CheckResult,
    ContractResult,
    HypothesisProposal,
    HypothesisRecord,
    PatchProposal,
)

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

# builtins that open files for writing (open is ok for reading)
_SENSITIVE_OPEN_MODES = frozenset({"w", "wb", "a", "ab", "x", "xb", "w+", "wb+", "a+", "ab+"})


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

_PROBLEM_SCALE_NAMES = frozenset(
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

    def __init__(
        self,
        problem_spec: ProblemSpec,
        *,
        operator_execute_signature: str | None = None,
    ) -> None:
        self._spec = problem_spec
        self._operator_signature = parse_execute_signature(operator_execute_signature)

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

    def validate_patch(self, patch: PatchProposal) -> ContractResult:
        """Run C4–C9 checks on a PatchProposal."""
        checks: List[CheckResult] = []

        checks.append(self._c4_file_whitelist(patch))
        checks.append(self._c5_frozen_files(patch))
        # Short-circuit: no point running AST checks on a file we already rejected
        if not checks[-1].passed or not checks[-2].passed:
            return _build_result(checks)

        checks.append(self._c6_ast_syntax(patch))
        if not checks[-1].passed:
            return _build_result(checks)

        checks.append(self._c7_interface_signature(patch))
        checks.append(self._c8_import_whitelist(patch))
        checks.append(self._c9_sensitive_api(patch))
        checks.append(self._c9b_non_rng_random(patch))
        checks.append(self._c9c_complexity_bound(patch))

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

        return _cr("C1_schema", passed, "heavy", detail, t0)

    # ------------------------------------------------------------------
    # C2: change_locus must be a known research locus
    # ------------------------------------------------------------------

    def _c2_change_locus(self, h: HypothesisProposal) -> CheckResult:
        t0 = time.monotonic_ns()
        categories = self._spec.operator_categories
        passed = h.change_locus in categories
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
            allowed_attr = {
                "create_new": "create_new_allowed",
                "modify": "modify_allowed",
                "remove": "remove_allowed",
            }.get(h.action)
            if allowed_attr is not None and not bool(
                getattr(surface, allowed_attr, True)
            ):
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
                    f"{list(getattr(surface, 'target_files', []) or [])}"
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
                    f"{list(getattr(surface, 'target_files', []) or [])}"
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
        passed = any(fnmatch.fnmatch(file_rel, pat) for pat in editable)
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
        violated = [pat for pat in frozen if fnmatch.fnmatch(file_rel, pat)]
        passed = len(violated) == 0
        detail = "not frozen" if passed else f"'{file_rel}' matches frozen patterns {violated}"
        return _cr("C5_frozen_files", passed, "heavy", detail, t0)

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

    def _c7_interface_signature(self, patch: PatchProposal) -> CheckResult:
        t0 = time.monotonic_ns()
        if patch.action == "delete":
            return _cr("C7_interface", True, "light", "delete action — no interface check", t0)

        try:
            file_rel = normalize_relative_patch_path(patch.file_path)
        except ValueError as exc:
            return _cr("C7_interface", False, "light", str(exc), t0)

        try:
            tree = ast.parse(patch.code_content)
        except SyntaxError:
            return _cr("C7_interface", False, "light", "unparseable code", t0)

        surface = self._surface_for_patch_path(file_rel)
        kind = getattr(surface, "kind", "operator") if surface is not None else None
        if kind == "policy":
            return self._c7_policy_interface(tree, surface, t0)
        if kind == "config":
            return _cr(
                "C7_interface",
                True,
                "light",
                "config surface interface check not implemented — skipped",
                t0,
            )

        classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        if not classes:
            if surface is not None and kind == "operator":
                return _cr(
                    "C7_interface",
                    False,
                    "light",
                    "operator surface file must define an operator class",
                    t0,
                )
            return _cr("C7_interface", True, "light", "no class found — skipped", t0)

        for cls in classes:
            for node in ast.walk(cls):
                if isinstance(node, ast.FunctionDef) and node.name == "execute":
                    args = [a.arg for a in node.args.args]
                    if tuple(args) == self._operator_signature.args:
                        return _cr("C7_interface", True, "light", "execute signature ok", t0)
                    else:
                        return _cr(
                            "C7_interface",
                            False,
                            "light",
                            "execute signature wrong: "
                            f"{args}, expected {self._operator_signature.expected_args_detail}",
                            t0,
                        )

        return _cr(
            "C7_interface",
            False,
            "light",
            "class found but no execute method defined",
            t0,
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

        required = tuple(getattr(surface, "required_functions", []) or [])
        if not required:
            return _cr(
                "C7_interface",
                True,
                "light",
                "policy surface has no required functions declared — skipped",
                start_ns,
            )

        functions = {
            node.name: [arg.arg for arg in node.args.args]
            for node in getattr(tree, "body", [])
            if isinstance(node, ast.FunctionDef)
        }
        missing = [name for name in required if name not in functions]
        wrong_args = {
            name: args
            for name, args in functions.items()
            if name in required and args != ["instance", "time_limit_sec"]
        }
        if missing or wrong_args:
            detail_parts: list[str] = []
            if missing:
                detail_parts.append(f"missing required functions {missing}")
            if wrong_args:
                detail_parts.append(
                    "wrong policy function args "
                    f"{wrong_args}, expected ['instance', 'time_limit_sec']"
                )
            return _cr(
                "C7_interface",
                False,
                "light",
                "; ".join(detail_parts),
                start_ns,
            )

        return _cr("C7_interface", True, "light", "policy interface ok", start_ns)

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

            # Direct call: eval(...), exec(...), subprocess(...)
            if isinstance(func, ast.Name):
                if func.id in _SENSITIVE_APIS:
                    violations.append(func.id)
                elif func.id == "open":
                    write_mode = _open_has_write_mode(node)
                    if write_mode:
                        violations.append(f"open(..., mode={write_mode!r})")

            # Attribute call: os.system(...), subprocess.Popen(...), socket.socket(...)
            elif isinstance(func, ast.Attribute):
                obj_name: Optional[str] = None
                if isinstance(func.value, ast.Name):
                    obj_name = func.value.id

                if obj_name == "os" and func.attr in _SENSITIVE_OS_ATTRS:
                    violations.append(f"os.{func.attr}")
                elif obj_name in _SENSITIVE_APIS:
                    violations.append(f"{obj_name}.{func.attr}")
                elif func.attr == "open":
                    # open() calls: check for write modes in kwargs or positional args
                    write_mode = _open_has_write_mode(node)
                    if write_mode:
                        violations.append(f"open(..., mode={write_mode!r})")

        passed = len(violations) == 0
        detail = "no sensitive APIs" if passed else f"sensitive APIs detected: {violations}"
        return _cr("C9_sensitive_api", passed, "heavy", detail, t0)

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

    def _c9c_complexity_bound(self, patch: PatchProposal) -> CheckResult:
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
                scale_args = sum(1 for arg in node.args if _is_problem_scale_expr(arg))
                repeat_scale = _constant_int_kwarg(node, "repeat")
                if scale_args >= 2 or (scale_args == 1 and repeat_scale is not None and repeat_scale > 1):
                    violations.append("product(... problem-scale iterables ...)")

        for node in ast.walk(tree):
            if isinstance(node, ast.While) and not _is_bounded_while(node):
                violations.append("uncapped while loop")

        loop_guard = _ProblemScaleLoopGuard()
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
        key = self._novelty_key(h)
        for existing in active_hypotheses + blacklist:
            # Rejected hypotheses only block if they come from the same champion version;
            # a champion upgrade opens the door to retry previously rejected modify paths.
            if existing.status == "rejected":
                if existing.base_champion_version != current_champion_version:
                    continue
            existing_key = self._novelty_key(existing)
            if key == existing_key:
                return _cr(
                    "C10_novelty",
                    False,
                    "light",
                    f"duplicate of existing hypothesis (key={key})",
                    t0,
                )
        return _cr("C10_novelty", True, "light", "novel", t0)

    def _novelty_key(self, h: HypothesisProposal | HypothesisRecord) -> tuple[Any, ...]:
        # create_new has no reliable singleton file identity, so keep intent in the key.
        if h.action == "create_new":
            return (
                h.change_locus,
                h.action,
                h.target_file,
                (h.hypothesis_text or "")[:50],
            )

        # Policy singleton files need semantic novelty: distinct policy hypotheses
        # against the same target pass, while exact same intents still fail C10.
        if h.action == "modify":
            surface = self._surface_for_hypothesis(h)
            if getattr(surface, "kind", None) == "policy":
                return (
                    h.change_locus,
                    h.action,
                    h.target_file,
                    self._semantic_intent_fingerprint(h),
                )

        # Ordinary modify/remove remains strict by locus/action/target file.
        return (h.change_locus, h.action, h.target_file)

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

    @staticmethod
    def _semantic_intent_fingerprint(
        h: HypothesisProposal | HypothesisRecord,
    ) -> str:
        parts = [
            getattr(h, "hypothesis_text", None) or "",
            getattr(h, "target_weakness", None) or "",
            getattr(h, "expected_effect", None) or "",
            getattr(h, "target_runtime_effect", None) or "",
            getattr(h, "runtime_budget_strategy", None) or "",
        ]
        normalized = " ".join(parts).casefold()
        normalized = re.sub(r"[^a-z0-9_.:/+-]+", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]

    def _research_surfaces(self) -> list[Any]:
        return list(getattr(self._spec, "research_surfaces", []) or [])

    def _surface_by_name(self, name: str) -> Any | None:
        for surface in self._research_surfaces():
            if getattr(surface, "name", None) == name:
                return surface
        return None

    def _surface_for_patch_path(self, file_rel: str) -> Any | None:
        for surface in self._research_surfaces():
            if self._target_matches_surface(file_rel, surface):
                return surface
        return None

    def _target_matches_surface(self, file_rel: str, surface: Any) -> bool:
        try:
            normalized = normalize_relative_patch_path(file_rel)
        except ValueError:
            return False
        target_files = getattr(surface, "target_files", []) or []
        return any(
            fnmatch.fnmatch(normalized, str(pattern).lstrip("/"))
            for pattern in target_files
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


def _in_whitelist(module_top: str, whitelist: set) -> bool:
    """Return True if module_top is explicitly allowed."""
    return module_top in whitelist


def _open_has_write_mode(call_node: ast.Call) -> Optional[str]:
    """Return the mode string if open() is called with a write mode, else None."""
    # open(path, mode) — mode is the second positional arg
    if len(call_node.args) >= 2:
        arg = call_node.args[1]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            if arg.value in _SENSITIVE_OPEN_MODES:
                return arg.value

    # open(path, mode=...) as keyword
    for kw in call_node.keywords:
        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
            if kw.value.value in _SENSITIVE_OPEN_MODES:
                return kw.value.value

    return None


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


def _is_problem_scale_expr(node: ast.AST) -> bool:
    if isinstance(node, ast.Name):
        return node.id in _PROBLEM_SCALE_NAMES
    if isinstance(node, ast.Attribute):
        return node.attr in _PROBLEM_SCALE_NAMES or _is_problem_scale_expr(node.value)
    if isinstance(node, ast.Subscript):
        return _is_problem_scale_expr(node.value)
    if isinstance(node, ast.Call):
        return any(_is_problem_scale_expr(arg) for arg in node.args)
    return False


def _is_bounded_while(node: ast.While) -> bool:
    if isinstance(node.test, ast.Constant) and node.test.value is True:
        return False
    if isinstance(node.test, ast.BoolOp):
        return any(_compare_has_small_constant(value) for value in node.test.values)
    if isinstance(node.test, ast.Compare):
        return _compare_has_small_constant(node.test)
    return False


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
    def __init__(self) -> None:
        self._depth = 0
        self.violations: List[str] = []

    def visit_For(self, node: ast.For) -> None:
        is_scale = _is_problem_scale_expr(node.iter)
        if is_scale:
            self._depth += 1
            if self._depth >= 3:
                self.violations.append("three-level problem-scale nested loops")
        self.generic_visit(node)
        if is_scale:
            self._depth -= 1
