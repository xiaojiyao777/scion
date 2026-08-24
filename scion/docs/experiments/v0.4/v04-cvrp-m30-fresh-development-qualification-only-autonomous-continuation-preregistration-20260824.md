# CVRP M30 fresh-development qualification-only autonomous continuation preregistration

Status: **PREPARED / NOT AUTHORIZED / NOT LAUNCHED**

Campaign label:
`v04-cvrp-m30-fresh-development-qualification-only-autonomous-continuation-20260824`

Future campaign root:
`/home/clawd/research/scion-experiments/v04-cvrp-m30-fresh-development-qualification-only-autonomous-continuation-20260824`

Runtime/source base:
`5d282ea8e9133e0146c47588f2310c9bd2493e50`

That commit finalizes the reviewed problem-neutral qualification auditor on
auditor carrier `2cc306e0388ebf47a2e6926c64f38c9db3dcb2d3`, itself based on the
qualification-only runtime carrier `2f424a2f1b870ce05833dd6683bfe3c9d2013820`.
Its public positive authority is the single
`audit_qualification_campaign(...)` entry point; the artifacts core is private,
and the tracked M30 expectation JSON supplies every M30-specific fact.
Preparation did not call a provider, execute a solver, create the campaign
root, rank an M31 identity or run the live command below. An early replay
inherited the legacy wide seed scan and read 18 tracked controlled synthetic
`.vrp`/`.sol` bodies, including names assigned to synthetic
validation/frozen controls. This was a real preparation-process boundary
violation and is not described as a near-miss. The final safe scanner excludes
every raw path before `git show`; an independently completed nonraw-only scan
produced the same 2,962-value union, 82 domain exclusions, five selected seeds
and exact digests, so the selection, label and salts did not change. No
external CVRPLIB corpus body or reserved heldout body was opened. The eventual
preparation commit and two independent red-team reviews are mandatory
prelaunch gates; this document itself grants no launch, retry, resume or
successor authority.

## Scientific question

Can the ordinary Scion H/C path, without a host-selected mechanism, target
file, patch, repair direction or falsifier body, use eight problem-owned
observations and 42 ordered native history records to autonomously find an
exact `modify` candidate on a development population that was outcome-unseen
when M30 was designed? Within six H/C proposal attempts, two verified candidate
chains, four formal screening stages and 60 shared provider calls, can one
candidate:

1. pass Contract, Verification and the normal-pipeline canary;
2. complete a `3 cases x 2 seeds` initial screen with `6/6` valid pairs and
   receive `expand / expand_screening`;
3. reuse the same branch, full H and complete ordered patch for a strict
   `6 cases x 4 seeds` expanded screen with `24/24` valid pairs, zero failure
   class and zero fleet regression; and
4. receive `pass / queue_validate`, stop before validation, and then pass the
   separate provider-/solver-free carrier, B0 reconstruction and complete
   path/byte audit?

The scientific result is not inferred from `queue_validate` or exit zero.
Only the complete postrun predicate below may produce
`QUALIFIED_FOR_NEW_FIXED_CANDIDATE_FUNNEL`.

## Why this is not a mechanical M28 replay

M28 used an outcome-exposed seen bank and a generic two-formal-round loop. It
spent 34/34 provider calls across four scheduled attempts, evaluated only one
initial screen and stopped valid-incomplete. M30 changes two scientific
dimensions before any new outcome exists:

- its six development cases and five development/canary seeds come from new,
  independently salted metadata-only selectors over outcome-unseen-at-start
  pools; and
- the reviewed qualification-only state machine makes proposal attempts,
  verified chains and formal stages independent hard limits. Failed verified
  chains are durably recorded and then parked/cleaned before a fresh B0 sibling
  can start.

The larger six-attempt/60-call envelope addresses the observed M28 early-fail
multi-candidate path without granting eight attempts or an unbounded search.
It does not treat M28's failure as evidence for a mechanism and does not
replay, repair or choose any prior patch.

## Ordinary research context

The tracked input is
`inputs/v04-cvrp-m30-m28-terminal-research-input.json`. Its first seven
observations are value-equal to the M28 input. The eighth is a strictly
aggregate, problem-owned M28 terminal observation:

- `stopped / execution_resource_exhausted / valid_incomplete`;
- 34 provider calls: 25 H turns, eight C research turns and one independent C
  final decision;
- four scheduled attempts, one evaluated outcome, two research-rejected
  outcomes and one resource-exhausted outcome;
- one `6/6` valid initial screen with zero failures/fleet regressions, case
  win/loss/tie `1/1/1`, median delta `0.0`, CI `[-2.5, 206.0]`,
  `fail / SCREENING_FAIL_CASE_QUALITY` and `continue_explore`;
- one later `PATCH_PROPOSAL_INVALID`, then provider-cap exhaustion before the
  final accepted H could reach C;
- 16 serial solver subprocesses and no expanded, validation, frozen,
  promotion, retention or `READY_VALIDATE` result.

The terminal counters contain two research rejections, while only one rejected
row is durable among the three ordinary M28 rows. The second rejection was an
H abstention observed through the bounded live safe-public projection; the
aggregate records that accounting caveat but does not invent a fourth history
row or claim terminal-only reconstruction.

The ordinary history order is the existing 15 files used by M28 followed by
the byte-exact tracked copy
`inputs/v04-cvrp-m30-m28-research-history.jsonl`. That copy is exactly three
newline-terminated rows and 54,790 bytes, value-equal to the preserved M28
root's ordinary `research_history.jsonl`. Thus M30 loads 16 files and 42 native
records. At the first H, the complete inventory is exactly eight observations
followed by 42 histories, or 50 entries. All 42 histories have usable H
headlines, so the first-H lexical nearest-history denominator is 42; the eight
aggregate observations have no candidate headline. Later H calls may also see
ordinary same-campaign records.

Every otherwise acceptable H still must read current source, read and cite the
candidate-specific lexical top-1 usable history ref in both basis arrays, and
state its falsification condition. The nearest-history ranker does not judge
novelty or choose a mechanism. A future provider-safe null-H row may enter the
general history inventory/read requirement, but has no hypothesis headline and
cannot enter nearest-headline ranking. No null-H sentinel patch, protocol or
decision body is written to the three public status/summary/history surfaces.

## Outcome-blind M30 population

### Case source and exclusions

The source universe is the exact union of `validation` and `frozen` from:

- `inputs/v04-cvrp-m19-fresh-development-split.yaml`;
- `inputs/v04-cvrp-m20-frontier-development-split.yaml`; and
- `inputs/v04-cvrp-m22-provider-recovery-development-split.yaml`.

Canonicalization is `strip`, backslash-to-slash, then
`PurePosixPath.as_posix()`. Every path must be relative below `cvrplib/`, have
no empty, `.` or `..` segment, and have a basename matching
`^(A|B|P|X)-n([1-9][0-9]*)-k([1-9][0-9]*)\.vrp$`. Exact canonical duplicates
fail preparation.

The universe is exactly 18 unique paths with family counts
`A=3, B=1, P=3, X=11` and time-band counts
`30/45/60/90/120 = 7/2/5/3/1`. It must be disjoint from the union of:

