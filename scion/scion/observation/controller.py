"""Host composition and selected source preparation for public research."""
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
import tempfile
import logging

from scion.contract.checks.targeting import check_patch_action_target
from scion.contract.surface_access import SurfaceAccess
from scion.observation.config import PublicResearchStop, normalize_public_research
from scion.observation.exclusions import formal_file_exclusions
from scion.observation.service import ObservationService
from scion.observation.source import ObservationError, SourceBinding, SourceCopier, prepare_source
from scion.problem.public_input import PublicInputError
from scion.problem.public_observation import resolve_public_observation_provider, PublicObservationConfigurationError
from scion.verification.development import development_safety_preflight_failure


class PublicResearchController:
    def __init__(self, *, service, problem_spec, split_manifest, source_roots,
                 configuration_files=(), materializer=None, sync_configuration=None, split_manager=None):
        self.service = service
        self.problem_spec, self.split_manifest = problem_spec, split_manifest
        self.split_manager = split_manager
        self.source_roots = tuple(Path(p) for p in source_roots)
        self.configuration_files = tuple(configuration_files)
        self.materializer, self.sync_configuration = materializer, sync_configuration
        self.session_count = 0
        self.active = None
        self.handoff_count = 0
        self.initial_config = None
        self.observation_enabled = True
        self.continuity = None
        self.failure_reason = None

    def exclusions(self, root):
        return formal_file_exclusions(problem_spec=self.problem_spec,
            split_manifest=self.split_manifest, source_roots=(*self.source_roots, root),
            configuration_files=self.configuration_files, split_manager=self.split_manager)

    def open_session(self, *, phase, source_root, initial_source=False,
                     approved_hypothesis=None, handoff=None, branch="campaign"):
        from scion.observation.session import PublicResearchSession
        if self.active is not None:
            self.active.close()
        if self.failure_reason:
            raise PublicResearchStop(self.failure_reason, phase=phase)
        if phase not in {"hypothesis", "code"} or (phase == "code" and approved_hypothesis is None):
            raise PublicResearchStop("INTERNAL_ERROR", phase=phase)
        if handoff is not None and (phase != "code" or handoff.hypothesis != approved_hypothesis
                or handoff.source_root != str(source_root) or handoff.initial_source != initial_source):
            raise PublicResearchStop("H_BINDING_REJECTED", phase=phase)
        self.session_count += 1
        self.service.begin_session()
        self.service.forbidden_files = self.exclusions(Path(source_root))
        self.active = PublicResearchSession(self, phase=phase, source_root=Path(source_root),
            initial_source=initial_source, approved_hypothesis=deepcopy(approved_hypothesis), handoff=handoff, branch=branch)
        try:
            with self.service.account_host_work():
                if self.continuity is not None:
                    self.active.source_condition = self.continuity.retain_source(source_root, branch=branch)
                    if phase == "hypothesis":
                        self.active.entries.extend(self.continuity.visible_entries())
                self.active.persist_index()
        except ObservationError as error:
            raise PublicResearchStop("GLOBAL_RESEARCH_LIMIT" if self.continuity is not None and error.reason_code == "LIMIT_NOT_AVAILABLE" else error.reason_code, phase=phase) from None
        except OSError:
            raise PublicResearchStop("PERSISTENCE_ERROR", phase=phase) from None
        return self.active

    def retain_before_cleanup(self, root, branch, kind):
        if self.continuity is None:
            return True
        if self.failure_reason:
            return False
        try:
            with self.service.account_host_work():
                self.continuity.retain_source(root, branch=branch, kind=kind)
            if self.service.stopped:
                raise ObservationError("GLOBAL_RESEARCH_LIMIT")
            return True
        except (Exception, KeyboardInterrupt) as error:
            self.record_material_failure(error)
            return False

    def record_material_failure(self, error):
        reason = ("USER_INTERRUPTED" if isinstance(error, KeyboardInterrupt) else
                  error.reason_code if isinstance(error, ObservationError) else
                  "PERSISTENCE_ERROR" if isinstance(error, OSError) else "INTERNAL_ERROR")
        if reason == "LIMIT_NOT_AVAILABLE":
            reason = "GLOBAL_RESEARCH_LIMIT"
        self.failure_reason = self.failure_reason or reason
        logging.getLogger(__name__).error("Research material retention failed: %s", reason)
        try:
            self.service._json(self.service.materials.root / "material_failure.json", {"reason_code": self.failure_reason})
        except (Exception, KeyboardInterrupt):
            pass  # In-memory stop remains effective when the filesystem is unavailable.

    @contextmanager
    def selected_source(self, session, role, patch=None):
        svc = self.service
        root = session.source_root
        svc.forbidden_files = self.exclusions(root)
        temporary = None
        try:
            if role == "draft":
                if patch is None:
                    raise ObservationError("DRAFT_PREFLIGHT_REJECTED")
                access = SurfaceAccess(self.problem_spec)
                for index, change in enumerate(patch.iter_file_changes()):
                    from scion.core.models import PatchProposal
                    single = PatchProposal(file_path=change.file_path, action=change.action,
                                           code_content=change.code_content)
                    if not check_patch_action_target(single, session.approved_hypothesis if index == 0 else None,
                        surface_access=access, selected_surface=session.approved_hypothesis.change_locus,
                        enforce_hypothesis_target=index == 0).passed:
                        raise ObservationError("H_BINDING_REJECTED")
                temporary = self.materializer.create_empty_candidate_workspace()
                root = Path(temporary)
                copier = SourceCopier(forbidden_files=svc.forbidden_files,
                    max_files=svc.budget.max_files_per_action, max_bytes=svc.budget.max_source_bytes)
                for path in svc.spec.subject_workspace_paths:
                    copier.copy(session.source_root, path, root)
                for path in svc.spec.subject_optional_workspace_paths:
                    copier.copy(session.source_root, path, root, optional=True)
                # The same base/draft materializer used by the formal path; no execution.
                try:
                    self.materializer.apply_ephemeral_patch(str(root), patch)
                except (ValueError, FileNotFoundError):
                    raise ObservationError("DRAFT_PREFLIGHT_REJECTED") from None
                if development_safety_preflight_failure(patch=patch, problem_spec=self.problem_spec,
                                                        candidate_workspace=str(root)) is not None:
                    raise ObservationError("DRAFT_PREFLIGHT_REJECTED")
                if self.sync_configuration is not None:
                    self.sync_configuration(str(root), session.approved_hypothesis, patch)
            available = tuple(p for p in svc.spec.subject_optional_workspace_paths if (root / p).is_file())
            try:
                # The initial mode was selected at composition. A disappearing
                # registry may not silently turn that same base into defaults.
                config = (deepcopy(self.initial_config) if session.initial_source and role != "draft"
                          else svc.provider.source_config(available, initial=False))
                if config is None:
                    raise ObservationError("SOURCE_UNAVAILABLE")
            except PublicInputError:
                raise ObservationError("SOURCE_UNAVAILABLE") from None
            # Include relative formal paths in disposable copies as well.
            svc.forbidden_files = tuple(set(svc.forbidden_files) | set(self.exclusions(root)))
            yield SourceBinding(root, role, f"session-{session.ordinal:06d}/{role}", config)
        finally:
            if temporary is not None:
                self.materializer.cleanup_candidate_workspace(temporary)

    def validate_initial_closure(self, root):
        svc = self.service
        with svc.account_host_work():
            with tempfile.TemporaryDirectory(prefix=".closure-", dir=svc.materials.root) as directory:
                destination = Path(directory)
                binding = SourceBinding(Path(root), "current", "initial", {})
                available = prepare_source(binding=binding, problem_root=svc.problem_root,
                    framework_root=svc.framework_root, spec=svc.spec, destination=destination,
                    copier=SourceCopier(forbidden_files=self.exclusions(Path(root)),
                        max_files=svc.budget.max_files_per_action, max_bytes=svc.budget.max_source_bytes))
                config = svc.provider.source_config(available, initial=True)
                svc.provider.validate_source_config(config, available)
                self.initial_config = deepcopy(config)
                # Public fixtures become ordinary readable inputs, without host paths.
                self.fixtures = []
                for path in svc.spec.fixture_paths:
                    raw = (destination / "public" / path).read_bytes()
                    svc.provider.validate_input(svc._decode(raw))
                    ref = svc.materials.append("input", raw)
                    self.fixtures.append({"ref": ref, "kind": "input", "bytes": len(raw),
                                          "phase": "public", "source_condition": None})


