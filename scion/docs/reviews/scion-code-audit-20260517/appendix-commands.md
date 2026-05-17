# Appendix - Commands And Evidence

All commands were run from `/home/clawd/research/or-autoresearch-agent`. No code was modified by these commands, and no raw `vrp/` research object files were touched.

## Repository State

```bash
git rev-parse --short HEAD
git status --short
git log --oneline -5
```

Key output:

```text
633508a
633508a Document API manifest validation smoke
88e27aa Repair solver-design destroy-repair API context
bc3efa8 Document APS budget validation smoke
63c255f Extend APS repair session budget
8114273 Repair solver-design object model control
```

`git status --short` was clean before adding these review documents.

## Static Evidence Commands

Representative read-only commands:

```bash
rg -n "solver_design|solver_algorithm|required_runtime_fields|complexity_scale_terms" scion/scion/problems/cvrp/problem-v1.yaml
nl -ba scion/scion/contract/gate.py | sed -n '680,760p'
nl -ba scion/scion/contract/gate.py | sed -n '1550,1695p'
nl -ba scion/scion/contract/gate.py | sed -n '1720,1785p'
nl -ba scion/scion/contract/checks/solver_design_integration.py | sed -n '40,190p'
nl -ba scion/scion/proposal/tools.py | sed -n '760,825p'
nl -ba scion/scion/proposal/solver_design_smoke.py | sed -n '55,125p'
nl -ba scion/scion/problems/cvrp/solver.py | sed -n '8430,8495p'
nl -ba scion/scion/protocol/experiment.py | sed -n '490,665p'
nl -ba scion/scion/runtime/subprocess_runner.py | sed -n '20,55p'
```

## Probe 1 - Dynamic Sensitive API Bypass

Command:

```bash
python - <<'PY'
from pathlib import Path
from scion.contract.gate import ContractGate
from scion.core.models import HypothesisProposal, PatchProposal
from scion.problem.bridge import legacy_problem_spec_from_v1, load_problem_spec_v1_from_yaml

root = Path('scion/scion/problems/cvrp').resolve()
spec = load_problem_spec_v1_from_yaml(root / 'problem-v1.yaml')
gate = ContractGate(legacy_problem_spec_from_v1(spec))
h = HypothesisProposal(
    hypothesis_text='Modify branch-owned solver design algorithm body with a bounded constructor.',
    change_locus='solver_design',
    action='modify',
    target_file='policies/baseline_algorithm.py',
    predicted_direction='improve',
    target_objectives=('total_distance',),
    novelty_signature={
        'algorithm_family': 'probe_family',
        'construction_strategy': 'probe_construct',
        'improvement_strategy': 'probe_improve',
        'acceptance_strategy': 'probe_accept',
        'runtime_budget_strategy': 'probe_budget',
    },
)
code = """def solve(instance, rng, time_limit_sec, context):
    __import__('os').system('true')
    return context.nearest_neighbor()
"""
patch = PatchProposal(file_path='policies/baseline_algorithm.py', action='modify', code_content=code)
result = gate.validate_patch(patch, hypothesis=h, selected_surface='solver_design')
print('passed', result.passed)
for check in result.checks:
    if check.name in {'C8_import_whitelist','C9_sensitive_api','C9e_solver_design_integration','C7_interface','C9c_complexity_bound'}:
        print(check.name, check.passed, check.detail)
PY
```

Key output:

```text
passed True
C7_interface True surface interface ok
C8_import_whitelist True imports ok
C9_sensitive_api True no sensitive APIs
C9c_complexity_bound True complexity ok
C9e_solver_design_integration True new solver_design helper functions are integrated
```

## Probe 2 - Preferred Baseline Wrapper Passes Core ContractGate

Command:

```bash
python - <<'PY'
from pathlib import Path
from scion.contract.gate import ContractGate
from scion.core.models import HypothesisProposal, PatchProposal
from scion.problem.bridge import legacy_problem_spec_from_v1, load_problem_spec_v1_from_yaml

root = Path('scion/scion/problems/cvrp').resolve()
spec = load_problem_spec_v1_from_yaml(root / 'problem-v1.yaml')
gate = ContractGate(legacy_problem_spec_from_v1(spec))
h = HypothesisProposal(
    hypothesis_text='Modify branch-owned solver design algorithm body.',
    change_locus='solver_design',
    action='modify',
    target_file='policies/baseline_algorithm.py',
    predicted_direction='improve',
    target_objectives=('total_distance',),
    novelty_signature={
        'algorithm_family': 'probe_family',
        'construction_strategy': 'probe_construct',
        'improvement_strategy': 'probe_improve',
        'acceptance_strategy': 'probe_accept',
        'runtime_budget_strategy': 'probe_budget',
    },
)
code = """def solve(instance, rng, time_limit_sec, context):
    return context.baseline(time_budget_sec=context.remaining_time())
"""
patch = PatchProposal(file_path='policies/baseline_algorithm.py', action='modify', code_content=code)
result = gate.validate_patch(patch, hypothesis=h, selected_surface='solver_design')
print('passed', result.passed)
for check in result.checks:
    if check.name in {'C7_interface','C9_sensitive_api','C9e_solver_design_integration'}:
        print(check.name, check.passed, check.detail)
PY
```

