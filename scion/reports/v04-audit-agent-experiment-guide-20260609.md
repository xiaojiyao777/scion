# Scion v0.4 Audit Agent Experiment Guide

Date: 2026-06-09

This guide is for audit agents that review Scion architecture or code without
running experiments themselves. Its purpose is to prevent false conclusions
caused by misunderstanding experiment entrypoints, copied configuration
snapshots, artifacts, counters, and the v3 decision boundary.

## Governing Boundary

Use `scion/design/scion-architecture-v3.md` as the architecture source of
truth.

The core invariant is:

- LLM output is tainted proposal material.
- Contract, verification, protocol execution, and safe feature extraction are
  the path into deterministic `DecisionFeatures`.
- Decision logic must only read `DecisionFeatures`.
- Problem-owned facts such as BKS, gap, case hardness, and research-object
  readiness are diagnostics and proposal guidance. They must not become generic
  framework decision inputs.
- Cross-branch lessons are proposal visibility and scheduler/research-map
  context. They are not promotion evidence by themselves.

When auditing, separate three questions:

1. Did the agent receive enough usable research context to propose real
   algorithmic changes?
2. Did the framework produce complete, replayable, adapter-backed evidence?
3. Did deterministic decision logic consume only safe structured features?

## Repository Layout and CWD Pitfalls

The checked-out repository root is normally:

```text
/home/clawd/research/or-autoresearch-agent
```

The Scion Python package root used by experiment launchers is:

```text
/home/clawd/research/or-autoresearch-agent/scion
```

Most experiment commands run with cwd set to that Scion directory and
`PYTHONPATH` set to the same directory.

This means some paths in launch files are intentionally relative to
`/home/clawd/research/or-autoresearch-agent/scion`, not to the repository root.
Do not treat this as a missing-file bug without checking cwd.

CVRP and warehouse currently use different package layouts:

- CVRP source package:
  `/home/clawd/research/or-autoresearch-agent/scion/scion/problems/cvrp`
- CVRP launcher path from cwd `scion/`:
  `scion/problems/cvrp/problem.yaml`
- Warehouse source package:
  `/home/clawd/research/or-autoresearch-agent/scion/problems/warehouse_delivery`
- Warehouse path from cwd `scion/`:
  `problems/warehouse_delivery/problem.yaml`

This asymmetry is historical. It matters for audit accuracy.

## Experiment Entrypoints

The common campaign entrypoint is:

```bash
python -m scion.cli.main run \
  --problem <problem.yaml> \
  --protocol <protocol.yaml> \
  --split <split_manifest.yaml> \
  --seeds <seed_ledger.yaml> \
  --campaign-dir <campaign_dir> \
  --rounds <N> \
  --time-limit-sec <seconds> \
  --agentic-session-timeout-sec <seconds> \
  --disable-early-stop \
  --agentic-proposal
```

The CVRP helper launcher is:

```bash
python scion/tools/launch_cvrp_agentic_campaign.py \
  --label <label> \
  --rounds <N> \
  --launch
```

The CVRP launcher prepares a detached run directory under:

```text
/home/clawd/research/scion-experiments
```

It writes `launch.env`, `run.sh`, starts `setsid + nohup`, and records `pid`,
`run.log`, `nohup.log`, `run_status.json`, and `exit.txt`.

Current local GPT experiment settings are usually:

```bash
SCION_MODEL=gpt-5.5
SCION_BASE_URL=http://127.0.0.1:8080
SCION_API_KEY=pwd
```

Do not infer the model from shell defaults alone. Confirm it from experiment
artifacts, especially status fields and `llm_traces`.

## Run Directory Anatomy

A typical detached run root looks like:

```text
<run_root>/
  launch.env
  run.sh
  run.log
  nohup.log
  pid
  exit.txt
  run_status.json
  campaign/
    run_status.json
    status.json
    campaign_summary.json
    scion.db
    agentic_sessions/
    artifacts/
    champions/
    llm_traces/
    metrics/
    workspaces/
```

Use the outer files to determine wrapper status. Use the inner `campaign/`
files to understand Scion campaign semantics.

Important files:

- `launch.env`: command-time environment and resolved problem/protocol/split
  paths.
- `run.sh`: exact command used by the detached wrapper.
- `run.log`: wrapper logs plus Scion CLI stdout/stderr.
- `exit.txt`: wrapper completion summary, if the wrapper finished.
- `campaign/run_status.json`: CLI wrapper audit written from inside Scion.
- `campaign/status.json`: current campaign state snapshot.
- `campaign/campaign_summary.json`: final or near-final summary.
- `campaign/scion.db`: durable campaign database.
- `campaign/llm_traces/*.json`: model calls and model names.
- `campaign/metrics/*.json`: protocol result artifacts.
- `campaign/agentic_sessions/<id>/`: per-proposal LLM/session artifacts.
- `campaign/artifacts/formal_candidates/index.jsonl`: replayable formal
  candidate patch artifacts.
