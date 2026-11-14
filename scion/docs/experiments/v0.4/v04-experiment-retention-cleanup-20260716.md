# v0.4 experiment retention cleanup audit — 2026-07-16

## Result

Fourteen exact, retention-aware cleanup batches removed 391 roots under
`/home/clawd/research/scion-experiments`. The first two batches were
prepared-only. The third batch extended the same evidence protections to empty
roots, pre-Protocol infrastructure failures, duplicate local resume copies, and
two superseded prepared validation roots whose formal replacements remain. The
fourth batch applied a tracked-evidence inventory to old formal/replay roots and
removed only one fully reconstructible pre-Protocol replay failure and one
empty wrapper shell with an identified retained rerun. The fifth batch removed
20 copied prepared shells only after proving that their campaign trees were
identical to retained CVRP/Warehouse canonical campaigns except for SQLite
`wal/shm` transients. Batch 6 removed only tiny pre-campaign shells whose
complete contents were launch metadata, stale PIDs, empty logs, or recorded
infrastructure errors. Batch 7 applied a larger-history disposition inventory
and removed only two roots whose completed replacements are retained. Batch 11
removed 12 more superseded pre-campaign, infrastructure-failure, dirty-
preflight, corrupt-launcher, or exact-subset roots only after an identified
retained owner and zero unique scientific evidence were verified for each.
Batch 13 removed one dry-run-only planned matrix subset and one wrong-working-
directory wrapper that stopped before Protocol, LLM, metric, or database work.
Batch 14 removed three zero-round shells whose only scientific payload was an
initial champion exactly retained by an identified completed owner.
Batch 15 removed two dry-run-only planned matrices after every planned job and
the only differing reserved telemetry schema were proved to be retained
elsewhere.
Batch 16 removed one pre-campaign transport failure with no campaign payload
and one pre-campaign authentication failure whose copied 1,083-file campaign
tree was byte-identical to a retained completed owner.
Batch 17 removed one pre-campaign launch shell only after its substantive
worktree diff and Git status were proved byte-identical to a retained exit-zero
eight-round owner and every patched base/result blob remained reconstructible.
Batch 18 removed one pre-evaluation permission-failure replay shell and one
zero-effective capacity-blocked successor only after copy-isolated SQLite
inspection and complete retained-owner payload equality were proved.
Batch 19 was a read-only boundary audit over all 752 remaining roots. It found
no whole root for which a retained-owner-equivalence proof covered every unique
research artifact, so it deleted nothing.

| Batch | Roots | Deleted logical bytes | GiB | Scope |
|---|---:|---:|---:|---|
| batch-1 | 136 | 4,847,322,762 | 4.514 | old names containing `preflight` |
| batch-2 | 120 | 4,113,033,342 | 3.831 | old prepared/report-only roots with other names |
| batch-3 | 23 | 1,278,214,144 | 1.190 | empty, pre-Protocol failure, duplicate, or superseded |
| batch-4 | 2 | 250,163,200 | 0.233 | reconstructible failed replay and empty wrapper shell |
| batch-5 | 20 | 792,592,384 | 0.738 | copied prepared shells with retained canonical campaigns |
| batch-6 | 64 | 868,352 | 0.001 | pre-campaign shells and trivial launch failures |
| batch-7 | 2 | 39,088,128 | 0.036 | failed matrix and aborted wrapper with completed replacements |
| batch-11 | 12 | 8,667,136 | 0.008 | superseded failures, dirty preflights, and one exact subset |
| batch-13 | 2 | 77,824 | 0.000 | planned-only exact subset and pre-Protocol wrong-cwd shell |
| batch-14 | 3 | 4,227,072 | 0.004 | zero-round exact subsets with completed retained owners |
| batch-15 | 2 | 57,344 | 0.000 | dry-run planned jobs and reserved schema retained by completed owners |
| batch-16 | 2 | 22,106,112 | 0.021 | pre-campaign failures with no unique scientific evidence |
| batch-17 | 1 | 94,208 | 0.000 | pre-campaign shell whose complete substantive payload is exactly retained |
| batch-18 | 2 | 210,616,320 | 0.196 | pre-evaluation failure and zero-effective successor with complete retained owners |
| **Total** | **391** | **11,567,128,328** | **10.773** | exact roots without unique retained evidence |

