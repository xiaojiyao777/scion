# CVRP M20 mechanism-frontier continuation preregistration

**State:** `TERMINAL_VALID_INCOMPLETE_CONFIGURATION_ERROR`

## Terminal result

M20 ran once from clean carrier `ce6c2c26` and the root is preserved.  The
frontier instruction worked at the hypothesis boundary: instead of another
equivalent `_or_opt` rewrite, H proposed an exact directed O(1) edge-delta for
the distinct-route `_swap` move.  C implemented that mechanism autonomously;
the patch passed bounded development checks, Hypothesis/Patch Contract,
formal Verification and canary.

Initial screening then completed all 12 pairs with no candidate, champion,
shared or bilateral runtime failure.  The six case results were three wins,
zero losses and three ties: `P-n76-k5` improved by 12, `X-n266-k58` by 838.5
and `X-n376-k94` by 83 distance units.  The case-median improvement was 6 with
CI `[0, 460.75]`; median runtime ratio was `1.0001169467`.  Protocol correctly
returned `expand / SCREENING_EXPAND_REQUIRED_FOR_PASS` and Decision requested
expanded screening.

The second scheduled call did not evaluate science.  The frozen config had
`n_cases_modify = expand_to_modify = 6` (and the same equality for
`create_new`), so Protocol rejected the non-growing expanded population with
`expanded case population must be larger than the initial population`.  The
terminal run is `stopped / valid_incomplete / execution_not_evaluated`, with
one evaluated initial screen and one `NOT_EVALUATED / EVALUATION_EXCEPTION`;
no second H, validation, frozen, promotion or champion change occurred.

This is positive development evidence for the autonomous `_swap` mechanism
and for the generic frontier instruction, but it is not expanded confirmation,
validation or a global CVRP improvement claim.  The label/root is not retried.
The framework follow-up moves multi-round expansion-shape validation before
provider or solver work and any continuation uses a new label and fresh input.

## Scientific object

Can a problem-neutral hypothesis-frontier instruction make Scion use current
campaign evidence as completed research—producing a concrete incremental
algorithmic delta or pivot instead of a semantically equivalent rewrite—while
preserving the autonomous bounded H/C and formal evaluation chain?

M19 showed both the opportunity and the defect: two byte-distinct `_or_opt`
patches independently produced three wins, zero losses and two ties on a fresh
screen, but their algorithmic content was equivalent. M20 changes only the
generic H instruction. It now says that mechanisms in `experiment_history`
form the current research frontier; revisiting a target is allowed only for a
concrete incremental delta addressing observed limitations, and an equivalent
rewrite is not a refinement. It does not ban same-file work, score novelty with
another model, require a different target, or mention CVRP, `_or_opt`,
construction, a patch or a repair.

The one run is `v04-cvrp-m20-mechanism-frontier-continuation-20260820` in the
fresh root
`/home/clawd/research/scion-experiments/v04-cvrp-m20-mechanism-frontier-continuation-20260820`.
The user's 2026-08-20 full experimental authorization delegates this bounded
continuation after clean-carrier and provider-/solver-free gates pass. It does
not authorize root reuse, retry, resume, input substitution or automatic M21.

## Carrier and research context

Production baseline is `06aefa8170194e019e60c32ba1cf2e8349d59fba`, whose only
change from the M19 carrier is the generic frontier prompt and its tests. The
launch must bind a clean descendant with an identical `scion/scion` subtree.

H receives the same problem-owned M7+M18 external input, the prior seven
history files through M15, the two M16 records, and
`inputs/v04-cvrp-m20-m19-research-history.jsonl`, an exact two-line copy of
M19 native history with SHA256
`e204afa707c282b97cdd3f0eff037240b6e92d61030e4006cd5404a4f789068d`.
The complete ordered prior has 25 records. C receives only
the approved current H, current source graph and public development tests. No
old campaign database, summary, metric, trace, workspace or candidate source
is reopened.

## Fresh development screen

Before any M20 candidate exists, SHA256 path ranking within family/size strata
selects a new zero-overlap development split after excluding every exact case
path declared at baseline `06aefa81`. No B0/candidate outcome is inspected.

Screening uses seeds `7370`, `6042` and cases `A-n33-k5`, `B-n35-k5`,
`P-n76-k5`, `A-n39-k6` at 30 seconds, `X-n266-k58` at 60 seconds and
`X-n376-k94` at 90 seconds. Declared but unavailable later-development data is
validation `A-n48-k7`, `P-n55-k15`, `X-n313-k71` with seeds `6241`, `8615`,
and frozen `A-n62-k8`, `P-n55-k8`, `X-n393-k38` with seeds `8498`, `7903`.
Canary is the public tiny case with seed `7260`. All twelve problem/solution
pairs are regular non-symlinks and load through the production CVRP parser;
all paths and seeds have zero overlap with baseline experiment inputs.

