# CVRP M24 bounded autonomous direction-research preregistration

**State:** `PREPARED_NOT_STARTED`

**Label:** `v04-cvrp-m24-autonomous-direction-research-development-20260821`

**Fresh campaign root:**
`/home/clawd/research/scion-experiments/v04-cvrp-m24-autonomous-direction-research-development-20260821`

**Prelaunch correction:** The first execution of the fenced shell stopped at
its process-absence guard before proxy metadata or the live command. `pgrep`
matched the enclosing shell because that shell's own command text contained the
later `scion.cli.main run` line. The campaign root remained absent and H, C,
Contract, Verification, solver, Protocol, Safe Features and Decision counts
all remained zero. The guard below now inspects only processes whose executable
name is Python. This is a preparation-control correction, not a scientific
attempt; no scientific input, resource or claim boundary changed.

## Scientific question

Can Scion use its bounded H source/history research session and bounded C
read/search/test/revise session to choose, implement, verify and formally screen
the next CVRP solver candidate without the host specifying a mechanism, target
file, patch or repair?

This is a development experiment of the V3 research chain. The host supplies
only the current committed source, ordinary prior observations and native
research history, declared public development tests, a fresh metadata-only
population, finite resources and the existing
Contract -> Verification -> Protocol -> Safe Features -> Decision authority
chain. Current source is authoritative; historical patches are observations,
not patches to replay.

## Ordinary research context

H receives the twelve explicitly ordered native history files from M9 through
M22. The first eleven are the already committed M22 inputs; the final file,
`inputs/v04-cvrp-m24-m22-research-history.jsonl`, is an ordinary byte-for-byte
copy of M22's three-record terminal history. Together they contain 33 native
H/patch/outcome/Protocol/Decision records.

The separate problem-owned input
`inputs/v04-cvrp-m24-m23-aggregate-research-input.json` contains the previously
used M7 and M18 observations followed by M23's fixed-candidate result. M23 is
explicitly bound to the M20 exact candidate represented in native history and
is represented as one scientific non-confirmation event: canary passed, all 24
expanded-screen pairs were valid, the exact candidate won two cases, lost none
and tied four, median delta was zero, the interval was `[0, 66.75]`, runtime was
effectively unchanged, protected regressions were zero, and Decision continued
exploration. This is a historical evidence relation, not a next-target
recommendation, and it is not fabricated as native Agent history.

The bounded H session initially sees complete source and history indexes. It
may read or search exact ordinary entries within the committed limits and must
cite at least one actually read reference in its tainted `research_basis`
before exporting one H. The host does not rank mechanisms, require a particular
history item or inspect proposal quality to choose a direction. C receives the
exact approved H plus the target/dependency/caller/public-test organization,
may use bounded development tools, and may export at most one patch for formal
gates. Neither the H basis nor development-test result enters Protocol, Safe
Features or Decision.

## Fresh development population

Selection used only family, dimension, companion-file presence and absence
from the current comparison inventory: M7, R67, M20-M23 and tracked v0.4
inputs. It did not inspect any new-candidate outcome or BKS quality. Every
selected `.vrp` and companion `.sol` is a regular non-symlink parsed by the
production adapter. The twelve cases and seven seeds have zero overlap with
that declared inventory and with each other across stages. This is not a claim
that every case name is globally absent from all older design documents.

Initial screening is the priority prefix:

- `cvrplib/B/B-n57-k7.vrp`
- `cvrplib/P/P-n60-k15.vrp`
- `cvrplib/X/X-n261-k13.vrp`

Expanded screening strictly contains it and adds:

- `cvrplib/A/A-n53-k7.vrp`
- `cvrplib/X/X-n167-k10.vrp`
- `cvrplib/X/X-n411-k19.vrp`

Screening seeds are `4358` and `1868`. Declared later-development populations
are validation `P-n55-k7`, `X-n308-k13`, `X-n548-k50` with seeds `5405`,
`4354`, and frozen `X-n275-k28`, `X-n480-k70`, `X-n876-k59` with seeds `2959`,
`6748`. Canary is the public tiny instance with seed `6746`.

Paired-effect measurement, fleet-violation protection, numerical quality gates,
time bands and `require_expanded_for_pass=true` are unchanged from M22. The
ordinary controls are:

