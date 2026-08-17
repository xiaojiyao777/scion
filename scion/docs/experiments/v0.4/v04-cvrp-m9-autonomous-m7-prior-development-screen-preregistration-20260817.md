# CVRP M9 autonomous prior-evidence development screen preregistration

*Date: 2026-08-17*

*State: `ORIGINAL_ONE_SHOT_CONSUMED / GENERIC_FIX_VALIDATED_OFFLINE / RERUN1_AUTHORIZED_PENDING_CLEAN_CARRIER`*

## Purpose and research boundary

This preparation freezes one minimal, real-Agent research-effectiveness
campaign for the question already stored in the ordinary research input:

> Can Scion use the structured M7 terminal evidence to autonomously propose,
> implement, verify and evaluate a next CVRP solver candidate without the host
> choosing its implementation, source file or algorithmic direction?

Scion is the system under study. CVRP is one problem-owned research object.
The normal V3 chain remains Agent H, H Contract, Agent C, C Contract,
executable Verification, Protocol, Safe Features and deterministic Decision.
The host fixes only the question, source boundary, population, resource
envelope and claim boundary. The Agent's scientific and implementation choices
are not preselected in this document or its YAML inputs.

This is a development-screen experiment, not a fixed-candidate confirmation.
It does not reuse an M7 or R67 execution carrier. The exact production source
baseline is the ordinary CVRP problem package in clean repository commit
`9ae49b2125ec3d0c49dc6dee047e081ee0487dce`. That commit does not contain the
M9 inputs in this document and is not itself an M9 execution carrier. A launch
carrier must be a clean descendant commit containing the reviewed inputs and
this preregistration; its exact commit must be recorded with a later explicit
authorization. These commits are ordinary source identities, not the root of
a signing, registration or receipt lifecycle.

## Frozen ordinary inputs

The normal CLI loads these values:

- problem: `scion/scion/problems/cvrp/problem.yaml`;
- authoritative sibling problem specification and adapter:
  `scion/scion/problems/cvrp/problem-v1.yaml`;
- research input:
  `scion/docs/experiments/v0.4/inputs/v04-cvrp-m9-m7-fc1-research-input.json`;
- Protocol:
  `scion/docs/experiments/v0.4/inputs/v04-cvrp-m9-development-protocol.yaml`;
- split:
  `scion/docs/experiments/v0.4/inputs/v04-cvrp-m9-development-split.yaml`;
- seed ledger:
  `scion/docs/experiments/v0.4/inputs/v04-cvrp-m9-development-seeds.yaml`.

The research input contains only confirmed M7 stage facts, its terminal
candidate failure and the existing claim limitations. It contains no host
instruction for the next implementation. Its values reach H only through the
CVRP-owned safe observation projector. C receives the Contract-approved H and
editable source, not the raw M7 observation.

The normal CLI automatically loads the sibling `problem-v1.yaml`, creates a
fresh campaign-local workspace and uses the CVRP adapter for feasibility,
objective and runtime evidence. No historical experiment database, M7/R67
workspace or fixed-candidate driver is an input.

## Development population

All twelve CVRPLIB cases below are development data. Their identities are
public here and none may later be described as a formal unseen population.
Every selected `.vrp` is a regular non-symlink file, has a regular non-symlink
companion `.sol`, and loads through the current CVRP production loader with a
non-null BKS cost and route count.

| Split | Ordered cases | Ordered seeds | Per-subject seconds |
| --- | --- | --- | --- |
| screening | `cvrplib/B/B-n39-k5.vrp`; `cvrplib/P/P-n22-k2.vrp`; `cvrplib/A/A-n46-k7.vrp`; `cvrplib/F/F-n45-k4.vrp`; `cvrplib/X/X-n195-k51.vrp`; `cvrplib/X/X-n256-k16.vrp` | `3001, 3011` | `30, 30, 30, 30, 45, 60` |
| validation | `cvrplib/A/A-n65-k9.vrp`; `cvrplib/X/X-n270-k35.vrp`; `cvrplib/X/X-n317-k53.vrp` | `3019, 3023` | `30, 60, 60` |
| frozen | `cvrplib/X/X-n384-k52.vrp`; `cvrplib/X/X-n420-k130.vrp`; `cvrplib/X/X-n469-k138.vrp` | `3037, 3041` | `90, 90, 90` |
| canary | `data/tiny_canary.json` | `3049` | `10` |