Measurement, numerical gates, paired ordering and development isolation are
unchanged from M19. `--rounds 2` allows at most two evaluated screening stages,
chosen by the normal Decision chain. Validation, frozen and promotion are zero.

## Resources, stops and claims

The frozen envelope is unchanged: provider cap 30; at most seven complete C,
Patch Contract and Verification attempts; Protocol/Safe Feature/Decision at
most two; Verification solver 14, canary solver 4, formal solver 48 and total
solver subprocesses 66; nominal/guarded solver seconds 2,620/3,610; provider
timeout sum 6,840; development/Verification pytest seconds 540/420; known
guarded total 11,410 under a 14,000-second outer hardwall. Model is
`gpt-5.6-terra`, reasoning high, local proxy, H timeout 120 and C timeout 240,
SDK retry zero.

Provider-cap exhaustion stops before dispatch. Provider/infrastructure,
resource, not-evaluated, unknown or interrupt results stop immediately.
Research rejection may continue only within cap. Two evaluated stages stop as
`requested_rounds_completed`. No result may claim independent discovery,
isolated causal effect, validation/frozen success, promotion, global CVRP
generalization, production readiness or v0.4 completion. The primary framework
outcome is whether attempt 2 is a real incremental/pivot mechanism after seeing
attempt 1; algorithm results remain development descriptions.

## Frozen command

```bash
set -euo pipefail
cd /home/clawd/research/or-autoresearch-agent/scion
test -n "${AUTHORIZED_M20_CARRIER:-}"
test "$(git rev-parse HEAD)" = "$AUTHORIZED_M20_CARRIER"
git diff --quiet
git diff --cached --quiet
REPO_ROOT="$(git rev-parse --show-toplevel)"
test "$REPO_ROOT" = /home/clawd/research/or-autoresearch-agent
git -C "$REPO_ROOT" diff --quiet \
  06aefa8170194e019e60c32ba1cf2e8349d59fba "$AUTHORIZED_M20_CARRIER" -- scion/scion
test ! -e /home/clawd/research/scion-experiments/v04-cvrp-m20-mechanism-frontier-continuation-20260820
command -v bwrap >/dev/null

PROXY_KEY_VALUE="$(curl -fsS --connect-timeout 5 --max-time 15 \
  http://127.0.0.1:8080/auth/status | \
  jq -er '.proxy_api_key | select(type == "string" and length > 0)')"
trap 'unset PROXY_KEY_VALUE' EXIT
curl -fsS --connect-timeout 5 --max-time 15 \
  -H "Authorization: Bearer $PROXY_KEY_VALUE" \
  http://127.0.0.1:8080/v1/models | \
  jq -e --arg model gpt-5.6-terra \
    'any(.data[]?; .id == $model)' >/dev/null

PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion:/home/clawd/.local/lib/python3.12/site-packages:/home/clawd/miniconda3/envs/claw/lib/python3.12/site-packages \
PYTHONDONTWRITEBYTECODE=1 \
SCION_PROBLEM_DATA_ROOT=/home/clawd/research/or-autoresearch-agent/vrp \
SCION_MODEL=gpt-5.6-terra \
SCION_REASONING_EFFORT=high \
SCION_BASE_URL=http://127.0.0.1:8080 \
SCION_API_KEY="$PROXY_KEY_VALUE" \
SCION_LLM_TIMEOUT_SEC=120 \
SCION_LLM_HYPOTHESIS_TIMEOUT_SEC=120 \
SCION_LLM_CODE_TIMEOUT_SEC=240 \
/home/clawd/miniconda3/envs/claw/bin/python -S -B -m scion.cli.main run \
  --problem /home/clawd/research/or-autoresearch-agent/scion/scion/problems/cvrp/problem.yaml \
  --research-input /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m19-m7-m18-research-input.json \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m10-m9-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m11-m10-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m12-m11-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m13-m12-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m14-m13-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m15-m14-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m16-m15-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m19-m16-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m20-m19-research-history.jsonl \
  --code-research-limits /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m11-code-research-limits.json \
  --protocol /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m20-frontier-development-protocol.yaml \
  --split /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m20-frontier-development-split.yaml \
  --seeds /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m20-frontier-development-seeds.yaml \
  --time-limit-sec 30 \
  --provider-call-cap 30 \
  --outer-hardwall-sec 14000 \
  --rounds 2 \
  --campaign-dir /home/clawd/research/scion-experiments/v04-cvrp-m20-mechanism-frontier-continuation-20260820
```

Preparation verifies clean carrier/origins, prompt projection, all loaders and
25 histories, both external observations, all declared cases/solutions, zero
baseline overlap, resource arithmetic, sandbox, proxy model metadata and
absent output. Any failure is `PREP_INVALID` with zero live provider/solver.