def compose_public_research(*, configuration, adapter, problem_spec, split_manifest,
                            source_root, initial_source_root, output_root, code_research_limits,
                            configuration_files=(), materializer=None, sync_configuration=None, experiment_protocol=None, research_material_imports=()):
    config = normalize_public_research(configuration)
    if research_material_imports and not config.research_materials_enabled:
        raise PublicResearchStop("OBS_CONFIG_INVALID")
    if not (config.public_observation_enabled or config.research_materials_enabled):
        return None
    if code_research_limits is None:
        raise PublicResearchStop("OBS_CONFIG_INVALID")
    split_manager = getattr(experiment_protocol, "split_manager", None)
    if experiment_protocol is not None and split_manager is None:
        raise PublicResearchStop("OBS_CONFIG_INVALID")
    try:
        provider = resolve_public_observation_provider(adapter, enabled=True)
        if not callable(getattr(provider, "source_config", None)):
            raise PublicResearchStop("OBS_PROVIDER_INVALID")
        spec = getattr(problem_spec, "spec_v1", problem_spec)
        service = ObservationService(provider=provider, problem_root=Path(spec.root_dir),
            framework_root=Path(__file__).resolve().parents[1], output_root=Path(output_root),
            forbidden_files=(), budget=config.budget)
        controller = PublicResearchController(service=service, problem_spec=problem_spec,
            split_manifest=split_manifest, source_roots=(initial_source_root, source_root),
            configuration_files=configuration_files, materializer=materializer,
            sync_configuration=sync_configuration, split_manager=split_manager)
        controller.observation_enabled = config.public_observation_enabled
        controller.validate_initial_closure(initial_source_root)
        # Snapshot paths too: copying a file cannot erase its formal-path exclusion.
        with tempfile.TemporaryDirectory(prefix=".closure-", dir=service.materials.root) as directory:
            prepare_source(binding=SourceBinding(Path(source_root), "current", "initial", {}),
                problem_root=service.problem_root, framework_root=service.framework_root,
                spec=service.spec, destination=Path(directory),
                copier=SourceCopier(forbidden_files=controller.exclusions(Path(source_root)),
                    max_files=config.budget.max_files_per_action, max_bytes=config.budget.max_source_bytes))
        from dataclasses import asdict
        service._json(service.materials.root / "configuration.json", asdict(config))
        if config.research_materials_enabled:
            from scion.observation.continuity import ResearchContinuity
            with service.account_host_work():
                controller.continuity = ResearchContinuity(controller)
                for directory in research_material_imports:
                    controller.continuity.import_directory(directory)
                controller.continuity.retain_source(source_root, kind="initial_baseline")
            if service.stopped:
                raise ObservationError("GLOBAL_RESEARCH_LIMIT")
        return controller
    except PublicObservationConfigurationError as error:
        raise PublicResearchStop(error.reason_code) from None
    except ObservationError as error:
        raise PublicResearchStop("GLOBAL_RESEARCH_LIMIT" if config.research_materials_enabled and error.reason_code == "LIMIT_NOT_AVAILABLE" else error.reason_code) from None
    except PublicInputError:
        raise PublicResearchStop("OBS_CONFIG_INVALID") from None
    except OSError:
        raise PublicResearchStop("PERSISTENCE_ERROR") from None
