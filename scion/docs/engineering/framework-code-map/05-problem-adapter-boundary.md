# Problem Adapter Boundary

## Scope / Sources

Sources read: `scion/scion/problem/spec.py`, `contracts.py`, `bridge.py`, `loader.py`, `objectives.py`, `scion/scion/config/problem.py`, CLI loading in `scion/scion/cli/main.py`, adapter-backed verification in `scion/scion/verification/`, `ExperimentProtocol` metric handling in `scion/scion/protocol/experiment.py`, runner contract in `scion/scion/runtime/runner.py`, and `LocalSubprocessRunner` in `scion/scion/runtime/subprocess_runner.py`.

## Authoritative Schema

`ProblemSpecV1` in `scion/scion/problem/spec.py` is the intended authoritative problem schema. It is strict Pydantic with `extra="forbid"` and includes:

- problem id/display/root/description;
- search space editable/frozen/import whitelist;
- solver and parameter search settings;
- operator interface and execute signature;
- research surfaces;
- objective policy and ordered objective metrics;
- LLM hints and family taxonomy;
- adapter import path;
- legacy compatibility fields for current campaign runtime.

Objective names must be unique, priorities must be contiguous `1..N`, weighted-sum objectives must all provide positive weights, research surface names must be unique, and adapter import path must live under `scion.problems.<id>.`.

## Bridge to Legacy Runtime

Campaign core still consumes legacy `ProblemSpec` from `scion/scion/config/problem.py`. The bridge in `scion/scion/problem/bridge.py` is the narrow compatibility layer:

- `load_problem_spec_v1_from_yaml()` loads strict v1 YAML and resolves `root_dir`.
- `legacy_problem_spec_from_v1()` converts v1 fields to legacy `ProblemSpec`.
- `bridge_problem_spec_v1()` returns a bundle containing legacy `ProblemSpec`, metric specs, objective policy, and operator execute signature.

The bridged legacy `ProblemSpec` also carries generic adapter metadata:
`spec_version="problem-v1"`, `adapter_import_path`, and
`requires_adapter_for_runtime=True`. These fields are compatibility metadata
for gate construction only; problem semantics still belong to the adapter and
problem package.

The CLI in `scion/scion/cli/main.py` reads legacy `problem.yaml`, then replaces it with bridged `problem-v1.yaml` data when present. It also loads the adapter and passes metric specs/objective policy to `ExperimentProtocol`.

## Adapter Contract

`ProblemAdapter` in `scion/scion/problem/contracts.py` is the framework/problem boundary. Core expects:

- prompt rendering: `render_problem_summary()`, `render_operator_interface()`;
- optional problem-object rendering: `render_problem_object()` for adapters
  that can expose instance model, solution model, objective policy, solver
  lifecycle, move/design grammar, and runtime evidence as one coherent object;
- instance loading: `load_instance(instance_path)`;
- solver output normalization: `deserialize_solver_output(raw_output, instance) -> SolverArtifact`;
- verification: `check_solution_consistency()`, `check_feasibility()`, `recompute_objective()`;
- optional lower-bound estimates for saturation analysis.

`SolverArtifact` carries raw output, objective mapping, feasible boolean, and optional problem-native normalized solution. Core should treat normalized solution as opaque.

`load_problem_adapter()` in `scion/scion/problem/loader.py` imports and instantiates adapters only from `scion.problems.<id>.*`.

`ContextManager` and APS `context.read_problem` consume optional
`render_problem_object()` when present. This is still adapter-owned prompt
context; core does not interpret the problem semantics inside that text.

## Metric Specs and Objective Policy

Objective comparison is problem-agnostic when metric specs are present. `scion/scion/problem/objectives.py` supports:

- lexicographic comparison by priority and direction;
- weighted-sum comparison with per-component weights;
- per-metric signed deltas and decisive metric reporting.

`ExperimentProtocol` uses metric specs/objective policy for candidate-vs-champion comparison. Production CLI sets `require_metric_specs=True` when metric specs come from `ProblemSpecV1`, so missing specs fail rather than falling back.

The legacy fallback in `scion/scion/protocol/evaluation.py` is generic minimization over objective keys, but it lacks problem-owned directions/tolerances and should not be used for new production problem packages.

## Runner Boundary

The runtime runner boundary is `Runner.run_solver()` in `scion/scion/runtime/runner.py`. It is problem-agnostic:

- workspace path;
- instance path string;
- seed;
- time limit;
- registry path.

`LocalSubprocessRunner` runs `solver.py` in the workspace, uses resource limits, sanitizes environment, forces `PYTHONHASHSEED=0`, and allows only `PATH`, `PYTHONPATH`, and `SCION_*` environment variables. It parses solver JSON into a generic `SolverOutput` with objective, feasible flag, and runtime audit dict.

