# v0.4 experiment retention cleanup audit — 2026-07-16

## Result

Eight exact, retention-aware cleanup batches removed 379 roots under
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
| **Total** | **379** | **11,329,949,448** | **10.552** | exact roots without unique retained evidence |

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

The filesystem delta is larger than the logical size sum because other
processes may allocate or release blocks concurrently. The auditable cleanup
quantity is the per-path recorded-byte sum in the manifest.

The historical manifest column name is retained for compatibility, but
batches 3 through 7 and batch 11 recorded pre-delete allocated bytes from
`du -s -B1`; the
arithmetic total is therefore an audit sum of each batch's recorded byte
measure, not a claim that every batch used one apparent-size metric.

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
per-subtree audit sum is 18,587,483,912 bytes (17.311 GiB). After batches 11
and 12, 764 top-level experiment directories remain. The independent
post-delete verification observed 42,077,360,128 bytes available (about 39.2
GiB), 66% used; the small difference from the immediate post-delete reading is
concurrent filesystem activity, so the manifests remain the cleanup authority.

## Follow-up boundary

Future cleanup should repeat the same evidence-based classification and produce
another manifest. It must not infer deletion solely from age or directory size.
Large historical formal runs require a separate tracked-evidence inventory
before removal.
