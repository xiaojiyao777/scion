# v0.4 Launch Absolute Scion Path Readiness - 2026-06-19

## Purpose

Prevent prepared WSL roots from passing static launch readiness when
`launch.env` uses relative checkout paths such as `SCION_DIR=scion` and
`PYTHONPATH=scion`. That relative form can import an older installed Scion when
the launched process changes working directories.

## Change

- `scion/tools/check_launch_readiness.py` now fails
  `run_script_pythonpath_enforced` with `scion_dir_not_absolute` when
  `SCION_DIR` is relative.
- `PYTHONPATH` must still contain that active checkout path before campaign
  start.
- Solver subprocesses already normalize inherited relative `PYTHONPATH`; this
  readiness check closes the prepared-root launch side of the same stale-import
  risk.

## Verification

Local:

- `PYTHONPATH=scion pytest -q scion/scion/tests/test_launch_readiness.py`:
  `78 passed`.
- `PYTHONPATH=scion pytest -q scion/scion/tests/test_rebuild_prepared_handoff.py scion/scion/tests/test_check_postrun_acceptance.py scion/scion/tests/test_rebuild_postrun_acceptance.py`:
  `49 passed`.
- `PYTHONPATH=scion python -m py_compile scion/tools/check_launch_readiness.py`:
  passed.

WSL:

- Runtime commit after applying the patch: `04a9f63a`.
- Same test groups passed in WSL:
  - `test_launch_readiness.py`: `78 passed`.
  - `test_rebuild_prepared_handoff.py`, `test_check_postrun_acceptance.py`,
    `test_rebuild_postrun_acceptance.py`: `49 passed`.
  - `py_compile scion/tools/check_launch_readiness.py`: passed.

Prepared roots regenerated with absolute
`PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion`:

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-abspath-04a9f63a-6r-gpt55-20260619T190850Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-abspath-04a9f63a-1r-gpt55-20260619T190850Z-claw`

Strict launch readiness with completion preflight:

- Both roots: `static_ready=true`, `launch_ready=false`, exit `64`.
- Both roots: `git_runtime_consistent=ok`, `git_runtime_worktree_clean=ok`,
  `problem_specific_prepared_handoff=ok`,
  `prepared_handoff_rebuild_declared_outputs_present=ok`,
  `run_script_pythonpath_enforced=ok`,
  `run_script_strict_postrun_rebuild=ok`, and
  `run_script_strict_postrun_readiness=ok`.
- Both roots record absolute WSL `SCION_DIR` and `PYTHONPATH`:
  `/home/xjy-ubuntu/research/or-autoresearch-agent/scion`.
- Remaining blocker is external provider auth:
  completion preflight returned HTTP `401`,
  `classification=not_authenticated`, `code=invalid_api_key`.