- every outcome-exposed `screening` field in M9, M19, M20 and M22;
- every declared M21 case, because M23 exposed the M21 reserve as its screen;
  and
- every M24/M28 case, including their preserved validation/frozen controls.

Including the shared tiny canary string, that union has 49 identities, 48 of
which are CVRPLIB paths. Overlap is a preparation failure, never a subtraction
or fallback. M23 validation/frozen/retained declarations that were never
reached may overlap the 18-case source pool; those identities remain
outcome-unseen. Therefore “fresh” means outcome-unseen at M30 start, not
globally identity-unseen or never previously declared.

### Case selector and frozen result

The exact case salt is:

`v04-cvrp-m30-fresh-development-qualification-only-autonomous-continuation-20260824|cases-v1`

Within each stratum rank by
`(sha256(utf8(salt) + NUL + utf8(canonical_path)).digest(), canonical_path)`
ascending, without resalting or fallback. Select the first two A cases with
dimension 20--100 and the first one in each of P 20--100, X 101--200,
X 201--350 and X 351--700. The resulting split order is fixed independently of
outcomes:

1. initial A rank 1: `cvrplib/A/A-n48-k7.vrp`;
2. initial P rank 1: `cvrplib/P/P-n55-k8.vrp`;
3. initial X 201--350 rank 1: `cvrplib/X/X-n204-k19.vrp`;
4. expansion A rank 2: `cvrplib/A/A-n45-k7.vrp`;
5. expansion X 101--200 rank 1: `cvrplib/X/X-n162-k11.vrp`;
6. expansion X 351--700 rank 1: `cvrplib/X/X-n685-k75.vrp`.

The exact digests and selector replay are frozen in
`scion/tests/fixtures/m30_fresh_development_qualification_only_replay.json`.
The initial case time-limit sum is `30 + 30 + 60 = 120s`; the expanded sum is
`30 + 30 + 60 + 30 + 45 + 90 = 285s`.

The case selector checked only tracked metadata and regular non-symlink
companion presence for the selected external `.vrp`/`.sol` pairs; it did not
open those bodies. The separate legacy seed-replay incident is disclosed above
and does not alter this selector statement. External M31 and M24
validation/frozen bodies remain closed.

### Seed selector and frozen result

At base `5d282ea8e9133e0146c47588f2310c9bd2493e50`, enumerate the tracked tree
with `git ls-tree -r -z --name-only`. The tree has 2,163 tracked paths. Retain
names whose casefolded path
contains `cvrp`, plus exact `scion/TASK.md`, but classify every name before any
blob read. Skip `.vrp`, `.sol` and every path with a `raw` segment. The only
readable suffix whitelist is `.csv`, `.json`, `.jsonl`, `.md`, `.py`, `.yaml`
and `.yml`; any other suffix fails closed before `git show`. The final base has
524 name-filtered paths: 18 raw-body paths skipped before read, 506 allowlisted
blobs and zero unknown suffixes. Among the allowlisted blobs, 69 JSON/YAML
files parse with zero errors and 322 files have at least one matching seed
line. For whitelisted JSON/YAML, recursively collect every non-bool integer
below any ancestor key containing `seed`; when the basename contains `seed`,
collect all non-bool integers. Additionally, from every whitelisted UTF-8 line
containing `seed` case-insensitively, collect decimal matches of
`(?<![A-Za-z0-9])([0-9]{1,9})(?![A-Za-z0-9])`. Union all values.

This produces 2,962 distinct tracked values. In closed domain
`[40000, 59999]`, 82 are excluded and 19,918 remain. Rank each remaining
integer by
`(sha256(utf8(seed_salt) + NUL + ascii_decimal(seed)).digest(), seed)`
ascending, using exact salt:

`v04-cvrp-m30-fresh-development-qualification-only-autonomous-continuation-20260824|seeds-v1`

The first four screening seeds are, in order, `54396`, `58420`, `52200` and
`45616`; the fifth is the normal-pipeline canary seed `59006`. Initial uses the
first two and expanded uses all four. There is no fallback, replacement,
resalting or use of the older 12-seed reserve as a selection pool.

### Frozen controls

All three controls have version
`0.4-cvrp-m30-fresh-development-qualification-only`:

- `inputs/v04-cvrp-m30-fresh-development-qualification-only-protocol.yaml`;
- `inputs/v04-cvrp-m30-fresh-development-qualification-only-split.yaml`;
- `inputs/v04-cvrp-m30-fresh-development-qualification-only-seeds.yaml`.

The Protocol is value-equal to M28 except `version`, the three priority cases
and canary seed. The split is value-equal except `version` and the six selected
screening paths. The seed ledger is value-equal except `version`, four
screening seeds and canary. Validation/frozen cases and seeds remain declared
value-equal to M24/M28 but qualification-only runtime may not dispatch them.

## Qualification-only state machine

The live command must explicitly pass all three independent limits; defaults
are forbidden:

- `max_proposal_attempts = 6`;
- `max_verified_candidate_chains = 2`;
- `max_formal_screening_stages = 4`.

A proposal attempt is one fresh EXPLORE H/C proposal path. An eval-only
`EXPLORE_EXPAND` stage reuses the exact branch and does not consume another
proposal attempt or call H/C. A verified chain is counted as soon as a distinct
branch passes Verification; a candidate-negative normal canary still consumes
that chain. An initial or expanded formal screening evaluation consumes one
formal-stage unit. No cap truncates a chain already dispatched.

Legal control flow is:

- preformal H/C/Contract/Verification failures consume an attempt but not a
  verified chain or formal stage;
- a verified canary-negative chain consumes one verified chain, writes its
  ordinary result, then parks;
- an initial `expand_screening` result makes only its exact branch eligible for
  the next step; no new H/C or sibling may interleave;
- after a nonqualifying verified-chain result, every ordinarily applicable
  Decision, lineage event and StepRecord is written before policy clears the
  branch workspace, patch, H and `current_code_hash`, then moves it to
  `PARKED_LINEAGE`; formal screens require their ordinary Decision, and an
  earlier candidate-negative canary likewise records `Decision.ABANDON` across
  summary, history and lineage before parking;
- a later candidate is a clean sibling of declared B0, never an ancestor-patch
  chain; and
- a positive `queue_validate` preserves its workspace and branch and stops at
  `qualification_boundary_reached` before validation dispatch.

Exhausting the six attempts, two verified chains or four formal stages at a
legal boundary yields `completed / valid / qualification_not_reached`, exit 0.
That means only “no qualifier in this bounded adaptive search.” Provider or
resource exhaustion, upstream/infra failure, hardwall, interrupt, missing or
unknown execution outcome, illegal branch/stage sequence and heldout-stage
observation remain typed incomplete terminals with nonzero exit. They are not
scientific negatives. `--rounds 4` is recorded for transparent campaign
metadata; in qualification-only mode the three explicit qualification caps,
not requested rounds, govern termination.

## Exact qualification predicate and carrier handoff

### Layer A: runtime boundary, not qualification

