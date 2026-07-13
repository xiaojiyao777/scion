# Operations Docs

*Last updated: 2026-07-13*

- [Scion v0.4 本地实验运行、回溯与复现手册](experiment-runbook.zh.md)
- [Historical v0.3 experiment concepts](experiment-quickref.md)
- [Historical v0.2/v0.3 baseline management](experiment-baseline-management.md)
- [Post-run analysis handoff](postrun-analysis-handoff.md)

Useful local tooling:

- `scion/tools/launch_cvrp_direct_campaign.py`: prepare or launch detached
  CVRP direct-v3 campaigns.
- `scion/tools/launch_warehouse_direct_campaign.py`: prepare or launch detached
  warehouse direct-v3 campaigns.
- `scion/tools/check_completion_proxy.py`: require a real, non-empty completion
  from the configured model route before a formal campaign starts.
- `scion/tools/postrun_artifact_inventory.py`: summarize run artifacts before
  delegating trace-level analysis.

These documents are for running and managing campaigns. Architecture and design
sources belong under `../../design/`.
