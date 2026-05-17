# 04 - Contract And Static Gates

## Reviewed Gates

- C6/C7 interface and surface target checks.
- C8 import whitelist.
- C9 sensitive API detection.
- C9b non-RNG random.
- C9c complexity bound.
- C9d instance identity.
- C9e solver-design helper integration.

The static gate set is substantially better than prompt-only control, but several checks are syntactic blacklists that generated Python can bypass.

## Findings

### F-01 - C9 misses dynamic sensitive API forms

- Severity: Critical
- Files:
  - `scion/scion/contract/gate.py:716`
  - `scion/scion/contract/gate.py:725`
  - `scion/scion/tests/test_contract.py:513`
- Problem: C9 catches direct `os.system(...)`, direct `open(...)`, and direct `*.read_text(...)`, but not `__import__("os").system(...)`, `getattr(__import__("os"), "system")(...)`, or dynamic file/path access.
- Trigger path: Because C8 checks only import statements, a patch can use the built-in `__import__` function and avoid both C8 and C9. The probe in the appendix confirms the full `validate_patch` result passed for a solver-design patch using this form.
- Impact: This is the highest-risk boundary bypass in the review. It allows arbitrary code patterns into the runtime subprocess if the generated code is later executed.
- Suggested fix: Ban dynamic import and reflective call primitives in generated code, and add tests for each bypass. Consider an AST allowlist per surface rather than expanding the blacklist indefinitely.

### F-05 - C9e reachability can be spoofed by dead load references

- Severity: Medium
- Files:
  - `scion/scion/contract/checks/solver_design_integration.py:114`
  - `scion/scion/contract/checks/solver_design_integration.py:149`
  - `scion/scion/contract/checks/solver_design_integration.py:889`
- Problem: `_call_reference_names` adds every loaded `ast.Name` to the call/reference set, not just actual calls or recognized first-class registration sites. This means a helper can be considered reachable even when it is only assigned or referenced in dead code.
- Trigger path: The short probe in the appendix used:

```python
def solve(instance, rng, time_limit_sec, context):
    unused = helper
    return context.nearest_neighbor()

def helper(instance, rng, time_limit_sec, context):
    return context.nearest_neighbor()
```

ContractGate returned `C9e_solver_design_integration True new solver_design helper functions are integrated`.

- Impact: C9e can fail to detect inert helper additions. Runtime smoke may still catch no behavioral change in some cases, but the static integration claim is not reliable.
- Suggested fix: Count only `ast.Call` edges for normal helpers. If first-class helper registration is needed, explicitly recognize known scheduler/operator registries and list/dict structures that are consumed by active solver paths. Add tests for `unused = helper`, `if False: helper`, and dead collections.

### F-06 - C9d instance identity check misses dataclass identity leaks

- Severity: Medium
- Files:
  - `scion/scion/contract/gate.py:1723`
  - `scion/scion/contract/gate.py:1735`
  - `scion/scion/contract/gate.py:1743`
  - `scion/scion/problems/cvrp/models.py:19`
- Problem: C9d flags `instance.name` and literal `getattr(instance, "name")`/`hasattr(instance, "name")`. It does not flag `repr(instance)`, `str(instance)`, `vars(instance)`, `instance.__dict__`, computed string `getattr(instance, "na" + "me")`, or dataclass field iteration.
- Trigger path: `CvrpInstance` is a frozen dataclass with a `name` field. Its default repr includes the case name. A generated policy/solver-design patch can branch on `if "X-n101" in repr(instance): ...` without touching `instance.name`.
- Impact: Case-specific behavior can leak into singleton policies and solver-design code despite the instance-identity surface rule. This is especially relevant for formal split integrity.
- Suggested fix: For identity-disallowed surfaces, reject `repr(instance)`, `str(instance)`, `vars(instance)`, `instance.__dict__`, dataclass field reflection, and nonliteral `getattr` on `instance`. Better, pass a restricted instance view without a `name` field to identity-disallowed surfaces.

### F-02 - Core ContractGate lacks the preferred-target baseline-wrapper rule

- Severity: High
- Files:
  - `scion/scion/problems/cvrp/adapter.py:1247`
  - `scion/scion/problems/cvrp/problem-v1.yaml:1030`
  - `scion/scion/contract/checks/solver_design_integration.py:149`
- Problem: The no-`context.baseline` rule for preferred `baseline_algorithm.py` exists in adapter preview and prompt/spec text, but C9e returns pass when no new helper functions are present. A direct `solve(...): return context.baseline(...)` patch has no new helper and is treated as integrated.
- Trigger path: The appendix probe confirmed ContractGate pass for this wrapper. APS algorithm smoke currently catches it through adapter preview, but C9e itself does not encode the rule.
- Impact: The static gate does not fully represent the solver-design boundary. This leaves core non-APS paths dependent on later statistical failure instead of semantic rejection.
- Suggested fix: Add a ContractGate check for forbidden solver-design context calls by target path. Keep adapter preview as fast feedback, but make ContractGate the authoritative static layer.

### F-13 - C9c is strong for obvious loops but still depends on declared scale-term vocabulary

- Severity: Low
- Files:
  - `scion/scion/contract/gate.py:961`
  - `scion/scion/contract/gate.py:1577`
  - `scion/scion/contract/gate.py:2562`
  - `scion/scion/problems/cvrp/problem-v1.yaml:903`
- Problem: C9c uses surface `bounds.complexity_scale_terms` when present. That is good for CVRP because `solver_design` declares `time_limit_sec`, `customer_count`, `route_count`, `candidate_count`, and `local_search_passes`. The fragility is that nondeclared aliases or helper-derived collections may be invisible to `_is_problem_scale_expr`.
- Trigger path: Generated code can copy problem-scale data into names outside the declared vocabulary and then nest loops on the copied names. Some cases may still be caught by unbounded while/combinations checks, but not all problem-scale loop shapes are semantically known.
- Impact: This is lower severity than F-01/F-05 because C9c already catches many high-risk forms and the recent 6-round run log showed an APS candidate rejected on `uncapped while loop at line 141`. The risk is regression when new helper names or surfaces are added.
- Suggested fix: Add semantic propagation for aliases assigned from known scale fields, and add tests for copied customer/route collections and helper-returned candidate lists.

## Existing Test Gaps

- `test_contract.py` covers direct `os.system` and direct `open`, but not dynamic import or dynamic attribute bypasses.
- Solver-design integration tests cover real helper call paths, but not dead references.
- Instance-identity tests should include dataclass repr and reflection forms.

