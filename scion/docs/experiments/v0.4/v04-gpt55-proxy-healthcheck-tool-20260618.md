# V0.4 GPT-5.5 Proxy Healthcheck Tool

Date: 2026-06-18

## Purpose

The current launch blocker is the local WSL `gpt-5.5` proxy. `/v1/models` and
dashboard status can be misleading because they may succeed while
`/v1/chat/completions` still fails from an invalidated backend session.

`scion/tools/check_gpt55_proxy.py` makes the required launch gate repeatable:
it performs a real chat-completion request, classifies common auth failures,
and can print a proxy OAuth login URL when completion is unhealthy.

The CVRP and warehouse agentic launchers now call the same helper during
`COMPLETION_PREFLIGHT=1`, so prepared roots and manual checks share one
definition of "LLM route healthy".

## Boundary Check

- This is an infrastructure preflight helper only.
- It does not change Decision, `DecisionFeatures`, Protocol, scheduling, gates,
  lifecycle policy, proposal context, or problem semantics.
- It reinforces the existing rule that live Scion campaigns must not launch
  until `/v1/chat/completions` returns HTTP `200` with non-empty content.
- Launcher integration only changes pre-campaign failure diagnostics. A failed
  healthcheck still exits before Scion starts and writes the existing outer
  wrapper `pre_campaign_completion_preflight=failed` status.

## Usage

On WSL:

```bash
cd /home/xjy-ubuntu/research/or-autoresearch-agent
/home/xjy-ubuntu/miniconda3/envs/scion/bin/python \
  scion/tools/check_gpt55_proxy.py --login-url-on-failure
```

Success criterion:

```text
CHAT_COMPLETION_OK http=200 model=gpt-5.5 content_len=...
```

Failure is explicit, for example:

```text
CHAT_COMPLETION_FAILED http=401 code=invalid_api_key classification=not_authenticated ...
LOGIN_URL=...
```

## Verification

Local:

```bash
PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_gpt55_proxy_check.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py
python -m py_compile \
  scion/tools/check_gpt55_proxy.py \
  scion/tools/launch_cvrp_agentic_campaign.py \
  scion/tools/launch_warehouse_agentic_campaign.py
git diff --check
```

Result:

- `28 passed`
- `py_compile` passed
- `git diff --check` passed

WSL check after installing the tool on commit `04bc996` correctly classified
the live proxy failure as unhealthy without launching a campaign.

## Residual Blocker

No campaign was launched. The WSL proxy still requires re-login before prepared
CVRP or warehouse roots may be started.
