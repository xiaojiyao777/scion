# v0.4 Subprocess PYTHONPATH Current-Checkout Repair

Date: 2026-06-19

## Purpose

Runtime smoke and protocol subprocesses run `solver.py` from a branch or smoke
workspace. If the parent session inherited a relative `PYTHONPATH` such as
`scion`, that relative entry was interpreted from the child workspace after
`cwd` switched, not from the parent checkout. On WSL this allowed the solver
subprocess to import an older installed Scion package and fail baseline
solver-design smoke with a stale `SolverAlgorithmContext` API.

## Change

- `LocalSubprocessRunner` now normalizes inherited relative `PYTHONPATH` entries
  against the parent process cwd before launching the child process.
- The solver workspace still stays first on `PYTHONPATH` so branch-local
  policies remain importable.
- Empty or missing `PYTHONPATH` remains unchanged apart from the existing
  workspace entry.

No solver semantics, protocol gates, Decision, lifecycle, or promotion behavior
changed.

## Verification

Focused runner regression:

```bash
PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_runner.py::TestRunnerSuccess::test_relative_pythonpath_is_resolved_before_child_cwd_switch
```

Local result: `1 passed in 0.17s`.

WSL regression plus previously failing code-phase planner smoke path:

```bash
PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/pytest -q \
  scion/scion/tests/test_runner.py::TestRunnerSuccess::test_relative_pythonpath_is_resolved_before_child_cwd_switch \
  scion/scion/tests/unit/test_agentic_session_model_planner.py::test_code_phase_targeted_read_context_carries_active_fact_anchor
```

WSL result: `2 passed in 16.38s`.

Syntax check:

```bash
PYTHONPATH=scion python -m py_compile \
  scion/scion/runtime/subprocess_runner.py
```

Local result: passed.

## Acceptance

Accepted as a runtime-path repair. Solver smoke/protocol subprocesses now keep
the current checkout on the import path even when the operator launched Scion
with a relative `PYTHONPATH`.
