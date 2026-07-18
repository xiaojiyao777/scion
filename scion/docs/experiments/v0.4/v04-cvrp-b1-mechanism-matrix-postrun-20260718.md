# CVRP B1 mechanism matrix postrun

*Date: 2026-07-18*
*Status: accepted conservative-scope diagnostic evidence; F1 unlocked*

## Identity and closure

The accepted one-time root is:

`/home/clawd/research/scion-experiments/v04-cvrp-b1-mechanism-matrix-20260718T074653Z-claw`

The user service exited normally with status zero. The root contains exactly
256 completed raw rows: 16 cases x 4 seeds x 4 fixed profiles, with 64 rows per
profile, 16 rows per profile-position, and scientific limits `192x30s +
64x45s`. Every row is feasible, has zero fleet violation, and stopped at the
preregistered internal time limit. There was no retry, resume, duplicate,
workspace reuse, or automatic rerun.

Frozen input hashes:

- manifest: `8e9bf79c58ce1a5b9aa1e18d1d02d828fe2c32823ea2662bd99c96b22a1589b9`;
- results: `0e3107c1ff544b0ddfad9578f1f4bc96e1aeac2af42ade05802f12ebd13d3fc0`;
- summary: `39af578efdefe3239d89e687396cdeb743c7d84aa8e7a3b4f5e824f2d0839a4b`;
- matrix closed receipt:
  `9b0b0b5eb17b7fed8fb9f38e3013e70038cbe0d2c2d13b056a63caa34a1a2a0c`;
- accepted postrun contract:
  `32b38dda34b1c87d6c0bcf41fc92e4782ae0f496aa9817aa32903e122aabbfd6`.

The problem-owned closer published both final artifacts once with O_EXCL and
fsync, then reproduced them byte-for-byte with `--check-existing`:

- comparison report:
  `833335bb497d3cd7b344c3d6b87269ae0469c2cb87ee76c52227859719a7851b`;
- comparison receipt:
  `03d1c466d09ed84a9bbd3b6a21333311da4f739a78e57102f5fa1ca8bffd5d43`;
- closer source aggregate:
  `ea0d8fe9e31b41dd005a929ce9f820b2fae2dabc6c612ee4d44db69d831b329c`.

Independent integrity/code and science/overlap reviews both closed at
P0=0/P1=0/P2=0 on the same source and design hashes. The focused suite passed
8 tests; Black, compileall, and diff checks passed.

## Host-overlap scope

Warehouse W2's slow MILP test overlapped B1. Jobs `174..211` are classified as
normal-priority overlap, `212..215` as the conservative unknown-end quartet,
and `216..255` as after the conservative boundary. B1 is not clean-host
throughput evidence.

The preregistered comparison views are:

- all 256 rows;
- 248 rows after excluding the two normal-priority boundary quartets;
- a conservative clean-host closure of 212 rows, removing ordinals
  `172..215` as whole quartets;
- the balanced 32-row CMT4 and M-n151-k12 normal-overlap block.

Absolute throughput in overlap regimes may be biased. Quality direction is
case-major and case-equal-weighted, so seed rows are repeated measurements and
never independent sample units.

## Result

The accepted verdict is `accepted_conservative_scope`.

| Contrast versus canonical | Full 256 case W/L/T | Clean 212 case W/L/T | Full median case distance delta, profile-canonical | Direction |
|---|---:|---:|---:|---|
| pure ALNS, no polish | 12/0/4 | 10/1/3 | +17.5 | canonical better |
| embedded VNS disabled | 11/1/4 | 10/1/3 | +7.5 | canonical better |
| initial VNS disabled | 7/3/6 | 6/2/6 | +0.75 | descriptive/heterogeneous |

Positive deltas mean the alternate profile is worse. The two main contrasts
remain `canonical_better` in the full, boundary-excluded, and conservative
clean views. In the balanced high-competition block both main contrasts are
canonical wins on both cases, with no failure cliff or reversed interaction.

The full-view median BKS gap and ALNS iterations were:

- canonical: `3.687%`, 17 iterations;
- pure ALNS: `5.700%`, 143 iterations;
- embedded-VNS-disabled: `5.138%`, 143 iterations;
- initial-VNS-disabled: `4.009%`, 16.5 iterations.

Removing embedded VNS frees substantially more ALNS iterations but worsens
solution quality. Embedded VNS therefore contributes material quality on this
fixed population; it is not merely invisible overhead starving a superior
ALNS loop. Initial VNS is much closer to neutral and heterogeneous. Because SA
cooling is iteration-based, the profiles also change the temperature path, so
B1 cannot attribute every delta solely to VNS wall time.

## Authority

B1 unlocks the preregistered CVRP F1 fixed ancestry decomposition. It does not
prove a production solver improvement, authorize promotion, choose a B2
profile, or justify an automatic rerun. The earlier root ending
`20260718T074602Z-claw` remains a superseded pre-manifest shell and is not
evidence.
