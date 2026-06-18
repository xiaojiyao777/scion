# Post-Run Analysis Handoff

*Last updated: 2026-06-18*

Use this handoff after every real-cost v0.4 agentic campaign. The main session
should delegate raw-artifact inspection to a subagent and keep the main thread
focused on experiment design, repair decisions, and the next run gate.

This document operationalizes the v3 boundary: proposal traces and free text are
tainted research evidence. They may guide the next proposal or repair, but they
must not be treated as promotion evidence or as a Decision-layer input.

## Required Input

Give the analysis subagent exactly these paths and constraints:

- `RUN_ROOT`: the outer experiment directory under
  `/home/clawd/research/scion-experiments/`.
- `CAMPAIGN_DIR`: usually `$RUN_ROOT/campaign`.
- Preferred generated brief, when present:
  `$RUN_ROOT/postrun_acceptance/analysis_brief/*.postrun_analysis_brief.md`.
- Preferred generated inventory, when present:
  `$RUN_ROOT/postrun_acceptance/inventory/*.postrun_artifact_inventory.md`.
- Preferred prepared-run manifest, when present:
  `$RUN_ROOT/prepared_run_manifest.md`.
- Design anchors:
  - `scion/design/scion-architecture-v3.md`
  - `scion/docs/AGENT_ONBOARDING.md`
- Current task: analyze the experiment, do not modify source code, do not start
  another experiment, and do not call external LLM providers.

The generated brief is a report-only delegation aid. It summarizes validity,
required artifacts, prepared-run contract checks, Phase 4 evidence coverage,
and the required questions below. It is not a quality judgment and must not be
used as a gate by itself. When a prepared-run manifest is present, the brief
also carries the pre-registered analysis intent, acceptance focus, and resume
source so the delegated review answers the intended research question.

## Required Artifact Pass

The subagent must inspect these artifacts when present:

- `$RUN_ROOT/run_status.json`, `$RUN_ROOT/run.log`, `$RUN_ROOT/command.txt`,
  `$RUN_ROOT/launch.env`.
- `$RUN_ROOT/prepared_run_manifest.v1.json` and
  `$RUN_ROOT/prepared_run_manifest.md` when present.
- `$CAMPAIGN_DIR/status.json`, `$CAMPAIGN_DIR/run_status.json`,
  `$CAMPAIGN_DIR/campaign_summary.json`, `$CAMPAIGN_DIR/scion.db`.
- `$CAMPAIGN_DIR/agentic_sessions/agentic_session_index.json`.
- `$CAMPAIGN_DIR/agentic_sessions/agentic_session_trace_index.json`.
- `$CAMPAIGN_DIR/llm_traces/*.json`.
- `$CAMPAIGN_DIR/metrics/*.json`.
- `$RUN_ROOT/postrun_acceptance/analysis_brief/*` and
  `$RUN_ROOT/postrun_acceptance/inventory/*` when present.
- `$RUN_ROOT/postrun_acceptance/research_efficiency/*` and
  `$RUN_ROOT/postrun_acceptance/manifests/*` when present.
- `$CAMPAIGN_DIR/archive/**`, `$CAMPAIGN_DIR/workspaces/**`,
  `$CAMPAIGN_DIR/champions/**` only as needed to verify patch identity,
  checkpoint behavior, or promoted snapshots.

If the run is `invalid_infra_only`, the analysis should stop after proving the
infra-only status. Do not interpret it as Scion research behavior.

Counter semantics:

- `--rounds` / `max_rounds` is the requested effective screened/formal candidate
  budget, not total loop steps or total proposal attempts.
- `effective_rounds_completed` is the requested-round budget counter.
- `formal_screened_candidates` counts formal screening candidates.
- `protocol_evaluated_candidates` counts Protocol-evaluated candidates across
  screening/validation/frozen.
- Proposal attempts, telemetry/validation repair attempts, branch lifecycle
  policy blocks, reconcile lifecycle steps, and scheduler active-slot blocks are
  separate explanatory counters.
- `total_rounds` is a legacy/external attempt surface; do not use it alone to
  decide run validity or scheduler behavior.

## Analysis Scope

The report must be branch-centric first, then round-centric.

For each branch:

- lineage: parent, clean fork vs same-branch refinement, base champion hash,
  checkpoint and rollback events;
- branch intent: hypothesis family, intervention type, selected surface,
  target file, novelty or material-difference claim;