Filesystem observations:

- before batch-1: 24,302,546,944 bytes available, 81% used;
- after batch-2: 34,316,902,400 bytes available, 73% used;
- immediately before batch-3: 33,868,734,464 bytes available, 73% used;
- after batch-3: 35,147,063,296 bytes available, 72% used;
- batch-3 observed available-space change: +1,278,328,832 bytes (1.191 GiB).
- batch-4 used-space observation: 87,579,115,520 to 87,329,017,856 bytes;
- batch-4 observed freed space: 250,097,664 bytes (238.5 MiB).
- after batches 6 and 7: 35,629,588,480 bytes available, 71% used.
- immediately before batches 11 and 12: 41,445,580,800 bytes available, 67% used;
- immediately after batches 11 and 12: 42,092,539,904 bytes available, 66% used;
- batches 11 and 12 observed available-space change: +646,959,104 bytes
  (617.0 MiB), versus a 635,191,296-byte recorded target sum.
- batch 13 available space: 41,566,863,360 to 41,566,941,184 bytes;
- batch 13 observed available-space change: +77,824 bytes, exactly matching
  its recorded allocated-byte sum.
- batch 14 available space: 41,509,257,216 to 41,514,598,400 bytes;
- batch 14 observed available-space change: +5,341,184 bytes, versus a
  4,227,072-byte recorded allocated-byte sum.
- batch 15 available space: 40,986,202,112 to 40,986,259,456 bytes;
- batch 15 observed available-space change: +57,344 bytes, exactly matching
  its recorded allocated-byte sum.
- batch 16 available space: 40,972,238,848 to 40,994,271,232 bytes;
- batch 16 observed available-space change: +22,032,384 bytes, versus a
  22,106,112-byte recorded allocated-byte sum.
- batch 17 available space: 40,550,375,424 to 40,550,449,152 bytes;
- batch 17 observed available-space change: +73,728 bytes, versus a
  94,208-byte recorded allocated-byte sum.
- batch 18 available space: 40,556,687,360 to 40,771,444,736 bytes;
- batch 18 observed available-space change: +214,757,376 bytes, exactly equal
  to 210,616,320 candidate bytes plus the 4,141,056-byte isolated audit copy.
- batch 19 was read-only: 752 roots remained, zero candidate bytes were
  deleted, and 40,398,311,424 bytes were available at audit completion.

The filesystem delta is larger than the logical size sum because other
processes may allocate or release blocks concurrently. The auditable cleanup
quantity is the per-path recorded-byte sum in the manifest.

The historical manifest column name is retained for compatibility, but
batches 3 through 7, batch 11, and batches 13-18 recorded pre-delete allocated
bytes from `du -s -B1`; the arithmetic total is therefore an audit sum of each
batch's recorded byte measure, not a claim that every batch used one apparent-
size metric.

## Prepared-only deletion predicate

Every deleted path passed all of these checks immediately before removal:

1. top-level root was older than 48 hours;
2. `run_status.json` reported `status=prepared`;
3. PID, start, end, and exit lifecycle fields were null;
4. `prepared_run_manifest.v1.json` reported `report_only=true`;
5. campaign, scheduler, and promotion mutation flags were all false;
6. no `.git` directory or registered git worktree was present;
7. a `/proc` cwd/open-fd scan found no active owner;
8. the root was an iterative handoff/preflight/smoke preparation superseded by later code history or formal run roots.

These roots could contain copied source, baseline caches, readiness output, or
handoff material, but did not contain a launched formal experiment transaction.
Cleanup was path-exact and was not an age-only deletion.

