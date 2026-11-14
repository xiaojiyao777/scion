# CVRP M19 fresh-population continuous research preregistration

**State:** `TERMINAL_VALID_POSITIVE_REPETITIVE_DEVELOPMENT`

## Scientific object

Can Scion use the complete ordinary M9-M16 H/patch/Protocol/Decision research
history together with the independent M18 fixed-candidate confirmation result
to choose its own next CVRP research direction, implement it with bounded code
tools, and produce stronger evidence on a fresh development population?

The host does not choose a target file, patch, mechanism, algorithm repair or
whether the next H should address construction completeness, refine local
search, or pivot elsewhere. The M18 observation is problem-owned ordinary
input projected into H only. C receives the approved current H, current source
graph and public development tests; it does not receive raw M18 artifacts or
old campaign workspaces. Generic Scion contains no M18 or CVRP result branch.

The one run is
`v04-cvrp-m19-fresh-population-continuous-research-20260820` in the fresh root
`/home/clawd/research/scion-experiments/v04-cvrp-m19-fresh-population-continuous-research-20260820`.
The user's 2026-08-20 full experimental authorization delegates this bounded
continuation after a clean carrier and provider-/solver-free preparation pass.
It does not authorize output-root reuse, resume, retry, replacement,
case/seed substitution or an automatic M20.

## Source and ordinary research inputs

Production source baseline is `47fe3dc6`: M19 changes no framework or problem
code. The launch must bind a clean descendant whose complete `scion/scion`
subtree is identical to that baseline.

`inputs/v04-cvrp-m19-m7-m18-research-input.json` contains two strictly
projected problem observations: the original M7 terminal and the M18 fixed
confirmation terminal. Its SHA256 is
`a5329a5ff96a762a27df11a70722b97acbc488dea8de5e322a56921eb87568c9`.
M18 contributes 20/24 valid pairs, one win, zero losses, four ties, four shared
construction failures, zero candidate-only failure, unchanged median runtime,
and the explicit non-confirmation claim boundary. It does not prescribe a
repair.

The prior seven committed history files are followed by
`inputs/v04-cvrp-m19-m16-research-history.jsonl`, an exact two-line copy of
M16's native history with SHA256
`da8a50163f88c7ae75b3b9f8c7528691314d19b2b844f2a67d6036db62ed6da7`.
The complete ordered history has 23 records. No campaign summary, database,
metric, trace, source snapshot or workspace is reopened.

## Fresh development population

The split was selected before any M19 candidate existed by deterministic
SHA256 ranking of path metadata within family/size strata, after excluding
every exact case path referenced by the repository at baseline `47fe3dc6`.
Selection did not execute B0 or a candidate and did not inspect outcome data.

Screening uses two fresh seeds (`6847`, `7169`) on:

- `A/A-n61-k9`, `B/B-n64-k9`, `P/P-n50-k10`, `A/A-n63-k9` at 30 seconds;
- `X/X-n289-k60` at 60 seconds;
- `X/X-n429-k61` at 90 seconds.

The following declared development cases and seeds are reserved and are not
available to H/C: validation uses `B-n50-k8`, `P-n16-k8`, `X-n298-k31` with
seeds `6162`, `8372`; frozen uses `A-n45-k7`, `X-n284-k15`, `X-n685-k75`
with seeds `8716`, `7565`. Canary is the public tiny case with seed `5069`.
All twelve `.vrp` files and companions are regular non-symlink inputs that load
through the production CVRP parser. All twelve paths and seven seeds have zero
overlap with the baseline's declared prior/current experiment inputs. These are
fresh development data, not a hidden formal population.

Measurement remains paired case-median total distance with protected fleet
violation, R3 numerical gates and `require_expanded_for_pass=true`. No gate is
relaxed. `--rounds 2` permits at most two evaluated screening stages: these may
be two candidates, or an initial plus expanded screen of one candidate if the
normal Decision chain selects that action. Validation and frozen counts are
zero in this run.

## Agent, tools and resource envelope

- model `gpt-5.6-terra`, reasoning high, local Codex proxy, SDK retry zero;
- H timeout 120 seconds; C/research/finalize timeout 240 seconds;
- one shared pre-dispatch provider cap of 30 across H and C;
- unchanged bounded read/search/revise/public-test/finalize session;
- current development checks, Patch Contract and Verification rerun for every
  finalized candidate; development results never substitute for formal gates;
- no provider-selected shell, arbitrary test, reserved data or old workspace;
- no host-supplied target, patch, repair, mechanism or candidate source.

| Resource | Hard maximum |
|---|---:|
| provider calls, H+C combined | 30 |
| autonomous H / Hypothesis Contract attempts | 30 |
| complete C sessions / formal candidates | 7 |
| Patch Contract / Verification calls | 7 each |
| Protocol / Safe Feature / Decision calls | 2 each |
| Verification solver subprocesses | 14 |
| Verification pytest subprocesses | 7 at 60 seconds |
| Protocol canary solver subprocesses | 4 |
| formal screening solver subprocesses | 48 |
| all solver subprocesses | 66 |
| nominal / guarded solver seconds | 2,620 / 3,610 |
| worst provider timeout seconds | 6,840 |
| cumulative development-test / Verification pytest seconds | 540 / 420 |
| known guarded total / outer hardwall | 11,410 / 14,000 seconds |