The twelve CVRPLIB paths have exact overlap count zero with the complete M7
population, the R67 plan and all current CVRP package case inputs. The seven
seeds likewise have exact overlap count zero with their ledgers. Selection used
only path, family, dimension, parser compatibility and those exclusion sets;
no outcome for the not-yet-created M9 candidate exists or was consulted.

Companion loading is not a claim that every route token in an external BKS
file was independently validated. M9 consumes the production loader's route
count for the protected fleet objective. BKS cost does not decide promotion.

## Measurement and one-stage execution

The problem specification owns the budget-exhausting runtime model and the
lexicographic objectives:

1. minimize `fleet_violation` as the protected objective;
2. then minimize `total_distance` on the raw-delta scale.

The practical deltas remain `2.0` for screening and `1.0` for later stages.
The YAML preserves the R3 paired case-median aggregation, runtime policy and
case-quality gates without weakening them, including the requirement that an
initial numeric pass is reported as an expanded-screening request rather than
as a pass. Dimension bands remain 30 seconds through dimension 100, 45 through
200, 60 through 350, 90 through 700 and 120 through 1,001. Canary remains 10
seconds.

The invocation fixes `--rounds 1`. In the current campaign loop this means one
formally evaluated Protocol stage, not one provider call and not one proposal
attempt. A Contract or Verification research rejection may lead to another
fresh Agent attempt within the provider cap. The first candidate that reaches
a valid screening Protocol result consumes the single evaluated round; the
campaign then stops even when Decision reports that later evidence would be
appropriate. Validation and frozen cases are therefore required complete
configuration values but are not executed by this invocation.

No expansion replay, validation, frozen run, promotion, retained comparison or
second evaluated candidate is authorized. A screening result requesting more
evidence is itself terminal for this one-stage campaign; the configured
expanded population and seeds are not executed by `--rounds 1`.

## Provider and process envelope

The planned provider is exactly `gpt-5.6-terra` with reasoning effort `high`,
routed through the local Codex proxy at `http://127.0.0.1:8080`. Direct fallback
to the default external endpoint is outside this preregistration. Hypothesis
calls have a 120-second hard timeout and Code calls have a 240-second hard
timeout. The public-call transport performs one SDK request, with SDK retry
equal to zero. Actual H and C provider requests share one campaign cap of six;
a seventh request is rejected before transport.

The structural positive-path maxima are:

| Resource | Maximum |
| --- | ---: |
| actual H+C provider requests | 6 |
| actual H provider requests | 6 |
| actual C provider requests | 3 |
| complete H+C sequences | 3 |
| H Contract calls | 6 |
| C Contract calls | 3 |
| executable Verification calls | 3 |
| Verification solver subprocesses | 6 |
| Verification pytest subprocesses | 6, each at most 60 seconds |
| Protocol calls | 1 |
| Protocol canary solver subprocesses | 2 |
| formal screening solver subprocesses | 24 |
| all solver subprocesses | 32 |
| declared solver subject-seconds | 1,100 |
| solver positive hard-timeout seconds, including 15-second guards | 1,580 |
| provider positive hard-timeout seconds | 1,080 |
| known pytest hard-timeout seconds | 360 |
| `mgr.run` outer hardwall seconds | 4,500 |

The solver count is derived from the bounded normal path: at most three
successful H+C sequences can reach Verification, each successful Verification
uses two candidate-canary solver executions, one Protocol canary uses at most
two solver executions, and the six-case/two-seed/two-arm screening uses 24.
The subject-second sum is `6*30 + 2*10 + 16*30 + 4*45 + 4*60 = 1100`.
The solver hard-timeout sum is
`6*45 + 2*25 + 16*45 + 4*60 + 4*75 = 1580`.

Safe Feature and Decision each run at most once. There is no provider replay,
campaign resume, case or seed substitution, population addition, or automatic
second evaluated round. A provider-output or Contract rejection occurs before
candidate acceptance and cannot modify the verified source. A Verification
rejection discards its isolated candidate workspace and likewise leaves the
verified source unchanged.

## Typed stopping rules