The batch 1-4 and 6-7 per-path record is in
[`v04-experiment-retention-cleanup-manifest-20260716.tsv`](./v04-experiment-retention-cleanup-manifest-20260716.tsv).
Batch 5 remains in its dedicated exact manifest linked below, and batch 11 is
recorded separately in
[`v04-experiment-retention-cleanup-batch11-20260716.tsv`](./v04-experiment-retention-cleanup-batch11-20260716.tsv).
Batch 13 is recorded in
[`v04-experiment-retention-cleanup-batch13-20260716.tsv`](./v04-experiment-retention-cleanup-batch13-20260716.tsv).
Batch 14 is recorded in
[`v04-experiment-retention-cleanup-batch14-20260716.tsv`](./v04-experiment-retention-cleanup-batch14-20260716.tsv).
Batch 15 is recorded in
[`v04-experiment-retention-cleanup-batch15-20260716.tsv`](./v04-experiment-retention-cleanup-batch15-20260716.tsv).
Batch 16 is recorded in
[`v04-experiment-retention-cleanup-batch16-20260716.tsv`](./v04-experiment-retention-cleanup-batch16-20260716.tsv).
Batch 17 is recorded in
[`v04-experiment-retention-cleanup-batch17-20260716.tsv`](./v04-experiment-retention-cleanup-batch17-20260716.tsv).
Batch 18 is recorded in
[`v04-experiment-retention-cleanup-batch18-20260716.tsv`](./v04-experiment-retention-cleanup-batch18-20260716.tsv).

## Batch-19 retained-evidence boundary

Batch 19 rescanned all `752` remaining top-level roots and `781` campaign
directories without modifying them. It protected the current R6-R11c,
Warehouse R2/R3, Phase A/B/C, baseline-strength, current successor/baseline,
and every root referenced from TASK, current-state, design, or experiment
reports. All `29` old status records whose legacy accounting fields were zero
remained fail-closed: each retained independent trace evidence, nonzero newer
accounting/formal evidence, or a protected archived launch.

Global trace-identity comparison found no unreferenced zero-value root whose
entire trace set was retained elsewhere. Seven unreferenced roots without the
standard database/metric/trace/formal layout were independent MILP, offline,
or direct-VRP research records containing unique logs, CSV data, analysis, or
results, rather than disposable shells with a named retained owner. Referenced
CVRP/Warehouse healthcheck and prepared-status copies also remained protected.

Three ambiguous roots were inspected only through copies under `/tmp`, with
WAL materialized into the audit copies and immutable SQLite reads. Source DB
size and timestamps were unchanged. Although one had a completed similarly
named owner, its two tool-selection traces were globally unique; the other two
also retained independent trace or hypothesis/session evidence. Temporary
audit copies were removed. The resulting deletion candidate set was empty:
zero roots and zero bytes were removed. Further whole-root cleanup must wait
for a newly provable complete retained-owner equivalence; otherwise it would
cross into unique research evidence.

## Batch-3 deletion predicate

Batch 3 first scanned active operating, planning, and experiment-report docs
and protected 73 exact roots. Every deleted path then passed all applicable
checks immediately before removal:

1. no live PID, `/proc` cwd, command line, or open-fd owner;
2. no `.git` directory or registered worktree;
3. no active-doc protection and no remaining repository reference, except that
   a duplicate root could be deleted only when its canonical source remained;
4. no unique Protocol result, effective new round, validation result, or
   promotion evidence;
5. one positive class was proven exactly: empty root, pre-Protocol
   infrastructure failure, premise-contradicted pre-Protocol signal, local
   resume with zero effective rounds and retained source evidence, or
   report-only prepared root superseded by an identified formal root.

The batch removed four empty roots, five old pre-Protocol infrastructure
failures, one premise-contradicted pre-Protocol signal root, eleven dead local
resume copies with zero effective rounds, and two superseded prepared
validation roots. It reduced the top-level experiment-root count from 887 to
864. This was not an age-, name-, or size-only deletion.

## Explicit retention

The cleanup did not remove:

- the live R11c root or any path found by the active-owner scan;
- current R6–R11c formal evidence used by TASK/current-state;
- baseline-strength Phase A/B/C evidence needed for later ALNS design;
- any root less than 48 hours old;
- any git runtime or worktree;
- any unique raw scientific evidence;
- any large historical matrix whose retention status remained ambiguous.

