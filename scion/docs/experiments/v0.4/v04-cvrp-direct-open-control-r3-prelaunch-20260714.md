# CVRP Direct Open Control R3 Prelaunch Audit

Date: 2026-07-14

Status: prepared-only; explicit launch authorization required

## Identity

- run root:
  `/home/clawd/research/scion-experiments/v04-cvrp-direct-open-control-r3-2r-gpt56sol-20260714T163231Z-claw`;
- runtime:
  `/home/clawd/research/or-autoresearch-agent-v04-direct-runtime-1978b426`;
- prepared/runtime commit: clean detached `1978b426`;
- model: `gpt-5.6-sol`;
- rounds: `2`;
- solver subprocess limit: `30` seconds;
- force surface/action/target: all empty;
- completion preflight: enabled inside run.sh;
- provider/live-probe calls so far: `0`.

This is a new root after the R2 static-auditor failure. R1 and R2 remain
superseded and must not be resumed, edited, or launched.

## Formal Data and Wrapper

The explicit external data root resolves all 40 formal cases, all 40 sibling
`.sol` files, and the package canary. The 81-file ordered identity is:

`ca7e470ec8d1f3569a690d10df5a170c4994108c71fecf5aa1a7a76b42630743`

The standalone checker reports no missing cases, missing companions, symlinks,
path escapes, or other unsafe files. The generated wrapper embeds the same
digest in both pre-provider and post-campaign checks. Its SHA256 is
`2074a4d6972461db7c4e4212947b3441b22dbf84c614c4ba0b708e0415b00150`,
matching `launch.env`.

`launch.env` and the data identity receipt are mode `0600`. The prepared root
contains only the API-key environment variable name; the key value is absent.
Scans for proxy-key and account-identity receipt fields are empty.

## Readiness

Static guarded-wrapper readiness passes with:

- `ready=true`;
- `static_ready=true`;
- `guarded_wrapper_launch_ready=true`;
- required failures: `[]`;
- optional failures: `[]`;
- campaign, scheduler, and promotion mutation: all `false`.

`launch_ready=false` is expected because no separate live completion was sent.
The guarded wrapper owns the sole live completion preflight and must execute it
before campaign initialization. The root has no PID, provider trace, live
preflight receipt, or campaign execution artifact.

## First-H Context Audit

The no-provider audit used the production construction path:

`ContextManager.build_hypothesis_context` ->
`proposal_context_snapshot` -> `build_prompt_turn_snapshot`

The provider-visible shape has three system blocks and one user prompt. Its
active surface is only `solver_design`. Targetable scope is 12 entries: 11
concrete algorithm files plus the declared
`policies/baseline_modules/*.py` wildcard. The concrete files are:

- `policies/baseline_algorithm.py`;
- `policies/baseline_modules/acceptance.py`;
- `policies/baseline_modules/config.py`;
- `policies/baseline_modules/construction.py`;
- `policies/baseline_modules/destroy_repair.py`;
- `policies/baseline_modules/local_search.py`;
- `policies/baseline_modules/route_first_heuristic.py`;
- `policies/baseline_modules/route_first_improvement.py`;
- `policies/baseline_modules/route_first_seeding.py`;
- `policies/baseline_modules/scheduler.py`;
- `policies/baseline_modules/state.py`.

The native audit render is about 87.3k characters. Open guidance is present:
no prepared file or mechanism is mandatory, the hypothesis must be
algorithmically material, and the agent may choose a CVRP-owned causal path.
Pattern counts are zero for:

- successor IDs;
- target-intent and forced targeting;
- mechanism ranking or denylist;
- telemetry gate;
- candidate caps;
- retry or backoff;
- truncation controls;
- semantic, token, context, or output budgets.

Independent review reports P0=`0`, P1=`0`, P2=`0`.

## Launch Discipline

Keep this root prepared-only until the operator explicitly authorizes launch.
At launch, provide `SCION_SHARED_PROXY_KEY` only in the process environment.
Poll about every three minutes. Never auto-retry, replace, resume, or silently
repair this run. After a terminal outcome, audit H/C receipts, solver pairs,
lineage, algorithmic materiality, runtime, and postrun readiness before any
continuation or promotion decision.
