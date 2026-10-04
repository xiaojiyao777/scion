# R17 independent Warehouse quota-boundary control

State: completed / requested_rounds_completed, valid, at
2026-10-03T13:35:48.349873+00:00. Two of two requested stages; pane dead exit0.
Launched once at 2026-10-03T13:23:26Z, tmux PID 459516.
A separate problem checks the shared
provider classification change on the same frozen runtime as
[CVRP R17](v04-cvrp-r17-quota-aware-autonomous-preregistration-20261003.md).
No control result enters CVRP H/C; no intentional live quota exhaustion.

Complete ordinary source/data: repository `surrogate`, 406 non-cache files.
Same problem, source and population as the R16 control. The inherited population
is outcome-informed engineering selection, not an independent quality estimate.
No host source repair. Public instance_development is excluded from formal stages.

[Protocol](inputs/v04-r17-warehouse-quota-control-protocol.yaml),
[split](inputs/v04-r17-warehouse-quota-control-split.yaml),
[seeds](inputs/v04-r17-warehouse-quota-control-seeds.yaml).
Initial small_6 × one seed; expansion adds small_1 × two seeds.
Validation small_3, frozen small_4, canary small_5. Mandatory expansion means
held-out stages cannot execute within this two-stage target.
First five primes above 190000: screening 190027/190031, validation 190051,
frozen 190063, canary 190093. No outcome-based reselection.
All objective/feasibility/confidence/Decision gates unchanged; the existing
stale calibration diagnostic is retained, not relabeled or weakened.

Two evaluated stages, K=1/max three branches, two-second solver limit.
gpt-5.6-sol high, H180/C300, SDK retry0/two charged typed redispatches,
80 physical calls, 7200-second outer guard, unchanged R3i C limits.
No run extension/resume or cap increase on failure. A valid negative is
acceptable. A framework defect blocks CVRP; an incomplete run stays incomplete
and requires an explicit exercised-coverage assessment before proceeding.

Before launch: full tests, source/data/public-formal closure and absent
output/session checks, one bounded inference health probe, no competing work.
After terminal: inspect ordinary H/C refs, correct branch source, typed outcome,
Contract/Verification/canary, complete paired Protocol and deterministic Decision.
This is a cross-problem wiring/control check, not retained algorithm evidence.

Runtime: `505dce03` plus the frozen uncommitted quota repair/tests and inputs.
Only documentation may change during formal measurement.
Output: `/home/clawd/research/scion-experiments/v04-r17-warehouse-quota-control-20261003`.
Tmux: `scion-r17-warehouse-quota-control-20261003`.

## Frozen invocation (executed once)

Read-only preparation passes: 406 non-cache source files, all five formal/canary
instances parsed, two public suites and complete support closure disjoint from
formal cases; strict expansion, resource/production/Verification composition
and absent output. One bounded real provider inference succeeds at 13:21 UTC,
separate from campaign accounting; no credential output. Focused tests and
format/lint checks pass. Full suite finishes before dispatch:
**2554 passed, 1 skipped in 434.47 s**.
Final no-overlap and absent output/session checks pass. Runtime and inputs
remain frozen; only status documentation changes during measurement.
[Live status](/home/clawd/research/scion-experiments/v04-r17-warehouse-quota-control-20261003/status.json).

```bash
set -Eeuo pipefail
cd /home/clawd/research/or-autoresearch-agent
test ! -e /home/clawd/research/scion-experiments/v04-r17-warehouse-quota-control-20261003
proxy_key_value=$(curl -fsS --connect-timeout 5 --max-time 15 http://127.0.0.1:8080/auth/status | jq -er '.proxy_api_key | select(type == "string" and length > 0)')
curl -fsS --connect-timeout 5 --max-time 15 -H "Authorization: Bearer $proxy_key_value" http://127.0.0.1:8080/v1/models | jq -e 'any(.data[]?; .id == "gpt-5.6-sol")' >/dev/null
exec env \
  PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
  PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion \
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  SCION_PROBLEM_DATA_ROOT=/home/clawd/research/or-autoresearch-agent/surrogate \
  SCION_MODEL=gpt-5.6-sol SCION_REASONING_EFFORT=high \
  SCION_BASE_URL=http://127.0.0.1:8080 SCION_API_KEY="$proxy_key_value" \
  SCION_LLM_TIMEOUT_SEC=180 SCION_LLM_HYPOTHESIS_RESEARCH_TURN_TIMEOUT_SEC=180 \
  SCION_LLM_CODE_RESEARCH_TURN_TIMEOUT_SEC=300 SCION_LLM_CODE_RESEARCH_FINALIZE_TIMEOUT_SEC=300 \
  /home/clawd/miniconda3/envs/claw/bin/python -B -m scion.cli.main run \
    --problem /home/clawd/research/or-autoresearch-agent/scion/problems/warehouse_delivery/problem-v1.yaml \
    --source-tree /home/clawd/research/or-autoresearch-agent/surrogate \
    --code-research-limits /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r3i-long-run-code-research-limits.json \
    --protocol /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-r17-warehouse-quota-control-protocol.yaml \
    --split /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-r17-warehouse-quota-control-split.yaml \
    --seeds /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-r17-warehouse-quota-control-seeds.yaml \
    --time-limit-sec 2 --rounds 2 --provider-call-cap 80 \
    --provider-transient-retries 2 --outer-hardwall-sec 7200 \
    --campaign-dir /home/clawd/research/scion-experiments/v04-r17-warehouse-quota-control-20261003
```