Batch 3 additionally rechecked that warehouse R2/R3, R6-R11c, Phase A/B,
open-control, formal validation/expanded roots, and each duplicate local
resume's canonical source still existed after deletion. R11c wrapper/campaign
PIDs 2892669/2892705 remained live and its root/runtime were untouched.

Six old `status=prepared` roots lacking `prepared_run_manifest.v1.json` remain
retained fail-closed:

- `v04-cvrp-postpivot-resume-ready-{preparedstatus,healthcheck,brief}-1r-gpt55-*`;
- `v04-warehouse-v2-followup-ready-{preparedstatus,healthcheck,brief}-6r-gpt55-*`.

The live-owner scan at batch-1 time resolved only R11c paths, with PIDs 2892669,
2892705, and a transient solver child 2901041. Recent roots skipped during
batch-2 included the direct open-control root and two R6 validation roots.

The batch-3 gray manifest originally retained 23 roots. Batch 5 resolved and
deleted 12 copied shells after exact campaign-tree equality checks; those rows
are now owned by the batch-5 deletion manifest. The current gray manifest
retains 11 exact roots totaling 261,582,536 recorded bytes: six referenced
missing-manifest prepared roots, two referenced infrastructure failures, two
referenced pre-Protocol signal roots, and one referenced one-round formal
signal. These remain fail-closed pending explicit evidence disposition:
[`v04-experiment-retention-cleanup-gray-20260716.tsv`](./v04-experiment-retention-cleanup-gray-20260716.tsv).

## Batch-4 tracked-evidence inventory

Batch 4 inspected old large/formal candidates before deletion and recorded
status, effective rounds, Protocol stages, raw-evidence counts, evidence
fingerprint, report references, canonical/superseding roots, and disposition.
It deleted exactly two roots:

- a fixed-replay root whose 20/20 rows all failed before Protocol with the same
  `FileNotFoundError`, had zero metrics, and whose normalized candidate
  manifests/source material are reconstructible from retained source and
  corrected replay roots;
- an aborted wrapper shell with no campaign, LLM call, Protocol work, metric,
  or nonempty log; its tracked launch report points to the retained actual
  rerun.

The inventory deliberately retained a zero-effective root containing unique
hypothesis/code/tool traces, a report-excluded replay root containing 105
unique raw metrics, and large v0.3/Phase-5/direct-VRP trees with unique formal
or analysis artifacts. The exact inventory is
[`v04-experiment-retention-tracked-evidence-inventory-batch4-20260716.tsv`](./v04-experiment-retention-tracked-evidence-inventory-batch4-20260716.tsv).
The batch reduced top-level roots from 864 to 862 and did not change the live
R11c root/runtime.

## Batch-5 copied prepared-shell inventory

Batch 5 began from 862 roots and deleted exactly 20 inactive copied prepared
shells: ten CVRP and ten Warehouse. Every candidate had only launch/preparation
files at its top level, no wrapper/stdout/stderr log, no registered worktree,
no live PID/cwd/cmdline/open-fd owner, and no repository reference outside this
cleanup audit. Four candidates had a `run_status.json` whose typed state was
`prepared_only=true`; the other 16 had no lifecycle status at all.

The CVRP copies contained 344 campaign files including 35 metrics, three formal
candidate files, seven LLM traces, and two transcripts. Their entire campaign
trees matched retained canonical root
`v04-cvrp-postpivot-guidance-agentic-1r-acc21ba-20260618T064210Z`. The Warehouse
copies contained 2,405 campaign files including 73 metrics, seven formal
candidate files, 37 LLM traces, and 15 transcripts. Their trees matched the
retained `rep01/full_context/campaign` under
`v04-warehouse-validation-transfer-contract-rerun6r-ce5d884-20260617T152944Z`.
`diff -qr` was clean for all 20 after excluding only SQLite `scion.db-wal` and
`scion.db-shm` transient files.

