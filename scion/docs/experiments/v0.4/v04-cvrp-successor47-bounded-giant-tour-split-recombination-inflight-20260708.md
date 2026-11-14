# CVRP successor47 inflight: bounded giant-tour split recombination

Date: 2026-07-08

Run root:
`/home/clawd/research/scion-experiments/v04-cvrp-successor47-bounded-giant-tour-split-recombination-server-claw-2r-gpt55-2r-gpt55-20260708T021541Z-claw`

## Launch

- Mechanism id: `bounded_giant_tour_split_recombination`.
- Design:
  `scion/docs/experiments/v0.4/v04-cvrp-successor47-bounded-giant-tour-split-recombination-design-20260708.md`.
- Git commit: `00bfeb60`.
- Runner: server-local conda `claw`.
- Model: local `gpt-5.5`.
- Started UTC: `2026-07-08T02:15:43Z`.
- PID: `1729980`.
- Rounds: `2`.
- Resume source:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor46b-best-solution-activation-contract-repair-server-claw-2r-gpt55-2r-gpt55-20260707T150022Z-claw`.
- Completion preflight: `ok: true`; chat completion returned non-empty content.

## Prepared Target

`prepared_run_manifest.v1.json` binds the prepared slot to:

- `target_intent_required_mechanism_ids`:
  `["bounded_giant_tour_split_recombination"]`
- `successor47_target_intent.mechanism_id`:
  `bounded_giant_tour_split_recombination`
- `successor47_target_intent.target_file`:
  `policies/baseline_modules/giant_tour_split.py`

## Initial Health Check

As of the launch check, `run_status.json` reports `status: running` with
`git_commit: 00bfeb60`. Six current-run LLM traces had appeared under
`campaign/llm_traces`, all using `gpt-5.5`. The target-intent, hypothesis, and
code prompts contain `bounded_giant_tour_split_recombination` and
`policies/baseline_modules/giant_tour_split.py`.

The copied `campaign/run.log`, `campaign/status.json`, and nested campaign
artifacts may include resume-source data from successor46b. For live launch
status, prefer the top-level `run_status.json`, top-level `run.log`, and
current-run files directly under `campaign/llm_traces`.

## Next Check

After completion, inspect top-level `run_status.json`, postrun readiness, the
current-run LLM trace sequence, and protocol summaries. Treat a two-round
result as noisy unless it reaches positive-at-MDE or exposes a clear
contract/runtime failure.