- `inputs/v04-cvrp-m24-autonomous-direction-research-development-protocol.yaml`
- `inputs/v04-cvrp-m24-autonomous-direction-research-development-split.yaml`
- `inputs/v04-cvrp-m24-autonomous-direction-research-development-seeds.yaml`
- `inputs/v04-cvrp-m11-code-research-limits.json`

## Stages, resources and stops

`--rounds 2` counts only completed formal Protocol stages. If the first initial
screen requests expansion, the second stage reuses that exact verified branch
and runs the six-case expanded screen without another H or C. If the first
screen returns to exploration, a later H may read its ordinary same-campaign
observation and choose a new direction. A short `RESEARCH_REJECTED` attempt does
not count as a formal round and may scheduler-forward, but all actual H and C
provider requests share the hard cap of 34.

The reused ordinary research limits allow at most eight H research turns and
eight C research actions plus one independent C final decision per attempt.
Thus 34 calls cover two maximally long H+C sessions; short rejected attempts
can make the attempt count larger, so this document does not assert a two-
candidate limit. SDK retry is zero.

The conservative envelope is:

- provider calls: `<=34`; H timeout `120s`, C turn/final timeout `240s`;
- formal evaluated Protocol/Safe-Feature/Decision stages: `<=2`;
- solver subprocesses: `<=56` (`16` Verification, `4` canary, `36` formal);
- solver nominal/guarded subject-seconds: `<=2140 / 2980`;
- development pytest: `<=510s`; Verification pytest: `<=480s`;
- known guarded work: `<=11650s`;
- campaign-run outer hardwall: `15000s`; serial solver concurrency `1`.

Validation, frozen evaluation, promotion and committed production/framework
source mutation are zero for this two-stage invocation. Candidate-workspace
mutation remains the bounded C research action. Even an expanded-screen pass
is only development evidence and cannot promote.

Provider-cap exhaustion is typed `resource_exhausted /
PROVIDER_CALL_CAP_EXHAUSTED` and returns exit 21 without an extra dispatch.
Provider/transport infrastructure stops return exit 20. Outer hardwall returns
124 with `OUTER_HARDWALL_EXCEEDED`. Other `NOT_EVALUATED`, unknown, interrupt or
evaluated-without-formal outcomes stop the invocation. A process exit of zero
is not itself a scientific success: terminal interpretation uses `status`,
`run_validity`, `evaluated_rounds`, `last_execution_outcome` and `stop_reason`.
There is no response retry, campaign resume, patch repair, population
replacement or automatic M25.

## Claims

Framework evidence may establish that H actually searched/read ordinary source
or history, produced a validated audit basis, exported one H, and that C used
bounded source and public-development tools before the unchanged formal gates.
Research-effectiveness evidence may describe whether the Agent distinguished
prior directions, proposed a material delta and made an observable prediction.
These are existence and quality observations, not host-enforced algorithm
truth.

CVRP mechanism evidence is problem-owned family association. Only a complete
paired observation can make it available; unsupported targets, incomplete
comparison or a later eval-only stage may correctly report typed unavailable.
It is never exact activation, causal proof, a host direction selector, a gate,
or a Decision feature.

Algorithm claims are limited to the exact development population reached in
this invocation. No validation/frozen, promotion, retained replay, global CVRP,
independent discovery, production readiness or v0.4-complete claim follows.

## Frozen one-shot command

The command uses normal `scion run`; it does not use the provider-free fixed-
candidate driver. Preparation requires a clean tracked worktree and index, all
named M24 inputs tracked, a fresh output root, bubblewrap, the local proxy model
metadata and no concurrent Scion/fixed-funnel process. These are ordinary
determinism and resource checks, not an object identity, lease, signature,
registry, receipt or hash lifecycle.