The ordinary terminal must be `completed / valid`, have stop reason
`qualification_boundary_reached`, qualification disposition
`ready_for_postrun_qualification_audit`, zero validation/frozen stages and
exactly one `READY_VALIDATE` branch. This state is **not** called qualified.

### Layer B: scientific screen predicate

Join `status.json`, `campaign_summary.json`, ordinary
`research_history.jsonl` and lineage in exact recorded order. Nonformal rows
and screening rows from other branches are legal. On the sole ready branch,
there must be exactly two aligned screening records with:

- identical complete H, identical complete ordered patch, identical branch id,
  identical editable hash and selected surface; these joined facts are the
  candidate-identity evidence;
- H action `modify`, at least one patch change, every change action `modify`,
  no duplicate path and no source-file creation/deletion;
- preformal Contract, Verification and normal canary success;
- initial cases exactly the first three frozen paths and seeds exactly
  `[54396, 58420]`, with total/attempted/valid `6/6/6`;
- expanded cases exactly all six frozen paths and seeds exactly
  `[54396, 58420, 52200, 45616]`, with total/attempted/valid `24/24/24`;
- zero failed, candidate-failed, champion-failed, shared-failed and
  bilateral-failed pairs, plus zero fleet regression in both stages; and
- gate/Decision progression exactly
  `expand -> expand_screening -> pass -> queue_validate`.

The sum is 30 stage-pairs, not 30 unique case-seed cells. Any incomplete
comparator, failure, alternate Decision, multiple qualifying/ready branches,
`create_new`, heldout-stage record or coverage mismatch fails qualification.
Other nonqualifying screened branches remain legal and are included in exact
durable counter and all-formal-bank accounting.

### Layer C: exact source carrier

Invoke the sole public production entry point
`scion.postrun.handoff.audit_qualification_campaign` with the tracked strict
M30 expectation JSON. It validates the terminal boundary and exact durable
accounting before reading any base blob: the terminal Layer-A gate runs before
history or SQLite access, then the auditor loads ordinary history and snapshots
the SQLite database/WAL/SHM to a private temporary directory and queries that
copy read-only without mutating the originals. It checks the exact frozen bank
and population on every summary formal row, joins each formal/expansion row's
stage, gate, Decision and candidate identity across summary, history and
lineage, accepts both legal expansion-dispatch shapes, and internally invokes
the production carrier selector. It must find exactly one
ready branch, exactly two aligned screening records for it, exact H/patch and
lineage/hash agreement, and exactly one production-hash-matching regular
non-symlink
`candidate_workspaces/candidate-*`. Other non-ready branches and nonmatching
historical workspace directories are allowed; missing, duplicate or mismatched
ready evidence fails closed. Neither the public API nor its CLI returns H,
patch bodies, branch ids or paths; it emits only a fixed success/unavailable
token and does not judge scientific quality.

Then mechanically materialize the exact 99 tracked regular ordinary files
under `scion/scion/problems/cvrp` from base
`5d282ea8e9133e0146c47588f2310c9bd2493e50`. Apply the sole canonical ordered
`modify` patch from the two screen records to scratch B0. Using the fixed-funnel
source projection, require full path-set and byte equality among rebuilt B0 and
the selected durable candidate. Require the actual changed-file list to be
nonempty and exactly equal to patch paths. Reject symlinks, nonregular entries,
path escape, duplicates, source creation/deletion or any byte mismatch.
Finally recompute the editable-source digest and compare it to the ready
branch's `current_code_hash` as a consistency check only; complete path/byte
equality is source authority.

This terminal-only source audit has one narrow opaque-byte exception to the
prelaunch raw-read prohibition: the complete 99-file tracked package includes
18 controlled synthetic `.vrp`/`.sol` files, so Layer C copies and compares
their bytes without parsing, printing, interpreting or exposing them to H/C.
That operation is permitted only after the positive runtime boundary and only
inside the exact base/candidate package comparison. It is not case, solver,
validation, frozen or algorithm evidence. The prelaunch seed-selector replay
continues to reject every `.vrp`, `.sol` and `raw` path before any blob read,
and all current preparation tests use a synthetic repository rather than the
real 99-file base.

Only Layers A, B and C together produce
`QUALIFIED_FOR_NEW_FIXED_CANDIDATE_FUNNEL`. Any missing/multiple/mismatch produces
`QUALIFICATION_CARRIER_UNAVAILABLE`; the M30 root remains ordinary development
evidence, and no person may choose a branch, repair/reapply a patch, substitute
a workspace or materialize M31. A later, separately authorized M31 prep may
copy only the exact 99-file B0 and qualified candidate projections to external
read-only bundles, verify full equality again, and derive every changed-file
and selected-surface argument mechanically.

The M30 replay makes this predicate executable without a provider, solver or
real raw body. It constructs an isolated synthetic Git repository, synthetic
campaign root, SQLite lineage database and 99-regular-file B0/candidate pair,
then calls the same sole public campaign API used for a future real terminal.
Its two positive shapes cover a nonqualifying other-branch formal screen and a
candidate-negative canary with `Decision.ABANDON`; both include a null-H
preformal row and one nonmatching historical workspace. M30-specific mutants
cover `create_new`, wrong bank, heldout-stage accounting and multiple ready
branches. The public auditor additionally enforces the closed three-state
terminal grammar and branch-hash shape, the closed preformal outcome taxonomy,
one-to-one Step/history/lineage accounting, and ordered-deduplicated
Decision/Protocol reason authority; hidden candidate evidence or a second
qualifying chain fails closed. The final generic auditor suite collects 136 tests; the
auditor/carrier combined gate is 149 tests and the exact generic postcommit
gate is 181 tests including qualification-only runtime coverage. Those tests
also cover durable counters, all
formal-bank rows, both expansion shapes, source policy, opaque byte equality,
canonical Git authority and stable private-copy SQLite/WAL/SHM reads. This
synthetic replay tests audit logic but is not M30 algorithm evidence and does
not replace the future audit on the actual terminal.

## Conditional M31 rule, not a materialized experiment

The conditional label is
`v04-cvrp-m31-fixed-candidate-full-funnel-20260824`. Its independent salts are:

- case: `v04-cvrp-m31-fixed-candidate-full-funnel-20260824|cases-v1`;
- seed: `v04-cvrp-m31-fixed-candidate-full-funnel-20260824|seeds-v1`.

No M31 case or seed was hashed, ranked, printed or written during M30
preparation. Only feasibility counts and a candidate-independent rule are
frozen. If M30 fails any qualification layer, this rule expires.

After removing the six M30 cases from the 18-case source universe, exact
stratum counts are:

`A20-100=1, B20-100=1, P10-19=1, P20-100=1, X101-200=1,
X201-350=4, X351-700=2, X701-1001=1`.

If separately authorized after M30 qualification, rank within strata by the
same canonical case tuple with the independent M31 salt. Select one screening
case in order from A20--100, B20--100, P20--100, X101--200, X201--350 and
X351--700. Only after conceptually removing those six, select retained cases
in order from P10--19, X201--350 and X351--700. Count-only feasibility leaves
three unused cases. The P retained stratum is **P10--19**, not P101--200.