Deletion initially stopped on the first root because copied champion
directories were owner-read-only (`0555`). No later root was touched during
that attempt. The retry changed only directory owner-write permission inside
the exact 20 deletion candidates, repeated the live-owner check, and removed
all candidates. Root count is now 842 and all 20 exact paths are absent. The
full path, predicate, pre-delete allocated bytes, and retained canonical owner
are recorded in
[`v04-experiment-retention-cleanup-batch5-20260716.tsv`](./v04-experiment-retention-cleanup-batch5-20260716.tsv).

Six similar `brief`, `healthcheck`, and `preparedstatus` copies remain
fail-closed because historical documents refer to them. Unique-trace
construction-pivot, successor38/44/44b, SIGTERM replay, Phase-5 replay, R6-R11c,
Warehouse R2/R3, Phase A/B/C, validation/frozen, recent, and ambiguous formal
roots also remain protected.

## Batch-6 pre-campaign shells

Batch 6 inspected all roots occupying at most 24 KiB and selected exactly 64
unreferenced roots. Every selected root contained only launch/environment
metadata, stale PID markers, runner scripts, empty logs, or one short
pre-campaign error. Four contained empty `campaign` or `agentic_sessions`
directories, but none contained a campaign file, database, metric, formal
candidate, LLM trace, workspace, or champion. Three other small roots were
excluded because they carried a current document reference or a result JSON.

Immediately before deletion, every selected path matched its recorded
allocated size, repository-reference scan, artifact predicate, git/worktree
check, and `/proc` cwd/open-fd scan. All 64 exact paths are absent. Their file
shape or exact error class is retained in
[`v04-experiment-retention-cleanup-batch6-20260716.tsv`](./v04-experiment-retention-cleanup-batch6-20260716.tsv).

## Batch-7 historical disposition

Batch 7 independently inspected 15 large-history candidates rather than
treating a later run as automatic authorization to delete earlier evidence.
It deleted exactly two roots:

- the first Phase-5 Warehouse context-control matrix, whose cells produced
  zero metrics and stopped on invalid proxy authentication or immediately
  after startup; the same commit/configuration matrix completed in retained
  root `v04-phase5-warehouse-controlpair-full-vs-nomeas-4x2-8r-20260613T011820Z-claw`;
- a seven-file Warehouse wrapper that failed on a bad problem path before
  campaign creation; corrected retained rerun
  `v04-p1-intent-replay-lifecycle-warehouse-verify-rerun-20r-gpt55-20r-gpt55-20260608T131951Z-claw`
  completed `20/20` valid rounds.

The first deletion attempt stopped inside the failed Phase-5 root because its
copied champion directories were owner-read-only. The retry changed only
directory owner-write permission within that exact candidate, repeated the
active-owner check, and completed both deletions.

Twelve other candidates remain. One v0.3 root has three exact repository
references; two zero-effective SIGTERM roots contain unique hypothesis/tool/
provider traces; and the remaining v0.3, partial, smoke, and complete formal
roots contain unique metrics or formal artifacts. A later, longer run does not
make those files exact duplicates. The full delete/retain reasoning and each
retained successor are recorded in
[`v04-experiment-retention-disposition-batch7-20260716.tsv`](./v04-experiment-retention-disposition-batch7-20260716.tsv).

After batch 7, 776 top-level experiment directories remain. Current R6-R11c,
Warehouse R2/R3, Phase A/B/C, and every protected large-history candidate
still exist.

## Batch-11 superseded failure roots

Batch 11 selected exactly 12 inactive roots whose lifecycle had stopped before
usable scientific evidence or whose content was an exact subset of a retained
owner. The classes were wrong working directory, wrong problem path, missing
API key, pre-calibration path failure, corrupt launcher, dirty-runtime
preflight, missing runtime dependency, and one exact subset. Every row passed
an immediate pre-delete size check, zero scientific-artifact check, zero
repository-reference check outside cleanup records, git/worktree exclusion,
and PID/cwd/command-line/open-fd scan. Its named retained owner existed both
before and after deletion.