## Terminal audit and launch decision

Ordinary [status](/home/clawd/research/scion-experiments/v04-r17-warehouse-quota-control-20261003/status.json)
and [summary](/home/clawd/research/scion-experiments/v04-r17-warehouse-quota-control-20261003/campaign_summary.json)
agree: four scheduled attempts, two evaluated screens, two research rejections,
no unknown/infrastructure/resource outcome, champion v1 / weight revision zero.
All 70 physical calls succeed at attempt index zero (H25, C-turn43, C-final2),
ten calls remain. Four H exports and two C-ready exports. No quota event occurs
in this control: injected regressions, not this success run, establish quota-stop
behavior. There is no promotion, expansion, validation, frozen or retained result.

| Attempt | Actual result |
|---|---|
| 1, MergeVehicles | Passing development/probe, Contract/Verification/canary; complete tie, continue_explore |
| 2, DestroyRebuild | Host development checks pass but falsifier fails; C explicitly abandons at finalization |
| 3, MoveOrder | Public unit check fails; invalid finalization rejected, no formal evidence |
| 4, branch-A DestroyRebuild continuation | Passing development/probe and formal checks; complete tie, continue_explore |

Both formal screens use small_6 / seed190027 with two-second paired limits:
[first metric](/home/clawd/research/scion-experiments/v04-r17-warehouse-quota-control-20261003/metrics/2b1a5800-f249-44bb-b1c3-51c0864d3e36.json)
and [second metric](/home/clawd/research/scion-experiments/v04-r17-warehouse-quota-control-20261003/metrics/0ffecf4e-bde3-494c-9969-229cbcaeb2ee.json).
Each is complete 1/1 valid, zero failures and protected-objective regressions;
both declared objective deltas and CI endpoints are zero. Both preserve
SCREENING_FAIL_WIN_RATE / CONTINUE_EXPLORE. Runtime ratios 0.7983 and 1.8031
(candidate -97 ms and +412 ms); this is neither quality improvement nor a
replicated speedup. The second result describes the cumulative two-file bundle.

All 406 initial champion files match the original source. All **45** visible C
source values match the correct base: champion for attempts1–3, accepted first
MergeVehicles head for attempt4. Final complete 406-file branch tree
`candidate_workspaces/candidate-9y348hfm` contains exactly the two history
sources (MergeVehicles plus DestroyRebuild), other files unchanged apart from
registry serialization/defaults; ordinary typed registry values are equal.
The superseded first workspace was ordinarily replaced, not restored; its exact
source value remains in history/traces. No campaign SQL was opened or modified.

Attempt2 receives failed/call/assertion_error/probe_line56 for its exact probe.
C's final explanation identifies that its completeness check rejects empty
vehicles before cleanup and chooses abandon; this is a source-grounded response
to feedback, not a proved scientific repair. Attempt3 still tries finalization
after failed public checks and is correctly rejected. Across the four complete
C transcripts, 17 source_not_visible, 11 command_field_invalid and two
selector_not_found tool errors remain a large efficiency limitation. No new
prompt/algorithm gate or budget widening is introduced to hide it.

The full planned control completes, exercising actual H/C refs, tainted proposal
rejection, exact accepted-head continuation, Contract, Verification, canary,
complete paired Protocol and deterministic negative Decision. No shared framework
blocker is found. Together with 2554 passing regressions, proceed with the
already preregistered CVRP R17 on the same frozen runtime and inputs. This is a
wiring/control conclusion, not evidence of better autonomous reasoning or CVRP
quality. No control outcomes are added to the CVRP input.