For seeds, use the same final-base scan and independent closed domain
`[60000, 79999]`. Exactly 84 tracked values are excluded and 19,916 remain,
enough for seven, but no rank was computed. On later materialization only, the
first four would be screening, the next two retained and the seventh strict
canary. M24 validation/frozen cases and seeds remain the fixed heldout stages.

The future fixed-candidate driver remains tracked
`scion/run_fixed_candidate_funnel.py`, with provider/H/C/patch generation,
Contract and Verification all zero. Its conditional maximum is 86 serial
solver subprocesses: strict canary 2, screening 48, validation 12, frozen 12
and retained 12. With the correct P10--19 30-second band, retained nominal is
`2*2*(30+60+90)=720s`; total nominal is `4820s`, communicate-guarded accounting
is `6110s`, and adding `86*(5+1)` possible kill/drain seconds gives `6626s`,
leaving `1374s` below an `8000s` hardwall. These are conditional rule facts,
not current authority or evidence.

## M30 resource envelope

The unchanged M11 research limits allow at most eight H turns, eight C
research turns, one independent C final decision and bounded public
development actions per attempt. Provider SDK retry is zero. An H that reaches
C can preemptively satisfy source/history/nearest requirements in three turns;
one C session uses at most eight research turns plus one final decision. Under
six sessions and a shared 60-call cap, the weighted provider-timeout maximum is
at five C sessions: `C=45, H=15`, so
`45*240 + 15*120 = 12600s`. Six C sessions force `C<=42, H>=18` and are lower.

The complete conservative accounting is:

- provider calls `<=60`, weighted provider timeouts `<=12600s`;
- public development work `<=6*90=540s`;
- Verification pytest work `<=6*120=720s`;
- Verification solver subprocesses `<=6*2=12`;
- normal canary subprocesses `<=4*2=8` because every initial or expanded
  formal dispatch reruns the normal-pipeline canary;
- formal subprocesses `<=2*(12+48)=120`;
- total serial solver subprocesses `<=140`;
- per chain formal nominal `480 + 2280 = 2760s`;
- total solver nominal `2*2760 + 12*30 + 8*10 = 5960s`;
- adding the runner's 15-second pre-kill communicate guard for each dispatch
  gives `5960 + 140*15 = 8060s`. This is dispatch accounting, not a strict
  elapsed bound;
- adding a possible five-second post-timeout kill wait and one-second output
  drain per subprocess gives `8060 + 140*6 = 8900s`;
- all known conservative work is
  `12600 + 540 + 720 + 8900 = 22760s`; and
- outer hardwall is `28000s`, leaving `5240s`; solver concurrency is one.

Component maxima deliberately need not co-occur. The outer hardwall is process
safety, not permission to add attempts, calls, chains, stages or retries.

## Three-layer claim boundary

1. **Framework.** Durable proposal/chain/stage counters, typed terminals,
   nearest-history enforcement, clean-sibling parking and exact postrun joins
   support only bounded framework/auditability claims.
2. **Research direction.** H reads/citations, C alignment, optional public
   probes and non-replay observations are descriptive. They do not establish a
   causal improvement in research quality, mechanism choice or falsifier use.
3. **Algorithm.** Complete paired initial/expanded results support only the
   exact candidate-versus-B0 claim on this preselected fresh-at-start but
   within-campaign adaptive development bank. Candidate discovery depends on
   M7--M28 ordinary history, and later M30 candidates may see earlier M30 bank
   outcomes.

No M30 result is independent discovery, globally case-unseen evidence,
mechanism causality, validation, frozen success, promotion, retained
improvement, production readiness, global CVRP generalization or v0.4
completion. A positive result only unlocks separately reviewed M31 prep.

## Prelaunch gates

Before any authorization, all of the following must hold:

- exact runtime/source base `5d282ea8e9133e0146c47588f2310c9bd2493e50`,
  with no production-source difference in the eventual prep commit and exact
  parentage from that base;
- the tracked strict expectation JSON loads through the production duplicate-
  key-free schema and names that exact base, source package, caps, banks,
  decisions, zero metrics and heldout prohibitions;
- the final prep is one committed, clean tracked tree and both independent
  science/privacy and runtime/resource red teams report no P0/P1;
- the M30 root is absent, M28 root is preserved, and the tracked M30 history
  copy is byte-equal to M28 ordinary history with exactly 3 lines/54,790 bytes;
- all controls load through production config types and replay tests reproduce
  the exact selector digests, 8+42 context, caps, resource arithmetic, source
  count and M31 count-only feasibility;
- selected M30 development case/solution companions and required runtime tools
  pass the separately reviewed preflight, while validation/frozen/M31 bodies
  remain unopened before their authorized stage; and
- no concurrent Scion/candidate process exists, the provider model metadata is
  checked only after authorization, and the campaign command below is run at
  most once.

Provider-/solver-free preparation validation is:

```bash
cd /home/clawd/research/or-autoresearch-agent
(
cd /
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/dev/null \
  PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion \
  /home/clawd/miniconda3/envs/claw/bin/python -B -m pytest -q \
  -p no:cacheprovider \
  /home/clawd/research/or-autoresearch-agent/scion/scion/tests/unit/core/test_m30_fresh_development_qualification_only_replay.py \
  /home/clawd/research/or-autoresearch-agent/scion/scion/tests/unit/core/test_qualification_only_campaign.py \
  /home/clawd/research/or-autoresearch-agent/scion/scion/tests/unit/test_candidate_carrier.py \
  /home/clawd/research/or-autoresearch-agent/scion/scion/tests/unit/test_qualification_audit.py
)
git diff --check
```

These tests may inspect tracked metadata and ordinary public artifacts. They
must not call the provider, invoke a solver, open validation/frozen/M31 raw
bodies or create the campaign root.

## Frozen one-shot command

The authorization record must supply the exact reviewed 40-hex preparation
commit as `AUTHORIZED_M30_PREP_SHA`. It is not inferred from whatever happens
to be checked out. The exact future shell below validates that commit and all
input/runtime boundaries before any proxy request. No default may substitute
for the three qualification limits. Its outer shell performs only the required
authorization-value expansion before absolute `/usr/bin/env -i` starts
`/bin/bash --noprofile --norc`; inherited `GIT_*`, exported shell functions,
aliases and startup-file configuration therefore cannot enter the authority
body. Every process/Git producer is checked explicitly; ignored importables
outside `__pycache__` fail closed, while `PYTHONPYCACHEPREFIX=/dev/null` keeps
legacy local cache files outside import authority:

```bash
AUTHORIZED_M30_PREP_SHA="${AUTHORIZED_M30_PREP_SHA:?authorization must name exact reviewed prep commit}"
/usr/bin/env -i \
  HOME=/home/clawd \
  PATH=/home/clawd/miniconda3/envs/claw/bin:/usr/bin:/bin \
  LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  AUTHORIZED_M30_PREP_SHA="$AUTHORIZED_M30_PREP_SHA" \
  /bin/bash --noprofile --norc <<'M30_LAUNCH'
set -euo pipefail
PATH=/home/clawd/miniconda3/envs/claw/bin:/usr/bin:/bin
export PATH
GIT_NO_REPLACE_OBJECTS=1
export GIT_NO_REPLACE_OBJECTS
PYTHONPYCACHEPREFIX=/dev/null
export PYTHONPYCACHEPREFIX
for tool in git env id bwrap prlimit curl jq pgrep timeout ps; do
  test "$(type -P "$tool")" = "/usr/bin/$tool"
done
test "$(type -P python)" = /home/clawd/miniconda3/envs/claw/bin/python

REPO=/home/clawd/research/or-autoresearch-agent
B30=5d282ea8e9133e0146c47588f2310c9bd2493e50
AUTHORIZED_M30_PREP_SHA="${AUTHORIZED_M30_PREP_SHA:?authorization must name exact reviewed prep commit}"
M30_CAMPAIGN_DIR=/home/clawd/research/scion-experiments/v04-cvrp-m30-fresh-development-qualification-only-autonomous-continuation-20260824
M30_LABEL=v04-cvrp-m30-fresh-development-qualification-only-autonomous-continuation-20260824
M28_HISTORY=/home/clawd/research/scion-experiments/v04-cvrp-m28-seen-bank-qualification-autonomous-continuation-20260824/research_history.jsonl
M30_EXPECTATIONS="$REPO/scion/docs/experiments/v0.4/inputs/v04-cvrp-m30-fresh-development-qualification-only-qualification-expectation.json"

cd "$REPO"
[[ "$AUTHORIZED_M30_PREP_SHA" =~ ^[0-9a-f]{40}$ ]]

m30_process_zero() {
  (
  cd /
  M30_LABEL="$M30_LABEL" \
    /home/clawd/miniconda3/envs/claw/bin/python -S -B <<'PY'
import os
import re
import subprocess

try:
    completed = subprocess.run(
        ["/usr/bin/ps", "-eo", "comm=,args="],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
except (OSError, subprocess.CalledProcessError):
    raise SystemExit(1) from None

label = os.environ["M30_LABEL"]
python_like_patterns = (
    r"-m\s+scion[.]cli[.]main\s+run(?:\s|$)",
    r"run_.*candidate.*[.]py",
    r"run_cvrp_controlled_e2e[.]py",
    r"(?:^|\s)\S*/solver[.]py(?:\s|$)",
    re.escape(label),
)
for line in completed.stdout.splitlines():
    fields = line.split(maxsplit=1)
    if not fields:
        continue
    command = fields[0]
    argv = fields[1].split() if len(fields) == 2 else []
    if command == "scion" and len(argv) >= 2 and argv[1] == "run":
        raise SystemExit(1)
    if (
        command.startswith("python") or command in {"bwrap", "prlimit"}
    ) and any(re.search(pattern, line) for pattern in python_like_patterns):
        raise SystemExit(1)
PY
  )
}

m30_untracked_gate() {
  (
  cd /
  REPO="$REPO" /home/clawd/miniconda3/envs/claw/bin/python -S -B <<'PY'
import os
import subprocess
from pathlib import Path

repository = Path(os.environ["REPO"])
def git_paths(*flags: str) -> tuple[bytes, ...]:
    try:
        completed = subprocess.run(
            ["/usr/bin/git", "ls-files", "-z", *flags, "--", "scion"],
            cwd=repository,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError):
        raise SystemExit(1) from None
    return tuple(path for path in completed.stdout.split(b"\0") if path)

allowed_file = b"scion/docs/engineering/module-debt/v04-large-file-modularization-plan-20260629.md"
allowed_prefix = b"scion/docs/planning/v0.5/"
for path in git_paths("--others", "--exclude-standard"):
    if path == allowed_file or path.startswith(allowed_prefix):
        continue
    raise SystemExit(1)
for path in git_paths("--others", "--ignored", "--exclude-standard"):
    lower = path.lower()
    if b"__pycache__" in lower.split(b"/"):
        continue
    if lower.endswith((b".py", b".pyc", b".pyo", b".so", b".pth")):
        raise SystemExit(1)
PY
  )
}

m30_tree_gate() {
  test "$(git rev-parse --verify HEAD^{commit})" = "$AUTHORIZED_M30_PREP_SHA"
  read -r -a commit_line <<<"$(git rev-list --parents -n 1 HEAD)"
  test "${#commit_line[@]}" -eq 2
  test "${commit_line[1]}" = "$B30"
  git diff --quiet
  git diff --cached --quiet
  test ! -e "$M30_CAMPAIGN_DIR" && test ! -L "$M30_CAMPAIGN_DIR"
  m30_untracked_gate
  m30_process_zero
}

m30_tree_gate

(
cd /
env -i \
  HOME=/home/clawd PATH=/home/clawd/miniconda3/envs/claw/bin:/usr/bin:/bin \
  LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPYCACHEPREFIX=/dev/null \
  GIT_NO_REPLACE_OBJECTS=1 \
  PYTHONPATH="$REPO/scion:/home/clawd/.local/lib/python3.12/site-packages:/home/clawd/miniconda3/envs/claw/lib/python3.12/site-packages" \
  REPO="$REPO" B30="$B30" M28_HISTORY="$M28_HISTORY" \
  /home/clawd/miniconda3/envs/claw/bin/python -S -B <<'PY'
from dataclasses import asdict
import importlib
import inspect
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

from scion.cli.commands.init_run import _load_research_input
from scion.config.problem import ProblemSpec, ProtocolConfig, SeedLedgerConfig, SplitManifest
from scion.core.code_research_limits import load_code_research_limits
from scion.core.qualification import QualificationOnlyConfig
from scion.core.research_history import load_research_histories
from scion.core.resource_envelope import ResourceEnvelope
from scion.problem.bridge import bridge_problem_spec_v1, load_problem_spec_v1_from_yaml
from scion.problem.loader import load_problem_adapter
from scion.postrun.handoff import load_qualification_audit_expectation
import scion

repo = Path(os.environ["REPO"])
base = os.environ["B30"]
assert sys.pycache_prefix == "/dev/null"
head = subprocess.check_output(
    ["git", "rev-parse", "HEAD"], cwd=repo, text=True
).strip()
expected_files = {
    "scion/TASK.md",
    "scion/docs/experiments/v0.4/README.md",
    "scion/docs/status/current-state.md",
    "scion/docs/experiments/v0.4/inputs/v04-cvrp-m30-fresh-development-qualification-only-protocol.yaml",
    "scion/docs/experiments/v0.4/inputs/v04-cvrp-m30-fresh-development-qualification-only-qualification-expectation.json",
    "scion/docs/experiments/v0.4/inputs/v04-cvrp-m30-fresh-development-qualification-only-seeds.yaml",
    "scion/docs/experiments/v0.4/inputs/v04-cvrp-m30-fresh-development-qualification-only-split.yaml",
    "scion/docs/experiments/v0.4/inputs/v04-cvrp-m30-m28-research-history.jsonl",
    "scion/docs/experiments/v0.4/inputs/v04-cvrp-m30-m28-terminal-research-input.json",
    "scion/docs/experiments/v0.4/v04-cvrp-m30-fresh-development-qualification-only-autonomous-continuation-preregistration-20260824.md",
    "scion/scion/tests/fixtures/m30_fresh_development_qualification_only_replay.json",
    "scion/scion/tests/unit/core/test_m30_fresh_development_qualification_only_replay.py",
}
changed = set(
    subprocess.check_output(
        ["git", "diff", "--name-only", f"{base}..{head}"], cwd=repo, text=True
    ).splitlines()
)
assert changed == expected_files
assert all(
    not path.startswith("scion/scion/") or path.startswith("scion/scion/tests/")
    for path in changed
)
tracked = set(
    subprocess.check_output(["git", "ls-files"], cwd=repo, text=True).splitlines()
)
assert expected_files <= tracked

package = (repo / "scion/scion").resolve()
assert [Path(path).resolve() for path in scion.__path__] == [package]
resolved_sys_path = [Path(path or os.getcwd()).resolve() for path in sys.path]
assert repo.resolve() not in resolved_sys_path
assert package.parent in resolved_sys_path
for name in (
    "scion.cli.main",
    "scion.cli.commands.init_run",
    "scion.config.problem",
    "scion.config.protocol_config",
    "scion.core.campaign",
    "scion.core.campaign_loop",
    "scion.core.explore_step.pipeline",
    "scion.core.qualification",
    "scion.core.research_history",
    "scion.core.resource_envelope",
    "scion.problem.bridge",
    "scion.problem.loader",
    "scion.postrun.handoff.qualification_audit",
    "scion.problems.cvrp.adapter",
    "scion.runtime.runner",
):
    origin = Path(inspect.getfile(importlib.import_module(name))).resolve()
    assert origin.is_relative_to(package), (name, origin)

inputs = repo / "scion/docs/experiments/v0.4/inputs"
m28_input = _load_research_input(inputs / "v04-cvrp-m28-m27-terminal-research-input.json")
m30_input = _load_research_input(inputs / "v04-cvrp-m30-m28-terminal-research-input.json")
assert m30_input["observations"][:7] == m28_input["observations"]
assert len(m30_input["observations"]) == 8

m30_history = inputs / "v04-cvrp-m30-m28-research-history.jsonl"
m28_history = Path(os.environ["M28_HISTORY"])
assert m28_history.is_file() and not m28_history.is_symlink()
history_bytes = m30_history.read_bytes()
assert history_bytes == m28_history.read_bytes()
assert history_bytes.count(b"\n") == 3 and len(history_bytes) == 54790
history_names = (
    "v04-cvrp-m10-m9-research-history.jsonl",
    "v04-cvrp-m11-m10-research-history.jsonl",
    "v04-cvrp-m12-m11-research-history.jsonl",
    "v04-cvrp-m13-m12-research-history.jsonl",
    "v04-cvrp-m14-m13-research-history.jsonl",
    "v04-cvrp-m15-m14-research-history.jsonl",
    "v04-cvrp-m16-m15-research-history.jsonl",
    "v04-cvrp-m19-m16-research-history.jsonl",
    "v04-cvrp-m20-m19-research-history.jsonl",
    "v04-cvrp-m21-m20-research-history.jsonl",
    "v04-cvrp-m22-m21-research-history.jsonl",
    "v04-cvrp-m24-m22-research-history.jsonl",
    "v04-cvrp-m26-m25-research-history.jsonl",
    "v04-cvrp-m27-m26-research-history.jsonl",
    "v04-cvrp-m28-m27-research-history.jsonl",
    "v04-cvrp-m30-m28-research-history.jsonl",
)
history = load_research_histories(
    tuple(inputs / name for name in history_names), expected_problem_id="cvrp"
)
assert len(history_names) == 16 and len(history) == 42

problem = ProblemSpec.from_yaml(str(repo / "scion/scion/problems/cvrp/problem.yaml"))
problem_v1 = load_problem_spec_v1_from_yaml(
    repo / "scion/scion/problems/cvrp/problem-v1.yaml"
)
bridge = bridge_problem_spec_v1(problem_v1)
adapter = load_problem_adapter(problem_v1)
protocol = ProtocolConfig.from_yaml(inputs / "v04-cvrp-m30-fresh-development-qualification-only-protocol.yaml")
split = SplitManifest.from_yaml(inputs / "v04-cvrp-m30-fresh-development-qualification-only-split.yaml")
seeds = SeedLedgerConfig.from_yaml(inputs / "v04-cvrp-m30-fresh-development-qualification-only-seeds.yaml")
limits = load_code_research_limits(inputs / "v04-cvrp-m11-code-research-limits.json")
envelope = ResourceEnvelope(provider_call_cap=60, outer_hardwall_sec=28000)
qualification = QualificationOnlyConfig(
    max_proposal_attempts=6,
    max_verified_candidate_chains=2,
    max_formal_screening_stages=4,
)
expectation = load_qualification_audit_expectation(
    inputs / "v04-cvrp-m30-fresh-development-qualification-only-qualification-expectation.json"
)
fixture = json.loads(
    (repo / "scion/scion/tests/fixtures/m30_fresh_development_qualification_only_replay.json").read_text()
)
case_ids = fixture["case_selection"]["split_order"]
seed_ids = [item["seed"] for item in fixture["seed_selection"]["selected"]]
assert problem.name == "cvrp"
assert problem_v1.id == bridge.problem_spec.name == "cvrp"
assert adapter.__class__.__module__ == "scion.problems.cvrp.adapter"
assert bridge.problem_spec.search_space.editable == [
    "policies/baseline_algorithm.py",
    "policies/baseline_modules/*.py",
]
assert protocol.version == split.version == seeds.version == "0.4-cvrp-m30-fresh-development-qualification-only"
assert split.screening == case_ids
assert tuple(split.screening[:3]) == protocol.screening.priority_case_ids
assert seeds.screening == seed_ids[:4]
assert protocol.screening.n_cases_modify == 3
assert protocol.screening.n_seeds == 2
assert protocol.screening.expand_to_modify == 6
assert protocol.screening.expand_n_seeds == 4
assert protocol.screening.require_expanded_for_pass is True
assert split.canary == protocol.canary.cases == ["data/tiny_canary.json"]
assert seeds.canary == protocol.canary.seeds == seed_ids[4:] == [59006]
assert split.validation == [
    "cvrplib/P/P-n55-k7.vrp",
    "cvrplib/X/X-n308-k13.vrp",
    "cvrplib/X/X-n548-k50.vrp",
]
assert split.frozen == [
    "cvrplib/X/X-n275-k28.vrp",
    "cvrplib/X/X-n480-k70.vrp",
    "cvrplib/X/X-n876-k59.vrp",
]
assert seeds.validation == [5405, 4354]
assert seeds.frozen == [2959, 6748]
assert [
    protocol.runtime.time_limits.resolve(
        stage="screening", case_path=case, fallback_time_limit_sec=30
    )
    for case in split.screening
] == [30, 30, 60, 30, 45, 90]
assert qualification.to_projection() == expectation.limits == {
    "max_proposal_attempts": 6,
    "max_verified_candidate_chains": 2,
    "max_formal_screening_stages": 4,
}
assert envelope.to_primitive() == {
    "provider_call_cap": 60,
    "outer_hardwall_sec": 28000,
}
assert expectation.base_revision == base
assert expectation.source_prefix == "scion/scion/problems/cvrp"
assert expectation.source_file_count == 99
assert len(expectation.screening[0].case_ids) == 3
assert len(expectation.screening[0].seed_set) == 2
assert len(expectation.screening[1].case_ids) == 6
assert len(expectation.screening[1].seed_set) == 4
assert asdict(limits) == json.loads(
    (inputs / "v04-cvrp-m11-code-research-limits.json").read_text()
)

# Metadata-only: lstat the six selected development cases and companions.
for relative in (
    "cvrplib/A/A-n48-k7.vrp",
    "cvrplib/P/P-n55-k8.vrp",
    "cvrplib/X/X-n204-k19.vrp",
    "cvrplib/A/A-n45-k7.vrp",
    "cvrplib/X/X-n162-k11.vrp",
    "cvrplib/X/X-n685-k75.vrp",
):
    case = repo / "vrp" / relative
    for path in (case, case.with_suffix(".sol")):
        mode = path.lstat().st_mode
        assert stat.S_ISREG(mode) and not stat.S_ISLNK(mode)
PY
)

(
cd /
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/dev/null \
  PYTHONPATH="$REPO/scion" \
  /home/clawd/miniconda3/envs/claw/bin/python -B -m pytest -q \
  -p no:cacheprovider \
  "$REPO/scion/scion/tests/unit/core/test_m30_fresh_development_qualification_only_replay.py" \
  "$REPO/scion/scion/tests/unit/core/test_qualification_only_campaign.py" \
  "$REPO/scion/scion/tests/unit/test_candidate_carrier.py" \
  "$REPO/scion/scion/tests/unit/test_qualification_audit.py"
)
git diff --check
m30_tree_gate

PROXY_KEY_VALUE="$(curl -fsS --connect-timeout 5 --max-time 15 \
  http://127.0.0.1:8080/auth/status | \
  jq -er '.proxy_api_key | select(type == "string" and length > 0)')"
trap 'unset PROXY_KEY_VALUE' EXIT
curl -fsS --connect-timeout 5 --max-time 15 \
  -H "Authorization: Bearer $PROXY_KEY_VALUE" \
  http://127.0.0.1:8080/v1/models | \
  jq -e --arg model gpt-5.6-terra \
    'any(.data[]?; .id == $model)' >/dev/null

m30_tree_gate
set +e
(
cd /
env -i \
  HOME=/home/clawd \
  PATH=/home/clawd/miniconda3/envs/claw/bin:/usr/bin:/bin \
  LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/dev/null \
  PYTHONUNBUFFERED=1 PYTHONHASHSEED=0 \
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
  --research-input /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m30-m28-terminal-research-input.json \
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
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m26-m25-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m27-m26-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m28-m27-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m30-m28-research-history.jsonl \
  --code-research-limits /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m11-code-research-limits.json \
  --protocol /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m30-fresh-development-qualification-only-protocol.yaml \
  --split /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m30-fresh-development-qualification-only-split.yaml \
  --seeds /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m30-fresh-development-qualification-only-seeds.yaml \
  --time-limit-sec 30 \
  --qualification-only \
  --max-proposal-attempts 6 \
  --max-verified-candidate-chains 2 \
  --max-formal-screening-stages 4 \
  --provider-call-cap 60 \
  --outer-hardwall-sec 28000 \
  --rounds 4 \
  --campaign-dir "$M30_CAMPAIGN_DIR"
)
M30_EXIT=$?
set -e
case "$M30_EXIT" in
  0|20|21|22|124) ;;
  *) echo "unexpected M30 exit: $M30_EXIT" >&2; exit "$M30_EXIT" ;;
esac
exit "$M30_EXIT"
M30_LAUNCH
```