- Invalid H/C output and H/C Contract or Verification rejection are typed
  `RESEARCH_REJECTED`. They may schedule a fresh research attempt only while an
  actual provider request remains under the shared cap.
- Exhausting the cap before another provider request is typed
  `RESOURCE_EXHAUSTED / PROVIDER_CALL_CAP_EXHAUSTED` and stops the campaign.
- Provider authentication, timeout, rate, transport or service failure is
  typed `BLOCKED_INFRA` and stops without provider replay.
- `NOT_EVALUATED`, another `BLOCKED_INFRA`, `RESOURCE_EXHAUSTED` or
  `INTERRUPTED` stops immediately.
- The 4,500-second watchdog records `OUTER_HARDWALL_EXCEEDED`, finalizes the
  interrupted campaign and exits with status 124.
- A canary veto produces no formal Protocol result. The current loop ends as
  `evaluated_without_formal_protocol_result`; it supports no algorithm-quality
  conclusion.
- The first complete screening Protocol result ends as
  `requested_rounds_completed`, regardless of its gate or Decision value.
- A preflight or unhandled exception yields no scientific claim.

Every terminal above ends this invocation. Starting another campaign requires
new explicit authorization.

## Planned normal CLI entry

This is a frozen command shape for later authorization, not an executable
authorization in this document:

```bash
set -euo pipefail
cd /home/clawd/research/or-autoresearch-agent/scion

test -n "${AUTHORIZED_M9_CARRIER:-}"
test "$(git rev-parse HEAD)" = "$AUTHORIZED_M9_CARRIER"
git diff --quiet
git diff --cached --quiet
REPO_ROOT="$(git rev-parse --show-toplevel)"
test "$REPO_ROOT" = /home/clawd/research/or-autoresearch-agent
git -C "$REPO_ROOT" diff --quiet \
  9ae49b2125ec3d0c49dc6dee047e081ee0487dce \
  "$AUTHORIZED_M9_CARRIER" -- scion/scion
test ! -e /home/clawd/research/scion-experiments/v04-cvrp-m9-autonomous-m7-prior-development-screen-20260817

PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion:/home/clawd/.local/lib/python3.12/site-packages:/home/clawd/miniconda3/envs/claw/lib/python3.12/site-packages \
PYTHONDONTWRITEBYTECODE=1 \
/home/clawd/miniconda3/envs/claw/bin/python -S -B - <<'PY'
from pathlib import Path

import scion
import scion.cli.commands.init_run as init_run
import scion.core.research_input as research_input
import scion.core.resource_envelope as resource_envelope
import scion.problems.cvrp.adapter as cvrp_adapter

root = Path("/home/clawd/research/or-autoresearch-agent/scion/scion").resolve()
if {Path(path).resolve() for path in scion.__path__} != {root}:
    raise SystemExit(f"unexpected scion namespace paths: {list(scion.__path__)}")
for module in (init_run, resource_envelope, research_input, cvrp_adapter):
    origin = Path(module.__file__).resolve()
    if root not in origin.parents:
        raise SystemExit(f"unexpected module origin: {origin}")
PY

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
  --research-input /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m9-m7-fc1-research-input.json \
  --protocol /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m9-development-protocol.yaml \
  --split /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m9-development-split.yaml \
  --seeds /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m9-development-seeds.yaml \
  --time-limit-sec 30 \
  --provider-call-cap 6 \
  --outer-hardwall-sec 4500 \
  --rounds 1 \
  --campaign-dir /home/clawd/research/scion-experiments/v04-cvrp-m9-autonomous-m7-prior-development-screen-20260817
```

The explicit working directory, interpreter, `-S`, dependency paths,
repository-first `PYTHONPATH` and bytecode-write exclusion are part of the
frozen entry. Using a bare installed `scion` executable is outside this
preregistration, because an editable installation can resolve another
checkout. The provenance block above must confirm that `scion` itself and the
loaded
`scion.cli.commands.init_run`, `scion.core.resource_envelope`,
`scion.core.research_input` and `scion.problems.cvrp.adapter` module files are
all beneath `/home/clawd/research/or-autoresearch-agent/scion/scion/` at the
authorized clean descendant of
`9ae49b2125ec3d0c49dc6dee047e081ee0487dce`.

