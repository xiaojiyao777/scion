# Warehouse Short Debug 4R Guidance Launch - 2026-06-15

## Purpose

This is the short warehouse rerun after the targeted prompt/guidance repair in
commit `38262b7`. It tests whether repaired proposal context improves
branch-lesson semantic use and avoids obvious order-level/swap runtime-heavy
clean forks before any full `3 x 24R` warehouse longrun is relaunched.

This is a compact ON-arm debug, not a governance on/off comparison and not a
promotion-power experiment.

## Launch

- Server root:
  `/home/clawd/research/scion-experiments/v04-warehouse-short-debug-4r-guidance-20260615T205022Z`
- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-short-debug-4r-guidance-20260615T205022Z`
- WSL tmux session: `scion_warehouse_short4r_guidance_205022`
- Started at UTC: `2026-06-15T20:51:18Z`
- Repository on WSL: `/home/xjy-ubuntu/research/or-autoresearch-agent`
- Commit: `bf420c2`
- Warehouse prompt/guidance repair commit: `38262b7`
- Fixed replay tooling commit present: `2a1ccb8`
- Python: `/home/xjy-ubuntu/miniconda3/envs/scion/bin/python`
- Model: local `gpt-5.5`
- API base: `http://127.0.0.1:8080`

## Shape

- Problem: warehouse production package
- Protocol: `scion/problems/warehouse_delivery/protocol_prod.yaml`
- Split: experiment-local copied `split_manifest_prod.yaml`
- Safe data root: `/home/xjy-ubuntu/research/scion-data`
- Rounds: `4`
- Cells: `1`
- Measurement governance: `on`
- Context profile: `compact-measurement-diagnostics`
- Time limit: `30s`
- Early stop: disabled
- Agentic proposal: enabled
- Session timeout: `900s`
- Wrapper timeout: `5h`

## Launch Health Check

Initial server-side sync after launch confirmed:

- `status.txt` exists and reports `status=running`
- `commit=bf420c2`
- `run.log` reached campaign startup:
  `Starting campaign: warehouse_delivery (max_rounds=4, mock_llm=False, disable_early_stop=True)`
- experiment-local `problem.yaml`, `problem-v1.yaml`, and
  `split_manifest_prod.yaml` were created with WSL paths and absolute WSL safe
  data root.

## Acceptance

Accept this run as a valid repaired short debug only if:

- wrapper exits `0`;
- `run_validity.status=valid`;
- requested attempts are reconciled against Protocol rows and pre-Protocol
  failures;
- prompt manifests show branch-lesson context is no longer truncated in the
  relevant hypothesis contexts, or any truncation is quantified and explained;
- clean-fork hypotheses expose semantic contrast fields rather than merely
  restating prior lessons;
- order-level/swap candidates either stay bounded or any remaining V9 runtime
  failure is concrete evidence for the next repair;
- code-stage source visibility remains intact.

The full warehouse `3 x 24R` longrun remains blocked until this short run is
postrun-audited.