- research trajectory: whether follow-ups use branch-local evidence, sibling
  lessons, and historical success/failure memory;
- outcome: screening, validation, frozen, abandon, park, rollback, promote, or
  infra stop;
- health judgment: useful research, weak but rational probe, repeated near
  duplicate, framework-control failure, object-model/prompt failure, provider
  failure, or genuine algorithm-quality abandonment.

For every campaign round/step, including attempts that fail before a formal
candidate is created, proposal-quality blocks, repair-loop stops, and
infra/provider stops:

- round/step id and branch id;
- hypothesis-stage prompt context summary, whether the agent saw enough of the
  declared problem object, and every tool call/result;
- for each hypothesis-stage tool call: whether it was relevant, non-looping,
  and useful for the research decision being made;
- hypothesis output: problem anchor, surface, target, mechanism signature,
  expected evidence, and whether it respected v3/scion boundaries;
- code-stage prompt context summary, whether the agent saw enough of the
  declared problem object and selected surface, and every tool call/result;
- for each code-stage tool call: whether it was relevant, non-looping, and
  useful for implementing or checking the proposed mechanism;
- patch output: changed files, whether the code implements the hypothesis, and
  whether it stayed inside the declared research surface;
- preview/smoke results, Contract, Verification, canary, Protocol, Safe Feature
  Extractor, and Decision path;
- whether Decision read only `DecisionFeatures` and whether tainted cross-branch
  memory stayed in proposal visibility;
- concrete repair or next-run implication.

## Required Questions

The final report must answer these questions directly:

1. Did the run complete enough formal candidates to be valid for its requested
   effective screened/formal candidate budget?
2. Did the agent perform effective research, or only satisfy framework controls?
3. Were branch hypotheses and code changes internally coherent?
4. Did branch-local follow-up and rollback/checkpoint behavior make sense?
5. Did the agent see enough of the declared problem object and selected surface
   before writing hypothesis and code outputs?
6. Were LLM tool calls relevant, non-looping, and useful, or did they consume
   budget without improving the research step?
7. Did preview/smoke results provide meaningful pre-protocol evidence, and did
   later prompts use that evidence correctly?
8. Did sibling branches learn from each other through proposal-visible memory
   without crossing into DecisionFeatures?
9. Did historical failure/success memory influence later proposal choices?
10. Were there repeated near-duplicate branches that scheduler/novelty should
   have diversified?
11. Are any failures framework/control regressions rather than algorithm-quality
   failures?
12. Is the next step repair, rerun at the same round count, or promote the
   experiment ladder to the next count?

## Output Format

Use this shape for the delegated report:

```markdown
# <run name> Post-Run Analysis

## Verdict
- Validity:
- Research quality:
- Framework health:
- Next step:

## Evidence Inventory
- Run status:
- Counters:
- Branch count:
- LLM calls:
- Formal candidates:
- Promotions:

## Branch Analyses
### Branch <id>
- Lineage:
- Hypothesis/code trajectory:
- LLM call trace:
- Evaluation/Decision:
- Cross-branch and historical memory use:
- Judgment:
- Repair implication:

## Round And LLM-Call Trace
| Step | Branch | Stage | Trace ids | Problem-object visibility | Tool-call quality | Output | Preview/smoke | Gate/Decision |
|---|---|---|---|---|---|---|---|---|

## Cross-Branch Research Map
- Similarity/difference:
- Useful lessons transferred:
- Missed transfer:
- Diversity pressure:

## Failure Taxonomy
- Framework boundary/control:
- Prompt/API/object-model:
- Repair-loop/accounting:
- Provider/infra:
- Algorithm-quality:

## Required Answers
1. ...

## Recommendations
- Repair before next run:
- Same-round rerun:
- Ladder advancement:
```

## Main-Session Follow-Up

After the subagent returns:

- accept only conclusions backed by artifact paths, trace ids, branch ids, SQL
  rows, or JSON fields;
- decide the next gate:
  - invalid infra only: rerun same round count after provider recovery;
  - framework/control regression: repair before another experiment;
  - valid short run with no major regression: advance through
    `4R -> 8R -> 12R -> 20R -> 40R -> 50R`;
  - real promotion or strong branch evidence: run the next confirmation step;
- update the relevant experiment doc under `scion/docs/experiments/v0.4/` and
  `scion/docs/status/current-state.md` when the result changes project state.