The same prelaunch check must confirm that `HEAD` equals that authorized
descendant, the tracked worktree and index are clean, and the campaign output
directory is absent. Relative to `9ae49b2125ec3d0c49dc6dee047e081ee0487dce`,
there may be no change under the CVRP production package or generic Scion core
and provider-path packages. The descendant may add only the reviewed ordinary
M9 documentation/configuration and project status records. Any wider change
requires a new review and authorization; it cannot be silently accepted.

The 4,500-second watchdog starts immediately around `mgr.run`; CLI import and
provider-/solver-free configuration loading occur before it and are not part
of that watchdog interval. The campaign directory must be absent at launch.
The local proxy credential is read ephemerally from `/auth/status`, passed only
through `SCION_API_KEY`, never printed or persisted, and unset on shell exit.
The authenticated `/v1/models` request is a metadata-only preflight confirming
that `gpt-5.6-terra` is advertised; it sends no research prompt and is not a
provider generation. Each local HTTP preflight has a five-second connection
timeout and a fifteen-second total timeout. Neither proxy preflight had been
run before authorization. Both bounded local metadata checks passed during the
authorized invocation; neither was a provider generation.

## Three claim layers

### Framework behavior

A complete path may establish that the external M7 observation reached H only
through the CVRP projector, H and C remained Agent-owned, the same approved H
reached C, and current Contract, Verification, Protocol, Safe Features and
Decision ran in order on a fresh isolated workspace. A failure before the end
supports only the subset actually observed.

### Research effectiveness

Post-run review may assess whether H substantively used the M7 evidence,
whether H and the produced source change were coherent, and whether a
candidate reached the development screen. Ignoring the observation, producing
invalid work, failing Contract or Verification, receiving a canary veto, or
showing weak screening evidence are valid negative results about current Scion
research effectiveness. No desired wording or solution direction is a runtime
gate.

### Algorithm evidence

At most, this invocation can provide descriptive evidence for one candidate on
the six-case development screen. It cannot establish formal improvement,
promotion, an isolated causal effect, a new algorithmic principle, global CVRP
generalization or production readiness. A later-stage Decision is only a
recommendation recorded at the end of this campaign, not later-stage evidence.

## Future formal population

The future formal population is intentionally unselected, unwritten,
unavailable to the Agent and not runnable under this preregistration. A later
document must select it by a predeclared metadata-only rule, before any formal
candidate solver call. It must exclude all M7 and R67 cases, all current CVRP
package inputs, all twelve M9 development cases and every seed named above.
It requires a separate resource envelope, claim boundary and explicit user
authorization.

## Terminal record

The user explicitly authorized one invocation on clean carrier
`b1d7f6e38c65c99cdc4cb399402a19b2341d8e85` under this complete envelope. The
tracked worktree and index were clean, production source differed by zero from
`9ae49b2125ec3d0c49dc6dee047e081ee0487dce`, module origins and CLI flags
matched the frozen entry, the target output root was absent, and both bounded
local proxy metadata checks passed.

At `2026-08-17T23:26:13.792156010Z`, before `mgr.run`, provider generation or a
solver subprocess, CLI construction of `ExperimentProtocol` created the output
root and its `metrics/` directory. `CampaignManager` then applied the fresh
output check and rejected that directory as unexpected:

```text
ValueError: campaign output must be fresh; choose a new directory (found: metrics)
```

The invocation exited immediately. The durable output tree is mode `0700` and
contains exactly one empty `metrics/` directory, also mode `0700`: zero files
and zero symlinks. `resource_envelope.json`, `research_input.json`, database,
LLM traces, status, summary, terminal and metric artifacts do not exist. No
H, H Contract, C, C Contract, Verification, Protocol, Safe Features, Decision,
lineage, formal screening, provider generation, solver or pytest observation
exists. There is no typed campaign terminal because the campaign object was
not constructed.

This supports only a framework launch-path finding: output initialization and
the fresh-output invariant conflict in the normal CLI. It supports no claim
about Agent research effectiveness or CVRP algorithm quality. The authorized
one-shot is consumed. The output root is preserved; no deletion, repair,
retry, resume, replacement run, later development stage or formal rung is
authorized.

## Generic initialization fix and one authorized rerun

