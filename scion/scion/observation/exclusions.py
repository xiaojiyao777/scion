"""Host-loaded Protocol file exclusions, never a provider-visible inventory."""
from pathlib import Path


def formal_file_exclusions(*, problem_spec, split_manifest, source_roots=(), configuration_files=(), split_manager=None):
    spec = getattr(problem_spec, "spec_v1", problem_spec)
    roots = {Path(spec.root_dir).absolute(), *(Path(p).absolute() for p in source_roots)}
    roots.update(Path(p).absolute() for p in getattr(split_manifest, "safe_data_roots", ()) or ())
    cases = []
    if split_manager is not None:
        from scion.core.models import ExperimentStage
        roots.update(Path(p).absolute() for p in split_manager.safe_data_roots())
        for stage in (ExperimentStage.SCREENING, ExperimentStage.VALIDATION, ExperimentStage.FROZEN):
            cases.extend(split_manager.get_cases(stage))
        cases.extend(split_manager.get_canary_cases())
    for name in ("screening", "validation", "frozen", "canary"):
        cases.extend(getattr(split_manifest, name, ()) or ())
    for owner in (spec, problem_spec):
        canary = getattr(owner, "canary_case_path", None)
        if canary:
            cases.append(canary)
    forbidden = {Path(p).resolve() for p in configuration_files}
    for case in cases:
        path = Path(case).expanduser()
        forbidden.update({path.resolve()} if path.is_absolute() else
                         {(root / path).resolve() for root in roots})
    return tuple(sorted(forbidden))