```bash
set -euo pipefail
cd /home/clawd/research/or-autoresearch-agent/scion
git diff --quiet
git diff --cached --quiet
test "$(git rev-parse --show-toplevel)" = /home/clawd/research/or-autoresearch-agent

for INPUT in \
  docs/experiments/v0.4/inputs/v04-cvrp-m24-autonomous-direction-research-development-protocol.yaml \
  docs/experiments/v0.4/inputs/v04-cvrp-m24-autonomous-direction-research-development-split.yaml \
  docs/experiments/v0.4/inputs/v04-cvrp-m24-autonomous-direction-research-development-seeds.yaml \
  docs/experiments/v0.4/inputs/v04-cvrp-m24-m22-research-history.jsonl \
  docs/experiments/v0.4/inputs/v04-cvrp-m24-m23-aggregate-research-input.json \
  docs/experiments/v0.4/inputs/v04-cvrp-m11-code-research-limits.json \
  docs/experiments/v0.4/v04-cvrp-m24-autonomous-direction-research-development-preregistration-20260821.md
do
  git ls-files --error-unmatch "$INPUT" >/dev/null
done

CAMPAIGN_DIR=/home/clawd/research/scion-experiments/v04-cvrp-m24-autonomous-direction-research-development-20260821
test ! -e "$CAMPAIGN_DIR"
test -x /usr/bin/bwrap
test -x /usr/bin/prlimit
test -z "$(ps -eo comm=,args= | awk '
  $1 ~ /^python/ &&
  ($0 ~ /-m scion[.]cli[.]main run/ || $0 ~ /run_.*candidate.*[.]py/) {
    print
    exit
  }
')"

PROXY_KEY_VALUE="$(curl -fsS --connect-timeout 5 --max-time 15 \
  http://127.0.0.1:8080/auth/status | \
  jq -er '.proxy_api_key | select(type == "string" and length > 0)')"
trap 'unset PROXY_KEY_VALUE' EXIT
curl -fsS --connect-timeout 5 --max-time 15 \
  -H "Authorization: Bearer $PROXY_KEY_VALUE" \
  http://127.0.0.1:8080/v1/models | \
  jq -e --arg model gpt-5.6-terra \
    'any(.data[]?; .id == $model)' >/dev/null

env -i \
  HOME=/home/clawd \
  PATH=/home/clawd/miniconda3/envs/claw/bin:/usr/bin:/bin \
  LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONHASHSEED=0 \
  PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion:/home/clawd/.local/lib/python3.12/site-packages:/home/clawd/miniconda3/envs/claw/lib/python3.12/site-packages \
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  SCION_PROBLEM_DATA_ROOT=/home/clawd/research/or-autoresearch-agent/vrp \
  SCION_MODEL=gpt-5.6-terra SCION_REASONING_EFFORT=high \
  SCION_BASE_URL=http://127.0.0.1:8080 SCION_API_KEY="$PROXY_KEY_VALUE" \
  SCION_LLM_TIMEOUT_SEC=120 \
  SCION_LLM_HYPOTHESIS_RESEARCH_TURN_TIMEOUT_SEC=120 \
  SCION_LLM_CODE_RESEARCH_TURN_TIMEOUT_SEC=240 \
  SCION_LLM_CODE_RESEARCH_FINALIZE_TIMEOUT_SEC=240 \
  /home/clawd/miniconda3/envs/claw/bin/python -S -B -m scion.cli.main run \
  --problem /home/clawd/research/or-autoresearch-agent/scion/scion/problems/cvrp/problem.yaml \
  --research-input /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m24-m23-aggregate-research-input.json \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m10-m9-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m11-m10-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m12-m11-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m13-m12-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m14-m13-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m15-m14-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m16-m15-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m19-m16-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m20-m19-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m21-m20-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m22-m21-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m24-m22-research-history.jsonl \
  --code-research-limits /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m11-code-research-limits.json \
  --protocol /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m24-autonomous-direction-research-development-protocol.yaml \
  --split /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m24-autonomous-direction-research-development-split.yaml \
  --seeds /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m24-autonomous-direction-research-development-seeds.yaml \
  --time-limit-sec 30 \
  --provider-call-cap 34 \
  --outer-hardwall-sec 15000 \
  --rounds 2 \
  --campaign-dir "$CAMPAIGN_DIR"
```

This standing authorization permits this command exactly once after the
ordinary inputs and preregistration are committed, the provider-/solver-free
preflight and independent review pass, and the output root is absent. It does
not authorize deletion/reuse of a created root or a second invocation.

No distribution, packaging, build, deployment, root/systemd, Trust/Hash
authority, object identity, lease, signing, registration or duplicate-closure
work is part of this experiment.