- `campaign/champions/champion_v*/`: copied champion workspace and copied
  problem/protocol files.
- `campaign/workspaces/<branch_id>/`: branch workspaces.

## Effective Configuration

Never assume a completed or running experiment used the current repository
source. Campaigns copy or reference configuration at launch time, and the source
tree may have changed afterward.

For an experiment audit, resolve effective configuration in this order:

1. Inspect `<run_root>/launch.env` and `<run_root>/run.sh`.
2. Inspect copied files under `campaign/champions/champion_v1/`.
3. Inspect metric artifacts under `campaign/metrics/`, especially per-pair case
   IDs and seeds.
4. Inspect `campaign/status.json` and `campaign/campaign_summary.json`.
5. Use the current repository source only to understand code paths, not to
   infer what an already-launched run used.

This distinction is important for CVRP. Some recent source files were updated
to use redesigned formal cases and more seeds, while older already-launched
runs still used the previous copied formal configuration.

## Campaign Data Flow

The high-level flow is:

```text
problem spec + protocol + split + seeds
  -> workspace materialization and champion snapshot
  -> proposal context construction
  -> LLM hypothesis session
  -> LLM code session and patch proposal
  -> contract gate
  -> verification gate
  -> canary or screening protocol
  -> safe feature extraction
  -> deterministic decision
  -> branch state, evidence, scheduler state, and optional promotion
```

For audit purposes, distinguish:

- Proposal context and LLM transcripts: what the agent saw and attempted.
- Contract and verification: whether the patch was admissible and runnable.
- Protocol metrics: what was actually measured.
- Safe features: what the deterministic decision layer was allowed to read.
- Branch lifecycle and scheduler state: how future branch selection was shaped.

Do not collapse these layers into one "the model decided" explanation.

## LLM Calls and Sessions

Each candidate normally has multiple LLM interactions. Audit by session and
phase, not just by final patch.

Useful locations:

```text
campaign/agentic_sessions/<session_id>/output.json
campaign/agentic_sessions/<session_id>/transcript.json
campaign/agentic_sessions/<session_id>/**/prompt*.json
campaign/llm_traces/*.json
```

For each round, inspect:

- hypothesis prompt visibility;
- tool-selection behavior and deterministic prefetch markers;
- tool observations that became visible to the model;
- hypothesis content and mechanism family;
- code prompt visibility;
- changed files and patch size;
- contract/verification/protocol result;
- decision outcome and reason codes;
- resulting branch state.

Recent tooling audits focus on whether deterministic control-flow overhead was
removed without depriving the agent of useful research context. Lower token or
tool-call counts are not success by themselves.

## Metrics, Formal Candidates, and Counters

Do not assume every counter means "one successful experiment".

Common counters:

- `proposal_attempts_total`: proposal attempts, including attempts blocked by
  proposal quality or retries before protocol evidence exists.
- `quality_blocks` or `proposal_quality_blocks`: proposal/schema quality
  failures before candidate protocol evaluation.
- `effective_rounds_completed`: legacy requested-round progress counter.
- `effective_protocol_rounds`: protocol-evaluated candidate rows counted toward
  the requested round budget.
- `protocol_metric_results`: completed protocol metric artifacts.
- `screening_protocol_results`, `validation_protocol_results`,
  `frozen_protocol_results`: stage-specific protocol counts.
- `formal_candidate_artifact_count`: replayable candidate artifacts, not a
  complete count of every LLM proposal or every metric file.

For CVRP metric artifacts, inspect pair-level entries rather than only aggregate
status. Pair-level fields identify the case, seed, candidate/champion objective,
runtime state, pair outcome, and stage.

An experiment can have more proposal attempts than formal candidate artifacts
because some proposals are blocked, repaired, or fail before formal artifact
capture.

## CVRP-Specific Audit Notes

CVRP is a problem package and should stay problem-owned. BKS, known-best gap,
case hardness, and route feasibility are valid CVRP diagnostics, but they are
not generic Scion decision features.

Current important facts for audit interpretation:

- Older CVRP screening splits were too saturated: many screening cases were
  already at or near BKS, so early screening was a weak research object.
- Some older 12R/40R runs used only two screening seeds because they were
  launched before the formal seed redesign.
- New CVRP formal source configuration expands screening seeds and removes
  solved-to-BKS screening cases, but older run artifacts still reflect their
  launch-time configuration.
