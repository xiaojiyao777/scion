# CVRP Successor26 Short-Horizon Seed Trajectory Selector In-Flight - 2026-06-30

## Status

Successor26 is running on the server-local `claw` environment.

- Run root:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor26-short-horizon-seed-trajectory-selector-server-2r-gpt55-20260630T132452Z-claw`
- PID: `1279060`
- Git commit: `6896451f`
- Model: `gpt-5.5`
- Base URL: `http://127.0.0.1:8080`
- Completion preflight: passed
- Rounds: `2`
- Time limit: `30`
- Forced surface/action/target:
  `solver_design` / `modify` /
  `policies/baseline_modules/scheduler.py`

## WSL Launch Attempt

The first WSL launch attempt did not start campaign execution:

- WSL run root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-successor26-short-horizon-seed-trajectory-selector-2r-gpt55-20260630T132127Z-claw`
- WSL runner commit: `30779274`
- Wrapper status: `finished`
- Wrapper exit status: `64`
- Pre-campaign completion preflight: failed
- HTTP status: `502`
- Failure detail: `tls handshake eof` while connecting to
  `https://chatgpt.com/backend-api/codex/responses`

Follow-up checks showed the WSL local gateway still listed `gpt-5.5`, but WSL
HTTPS requests to `chatgpt.com`, `api.openai.com`, and `example.com` failed at
TLS. Treat the WSL attempt as an environment/network preflight failure, not as a
Scion campaign result.

## Mechanism Contract

The campaign should implement and test
`short_horizon_seed_trajectory_selector`:

- compare a small existing seed set after a strictly bounded short-horizon
  trajectory;
- record baseline versus selected post-trajectory total-distance delta before
  full ALNS/VNS;
- keep construction edits limited to narrow seed candidate exposure if needed;
- keep generic core and `DecisionFeatures` unchanged.

## Next Check

When the run finishes, inspect `run_status.json`, postrun acceptance readiness,
formal row decisions, mechanism telemetry, and CMT2/CMT4 case-level deltas.
