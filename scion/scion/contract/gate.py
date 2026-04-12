"""ContractGate: static validation of HypothesisProposal and PatchProposal."""
from __future__ import annotations

import ast
import fnmatch
import time
from typing import List, Optional

from scion.config.problem import ProblemSpec
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


class ContractGate:
    """Static gate that validates proposals before any code is executed."""

    def __init__(self, problem_spec: ProblemSpec) -> None:
        self._spec = problem_spec

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate_hypothesis(
        self,
        hypothesis: HypothesisProposal,
        active_hypotheses: List[HypothesisRecord],
        blacklist: List[HypothesisRecord],
    ) -> ContractResult:
        """Run C1, C2, C3, C10 checks on a HypothesisProposal."""
        checks: List[CheckResult] = []

        checks.append(self._c1_schema(hypothesis))
        checks.append(self._c2_change_locus(hypothesis))
        checks.append(self._c3_action_target(hypothesis))
        checks.append(self._c10_novelty(hypothesis, active_hypotheses, blacklist))

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
    # C2: change_locus must be a known operator category
    # ------------------------------------------------------------------

    def _c2_change_locus(self, h: HypothesisProposal) -> CheckResult:
        t0 = time.monotonic_ns()
        categories = self._spec.operator_categories
        passed = h.change_locus in categories
        detail = (
            "change_locus ok"
            if passed
            else f"change_locus '{h.change_locus}' not in {categories}"
        )
        return _cr("C2_change_locus", passed, "heavy", detail, t0)

    # ------------------------------------------------------------------
    # C3: action-target consistency
    # ------------------------------------------------------------------

    def _c3_action_target(self, h: HypothesisProposal) -> CheckResult:
        t0 = time.monotonic_ns()
        passed = True
        detail = "action-target ok"

        if h.action in ("modify", "remove"):
            if not h.target_file:
                passed = False
                detail = f"action='{h.action}' requires target_file"
        elif h.action == "create_new":
            # create_new should NOT have a target_file pointing to an existing operator
            # (no hard rule in the spec, so we just require the action is known)
            pass

        return _cr("C3_action_target", passed, "heavy", detail, t0)

    # ------------------------------------------------------------------
    # C4: file whitelist — file_path must match an editable pattern
    # ------------------------------------------------------------------

    def _c4_file_whitelist(self, patch: PatchProposal) -> CheckResult:
        t0 = time.monotonic_ns()
        file_rel = patch.file_path.lstrip("/")
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
        file_rel = patch.file_path.lstrip("/")
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
    # C7: Interface signature — if file contains a class, it must have
    #     execute(self, solution, rng)
    # ------------------------------------------------------------------

    def _c7_interface_signature(self, patch: PatchProposal) -> CheckResult:
        t0 = time.monotonic_ns()
        if patch.action == "delete":
            return _cr("C7_interface", True, "light", "delete action — no interface check", t0)

        try:
            tree = ast.parse(patch.code_content)
        except SyntaxError:
            return _cr("C7_interface", False, "light", "unparseable code", t0)

        classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        if not classes:
            # No class defined — not an operator file, skip check
            return _cr("C7_interface", True, "light", "no class found — skipped", t0)

        for cls in classes:
            for node in ast.walk(cls):
                if isinstance(node, ast.FunctionDef) and node.name == "execute":
                    args = [a.arg for a in node.args.args]
                    if args == ["self", "solution", "rng"]:
                        return _cr("C7_interface", True, "light", "execute signature ok", t0)
                    else:
                        return _cr(
                            "C7_interface",
                            False,
                            "light",
                            f"execute signature wrong: {args}, expected ['self','solution','rng']",
                            t0,
                        )

        return _cr(
            "C7_interface",
            False,
            "light",
            "class found but no execute method defined",
            t0,
        )

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
    # C10: Novelty check
    # ------------------------------------------------------------------

    def _c10_novelty(
        self,
        h: HypothesisProposal,
        active_hypotheses: List[HypothesisRecord],
        blacklist: List[HypothesisRecord],
    ) -> CheckResult:
        t0 = time.monotonic_ns()
        # For create_new, target_file is typically None/empty so two different new
        # operators in the same category would collide — add hypothesis prefix to distinguish.
        if h.action == "create_new":
            key = (h.change_locus, h.action, h.target_file, h.hypothesis_text[:50])
        else:
            key = (h.change_locus, h.action, h.target_file)
        for existing in active_hypotheses + blacklist:
            if existing.action == "create_new":
                existing_key = (
                    existing.change_locus,
                    existing.action,
                    existing.target_file,
                    existing.hypothesis_text[:50] if existing.hypothesis_text else "",
                )
            else:
                existing_key = (
                    existing.change_locus,
                    existing.action,
                    existing.target_file,
                )
            if key == existing_key:
                return _cr(
                    "C10_novelty",
                    False,
                    "light",
                    f"duplicate of existing hypothesis (key={key})",
                    t0,
                )
        return _cr("C10_novelty", True, "light", "novel", t0)


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
