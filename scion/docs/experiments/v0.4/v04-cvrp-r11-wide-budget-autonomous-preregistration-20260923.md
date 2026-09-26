# CVRP R11: autonomous research under the wider equal budgets

State: completed normally at `2026-09-24T05:58:23.243135+00:00` after 12
screening stages / ten distinct candidates. All 108 pairs are valid; no
promotion or held-out stage. Final B has a modest but uncertain expanded
signal (+10, CI [-1,216.75]). See the
[postrun](v04-cvrp-r11-wide-budget-autonomous-postrun-20260924.md) for source
fidelity, inactive phase-handoff diagnosis and the next research rung.
R11 is terminal and must not resume. The design below remains frozen.

Launched once at `2026-09-23T23:47:06Z` (process start), driver PID
166821, tmux `scion-r11-wide-budget-autonomous-20260923`, under the user's
request to commit/push first, then analyze, optimize and launch a new experiment.
The prior work was committed and pushed as `841de42b` before this slice.
The ordinary input/source/history checks and focused tests passed before launch.
R9 and R10 are terminal; neither is resumed. R10's
[postrun](v04-cvrp-r10-wide-budget-b0-postrun-20260923.md) preserves screening
success and incomplete validation comparator evidence.

At the initial live check, version 1 / weight revision 0 and zero evaluated
rounds were recorded. All 100 ordinary files in `champions/champion_v1` equal
the selected source. The first two real `gpt-5.6-sol` H calls succeeded:
`read_source`, then `read_history`. Their actual structured contexts contain
the exact new screening-only question and four-observation / 90-record indexes.
This verifies startup and availability, not comprehensive evidence attention
or any formal result. Runtime and inputs are frozen; only launch-status docs
are updated after startup. New R10 analysis/R11 docs/inputs/tests remain
uncommitted atop `841de42b`.

## Source, question and autonomy

Start from the complete ordinary
[R10 candidate snapshot](/home/clawd/research/scion-experiments/v04-cvrp-r10-wide-budget-b0-20260923/input_snapshots/candidate),
100 files equal to R9's final branch-C tree. Keep the complete bundle, including
unused helpers, without a host solver patch or patch-chain reconstruction.
Fresh version 1 / weight revision 0, branches, provider counters and output.
This is a local research baseline, not a promoted or retained-B0 champion.

Can autonomous H/C improve this complete algorithm under R10's wider budgets
while preserving feasibility and fleet protection? R10 screening is the
selection evidence: 24 valid counterbalanced pairs, W/L/T 3/0/3, median 19.75,
CI [0,179], SCREENING_PASS. The candidate still has zero ALNS iterations on
both large screening cases; the four +198 effects on one of them are not
evidence for a changed ALNS mechanism. H chooses the research direction and
C its implementation. No target file, phase schedule, mechanism, prescribed
patch, mandatory history action, novelty or activity gate is introduced.

## Safe ordinary evidence

The [research input](inputs/v04-cvrp-r11-wide-budget-autonomous-research-input.json)
preserves all four R4/R5/R6/R8 observations unchanged. The directly visible
current question adds R10's screening aggregate, every screening case median
and seed delta, counterbalancing and selected screening phase observations.
It explicitly separates bundle evidence from mechanism causality and local
comparisons from original B0. No validation outcome, diagnostic or case is
included. The existing observation schema models terminal/failure observations;
R10's successful screening stage is therefore ordinary question context, not
a fabricated whole-run terminal observation. No schema or framework changes.

Load R3, R3b, R3c, R3d, R3e, R3f, R3g, R3h, R3i, R7, R9 histories in the exact
order below: 113 raw records / 4,096,146 bytes, with 90 H-visible scientific
records and 23 operational rows excluded by the unchanged projection.
Keep every ordinary record within existing lossless H-only
projection semantics, not just winning hypotheses or selected branch C.
R9 includes its actual exported patches and all negative/uncertain screening
outcomes; fixed R10 has no H/C ledger to invent. History restores no mutable
state. Availability is checked, but particular reads are not forced and
provider success is not evidence of improvement.

