# v0.4 experiment retention cleanup audit — 2026-07-16

## Result

Four exact, retention-aware cleanup batches removed 281 roots under
`/home/clawd/research/scion-experiments`. The first two batches were
prepared-only. The third batch extended the same evidence protections to empty
roots, pre-Protocol infrastructure failures, duplicate local resume copies, and
two superseded prepared validation roots whose formal replacements remain. The
fourth batch applied a tracked-evidence inventory to old formal/replay roots and
removed only one fully reconstructible pre-Protocol replay failure and one
empty wrapper shell with an identified retained rerun.

| Batch | Roots | Deleted logical bytes | GiB | Scope |
|---|---:|---:|---:|---|
| batch-1 | 136 | 4,847,322,762 | 4.514 | old names containing `preflight` |
| batch-2 | 120 | 4,113,033,342 | 3.831 | old prepared/report-only roots with other names |
| batch-3 | 23 | 1,278,214,144 | 1.190 | empty, pre-Protocol failure, duplicate, or superseded |
| batch-4 | 2 | 250,163,200 | 0.233 | reconstructible failed replay and empty wrapper shell |
| **Total** | **281** | **10,488,733,448** | **9.768** | exact roots without unique retained evidence |

Filesystem observations:

- before batch-1: 24,302,546,944 bytes available, 81% used;
- after batch-2: 34,316,902,400 bytes available, 73% used;
- immediately before batch-3: 33,868,734,464 bytes available, 73% used;
- after batch-3: 35,147,063,296 bytes available, 72% used;
- batch-3 observed available-space change: +1,278,328,832 bytes (1.191 GiB).
- batch-4 used-space observation: 87,579,115,520 to 87,329,017,856 bytes;
- batch-4 observed freed space: 250,097,664 bytes (238.5 MiB).

The filesystem delta is larger than the logical size sum because other
processes may allocate or release blocks concurrently. The auditable cleanup
quantity is the per-path recorded-byte sum in the manifest.

The historical manifest column name is retained for compatibility, but
batches 3 and 4 recorded pre-delete allocated bytes from `du -s -B1`; the
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

The complete per-path record is in
[`v04-experiment-retention-cleanup-manifest-20260716.tsv`](./v04-experiment-retention-cleanup-manifest-20260716.tsv).

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

Ten old `status=prepared` roots lacking `prepared_run_manifest.v1.json` were
retained fail-closed (353,693,897 logical bytes total):

- `v04-cvrp-postpivot-resume-ready-{preparedstatus,healthcheck,inventory,coverage,brief}-1r-gpt55-*`;
- `v04-warehouse-v2-followup-ready-{preparedstatus,healthcheck,inventory,coverage,brief}-6r-gpt55-*`.

The live-owner scan at batch-1 time resolved only R11c paths, with PIDs 2892669,
2892705, and a transient solver child 2901041. Recent roots skipped during
batch-2 included the direct open-control root and two R6 validation roots.

The batch-3 gray manifest retains 23 exact roots totaling 685,924,047 current
apparent bytes. It includes missing-manifest prepared lineages, two referenced
infrastructure failures, two referenced pre-Protocol signal roots, and one
referenced one-round formal signal. These remain fail-closed pending explicit
evidence disposition:
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

## Follow-up boundary

Future cleanup should repeat the same evidence-based classification and produce
another manifest. It must not infer deletion solely from age or directory size.
Large historical formal runs require a separate tracked-evidence inventory
before removal.
