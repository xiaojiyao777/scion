# Archived Run Scripts

*Last updated: 2026-05-07*

This folder contains historical v0.2/v0.3 launcher and direct-runner scripts
that are no longer the active v0.4 experiment entry points.

Use the v0.4 CLI instead:

```bash
cd /home/clawd/research/or-autoresearch-agent/scion
/home/clawd/miniconda3/envs/claw/bin/python -m scion.cli.main run --help
```

The only root-level helper intentionally left outside this archive is:

```text
run_cvrp_controlled_e2e.py
```

It remains useful for the current v0.4 controlled CVRP E2E smoke and final
evidence plumbing.

Archived files:

| File | Historical role |
| --- | --- |
| `run_v02_sprintd.py` | v0.2 Sprint D direct campaign runner. |
| `run_v02_uuid_fix_validation.py` | v0.2 UUID-fix validation runner. |
| `run_sprint_f4.sh` | v0.2/v0.3 Sprint F4 tmux launcher. |
| `run_mock_campaign.py` | old warehouse mock direct-runner. |
| `run_full_campaign.py` | old warehouse real-LLM direct-runner. |
| `run_v3_campaign.py` | old warehouse v3 direct-runner before the CLI became the main path. |
| `run_w16_campaign.py` | v0.3 W16 validation campaign runner. |
| `launch_w16.sh` | v0.3 W16 batch launcher. |
| `auto_w16.sh` | v0.3 W16 auto batch launcher. |
| `run_validation_campaign.py` | v0.3 post-optimization / closure validation runner. |
| `run_closure_validation.py` | v0.3 closure validation multi-campaign launcher. |
| `launch_closure_validation.sh` | v0.3 closure validation wrapper. |

These scripts were originally written to live in the `scion/` root and several
of them compute paths from `Path(__file__).parent` or hardcoded absolute paths.
If a historical experiment must be replayed, copy the relevant script back to a
throwaway checkout or update its paths explicitly. Do not use these files for
new v0.4 CVRP experiments.