All 12 exact roots are absent, while their retained owners and the current
R6-R11c, Warehouse R2/R3, and Phase A/B/C anchors remain. The exact path,
classification, recorded allocated bytes, retained owner, and validation
conclusion are in
[`v04-experiment-retention-cleanup-batch11-20260716.tsv`](./v04-experiment-retention-cleanup-batch11-20260716.tsv).

## Batch-13 planned subset and pre-Protocol shell

Batch 13 selected exactly two inactive roots after repeating the pre-delete
allocated-size, repository-reference, git/worktree, symlink, PID, cwd, command-
line, and open-fd checks. The first root contained only a dry-run manifest,
planned results, and summary for six jobs; every objective, runtime, move, and
best-update field was null. Its exact seed/instance/mechanism coverage exists
in the retained 96/96-completed mechanism-matrix root. The second root held
only launcher/wrapper metadata and an empty campaign directory: an incorrect
working directory made `problem.yaml` resolution fail before Protocol, LLM,
metric, or database work, while the retained verify2 root completed the same
four-round command shape from the correct directory.

Both deleted roots are absent, both named retained owners remain, and the
observed available-space increase exactly equals the 77,824-byte manifest sum.
The exact paths and proofs are in
[`v04-experiment-retention-cleanup-batch13-20260716.tsv`](./v04-experiment-retention-cleanup-batch13-20260716.tsv).

## Batch-14 zero-round exact subsets

Batch 14 selected exactly three inactive zero-round roots. Every candidate
reported `total_rounds=0`, `n_steps=0`, and `n_experiments=0`; its Branch,
Hypothesis, experiment-event, and weight-optimization tables were empty. The
only scientific payload was one initial champion. For each root, the complete
initial champion tree and its SQLite `code_snapshot_hash` exactly matched a
named retained owner that later completed four, three, or two rounds.

Immediately before deletion, all three roots matched their recorded allocated
size, had no repository reference outside the cleanup manifest, contained no
git directory or registered worktree, and had no live PID, cwd, or open-fd
owner. The first delete attempt stopped on owner-read-only champion directories
after removing only writable files inside the same three candidates. No other
root was touched. The retry added owner-write permission only to directories
inside those exact candidates, repeated the live-owner check, and completed
their removal. All three retained owners remain.

The exact paths, pre-delete allocated bytes, classifications, retained owners,
and validation conclusions are in
[`v04-experiment-retention-cleanup-batch14-20260716.tsv`](./v04-experiment-retention-cleanup-batch14-20260716.tsv).

## Batch-15 dry-run planned matrices

Batch 15 selected exactly two inactive dry-run matrices. Each root contained
only `manifest.json`, `results.json`, and `summary.csv`; all three jobs were
`planned`, every objective/runtime/move observation was null, and no raw,
workspace, database, LLM, metric, formal, Protocol, or promotion evidence
existed. Every exact job ID is completed with a nonempty raw result in a named
retained owner: one owner completed 80/80 jobs and the other completed 60/60.

The second planned root declared `objective_probes` in its reserved result
schema. Its three-job schema digest,
`bfadb711a8ecd43f7c89ed601cdb38d8e20ecc5168c6058393e7a40969fea1c8`,
is used by all 80 jobs in the retained VNS-variants owner, and its three
mechanism definitions exactly match the retained P76 deep-mechanism owner.
Thus neither an observation nor a schema variant depended on the planned root.

Immediately before deletion both roots still matched their recorded allocated
size, had no repository reference outside cleanup records, contained no git
directory or registered worktree, and had no PID, cwd, command-line, or open-fd
owner. Both deleted roots are absent, both primary owners remain, and the
observed available-space increase exactly equals the 57,344-byte manifest sum.
The exact record is in
[`v04-experiment-retention-cleanup-batch15-20260716.tsv`](./v04-experiment-retention-cleanup-batch15-20260716.tsv).

## Batch-16 pre-campaign failures and copied evidence

Batch 16 selected exactly two inactive pre-campaign failures. The Warehouse
root ended during completion preflight with a transport timeout and wrapper
exit 64. It contains no Campaign directory, database, LLM session, metric,
formal candidate, or workspace. A retained replacement has the same execution,
model, research-guidance, and data-root contract, and its retained R2 successor
completed two rounds and two experiments validly.