Solver `runtime` output is also the evidence surface for
`research_surfaces` v2. Problem packages declare required runtime fields on a
surface with `evidence.required_runtime_fields`; Scion core only checks generic
presence, empty values, obvious `*_errors` counts, and generic
`*_loaded`/`*_executed`/`*_active` truthiness. Problem-specific interpretation
stays in the package's solver, adapter rendering, and evidence docs.

Problem packages can use `SCION_*` env vars to resolve external data roots without core naming problem-specific variables.

## Adapter-Backed Verification

Verification checks V5/V6/V7/V8 are where problem semantics should enter runtime validation:

- V5 solution consistency calls `adapter.deserialize_solver_output()` and `adapter.check_solution_consistency()`.
- V6 feasibility calls adapter load/deserialize/consistency/feasibility.
- V7 objective calls adapter load/deserialize/recompute, requires declared
  objective metric names to exist in reported and recomputed objective maps,
  and compares auxiliary recomputed keys only when both sides report them.
- V8 nondeterminism calls adapter load/deserialize for both same-seed canary
  runs and compares a stable canonical artifact signature. The default
  signature uses normalized solution, adapter-filtered objective, and feasible
  flag; adapters may optionally expose a dynamic canonical fingerprint method.

`VerificationGate` can enforce fail-closed behavior with `strict_runtime_checks=True` and `require_adapter_for_runtime=True`. For bridged `ProblemSpecV1` packages, adapter-required metadata now makes this fail-closed behavior automatic even if the adapter object is accidentally omitted: V5/V6/V7/V8 return heavy verification failures instead of using legacy fallback paths.

Selected-surface runtime audit is enforced during verification when
`VerificationGate.run()` receives selected-surface metadata, normally from
`HypothesisProposal.change_locus`. It is also enforced on candidate-side canary
and screening/validation/frozen protocol runs when `ExperimentProtocol` is
constructed with a problem spec that declares research surfaces. The protocol
receives `selected_surface` through `EvaluationRequest`, passes the active
problem spec and surface name into `scion.runtime.audit`, and fails closed when
declared `evidence.required_runtime_fields` are missing, empty, or explicitly
failed. Champion-side protocol audit remains generic so a champion workspace is
not rejected for lacking candidate-surface evidence fields.

## Places Core Should Not Hardcode Problem Semantics

Avoid adding warehouse or CVRP-specific logic to these framework areas:

- `ContractGate` research-surface validation should use `ProblemSpecV1.research_surfaces`, not fixed categories.
- `VerificationGate` should call adapter methods for V5/V6/V7/V8, not reconstruct problem-native objects.
- `ExperimentProtocol` should use metric specs/objective policy, not fixed metric names.
- `ContextManager` should render adapter/problem spec summaries and research surfaces, not domain text directly.
- `SafeFeatureExtractor` and `DecisionEngine` should operate on generic stats/runtime fields, not problem-specific objective names.
- `LineageRegistry` and `EvidenceRecorder` should store generic evidence plus refs; problem-specific final evidence belongs under `scion/scion/evidence/` or the problem package.

Known current risk areas:

- `scion/scion/verification/state_mutation.py` legacy fallback still assumes
  `assignment`/`vehicles` output structure, but bridged adapter-required
  problem-v1 specs are isolated from that fallback.
- V6/V7 legacy oracle fallback and V8 objective-only comparison remain
  compatibility paths only; bridged adapter-required problem-v1 specs are
  isolated from them.
- `scion/scion/contract/gate.py` complexity guard now prefers v2 surface
  `bounds.complexity_scale_terms`; route/customer/order/vehicle names remain as
  a legacy-only fallback when surface metadata is absent.
- `scion/scion/contract/gate.py` also enforces generic research-surface
  governance before candidate code runs: file-read APIs are forbidden even in
  read-only mode, and non-operator policy/config/portfolio/construction/
  acceptance_restart/solver_design or singleton surfaces cannot access
  `instance.name` or direct `getattr`/`hasattr` probes for that name. Problem
  packages should expose safe structural instance APIs instead of case
  identifiers.
- Custom protocol stubs or legacy protocols that do not carry problem specs with
  declared research surfaces remain on the compatibility path and do not receive
  automatic selected-surface forwarding from `EvaluationPipeline`.
- CVRP final evidence modules are correctly outside core, but any reuse by another problem should go through generic `final_quality.py` or a new problem-specific adapter.

New problem packages should make adapter-backed verification mandatory and avoid relying on legacy oracle/output fallbacks.
