# CVRP M18 `_or_opt` fixed-candidate confirmation preregistration

**State:** `TERMINAL_COMPLETED_CONFIRMATION_NOT_SUPPORTED`

M18 is a new one-shot label for the mechanical Protocol-shape correction found
by M17 before its first formal pair. Candidate, B0, six cases, four formal
seeds, canary, ordering, time limits, numerical gates, 50-subprocess budget,
5,400-second hardwall and claim boundary are byte-for-byte or value-for-value
unchanged. Only the latent initial declaration changes from 6 cases / 4 seeds
to 3 cases / 2 seeds, so the already frozen 6 / 4 execution is a valid expanded
screen. M18 does not consume or interpret the M17 canary as scientific evidence;
it reruns its own strict canary.

The scientific question and claim limits are exactly those in the preserved
[M17 record](v04-cvrp-m17-oropt-fixed-candidate-confirmation-preregistration-20260820.md).
Provider, H, C, patch, retry, resume, validation, frozen, promotion and
automatic-next-round counts remain zero. Any completed negative or incomplete
screen is a valid terminal result and stops.

The fresh output root is
`/home/clawd/research/scion-experiments/v04-cvrp-m18-oropt-confirmation-20260820`.
The read-only source/data input root is unchanged.

```bash
cd /home/clawd/research/or-autoresearch-agent/scion
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion:/home/clawd/.local/lib/python3.12/site-packages:/home/clawd/miniconda3/envs/claw/lib/python3.12/site-packages \
PYTHONDONTWRITEBYTECODE=1 \
/home/clawd/miniconda3/envs/claw/bin/python -S -B \
  /home/clawd/research/or-autoresearch-agent/scion/run_fixed_candidate_screen.py \
  --config /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m18-confirmation-population.json \
  --input-root /home/clawd/research/or-autoresearch-agent/campaign_out/v04-cvrp-m17-oropt-confirmation-20260820-input \
  --output-dir /home/clawd/research/scion-experiments/v04-cvrp-m18-oropt-confirmation-20260820
```

## Terminal result

M18 completed once from carrier `1703d22528ffd5d8403bfbd708294300c2acd915`.
It used exactly 50 solver subprocesses, 2,660 nominal subject-seconds and
3,410 positive guarded seconds. No provider, H, C, patch, retry, validation,
frozen, promotion or automatic next-round action ran. The subject-workspace
directory was empty after completion.

The expanded screen attempted all 24 declared pairs. Twenty pairs were valid;
four `X-n627-k43` pairs were shared champion-and-candidate construction
failures (`unable to pack customer 624 into 43 routes`). Candidate-only and
bilateral failures were both zero. Among the five valid case aggregates,
`A-n37-k5`, `B-n51-k7`, `P-n50-k8` and `X-n237-k14` tied. `X-n351-k40`
improved by 26.5 distance units. The aggregate result was one win, zero losses
and four ties with median delta `0` and CI `[0, 26.5]`.

Protocol returned `fail` with
`SCREENING_FAIL_CASE_QUALITY` and
`SCREENING_PARTIAL_CHAMPION_EVIDENCE`. Safe Features and Decision therefore
returned `continue_explore / SCREENING_PARTIAL_CHAMPION_EVIDENCE`; the driver
wrote terminal type `CONFIRMATION_NOT_SUPPORTED`. Runtime evidence does not
support the intended speed mechanism: the median candidate/champion runtime
ratio was `0.9998438773735676`, median runtime delta was `-6.5 ms`, and the
runtime regression rate was `0.4` across 20 valid pairs.

The defensible conclusion is narrow. The exact M16 candidate remained safe on
the new population and produced one quality improvement, but the fixed
confirmation gate did not support it as a general improvement and did not
show a meaningful wall-clock speedup. The four shared failures diagnose a B0
construction limitation, not a candidate regression. No independent
discovery, isolated `_or_opt` causal effect, validation/frozen success,
promotion, global CVRP generalization or production-readiness claim is made.

Durable outputs are preserved at
`/home/clawd/research/scion-experiments/v04-cvrp-m18-oropt-confirmation-20260820`.