## Prospective comparisons and the known limitation

[Protocol](inputs/v04-cvrp-r11-wide-budget-autonomous-protocol.yaml) exactly
preserves R10's science and equal 60/90/120/180/240-second dimension bands;
only version and canary seed change. Canary remains 10 seconds. Algorithm-owned
0.80 fraction, 3% reserve and scheduling are unchanged before launch.
Use the same [R7 split](inputs/v04-cvrp-r7-autonomous-source-continuation-split.yaml):
six known adaptive screening cases, six validation cases, twelve frozen cases.
The first nine primes above 100,000 define
[seeds](inputs/v04-cvrp-r11-wide-budget-autonomous-seeds.yaml):

| Stage | Seeds | Maximum pairs per complete stage |
|---|---|---:|
| screening | 100003,100019,100043,100049 | 24 |
| validation | 100057,100069 | 12 |
| frozen | 100103,100109 | 24 |
| safety-only canary | 100129 | 1 |

Screening starts at 3 x 2 and must expand to 6 x 4 before a pass. Validation
and frozen reuse the exact candidate. Complete pairs, feasibility, fleet
protection, practical deltas (screening 2.0 / validation 1.0), nonnegative CI,
net case score >=0.25 and loss rate <=0.20 remain unchanged. Parameter search
stays disabled. K=1 and the existing maximum-three-branch scheduler retain
verified provisional source heads after screening and roll back only on
Contract/Verification failure.

**Operator-only limitation:** R10 has executed validation and exposed its
outcomes to the operator; do not call it unopened. A shared constructor failed
on one validation case, and R11's starting champion retains that constructor.
Reaching validation may therefore yield incomplete comparator evidence again.
This run is useful for prospective autonomous screening development, not a
promise of reaching promotion. The case is not removed or repaired, no private
failure detail is fed to H/C, and no in-run change or bypass is authorized.
Frozen and the separate pre-R3 retained block remain unopened; the latter is
outside R11. New seeds do not restore globally unseen-case status.

Autonomous execution uses the existing champion-first order, not the fixed
R10 AB/BA driver. Declare this limitation; do not change framework measurement
in this slice. A local promotion, if validly reached, is against the local
starting source or later local champion, not B0. Retained superiority needs
a separate prospective exact-source comparison. Resolving an invalid original
comparator cannot silently redefine B0 or erase R10's failure.

## Runtime, resources and prelaunch checks

Preparation HEAD `841de42b` on `v0.4-dev`; runtime unchanged from `e405bfd2`.
This slice changes only docs, three prospective inputs and an input test.
No implementation, scientific boundary or algorithm patch is host-authored.
Freeze runtime, source, data and inputs before launch. All tests and preparation
must finish before measurement; no concurrent solver, maintenance or cleanup.

Target 12 formally evaluated stages, not 12 candidates or provider calls.
Provider `gpt-5.6-sol`, reasoning high, via the existing local proxy. H/default
timeout 180 s, C turn/finalization 300 s, SDK retries zero. Reuse R3i C-session
limits: 12 turns, 8 reads, 8 searches, 4 tests, no total transcript-character
ceiling. Invocation cap 600 physical dispatches, at most two charged typed
transient redispatches of each frozen request, outer guard 172,800 s.
These are explicit resource bounds, not quality gates or a claim of unlimited
provider capacity. All comparative solver limits are the same for both arms.

Before launch validate input parity, fresh/disjoint prime seeds, complete
source and fresh output, all formal/canary data files, CLI expansion settings,
ordered history and H-only projection. Run focused continuation/history/
redteam/CLI/session/fixed-funnel/input regressions, Ruff F/E9 and diff checks.
No core change requires a new full suite or Warehouse control. Confirm model
catalog availability without printing credentials; successful generation must
then be observed separately. Launch once into the absent output/session:

- Output: `/home/clawd/research/scion-experiments/v04-cvrp-r11-wide-budget-autonomous-20260923`.
- Tmux: `scion-r11-wide-budget-autonomous-20260923`.

