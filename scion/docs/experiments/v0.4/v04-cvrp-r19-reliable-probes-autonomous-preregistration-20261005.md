# CVRP R19 reliable tests real paths and gain stability

State: **completed**, October7 at10:19:30 Beijing /02:19:30 UTC; valid12/12,
320 pairs,105 successful calls, final SCREENING_PASS/queue_validate but no
validation or promotion before the requested-stage cap. Never resume. See the
[October8 postrun](v04-cvrp-r19-reliable-probes-autonomous-postrun-20261008.md).
Started once October6 at17:31:21 Beijing /09:31:21 UTC, PID578803, after the
fresh P16 control completed and passed its terminal audit. The design and startup
wording below is historical, not a current launch instruction.
October 5 user authorizes analysis,
optimization and a fresh experiment, emphasizing test reliability, actual-path
coverage and stable gains. [R18 terminal analysis](v04-cvrp-r18-research-context-autonomous-preregistration-20261004.md#terminal-analysis-october-5)
finds twelve valid screening stages /176 pairs, no promotion, wrong or
uncollected tests, mock-only coverage, a failed correction of an actual chain
defect, and seed-fragile gains. This design tests research support and denser
screening, not a host-selected algorithm fix.

## Intervention and falsifiable questions

Shared support adds a bounded `pytest_no_tests_collected` hint for pytest exit5,
while retaining inconclusive outcome and unchanged readiness rules. No child
exception text, private data, automatic repair, additional retries or authority.
Generic prompts explain collected assertions, independent references and that
revise replaces a whole draft against the original session edit base; reads do
not show the overlaid draft. Failed exact executable patches remain rejected.

Optional problem-owned public examples add independently checked rational
arithmetic and real solve-entry observation across synthetic 40-/320-customer
sizes, capacities10/40 and public seeds1703/1709. Wrappers call the real
construction and operators without changing guards, budgets or returned results.
The public fixture grants .35/1.4 seconds to the respective sizes within the
unchanged ten-second probe sandbox; these are not Protocol limits. Mutation
regressions check empty registries, bypassed entry and wrong arithmetic.
None is a new collected candidate gate, required testing style or solver recipe.

Actual H/C postrun should distinguish reference validity, collected tests, real
path entry, completed transitions, acceptance and best improvement. Inspect
whether corrected drafts can retain intended changes, and whether complete seed
patterns support gains. A model may choose different tests or none. No activity,
novelty, source-read, ablation or mechanism requirement is introduced.

## Scientific design and limitations

Initial source remains the complete100-file R12-A-fixed tree:
`/home/clawd/research/scion-experiments/v04-cvrp-r13-constructor-fixed-b0-20260926/input_snapshots/candidate`.
No R18 candidate is selected, reconstructed or merged. Common constructor repair
is prior operator-assisted engineering, not autonomous discovery or promotion.

[Research input](inputs/v04-cvrp-r19-reliable-probes-autonomous-research-input.json)
preserves the preceding question and all five observations, amending only the
prospective R19 seed-count sentence and adding all R18 screening/public-source
context. Eighteen ordered history files are loaded whole, with all twelve R18
screening records, not a favorable selection. No private validation or control
output is fed to H/C.

[Protocol](inputs/v04-cvrp-r19-reliable-probes-autonomous-protocol.yaml) changes
only version/canary seed and screening seed counts: five initial cases ×four
seeds, mandatory six-case ×six-seed expansion. Validation6×2 and frozen12×2
remain unchanged, as do all case populations, feasibility/fleet protection,
case-level aggregation and scientific thresholds. Practical screening margin2
and validation margin1 are unchanged. Dimension limits60/90/120/180/240 seconds,
canary10, algorithm fraction and reserve are unchanged. Do not pool differently
sampled initial/expanded stages or compare their medians as a trajectory.

[Seed ledger](inputs/v04-cvrp-r19-reliable-probes-autonomous-seeds.yaml) fixes the
first eleven primes above220000 before outcomes: screening
220009/220013/220019/220021/220057/220063; validation220123/220141;
frozen220147/220151; canary220163. This is outcome-informed development design:
more sampled seeds may expose fragility earlier, but do not create independent
case generalization, prove stability or repair absent MDE/power calibration.

K=1/max three branches, twelve evaluated stages, gpt-6.1-sol high, H180/C300,
SDK retry0/two charged typed redispatches,600 physical calls and172800-second
outer guard remain unchanged. R3i C limits remain12 turns/8 reads/8 searches/
4 tests, uncapped transcript characters; parameter search off. More pairs per
stage can take longer within the same outer guard; an incomplete run stays
incomplete. No budget widening or terminal resume. The October5 user-approved
model amendment changes only the prospective H/C model from gpt-5.6-sol to
gpt-6.1-sol; high and all other settings stay fixed. P15 and the model change
cannot be separated causally by this run.

Champion-first ordering remains a limitation. Any promising exact candidate
still needs independent counterbalanced retained confirmation. Previously exposed
validation is not new independent evidence; frozen/retained remain conditionally
unopened. A positive screen is not promotion or original-B0 superiority.

## Verification and launch conditions

Runtime is pushed base `484433ea` plus scoped uncommitted P15 and P16 changes.
That was the control's launch-time provenance. The subsequent October5 request
authorizes committing/pushing the same frozen set without changing runtime or
inputs. At18:31 Beijing the fresh control remains running0/2; CVRP is not launched.
Freeze the ordinary checkout and inputs before measurement, with no additional
authority/packaging system.
Focused regressions, full suite, source/data/public-formal closure, exact safe
H projection and actual initial source comparison must pass.

Run the [fresh import-feedback Warehouse control](v04-r19-warehouse-import-feedback-control-20261005.md)
first on the same runtime. Audit actual H/C source, corrections and paired science.
A real execution/boundary defect blocks CVRP; negative quality alone does not.
Preserve incomplete controls and their limits instead of silently extending them.
One bounded provider health inference is allowed; do not print/store credentials.

No tests, competing solvers, maintenance or runtime/input changes overlap either
measurement. Only status/analysis docs may change. R18 and all historical evidence
stay untouched. At CVRP startup verify all100 files, exact question/observations/
history index, successful actual H and the frozen resource envelope.

Output: `/home/clawd/research/scion-experiments/v04-cvrp-r19-reliable-probes-autonomous-20261005`.
Tmux: `scion-r19-reliable-probes-autonomous-20261005`.

## Planned direct invocation

```bash
set -Eeuo pipefail
cd /home/clawd/research/or-autoresearch-agent
test ! -e /home/clawd/research/scion-experiments/v04-cvrp-r19-reliable-probes-autonomous-20261005
proxy_key_value=$(curl -fsS --connect-timeout 5 --max-time 15 http://127.0.0.1:8080/auth/status | jq -er '.proxy_api_key | select(type == "string" and length > 0)')
curl -fsS --connect-timeout 5 --max-time 15 -H "Authorization: Bearer $proxy_key_value" http://127.0.0.1:8080/v1/models | jq -e 'any(.data[]?; .id == "gpt-6.1-sol")' >/dev/null
exec env \
  PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
  PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion \
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  SCION_PROBLEM_DATA_ROOT=/home/clawd/research/scion-experiment-inputs/v04-cvrp-r6-minus-2for1-b0-20260921/data \
  SCION_MODEL=gpt-6.1-sol SCION_REASONING_EFFORT=high \
  SCION_BASE_URL=http://127.0.0.1:8080 SCION_API_KEY="$proxy_key_value" \
  SCION_LLM_TIMEOUT_SEC=180 SCION_LLM_HYPOTHESIS_RESEARCH_TURN_TIMEOUT_SEC=180 \
  SCION_LLM_CODE_RESEARCH_TURN_TIMEOUT_SEC=300 SCION_LLM_CODE_RESEARCH_FINALIZE_TIMEOUT_SEC=300 \
  /home/clawd/miniconda3/envs/claw/bin/python -B -m scion.cli.main run \
    --problem /home/clawd/research/or-autoresearch-agent/scion/scion/problems/cvrp/problem-v1.yaml \
    --source-tree /home/clawd/research/scion-experiments/v04-cvrp-r13-constructor-fixed-b0-20260926/input_snapshots/candidate \
    --research-input /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r19-reliable-probes-autonomous-research-input.json \
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
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r11-wide-budget-autonomous-20260923/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r12-post-r11-autonomous-20260924/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r14-post-r13-autonomous-20260927/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r15-feedback-repair-autonomous-20260927/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r16-probe-diagnostics-autonomous-20260928/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r17-quota-aware-autonomous-20261003/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r18-research-context-autonomous-20261004/research_history.jsonl \
    --code-research-limits /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r3i-long-run-code-research-limits.json \
    --protocol /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r19-reliable-probes-autonomous-protocol.yaml \
    --split /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r7-autonomous-source-continuation-split.yaml \
    --seeds /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r19-reliable-probes-autonomous-seeds.yaml \
    --time-limit-sec 60 --rounds 12 --provider-call-cap 600 \
    --provider-transient-retries 2 --outer-hardwall-sec 172800 \
    --campaign-dir /home/clawd/research/scion-experiments/v04-cvrp-r19-reliable-probes-autonomous-20261005
```

## Verification and actual execution

Full suite passes **2659 tests / one skip in453.27 seconds**. Focused groups
pass200 probe/development and92 revision/input tests (overlapping, not additive).
The first focused run exposed two failures in the new example: .65 seconds at
320 customers could finish construction without any operator call. The example
now grants1.4 seconds there, with unchanged real clocks/guards and the actual-call
assertion retained. Both repository source and the complete selected R12-A-fixed
source pass the entire optional14,819-character example within the existing
ten-second sandbox. No algorithm or Protocol time limit was changed.

Read-only preflight passes:100 initial source files parse; all25 CVRP and five
Warehouse formal/canary cases load using actual workspace/safe-root resolution;
public/formal closure and fresh-output checks pass. Eighteen whole histories
contain188 raw rows and165 safe H records; with five unchanged observations the
H index has170 entries. The exact question has13,556 characters, H source index30
entries and C17 readonly bodies. Warehouse has406 non-cache source files (plus
five pre-existing pytest cache files), H17 source entries and C9 readonly bodies.
Both contexts expose models.py read-only, not editable. No output, solver or
provider call is created. CLI help, changed-file Ruff F/E9 and diff checks pass.

Runtime and scientific inputs are now frozen at pushed base484433ea plus P15
uncommitted changes; only status/analysis docs may change from this point. Pending
bounded service health and Warehouse terminal audit before CVRP launch. Startup
alone will not establish improved research behavior or scientific benefit.

One single bounded health inference succeeds at14:20:52 Beijing (06:20:52 UTC).
Warehouse starts once at14:21:18 Beijing, PID530783. Early H requests encounter
upstream overloaded-server502 errors, including a successful bounded retry;
record eventual completion/coverage before the CVRP decision. No extra retry or
budget is added. Post-freeze inspection notes a cosmetic input-label limitation:
the new protocol/split files retain their predecessor YAML version strings and
new seed files use an unpunctuated04 prefix. Loaders and input regressions check
the effective populations/seeds/gates, not these descriptive labels. The distinct
R19 filenames, explicit invocation and seed values identify the inputs; do not
rewrite frozen inputs mid-measurement to correct labels.

## Control terminal and remaining work

Warehouse stops October5 at14:37:22 Beijing with80/80 calls used,43 explicit
upstream overloaded-server502 failures and **zero of two evaluated stages**.
Validity is `invalid_no_evaluated_outcome`, not valid negative science. Thirty-seven
calls succeed, including four completed H values and two C actions; no candidate
finishes testing/readiness or formal evaluation. The full terminal/source/retry
audit is in the linked control report. No control results are appended to CVRP.

**CVRP is not launched and its output directory does not exist.** The completed
implementation and regressions do not establish improved research or stable
algorithm gains. Service recovery and a fresh preregistered complete Warehouse
control are required before launch; do not resume the exhausted control, enlarge
its cap or execute the command above while that prerequisite is missing.

After all measurement ended, only the unexecuted CVRP protocol/seed version
labels were corrected to0.4-cvrp-r19-reliable-probes-autonomous, with an explicit label regression.
Five input tests pass again in0.61 seconds; Ruff/diff checks pass. Effective seed
values, populations, thresholds and runtime are unchanged. Executed Warehouse
inputs retain their original labels and bytes. The2659-test full run covers the
unchanged production implementation; the post-terminal change is prospective
metadata plus its assertion, not an unreported mid-run edit. No Git commit/push.

## Prospective model amendment after service diagnostics

October5 follow-up explicitly approves proceeding with gpt-6.1-sol after two
successful bounded tool probes via the existing proxy. A contemporaneous
gpt-5.6-sol probe also succeeds; neither global outage nor model-specific failure
is established. The new linked Warehouse control has a fresh root and seeds,
with the original80-call cap. Its full terminal audit must precede CVRP launch.
The original failed control, its executed inputs and all historical evidence stay
unchanged. CVRP has never dispatched, so its existing fresh output/seed ledger,
complete source, all18 histories and question remain prospective and unchanged.
Only the planned model is amended; no runtime, tool schema, gate or prompt repair.
This is not a controlled model benchmark or isolated estimate of P15's benefit.

## Prospective P16 amendment after complete Sol control

The Sol control completed valid2/2 at16:36:07 Beijing, two scientific ties and
78 calls with one recovered overload. Its terminal audit preserves repeated
import failures, omitted import-rule context and missing ordinary activation
evidence. Latest user approval authorizes shared feedback repair and a new
control before CVRP. No CVRP dispatch has occurred, so all prepared source,
18 histories, question, seeds, gates and caps remain prospective and unchanged.

P16 exposes existing effective C8 import roots through target API guidance,
optionally locates a rejected import in the submitted draft, and explains the
difference between forced wiring/entry counts and actual completed transitions.
No accepted imports, readonly edits, test requirements, scientific rules or
algorithm mechanisms change. P15 plus P16 plus model effects are not separated
causally. The completed Sol control is not evidence for this subsequently changed
runtime: the newly linked fresh control must be completed and audited first.
Neither control's outcomes nor Warehouse-specific repair recipes enter CVRP H/C.
P16 full regression2678 passed / one skip,24 input checks and source/data/context
preflight pass. The new control starts once18:26:58 Beijing, PID543472; initial
406-file equality, actual H model calls and frozen resource limits pass startup
audit. CVRP remains unlaunched until its complete terminal audit; no production
or scientific input edits/tests overlap the running control.

## October6 launch authorization and final preflight

User asks to check again and proceed now that the control should be complete.
It completed October5 at18:41:23 Beijing, valid2/2 with42 successful calls and
two valid quality ties. The October6 terminal/source/feedback/metric audit in its
linked report finds no execution/boundary blocker. Live C8 corrections and a
small real-entry probe are observed; cross-branch attribution and population
benefit remain limitations, not relabeled successes. No control result is added
to CVRP inputs.

Runtime/scientific inputs are pushed6380a59e, unchanged from that control. Fresh
entry is clean; all prior experiment carriers are dead. Twenty-four R16–R19 input
tests pass in1.75 seconds; the earlier2678-pass/one-skip full suite still applies
to unchanged runtime. Read-only preflight rechecks100 source files/48 Python
parses,25 cases, public/formal closure,18 whole history files/188 raw/165 safe
rows plus five projected observations,170 history indexes, exact13,556-character
question,30 H sources and17 readonly C sources. Ad hoc audit assertions initially
compared raw observations to normalized projections and omitted the two explicit
public H test sources; using the actual provider projection/corpus resolves both
without runtime/input changes. One bounded real tool inference succeeds on
gpt-6.1-sol high at17:29:06 Beijing October6 in3.764 seconds, with SDK retry0.

The preregistered20261005 output/session names remain unused and are retained as
design labels; actual execution will be dated October6. Source, histories, seeds,
model, gates, twelve stages,600 calls and48-hour hardwall remain unchanged. Only
status/analysis docs change; no new commit/push is requested this turn.

## Actual October6 launch and startup

The exact documented direct CLI launches once at17:31:21 Beijing, PID578803,
using the unused preregistered output/session above. No campaign, solver or test
process overlaps launch; production/source inputs still equal6380a59e. The
[startup status](/home/clawd/research/scion-experiments/v04-cvrp-r19-reliable-probes-autonomous-20261005/status.json)
records running/pending0/12 in first H research. All100 non-cache champion files
are byte-equal to the selected R12-A-fixed source. Stored resource envelope is
600 calls/two charged typed redispatches/172800 seconds, and stored C limits
equal the unchanged preregistered input.

The [first actual H trace](/home/clawd/research/scion-experiments/v04-cvrp-r19-reliable-probes-autonomous-20261005/llm_traces/20261006T093130753165_hypothesis_research_turn_4c383593.json)
succeeds at attempt0 on gpt-6.1-sol, timeout180, with read_source. Process model
and reasoning effort are gpt-6.1-sol high. Actual question exactly matches all
13,556 characters; actual170-entry history and30-entry source indexes exactly
match the normal safe provider projection, including five observations and165
safe history records. Index comparison uses the same JSON representation
(source adjacency tuples serialize as lists), not raw Python-type equality.
No runtime or input was changed during these read-only checks. This establishes
startup fidelity, not improved research correctness or retained scientific gain.
Freeze runtime/inputs and avoid tests, competing solvers and maintenance while
measurement runs; never resume the old terminal controls.