`PROXY_KEY_VALUE` is an ephemeral post-authorization shell value and is never
written to an artifact. Exact exit meanings are: `0` for either the positive
qualification boundary or a completed valid bounded negative, `20` for
infrastructure failure, `21` for resource exhaustion, `22` for an incomplete
qualification terminal and `124` for the outer hardwall. Exit zero alone is
never qualification. This command is not run during preparation. It has no
automatic retry, resume, replacement root, validation/frozen tail, M31
materialization, distribution, deployment, Trust/Hash or v0.4 completion
authority.

## Frozen postrun qualification command

After the one-shot process is fully terminal, the only command permitted to
name a qualified carrier is this provider-/solver-free read-only audit. A
negative/incomplete root fails before source materialization. A positive Layer
A boundary permits the narrow opaque 99-file comparison described above. The
same authorization record must supply the exact reviewed preparation commit;
the wrapper uses the same clean-shell bootstrap, then rechecks that commit, its
sole B30 parent, the clean/scoped-untracked tree, terminal process/root boundary,
strict-expectation bytes and auditor module origins both before and after the
public audit. Its success stdout is withheld until those post-audit checks also
pass:

```bash
AUTHORIZED_M30_PREP_SHA="${AUTHORIZED_M30_PREP_SHA:?authorization must name exact reviewed prep commit}"
/usr/bin/env -i \
  HOME=/home/clawd \
  PATH=/home/clawd/miniconda3/envs/claw/bin:/usr/bin:/bin \
  LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  AUTHORIZED_M30_PREP_SHA="$AUTHORIZED_M30_PREP_SHA" \
  /bin/bash --noprofile --norc <<'M30_POSTRUN'
set -euo pipefail
PATH=/home/clawd/miniconda3/envs/claw/bin:/usr/bin:/bin
export PATH
GIT_NO_REPLACE_OBJECTS=1
export GIT_NO_REPLACE_OBJECTS
PYTHONPYCACHEPREFIX=/dev/null
export PYTHONPYCACHEPREFIX
for tool in git env ps; do
  test "$(type -P "$tool")" = "/usr/bin/$tool"
done
test "$(type -P python)" = /home/clawd/miniconda3/envs/claw/bin/python

REPO=/home/clawd/research/or-autoresearch-agent
B30=5d282ea8e9133e0146c47588f2310c9bd2493e50
AUTHORIZED_M30_PREP_SHA="${AUTHORIZED_M30_PREP_SHA:?authorization must name exact reviewed prep commit}"
M30_CAMPAIGN_DIR=/home/clawd/research/scion-experiments/v04-cvrp-m30-fresh-development-qualification-only-autonomous-continuation-20260824
M30_LABEL=v04-cvrp-m30-fresh-development-qualification-only-autonomous-continuation-20260824
M30_EXPECTATIONS="$REPO/scion/docs/experiments/v0.4/inputs/v04-cvrp-m30-fresh-development-qualification-only-qualification-expectation.json"
M30_EXPECTATIONS_SHA256=4141167ecd1dfca46299940716f4e81ccaba26682240fd7e991a08615662ed57

cd "$REPO"
[[ "$AUTHORIZED_M30_PREP_SHA" =~ ^[0-9a-f]{40}$ ]]

m30_postrun_process_zero() {
  (
  cd /
  M30_LABEL="$M30_LABEL" \
    /home/clawd/miniconda3/envs/claw/bin/python -S -B <<'PY'
import os
import re
import subprocess

try:
    completed = subprocess.run(
        ["/usr/bin/ps", "-eo", "comm=,args="],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
except (OSError, subprocess.CalledProcessError):
    raise SystemExit(1) from None

label = os.environ["M30_LABEL"]
python_like_patterns = (
    r"-m\s+scion[.]cli[.]main\s+run(?:\s|$)",
    r"run_.*candidate.*[.]py",
    r"run_cvrp_controlled_e2e[.]py",
    r"(?:^|\s)\S*/solver[.]py(?:\s|$)",
    r"audit-qualification-campaign",
    re.escape(label),
)
for line in completed.stdout.splitlines():
    fields = line.split(maxsplit=1)
    if not fields:
        continue
    command = fields[0]
    argv = fields[1].split() if len(fields) == 2 else []
    if (
        command == "scion"
        and len(argv) >= 2
        and argv[1] in {"run", "audit-qualification-campaign"}
    ):
        raise SystemExit(1)
    if (
        command.startswith("python") or command in {"bwrap", "prlimit"}
    ) and any(re.search(pattern, line) for pattern in python_like_patterns):
        raise SystemExit(1)
PY
  )
}

m30_postrun_untracked_gate() {
  (
  cd /
  REPO="$REPO" /home/clawd/miniconda3/envs/claw/bin/python -S -B <<'PY'
import os
import subprocess
from pathlib import Path

repository = Path(os.environ["REPO"])
def git_paths(*flags: str) -> tuple[bytes, ...]:
    try:
        completed = subprocess.run(
            ["/usr/bin/git", "ls-files", "-z", *flags, "--", "scion"],
            cwd=repository,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError):
        raise SystemExit(1) from None
    return tuple(path for path in completed.stdout.split(b"\0") if path)

allowed_file = b"scion/docs/engineering/module-debt/v04-large-file-modularization-plan-20260629.md"
allowed_prefix = b"scion/docs/planning/v0.5/"
for path in git_paths("--others", "--exclude-standard"):
    if path == allowed_file or path.startswith(allowed_prefix):
        continue
    raise SystemExit(1)
for path in git_paths("--others", "--ignored", "--exclude-standard"):
    lower = path.lower()
    if b"__pycache__" in lower.split(b"/"):
        continue
    if lower.endswith((b".py", b".pyc", b".pyo", b".so", b".pth")):
        raise SystemExit(1)
PY
  )
}

m30_postrun_tree_gate() {
  test "$(git rev-parse --verify HEAD^{commit})" = "$AUTHORIZED_M30_PREP_SHA"
  read -r -a commit_line <<<"$(git rev-list --parents -n 1 HEAD)"
  test "${#commit_line[@]}" -eq 2
  test "${commit_line[1]}" = "$B30"
  git diff --quiet
  git diff --cached --quiet
  test -d "$M30_CAMPAIGN_DIR" && test ! -L "$M30_CAMPAIGN_DIR"
  m30_postrun_untracked_gate
  m30_postrun_process_zero
}

m30_postrun_origin_gate() {
  (
  cd /
  env -i \
    HOME=/home/clawd PATH=/home/clawd/miniconda3/envs/claw/bin:/usr/bin:/bin \
    LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPYCACHEPREFIX=/dev/null \
    GIT_NO_REPLACE_OBJECTS=1 \
    PYTHONPATH="$REPO/scion:/home/clawd/.local/lib/python3.12/site-packages:/home/clawd/miniconda3/envs/claw/lib/python3.12/site-packages" \
    REPO="$REPO" M30_EXPECTATIONS="$M30_EXPECTATIONS" \
    M30_EXPECTATIONS_SHA256="$M30_EXPECTATIONS_SHA256" \
    /home/clawd/miniconda3/envs/claw/bin/python -S -B <<'PY'
import hashlib
import importlib
import inspect
import os
import sys
from pathlib import Path

import scion

repo = Path(os.environ["REPO"])
assert sys.pycache_prefix == "/dev/null"
package = (repo / "scion/scion").resolve()
assert [Path(path).resolve() for path in scion.__path__] == [package]
resolved_sys_path = [Path(path or os.getcwd()).resolve() for path in sys.path]
assert repo.resolve() not in resolved_sys_path
assert package.parent in resolved_sys_path
for name in (
    "scion.cli.main",
    "scion.cli.commands.qualification_audit",
    "scion.config.problem",
    "scion.core.execution_outcome",
    "scion.core.models",
    "scion.core.path_match",
    "scion.core.paths",
    "scion.core.research_history",
    "scion.core.research_surface_index",
    "scion.postrun.handoff",
    "scion.postrun.handoff.candidate_carrier",
    "scion.postrun.handoff.qualification_audit",
    "scion.runtime.workspace",
):
    origin = Path(inspect.getfile(importlib.import_module(name))).resolve()
    assert origin.is_relative_to(package), (name, origin)
expectations = Path(os.environ["M30_EXPECTATIONS"])
assert expectations.is_file() and not expectations.is_symlink()
assert (
    hashlib.sha256(expectations.read_bytes()).hexdigest()
    == os.environ["M30_EXPECTATIONS_SHA256"]
)
PY
  )
}

m30_postrun_tree_gate
m30_postrun_origin_gate
set +e
M30_AUDIT_STDOUT="$(
  cd /
  env -i \
  HOME=/home/clawd \
  PATH=/home/clawd/miniconda3/envs/claw/bin:/usr/bin:/bin \
  LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/dev/null \
  PYTHONUNBUFFERED=1 \
  GIT_NO_REPLACE_OBJECTS=1 \
  PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion:/home/clawd/.local/lib/python3.12/site-packages:/home/clawd/miniconda3/envs/claw/lib/python3.12/site-packages \
  /home/clawd/miniconda3/envs/claw/bin/python -S -B -m scion.cli.main \
  audit-qualification-campaign \
  "$M30_CAMPAIGN_DIR" \
  --expectations "$M30_EXPECTATIONS" \
  --repo-root "$REPO" \
  --base-commit "$B30"
)"
M30_AUDIT_EXIT=$?
set -e
m30_postrun_tree_gate
m30_postrun_origin_gate
if test "$M30_AUDIT_EXIT" -eq 0 && \
   test "$M30_AUDIT_STDOUT" = QUALIFIED_FOR_NEW_FIXED_CANDIDATE_FUNNEL; then
  printf '%s\n' "$M30_AUDIT_STDOUT"
elif test "$M30_AUDIT_EXIT" -ne 0 && test -z "$M30_AUDIT_STDOUT"; then
  exit "$M30_AUDIT_EXIT"
else
  echo QUALIFICATION_CARRIER_UNAVAILABLE >&2
  exit 1
fi
M30_POSTRUN
```

Success is exactly one stdout line:
`QUALIFIED_FOR_NEW_FIXED_CANDIDATE_FUNNEL`. Every ordinary caught failure is
nonzero with the uniform `QUALIFICATION_CARRIER_UNAVAILABLE` token and no
body, branch or path detail. Without the success token, M31 remains expired
and unmaterialized; no human may reinterpret a root or select a candidate.