- The strong claim "VNS erases all Scion modifications" is not globally
  supported by artifacts: non-tie pair outcomes exist, and editable surfaces
  include solver-design files beyond a single operator hook.
- A narrower risk remains: weak or upstream-local changes can be absorbed by
  the existing ALNS/VNS search basin and produce all-tie outcomes. Audit this
  by target surface and mechanism family, not as a blanket framework failure.

When auditing a CVRP run, always answer:

- Which effective formal split and seeds did this run use?
- Did screening contain enough non-saturated cases for a win to be measurable?
- Did any candidate produce non-tie pair outcomes?
- Which target surfaces were modified?
- Did branch lessons influence later hypotheses as advisory research context?
- Did evidence stop at screening, or reach validation/frozen?

## Warehouse Contrast

Warehouse experiments are useful as a contrast case because earlier runs showed
the Scion loop can produce promotions on that simpler problem. This supports the
interpretation that CVRP failures may be research-object, protocol, context, or
surface-design issues rather than proof that the generic Scion loop is broken.

Still, do not overgeneralize from warehouse to CVRP:

- warehouse uses a different problem layout;
- warehouse cases are smaller and faster;
- warehouse algorithm surfaces are less dominated by heavy local-search
  dynamics;
- warehouse evidence reaching promotion does not automatically validate CVRP
  research-object design.

## Context Quality Audit

A recurring v3 risk is context degeneration into a log pile.

When auditing prompts, do not only count tokens. Classify prompt content:

- problem mechanics and active solver facts;
- relevant target source;
- branch-local history;
- screening/runtime feedback;
- cross-branch lessons;
- tool observations;
- governance, compliance, and audit metadata;
- raw logs or duplicated state.

The desired outcome is not "shorter prompts". The desired outcome is that the
agent has enough context to do real algorithm research while not spending most
attention on framework compliance or duplicated logs.

If context is shortened but the agent loses problem mechanics, source facts,
runtime feedback, or cross-branch lessons, that is a regression.

## Valid Audit Conclusions

Good conclusions should be tied to evidence and layer boundaries.

Valid:

- "This run used old screening seeds because `launch.env`, copied seed ledger,
  and metric pairs show seeds `[11, 29]`."
- "This branch produced a code patch but no protocol metric because it was
  blocked before evaluation."
- "This candidate modified an upstream local-search-adjacent surface and all
  pairs tied, so VNS absorption is plausible for this mechanism family."
- "Cross-branch lessons were visible in proposal context but did not appear to
  change the hypothesis mechanism."
- "The prompt contains enough source but not enough compact branch-local
  failure signal."

Invalid or incomplete:

- "The current repo seed ledger has four seeds, so this old run used four
  screening seeds."
- "No promotion means the framework is broken."
- "BKS should be added to `DecisionFeatures`."
- "Fewer tool calls means the agent behaved better."
- "All CVRP changes are erased by VNS" without checking pair-level non-ties and
  modified target surfaces.

## Minimal Audit Checklist

For each experiment:

1. Record run root, campaign dir, git commit, model, and wrapper status.
2. Resolve effective problem/protocol/split/seed files from launch artifacts and
   copied champion files.
3. Count proposal attempts, quality blocks, protocol metric rows, and formal
   candidate artifacts separately.
4. For each round, read the LLM hypothesis and code sessions.
5. Identify target files, mechanism family, and whether the change is materially
   different from recent branches.
6. Trace contract, verification, protocol, safe features, decision, and branch
   state transition.
7. Inspect pair-level metrics for non-ties, runtime failures, and stage reached.
8. Check whether branch-local and cross-branch lessons were visible and used as
   advisory research context.
9. Classify failures by layer: proposal quality, contract, verification,
   protocol evidence, runtime/fresh champion, lifecycle/scheduler, or algorithm
   signal.
10. State whether the observed issue belongs in generic Scion core, problem
    package configuration, prompt/context profile, or experiment protocol.

## Useful Read Commands

Examples:

```bash
sed -n '1,220p' <run_root>/launch.env
sed -n '1,260p' <run_root>/run.log
jq . <run_root>/campaign/run_status.json
jq . <run_root>/campaign/status.json
jq . <run_root>/campaign/campaign_summary.json
find <run_root>/campaign/llm_traces -type f | sort | head
find <run_root>/campaign/agentic_sessions -maxdepth 3 -type f | sort | head
find <run_root>/campaign/metrics -type f | sort | head
sed -n '1,80p' <run_root>/campaign/artifacts/formal_candidates/index.jsonl
```

If `jq` is unavailable, use Python JSON pretty-printing or plain `sed` for
small files.