Research rejection may continue only below the provider cap. Provider-cap
exhaustion stops before dispatch. Provider fault, other infrastructure or
resource failure, not-evaluated result, unknown result or interrupt stops
immediately. A canary veto carries no Protocol claim. Two evaluated stages
stop as `requested_rounds_completed`; hardwall termination must kill active
children and project `INTERRUPTED / OUTER_HARDWALL_EXCEEDED`.

## Claim boundary

Framework claims may describe whether Scion used cross-campaign evidence,
chose a direction without a host patch, operated the bounded C tool loop, and
completed Contract, Verification, Protocol, Safe Features and Decision.
Research-effectiveness claims may describe whether the generated candidates
addressed prior evidence and how they behaved on this fresh development
screen. Algorithm claims remain descriptive and development-only. No M19
result is independent algorithm discovery, isolated causal effect, validation
or frozen success, promotion, global CVRP generalization, production
readiness, or v0.4 completion.

## Frozen command

```bash
set -euo pipefail
cd /home/clawd/research/or-autoresearch-agent/scion
test -n "${AUTHORIZED_M19_CARRIER:-}"
test "$(git rev-parse HEAD)" = "$AUTHORIZED_M19_CARRIER"
git diff --quiet
git diff --cached --quiet
REPO_ROOT="$(git rev-parse --show-toplevel)"
test "$REPO_ROOT" = /home/clawd/research/or-autoresearch-agent
git -C "$REPO_ROOT" diff --quiet \
  47fe3dc6 "$AUTHORIZED_M19_CARRIER" -- scion/scion
test ! -e /home/clawd/research/scion-experiments/v04-cvrp-m19-fresh-population-continuous-research-20260820
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
  --code-research-limits /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m11-code-research-limits.json \
  --protocol /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m19-fresh-development-protocol.yaml \
  --split /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m19-fresh-development-split.yaml \
  --seeds /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m19-fresh-development-seeds.yaml \
  --time-limit-sec 30 \
  --provider-call-cap 30 \
  --outer-hardwall-sec 14000 \
  --rounds 2 \
  --campaign-dir /home/clawd/research/scion-experiments/v04-cvrp-m19-fresh-population-continuous-research-20260820
```

Preparation must verify the clean carrier and exact module origins, all input
loaders and 23 histories, CVRP projection of both observations, every declared
case and solution, zero baseline overlap, resource arithmetic, public sandbox,
proxy model metadata and absent output. Any failure is `PREP_INVALID` with no
live provider or solver call.

## Terminal result

M19 ran once from clean carrier
`45fd6a41acec80333b9203646d2ce7fed857abbf` and exited zero as
`completed / valid / requested_rounds_completed`. It used ten provider calls,
scheduled two candidates, evaluated two complete screening stages and wrote
two native ordinary history records. Research rejection, infrastructure,
resource, interrupt, not-evaluated and unknown counts are zero. No related
process remained. Champion is still v1; validation, frozen and promotion are
zero.

Both autonomous H/C paths chose `policies/baseline_modules/local_search.py`
and replaced `_or_opt` trial-route reconstruction with a directed constant-time
delta. Both passed bounded public development checks, formal Contract,
Verification and canary. Their patch sources are byte-distinct, but a direct
diff shows only equivalent boundary-variable factoring and equivalent
whole-route removal arithmetic; they do not represent distinct algorithmic
mechanisms.

Candidate 1 completed 12/12 pairs: ten were valid and both `X-n429-k61`
pairs were shared champion-and-candidate construction failures. Candidate-only
and bilateral failures were zero. `A-n61-k9`, `B-n64-k9` and `X-n289-k60`
won by 11.5, 6.5 and 15 respectively; `P-n50-k10` and `A-n63-k9` tied. The
case aggregate was three wins, zero losses, two ties, median `6.5`, CI
`[0, 15]`. Protocol returned `SCREENING_EXPAND_REQUIRED_FOR_PASS`; partial
champion evidence made Decision `continue_explore`.

Candidate 2 independently regenerated the same mechanism with a different
source expression. It again had ten valid pairs, two shared `X-n429-k61`
failures and no candidate-only or bilateral failure. `B-n64-k9`, `P-n50-k10`
and `X-n289-k60` won by 7, 1 and 44; both A cases tied. The aggregate was three
wins, zero losses, two ties, median `1`, CI `[0, 44]`; Protocol returned
`SCREENING_EXPAND_INITIAL_QUALITY` and Decision again conservatively continued.
Measured wall-clock runtime remained essentially equal to B0 in both screens.

The defensible algorithm conclusion is positive but development-only: the
directed constant-time `_or_opt` mechanism produced three no-loss case wins in
two byte-distinct implementations on a fresh population, without a
candidate-side failure. The shared X429 construction failure still prevents
complete evidence and no expanded, validation, frozen or promotion stage ran.

The framework conclusion is mixed. Ordinary M18 input and all 23 history
records reached H, and the complete bounded H/C→Contract→Verification→Protocol
→Safe Features→Decision chain worked twice. However, the second H also saw the
first M19 experiment through `experiment_history` and still proposed a
semantically equivalent mechanism. The next framework experiment should test
a problem-neutral research-frontier instruction that requires an H revisiting
an evaluated target to state a materially new algorithmic delta, without
forbidding legitimate same-file refinement or encoding a CVRP target.

The immutable root is
`/home/clawd/research/scion-experiments/v04-cvrp-m19-fresh-population-continuous-research-20260820`;
it is not retried or resumed.
