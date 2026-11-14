# CVRP B1 mechanism matrix inflight record

Date: 2026-07-18

Status: running; no acceptance claim yet

## Accepted B0 launch authority

- pushed commit: `90a109b23ed3a0fa3c34a4c178190d9e999316cc`
- accepted dry root: `/tmp/scion-cvrp-b0-fourth-review-claw-dry`
- accepted dry manifest SHA-256:
  `0151e2be99417f9e026438d914cad2b83497cee8855f113a9b515d3f1bb882b1`
- independent code review: P0=0, P1=0
- independent science review: P0=0, P1=0
- launch files:
  - `scion/tools/cvrp_mechanism_matrix.py`:
    `4d0b787245d112dbb168acabd8d5c4b176854639ae555efa4e7d110983eb4231`
  - `scion/scion/problems/cvrp/evidence/b0_runner_contract.py`:
    `38f81e045da0ac19940d23a2d93183d80740b31d4444c568c74e6bd9f8b58739`
  - `scion/scion/tests/unit/evidence/test_cvrp_b0_runner_contract.py`:
    `7e7b6acd752b92a425d8b4f85c16a29336a56429fcf60be979b9c02629d92e6c`

## Live B1 root

- systemd user unit: `scion-cvrp-b1-20260718T074653Z.service`
- main PID at launch: `3776952`
- root:
  `/home/clawd/research/scion-experiments/v04-cvrp-b1-mechanism-matrix-20260718T074653Z-claw`
- launcher log:
  `/home/clawd/research/scion-experiments/v04-cvrp-b1-mechanism-matrix-20260718T074653Z-claw.launcher.log`
- live manifest SHA-256:
  `8e9bf79c58ce1a5b9aa1e18d1d02d828fe2c32823ea2662bd99c96b22a1589b9`
- launcher and child:
  `/home/clawd/miniconda3/envs/claw/bin/python3.12`

The run is the fixed serial 16-case x 4-seed x 4-profile matrix: 256 jobs,
192 Protocol-resolved 30-second jobs and 64 Protocol-resolved 45-second jobs.
It uses the balanced Latin profile order and `solver_design` surface. There is
no resume, retry, workspace reuse, selector, command-line time override,
budget, cap, or output truncation.

At the first low-frequency health check the systemd unit was active/running,
the manifest contained 256 jobs with `dry_run=false`, and 11 raw results were
present. No results summary or closed receipt existed yet, as expected.

## Host-overlap observation

A Warehouse W2 historical slow MILP test process (PID `3791879`) started at
`2026-07-18 08:56:08 UTC` on the same host while B1 was live. At the
`2026-07-18 09:17:50 UTC` audit, 37 B1 raw files had mtimes after that start.
The test was then lowered to nice `19`/idle I/O priority; it ended naturally
before a later termination attempt, when B1 had 215 raw files. This was not a
provider retry or another Scion experiment, but its CPU overlap can affect a
time-limited solver and therefore cannot be silently ignored.

B1 should continue once, without automatic restart. Completion analysis must
bind the exact overlap interval to execution-job ordinals/profile order and
compare objective/runtime/timeout behavior before deciding whether the full
matrix, an unaffected subset, or no causal comparison is acceptable. Do not
launch F1 or W3 on this host until that integrity decision is reviewed.

## Superseded non-evidence root

The earlier shell-background handoff root
`/home/clawd/research/scion-experiments/v04-cvrp-b1-mechanism-matrix-20260718T074602Z-claw`
contains only an authority snapshot. Its process did not survive the launch
shell handoff; it has no manifest, jobs, results, or receipt. It is superseded
operational debris and must not be reused or cited as experiment evidence.

## Acceptance after completion

B1 remains unaccepted until the live unit terminates successfully and the root
contains all 256 completed raw results, an integrity-verified results artifact,
the closed receipt, and a problem-owned comparison report. F1 stays locked
until that acceptance is complete.