The CVRP root ended during completion preflight with an authentication failure
and no execution marker. Its Campaign directory was copied from the retained
completed owner
`v04-cvrp-proofstatus-followup-05ade2e0-2r-gpt55-20260625T155106Z-claw`:
all 1,083 relative files compared byte-for-byte equal and both relative-tree
digests were
`7bca4bbf524f3917e1858392eb72d16576c75a51444d66ddcf2f72a021296777`.
The retained owner remains valid and complete at two rounds/two experiments,
and the candidate's referenced Git commit remains available.

Immediately before deletion both roots matched their recorded allocated sizes,
had no repository reference, git directory, registered worktree, live PID,
cwd, command line, or open descriptor. Read-only permissions in the copied
champion tree stopped the first exact deletion attempt after writable files had
been removed. Only that already-approved candidate tree had owner-write
permission restored; deletion then completed. Both roots are absent and all
three named retained replacement/owner roots remain. The exact record is in
[`v04-experiment-retention-cleanup-batch16-20260716.tsv`](./v04-experiment-retention-cleanup-batch16-20260716.tsv).

## Batch-17 exact retained launch payload

Batch 17 selected one inactive pre-campaign shell. It contained six files: an
empty run log, launch metadata, a stale PID, Git status, and a worktree diff.
It had no Campaign, database, metric, LLM, formal, or workspace evidence. Its
`worktree.diff` and `git-status.txt` were byte-identical to the named retained
owner, with diff SHA-256
`a573be20f1b16af4209aa0a410e0d34ce9a6e484b54b1c64a5643ee226fed283`.
The retained owner exited zero after eight rounds and retains 24 metric files,
145 LLM/agent files, and the exact intermediate patch. Every one of the 12
patched base blobs remains in Git commit `3da3f137`; 11 final result blobs are
also retained by `0a794790`, while the differing current-state intermediate is
preserved verbatim in the retained diff.

Immediately before deletion the shell still occupied 94,208 allocated bytes,
had no repository reference, symlink, Git directory, registered worktree,
live PID, cwd, command line other than the audit process itself, or open file
descriptor. The exact shell is absent, the completed owner remains, and five
nearby candidates with document references, a unique launcher, different
runtime conditions, or unique LLM traces were explicitly retained. The exact
record is in
[`v04-experiment-retention-cleanup-batch17-20260716.tsv`](./v04-experiment-retention-cleanup-batch17-20260716.tsv).

## Batch-18 pre-evaluation and zero-effective retained payloads

Batch 18 selected two inactive roots. The first stopped before candidate
evaluation with two `PermissionError` rows. It had no database, metric, LLM,
formal, or workspace evidence, and all 910 materialized files were byte-equal
to a subset of the named owner that completed both replay arms.

The second reported zero rounds, steps, experiments, screened experiments, and
effective rounds. Its LLM traces, agent sessions, metrics, workspaces,
champions, formal candidates, and Branch/H/champion/weight database rows were
identical to valid successor17. Its only additions were two pre-Protocol
`capacity_blocked` scheduler events; corrected successor18b remains valid and
complete.

All SQLite inspection was performed only after reflink/copy isolation under
`/tmp`, using read-only immutable connections. Before and after that audit,
candidate and retained-owner allocated/logical bytes, root and database
mtimes, full-tree metadata digests, and repository-reference counts were
unchanged. The final deletion gate found no repository reference, symlink, Git
marker, worktree registration, PID, cwd, command line, or open descriptor.
Owner-write permission was added only to 56 and 22 directories inside the two
exact candidates. Both candidates and the temporary audit copy are absent;
all three retained owners are unchanged. The exact record is in
[`v04-experiment-retention-cleanup-batch18-20260716.tsv`](./v04-experiment-retention-cleanup-batch18-20260716.tsv).

## Batches 8-10 and 12 exact static-subtree compaction