Key output:

```text
passed True
C7_interface True surface interface ok
C9_sensitive_api True no sensitive APIs
C9e_solver_design_integration True new solver_design helper functions are integrated
```

## Probe 3 - Dead Helper Reference Passes C9e

Command:

```bash
python - <<'PY'
from pathlib import Path
from scion.contract.gate import ContractGate
from scion.core.models import HypothesisProposal, PatchProposal
from scion.problem.bridge import legacy_problem_spec_from_v1, load_problem_spec_v1_from_yaml

root = Path('scion/scion/problems/cvrp').resolve()
spec = load_problem_spec_v1_from_yaml(root / 'problem-v1.yaml')
gate = ContractGate(legacy_problem_spec_from_v1(spec))
h = HypothesisProposal(
    hypothesis_text='Modify branch-owned solver design algorithm body.',
    change_locus='solver_design',
    action='modify',
    target_file='policies/baseline_algorithm.py',
    predicted_direction='improve',
    target_objectives=('total_distance',),
    novelty_signature={
        'algorithm_family': 'probe_family',
        'construction_strategy': 'probe_construct',
        'improvement_strategy': 'probe_improve',
        'acceptance_strategy': 'probe_accept',
        'runtime_budget_strategy': 'probe_budget',
    },
)
code = """def solve(instance, rng, time_limit_sec, context):
    unused = helper
    return context.nearest_neighbor()

def helper(instance, rng, time_limit_sec, context):
    return context.nearest_neighbor()
"""
patch = PatchProposal(file_path='policies/baseline_algorithm.py', action='modify', code_content=code)
result = gate.validate_patch(patch, hypothesis=h, selected_surface='solver_design')
print('passed', result.passed)
for check in result.checks:
    if check.name in {'C9e_solver_design_integration'}:
        print(check.name, check.passed, check.detail)
PY
```

Key output:

```text
passed True
C9e_solver_design_integration True new solver_design helper functions are integrated
```

## Experiment Artifact Reads

Commands:

```bash
python - <<'PY'
import json
from pathlib import Path

for root in [
    Path('/home/clawd/research/scion-experiments/v04-api-manifest-sonnet-3r-20260517T034512Z/campaign'),
    Path('/home/clawd/research/scion-experiments/v04-api-manifest-sonnet-6r-20260517T042338Z/campaign'),
]:
    print('ROOT', root)
    for name in ['status.json','campaign_summary.json']:
        path = root / name
        print('FILE', name, 'exists=', path.exists())
        if path.exists():
            data = json.loads(path.read_text())
            print('keys', list(data.keys())[:30])
            for k in ['updated_at','n_steps','stopped_reason']:
                if k in data:
                    print(k, data[k])
    print('---')
PY
```

Key output:

```text
ROOT /home/clawd/research/scion-experiments/v04-api-manifest-sonnet-3r-20260517T034512Z/campaign
FILE status.json exists= True
updated_at 2026-05-17T04:18:13.027607+00:00
n_steps 3
stopped_reason max_rounds_exhausted
FILE campaign_summary.json exists= True
stopped_reason max_rounds_exhausted
---
ROOT /home/clawd/research/scion-experiments/v04-api-manifest-sonnet-6r-20260517T042338Z/campaign
FILE status.json exists= True
updated_at 2026-05-17T04:59:18.682323+00:00
n_steps 4
FILE campaign_summary.json exists= False
---
```

3-round summary step extraction:

```text
steps 3 stopped max_rounds_exhausted
round 1 decision abandon decision_reason_codes ['SCREENING_FAIL_WIN_RATE'] selected_surface solver_design
round 2 decision abandon decision_reason_codes ['SCREENING_FAIL_WIN_RATE'] selected_surface solver_design
round 3 decision abandon decision_reason_codes ['SCREENING_FAIL_WIN_RATE'] selected_surface solver_design
```

6-round launch evidence:

```text
COMMAND: /home/clawd/miniconda3/envs/claw/bin/python -m scion.cli.main run --problem scion/problems/cvrp/problem.yaml --protocol scion/problems/cvrp/formal/protocol.yaml --split scion/problems/cvrp/formal/split_manifest.yaml --seeds scion/problems/cvrp/formal/seed_ledger.yaml --campaign-dir /home/clawd/research/scion-experiments/v04-api-manifest-sonnet-6r-20260517T042338Z/campaign --rounds 6 --time-limit-sec 10 --disable-early-stop --agentic-proposal --agentic-session-timeout-sec 240
export SCION_PROBLEM_DATA_ROOT=/home/clawd/research/or-autoresearch-agent/vrp
```

