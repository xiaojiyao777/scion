# v0.4 GPT-5.5 Proxy Format Alias

Date: 2026-06-19

## Purpose

During the current launch-auth check, `check_gpt55_proxy.py` rejected
`--format json` even though the surrounding Scion readiness tools use
`--format json` for machine-readable output. The tool already supported
`--json`; this repair adds `--format {text,json}` as a compatible operator
interface while preserving `--json`, probe semantics, and exit codes.

This is an operator-readiness repair only. It does not change LLM transport,
proposal behavior, protocol gates, `DecisionFeatures`, or problem semantics.

## Verification

Focused regression:

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_gpt55_proxy_check.py
```

Result: `5 passed in 0.22s`.

CLI surface check:

```bash
python scion/tools/check_gpt55_proxy.py --help | rg -- '--format|--json|--login-url-on-failure'
```

Confirmed that help exposes `--format {text,json}`, `--json`, and
`--login-url-on-failure`.

JSON parse check on an intentionally unreachable local port:

```bash
python scion/tools/check_gpt55_proxy.py \
  --base-url http://127.0.0.1:9 \
  --model gpt-5.5 \
  --api-key pwd \
  --timeout-sec 0.2 \
  --format json
```

Result: output parsed as JSON with `ok=false` and
`chat.classification=transport_error`; exit code remained `64`.

## Current Auth Status

The live WSL proxy is still not launch-ready. The latest WSL probe using the
same tool reports:

- `ok=false`
- chat HTTP `401`
- `classification=not_authenticated`
- `code=invalid_api_key`
- auth pool `active=0`, `refreshing=1`, `total=1`

The prepared warehouse and CVRP roots must still wait for strict launch
readiness to report `launch_ready=true`.