Batches 8-10 and 12 did not delete experiment roots or scientific evidence. They
removed only repeated static source/data/test subtrees below directories that
own a `registry.yaml`, after proving each occurrence byte-for-byte equivalent
to a retained Git owner commit. Python caches were allowed as untracked extras;
they were included in the recorded allocated-byte deletion but excluded from
the source-content hash because Git cannot restore caches.

| Batch | Roots retained | Registry parents | Subtrees | Allocated bytes | GiB |
|---|---:|---:|---:|---:|---:|
| batch-8 | 8 | 229 | 1,374 | 2,726,719,488 | 2.539 |
| batch-9 | 6 | 268 | 1,154 | 2,947,604,480 | 2.745 |
| batch-10 | 6 | 97 | 194 | 956,686,336 | 0.891 |
| batch-12 | 1 | 64 | 128 | 626,524,160 | 0.583 |
| **Static total** | **21 root memberships** | **658** | **2,850** | **7,257,534,464** | **6.759** |

For every occurrence, the audit verified that the owner commit exists, the
Git source subtree exists, no symlink is present, a recursive comparison has
zero mismatches after excluding only `__pycache__`, `.pytest_cache`, and
`*.pyc`, and the current allocated size matches the manifest. The manifests
record root, registry-parent-relative path, subtree, allocated bytes, full Git
commit, Git source, deterministic source-tree SHA-256, and a restore command
template:

- [`v04-experiment-static-subtree-cleanup-batch8-20260716.tsv`](./v04-experiment-static-subtree-cleanup-batch8-20260716.tsv);
- [`v04-experiment-static-subtree-cleanup-batch9-20260716.tsv`](./v04-experiment-static-subtree-cleanup-batch9-20260716.tsv);
- [`v04-experiment-static-subtree-cleanup-batch10-20260716.tsv`](./v04-experiment-static-subtree-cleanup-batch10-20260716.tsv);
- [`v04-experiment-static-subtree-cleanup-batch12-20260716.tsv`](./v04-experiment-static-subtree-cleanup-batch12-20260716.tsv).

Batch 8 compacted six static subtrees from Phase-5 Warehouse matrix/replay
copies. Batch 9 compacted four or five static subtrees from retained v0.3
validation trees; `v03-validation` correctly uses distinct historical owners
for `data/tests` and `sprint-f4-milp-results/milp_bounds`. Batch 10 compacted
only `data` and `tests` from Sprint-F roots. Batch 12 removed only `data` and
`tests` from 64 registry-owning parents in the retained Warehouse long-run
regression root. All 128 copies matched Git commit
`f384884d4fe45d5f87cabdab193054b1f66e9c79` and the manifest hashes.

Deletion changed owner-write permission only while removing an exact subtree
and restored each retained registry parent's original mode. Full post-delete
checks found all 2,850 target paths absent while registry, database, metric,
LLM/session, formal-artifact, and log counts remained unchanged within every
batch. Operators, root Python, registry files, workspaces, archives, champions,
formal patches, DBs, metrics, statuses, summaries, traces, logs, and postrun
reports were not selected. The 21 root memberships remain in place.

Batch 12's first removal attempt cleared the first selected `data` directory
but stopped before removing its empty directory entry because the retained
registry parent was owner-read-only. No later target or whole root was touched
in that attempt. The retry temporarily added owner-write permission only to
each exact target's direct parent, removed the target, and immediately restored
the parent's original mode. All 128 targets then passed absence checks. Within
the retained Warehouse root, post-delete counts remain 64 registries, 3
databases, 464 metrics, 131 formal artifacts, 1,798 LLM/session files, 4 logs,
and 12 outer reports.

Across whole-root deletion and static compaction, the recorded per-path/
per-subtree audit sum is 18,824,662,792 bytes (17.532 GiB). After batch 18,
752 top-level experiment directories remain. Its immediate post-delete
verification observed 40,771,444,736 bytes available; filesystem readings may
continue to move with concurrent activity, so the manifests remain the cleanup
authority.

## Follow-up boundary

Future cleanup should repeat the same evidence-based classification and produce
another manifest. It must not infer deletion solely from age or directory size.
Large historical formal runs require a separate tracked-evidence inventory
before removal.