Prelaunch checks: 208 focused tests passed in 2.75 seconds; targeted Ruff F/E9
and formatting checks passed. Read-only preparation parsed all 24 formal cases
plus canary, validated source/fresh-output selection, disabled parameter search,
expansion and resource/session bounds. All 11 explicitly named histories load
in order; actual H-context projection contains all 90 scientific records,
four unchanged observations and the exact new screening-only question.
Preparation created no campaign output and ran no provider or solver.
The final catalog check found the configured model; only dead prior experiment
panes existed, no active competing solver/test/cleanup was found, both fresh
output and session were absent, and 63 GiB disk was available.

## Frozen invocation

From the main checkout after prelaunch checks; never print the runtime credential.

```bash
set -Eeuo pipefail
cd /home/clawd/research/or-autoresearch-agent
test ! -e /home/clawd/research/scion-experiments/v04-cvrp-r11-wide-budget-autonomous-20260923
proxy_key_value=$(curl -fsS --connect-timeout 5 --max-time 15 http://127.0.0.1:8080/auth/status | jq -er '.proxy_api_key | select(type == "string" and length > 0)')
curl -fsS --connect-timeout 5 --max-time 15 -H "Authorization: Bearer $proxy_key_value" http://127.0.0.1:8080/v1/models | jq -e 'any(.data[]?; .id == "gpt-5.6-sol")' >/dev/null
exec env \
  PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
  PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion \
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  SCION_PROBLEM_DATA_ROOT=/home/clawd/research/scion-experiment-inputs/v04-cvrp-r6-minus-2for1-b0-20260921/data \
  SCION_MODEL=gpt-5.6-sol SCION_REASONING_EFFORT=high \
  SCION_BASE_URL=http://127.0.0.1:8080 SCION_API_KEY="$proxy_key_value" \
  SCION_LLM_TIMEOUT_SEC=180 SCION_LLM_HYPOTHESIS_RESEARCH_TURN_TIMEOUT_SEC=180 \
  SCION_LLM_CODE_RESEARCH_TURN_TIMEOUT_SEC=300 SCION_LLM_CODE_RESEARCH_FINALIZE_TIMEOUT_SEC=300 \
  /home/clawd/miniconda3/envs/claw/bin/python -B -m scion.cli.main run \
    --problem /home/clawd/research/or-autoresearch-agent/scion/scion/problems/cvrp/problem-v1.yaml \
    --source-tree /home/clawd/research/scion-experiments/v04-cvrp-r10-wide-budget-b0-20260923/input_snapshots/candidate \
    --research-input /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r11-wide-budget-autonomous-research-input.json \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r3-normal-k1-sol-20260828-r1/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r3b-normal-k1-sol-20260829-r1/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r3c-normal-k1-sol-20260830-r1/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r3d-normal-k1-sol-20260830-r1/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r3e-normal-k1-sol-20260830-r1/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r3f-normal-k1-sol-20260831-r1/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r3g-normal-k1-sol-20260901-r1/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r3h-normal-k1-sol-20260902-r1/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r3i-normal-k1-sol-20260903-r1/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r7-autonomous-source-continuation-20260921/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r9-post-b0-autonomous-20260922/research_history.jsonl \
    --code-research-limits /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r3i-long-run-code-research-limits.json \
    --protocol /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r11-wide-budget-autonomous-protocol.yaml \
    --split /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r7-autonomous-source-continuation-split.yaml \
    --seeds /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r11-wide-budget-autonomous-seeds.yaml \
    --time-limit-sec 60 --rounds 12 --provider-call-cap 600 \
    --provider-transient-retries 2 --outer-hardwall-sec 172800 \
    --campaign-dir /home/clawd/research/scion-experiments/v04-cvrp-r11-wide-budget-autonomous-20260923
```

After launch, check the 100-file initial champion equality and actual first H
input: current wide-budget screening question, four prior observations and the
complete ordered scientific history index. Inspect successful real H calls,
not only catalog presence. Do not require particular research actions.
After terminal completion analyze actual H/C, complete source fidelity, valid
and failed pairs and deterministic decisions before selecting another rung.
Do not open the original SQLite or resume terminal state.