After reviewing the terminal finding above, the user explicitly instructed us
to fix the generic defect and authorized one rerun. That instruction does not
reinterpret the first invocation or erase its terminal record. The original
output root remains preserved exactly as observed.

The generic fix makes `ExperimentProtocol` construction side-effect free and
creates its metrics directory only when `run_experiment` actually begins.
`CampaignManager` still applies the same strict fresh-output check before it
installs campaign services; the check is not weakened and an existing nonempty
root remains invalid. Offline regressions cover absent, existing-empty and
existing-nonempty roots, provider-zero rejection, ordinary input/resource
artifacts, constructor-zero-output and direct Protocol metrics creation. No
CVRP- or Warehouse-specific condition is introduced.

Exactly one rerun is authorized after this fix is committed as a clean
descendant carrier and independently rechecked. It retains every scientific,
resource, stopping and claim boundary in this preregistration. The only
execution changes are the reviewed generic initialization fix, its tests, the
new exact carrier commit and this fresh output root:

```text
/home/clawd/research/scion-experiments/v04-cvrp-m9-autonomous-m7-prior-development-screen-rerun1-20260817
```

The rerun must use the same unique Python/module entry, local proxy, model,
research input, Protocol, split, seeds, `--rounds 1`, provider-call cap 6 and
4,500-second `mgr.run` hardwall already frozen above. Before launch, the exact
new carrier must be `HEAD`, the tracked worktree and index must be clean, the
new root must be absent, the original root must remain unchanged, and an
independent check must confirm that production changes from carrier
`b1d7f6e38c65c99cdc4cb399402a19b2341d8e85` are limited to the two reviewed
problem-neutral Protocol initialization files.

For the rerun, the original command block remains exact except for the carrier
diff gate and campaign directory. Its earlier zero-production-diff check is
replaced by this exact four-file fix-and-test check:

```bash
EXPECTED_FIX_FILES=$'scion/scion/protocol/experiment/facade.py\nscion/scion/protocol/experiment/stages.py\nscion/scion/tests/test_campaign_control_boundaries.py\nscion/scion/tests/test_protocol_split_runtime.py'
test "$(git -C "$REPO_ROOT" diff --name-only \
  b1d7f6e38c65c99cdc4cb399402a19b2341d8e85 \
  "$AUTHORIZED_M9_CARRIER" -- scion/scion)" = "$EXPECTED_FIX_FILES"
test ! -e /home/clawd/research/scion-experiments/v04-cvrp-m9-autonomous-m7-prior-development-screen-rerun1-20260817
test "$(find /home/clawd/research/scion-experiments/v04-cvrp-m9-autonomous-m7-prior-development-screen-20260817 -mindepth 1 -maxdepth 1 -printf '%f\n')" = metrics
test -d /home/clawd/research/scion-experiments/v04-cvrp-m9-autonomous-m7-prior-development-screen-20260817/metrics
test -z "$(find /home/clawd/research/scion-experiments/v04-cvrp-m9-autonomous-m7-prior-development-screen-20260817/metrics -mindepth 1 -print -quit)"
```

The final `--campaign-dir` argument is replaced by the `rerun1` path above.
All other environment values, preflights and CLI arguments remain byte-for-byte
the same.

The first post-fix shell preflight on carrier
`8960f223ddb01f9313b961c541409d9ae3abfe69` stopped before `scion run`: after
changing into the `scion/` subdirectory, the new exact-diff check incorrectly
used the repository-root-relative `scion/scion` pathspec without `git -C
"$REPO_ROOT"`. That check alone returned nonzero. The carrier, tracked/index
cleanliness, original root, absent rerun root, module origins, local proxy and
model checks all passed. The rerun root remained absent and provider
generations, solver subprocesses and campaign artifacts remained zero. The
corrected command above anchors the diff at the repository root. Because the
rerun process was not invoked, the authorized single rerun remains pending;
this preflight stop is not a campaign attempt and supplies no scientific
observation.

Any failed fix check, carrier check or preflight stops without launching. Once
the rerun process is invoked, its first typed or pre-campaign terminal consumes
this authorization. There is no deletion of either output root, retry, resume,
repair run, third attempt, automatic next round, later development stage or
formal rung under this amendment.
