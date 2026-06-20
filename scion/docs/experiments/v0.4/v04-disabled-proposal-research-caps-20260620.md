# Disabled Proposal And Agentic Research Caps

Date: 2026-06-20

## Decision

Focused v0.4 warehouse and CVRP prepared roots now use `0` to disable
proposal-attempt, proposal-quality, APS step/tool-call, code-tool-call, and
observation-character caps:

- `proposal_attempt_limit=0`
- `proposal_quality_loop_limit=0`
- `agentic_tool_max_steps=0`
- `agentic_tool_max_calls=0`
- `agentic_code_tool_max_calls=0`
- `agentic_observation_max_chars=0`

The APS wall-time guard remains enabled at `agentic_session_timeout_sec=3600`.
The core campaign loop still preserves the high-water
`campaign_safety_step_limit`, the normal circuit breaker, and explicit
per-path guards such as scheduler active-slot and telemetry-repair limits.

This removes fixed prepared-run caps that could stop agentic repair,
schema-quality retries, source/tool exploration, or hypothesis/code-generation
before Scion reached useful effective research rounds.

## Boundary

This is generic runtime control-plane behavior. It does not add CVRP,
warehouse, BKS, case-hardness, prompt text, or mechanism ranking fields to
`DecisionFeatures`. Problem-specific diagnostics remain problem-owned,
proposal-only inputs.

## Implementation

- Core `CampaignLoop` treats configured proposal-attempt and proposal-quality
  limits of `0` as disabled.
- APS budget helpers treat step, tool-call, and observation limits of `0` as
  disabled. Disabled observation caps preserve full observations instead of
  compacting or charging them against a zero ceiling.
- The old aggregate `attempt_limit_exhausted` fallback is now a
  `campaign_safety_step_limit_exhausted` safety stop.
- Warehouse and CVRP focused launchers default proposal and APS research caps
  to `0`; CLI validation accepts `0` for those caps while still requiring a
  positive session timeout.
- Launch readiness still fails missing, invalid, or command-disconnected cap
  fields. Exact `0` values for caps with disabled runtime semantics are
  reported under `run_script_proposal_headroom_enforced.detail.disabled`, not
  as warnings or launch gates. Positive values below the historical
  recommendation remain audit warnings only.

## Verification

Local:

```bash
pytest scion/scion/tests/unit/core/test_retry_round_accounting_campaign_loop.py -q
pytest scion/scion/tests/test_cvrp_agentic_launcher.py scion/scion/tests/test_warehouse_agentic_launcher.py -q
pytest scion/scion/tests/test_launch_readiness.py -q
pytest scion/scion/tests/test_cli_run_options.py -q
pytest scion/scion/tests/test_campaign_basics_continue.py -q
pytest scion/scion/tests/unit/test_agentic_session_grounding.py scion/scion/tests/unit/test_agentic_session_tool_selection.py scion/scion/tests/test_cli_run_options.py scion/scion/tests/test_cvrp_agentic_launcher.py scion/scion/tests/test_warehouse_agentic_launcher.py -q
```

Local focused results:

- Proposal-cap repair suite: `204 passed` across campaign-loop, launcher,
  readiness, CLI, and campaign-basics tests.
- APS-cap suite: `79 passed`.
- Final readiness suite after disabled-warning cleanup: `101 passed`.

WSL with explicit checkout `PYTHONPATH`:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest \
  scion/scion/tests/unit/core/test_retry_round_accounting_campaign_loop.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_cli_run_options.py \
  scion/scion/tests/test_campaign_basics_continue.py -q
```

WSL focused results:

- Proposal-cap repair suite: `204 passed`.
- APS-cap and launcher/CLI/readiness suite: `180 passed`.
- Final readiness suite after disabled-warning cleanup: `101 passed`.

## Current Prepared Roots

Generated on WSL at launch-authoritative runtime commit `27de4218`; local
equivalent HEAD is `9c284940`. Both roots are mirrored under
`/home/clawd/research/scion-experiments/` with the same directory names.

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-size70hypctx-27de4218-nocaps-aps0-preflight-6r-gpt55-20260620T111148Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-phase4-size70hypctx-27de4218-nocaps-aps0-preflight-4r-gpt55-20260620T111201Z-claw`

Strict launch readiness for both reports:

- `static_ready=true`
- `launch_ready=false`
- `failed_static_required_checks=[]`
- `failed_required_checks=["completion_preflight"]`
- `headroom_status=ok`
- `headroom_failures=[]`
- `headroom_warning_count=0`
- `disabled_count=18`

The remaining blocker is external `gpt-5.5` completion auth:
HTTP `401`, `classification=not_authenticated`, `code=invalid_api_key`;
auth pool `active=0`, `total=1`.
