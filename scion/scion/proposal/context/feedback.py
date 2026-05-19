"""Proposal-visible feedback and memory renderers.

This module owns prompt-facing feedback exposure policy for normalized
framework facts. It renders screening-stage and pre-protocol proposal feedback
only; validation/frozen per-case detail and raw metrics are not exposed here.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, List, Mapping, Optional

from scion.core.models import ExperimentStage, StepRecord
from scion.proposal.mechanism_labels import extract_mechanism_label

_SAFE_PRE_PROTOCOL_FAILURE_STAGES = {
    "agent_quality_blocked",
    "proposal",
    "hypothesis_contract",
    "code_generation",
    "patch_contract",
    "workspace",
    "verification",
}


def _is_screening_protocol_step(step: StepRecord) -> bool:
    return (
        step.protocol_result is not None
        and step.protocol_result.stage == ExperimentStage.SCREENING
    )


def _is_safe_pre_protocol_failure_step(step: StepRecord) -> bool:
    return (
        step.protocol_result is None
        and step.failure_stage in _SAFE_PRE_PROTOCOL_FAILURE_STAGES
    )


def _is_promotion_path_step(step: StepRecord) -> bool:
    decision = getattr(step.decision, "value", step.decision)
    return str(decision or "").lower() == "promote"


def _promotion_path_key(step: StepRecord) -> tuple[str, str, str, str, str]:
    hypothesis = step.hypothesis
    return (
        step.branch_id,
        hypothesis.hypothesis_text or "",
        hypothesis.change_locus or "",
        hypothesis.action or "",
        hypothesis.target_file or "",
    )


def _filter_hypothesis_prompt_steps(
    step_history: List[StepRecord],
) -> List[StepRecord]:
    """Keep only protocol facts allowed into hypothesis prompts."""
    promotion_path_keys = {
        _promotion_path_key(step)
        for step in step_history
        if _is_promotion_path_step(step)
    }
    return [
        step
        for step in step_history
        if _promotion_path_key(step) not in promotion_path_keys
        and (
            _is_screening_protocol_step(step)
            or _is_safe_pre_protocol_failure_step(step)
        )
    ]


def _history_step_status(step: StepRecord) -> str:
    if _is_screening_protocol_step(step):
        return f"SCREENING_{step.protocol_result.gate_outcome.upper()}"
    if _is_safe_pre_protocol_failure_step(step):
        return f"FAILED_{str(step.failure_stage).upper()}"
    return "HIDDEN"


def _build_agent_quality_feedback(
    step_history: List[StepRecord],
    branch_id: str,
) -> str:
    """Render recent proposal-only quality blocks for the next hypothesis.

    This is tainted proposal context, not Decision input. It keeps exact smoke
    diagnostics visible enough for the next LLM step to avoid repeating a patch
    that failed before protocol, while validation/frozen data remain excluded.
    """

    branch_steps = [
        step
        for step in _filter_hypothesis_prompt_steps(step_history)
        if step.branch_id == branch_id
    ]
    lines: list[str] = []
    for step in reversed(branch_steps):
        summary = _agent_quality_failure_summary(step)
        if not summary:
            continue
        lines.append(summary)
        if len(lines) >= 4:
            break
    if not lines:
        return ""
    return "\n".join(
        [
            "Recent proposal-only quality blocks before screening:",
            *reversed(lines),
            (
                "Use these as repair signals for the next hypothesis/code path; "
                "they do not retire the solver_design boundary or affect "
                "DecisionFeatures."
            ),
        ]
    )


def _agent_quality_failure_summary(step: StepRecord) -> str:
    ref = step.proposal_session_ref if isinstance(step.proposal_session_ref, Mapping) else {}
    primary = ref.get("primary_failure") if isinstance(ref, Mapping) else None
    if not isinstance(primary, Mapping):
        primary = {}
    stage = str(primary.get("stage") or step.failure_stage or "").strip()
    reason = str(primary.get("reason") or "").strip()
    category = str(primary.get("category") or "").strip()
    code = str(primary.get("code") or "").strip()
    detail = str(primary.get("detail") or step.failure_detail or "").strip()
    combined = " ".join((stage, reason, category, code, detail)).lower()
    if (
        stage != "agent_quality_blocked"
        and step.failure_stage != "agent_quality_blocked"
        and "algorithm_smoke_failure" not in combined
        and "proposal_premise_contradicted" not in combined
    ):
        return ""
    label = code or reason or category or stage or "agent_quality_blocked"
    target = step.hypothesis.target_file or "(no target_file)"
    detail = _first_line(detail)[:900]
    line = (
        f"- round {step.round_num}: {label}; "
        f"target={target}; action={step.hypothesis.action}; "
        f"locus={step.hypothesis.change_locus}"
    )
    if category and category != label:
        line += f"; category={category}"
    if detail:
        line += f"; detail={detail}"
    return line


def _build_experiment_history(
    step_history: List[StepRecord],
    branch_id: str,
    taxonomy: Optional[list] = None,
) -> str:
    """Build structured experiment history with case-level feedback.

    T26: Includes "What Worked" section before "What Failed" to prevent
    the model from becoming overly conservative after many failures.

    Recent 3 rounds: aggregate + pattern + selected cases.
    Older rounds (4-8): aggregate only.
    Consecutive 3+ same-type verification failures -> inject diagnosis block.
    """
    branch_steps = [
        s for s in _filter_hypothesis_prompt_steps(step_history)
        if s.branch_id == branch_id
    ]
    if not branch_steps:
        return "(no prior experiment rounds on this branch)"

    what_worked = _build_what_worked_section(branch_steps, taxonomy=taxonomy)

    recent = branch_steps[-8:]
    lines: List[str] = []
    n_recent = len(recent)

    if what_worked:
        lines.append(what_worked)

    for idx, s in enumerate(recent):
        is_detailed = idx >= max(0, n_recent - 3)
        status = _history_step_status(s)
        line = f"  Round {s.round_num} [{status}]"
        line += f"  hypothesis: {s.hypothesis.change_locus}/{s.hypothesis.action}"
        if s.hypothesis.target_file:
            line += f" → {s.hypothesis.target_file}"
        line += f"\n    hypothesis_text: {s.hypothesis.hypothesis_text}"
        if s.failure_stage:
            line += f"\n    failed_at: {s.failure_stage}"
            if s.failure_stage == "verification" and s.verification_detail:
                detail_str = s.verification_detail[:200]
                line += f" — {detail_str}"
            else:
                detail_str = _pre_protocol_failure_detail_for_history(s)
                if detail_str:
                    line += f" — {detail_str}"
        if (
            s.protocol_result is not None
            and s.protocol_result.stage == ExperimentStage.SCREENING
        ):
            pr = s.protocol_result
            st = pr.stats
            line += (
                f"\n    screening: case_win_rate={st.win_rate:.2f}"
                f"  gate_win_rate={st.win_rate:.2f}"
                f"  median_delta={st.median_delta:.4f}"
                f"  outcome={pr.gate_outcome}"
            )
            if is_detailed and pr.pattern_summary:
                line += "\n" + _render_pattern_summary(pr.pattern_summary)
            if is_detailed and pr.case_feedback:
                selected = _select_cases_for_prompt(pr.case_feedback, max_cases=4)
                for cf in selected:
                    line += "\n" + _render_case_feedback(cf)
        lines.append(line)

    diagnosis = _build_consecutive_failure_diagnosis(branch_steps)
    if diagnosis:
        lines.append(diagnosis)

    return "\n".join(lines)


def _pre_protocol_failure_detail_for_history(step: StepRecord) -> str:
    ref = step.proposal_session_ref if isinstance(step.proposal_session_ref, Mapping) else {}
    primary = ref.get("primary_failure") if isinstance(ref, Mapping) else None
    if not isinstance(primary, Mapping):
        primary = {}
    parts = [
        str(primary.get("stage") or step.failure_stage or "").strip(),
        str(primary.get("reason") or "").strip(),
        str(primary.get("category") or "").strip(),
        str(primary.get("code") or "").strip(),
        str(primary.get("detail") or step.failure_detail or "").strip(),
    ]
    compact = " ".join(part for part in parts if part)
    compact = _first_line(compact)
    return compact[:700]


def _render_pattern_summary(pattern) -> str:
    """Render ScreeningPatternSummary as compact prompt text."""
    lines = [
        f"    pattern: cases={pattern.total_cases}"
        f" win={pattern.winning_cases} loss={pattern.losing_cases} mixed={pattern.mixed_cases}",
    ]
    if pattern.wins_by_decisive_objective:
        lines.append(f"      wins by objective: {pattern.wins_by_decisive_objective}")
    if pattern.losses_by_decisive_objective:
        lines.append(f"      losses by objective: {pattern.losses_by_decisive_objective}")
    if pattern.key_observations:
        for obs in pattern.key_observations:
            lines.append(f"      • {obs}")
    return "\n".join(lines)


def _render_case_feedback(cf) -> str:
    """Render a single CaseAggregateFeedback with directional language (T09)."""
    feature_label = _render_case_feature_label(getattr(cf, "case_features", {}) or {})
    result_upper = cf.dominant_result.upper()

    metric = cf.decisive_metric if hasattr(cf, 'decisive_metric') else getattr(cf, 'dominant_decisive_objective', 'tie')
    deltas = cf.median_deltas if hasattr(cf, 'median_deltas') and cf.median_deltas else {}

    delta_parts = []
    for name, val in sorted(deltas.items()):
        direction = "↓" if val > 0 else "↑"
        delta_parts.append(f"{name} {direction}{abs(val):.1f} (Δ={val:+.1f})")

    if delta_parts:
        decisive_str = f"Decisive: {metric} — " + ", ".join(delta_parts)
    else:
        decisive_str = f"Decisive: {metric}"

    baseline_note = ""
    baseline_parts = [
        f"{key}={value}"
        for key, value in sorted((getattr(cf, "case_features", {}) or {}).items())
        if str(key).startswith("champion_")
    ]
    if baseline_parts:
        baseline_note = "\n        Champion baseline: " + ", ".join(baseline_parts)

    return (
        f"      {cf.case_id} ({feature_label}): {result_upper}"
        f" (W/L/T={cf.wins}/{cf.losses}/{cf.ties}, consistency={cf.seed_consistency:.2f})"
        f"\n        {decisive_str}"
        f"{baseline_note}"
    )


def _render_case_feature_label(features: dict) -> str:
    if not features:
        return "features=unknown"
    preferred = ["size_bucket", "path_stem"]
    keys = [key for key in preferred if key in features]
    keys.extend(sorted(key for key in features if key not in keys and not str(key).startswith("champion_")))
    parts = [f"{key}={features[key]}" for key in keys[:4]]
    return ", ".join(parts) if parts else "features=unknown"


def _select_cases_for_prompt(cases, max_cases: int = 4) -> list:
    """Select most informative cases for prompt inclusion."""
    scored = []
    seen_sizes: set = set()
    for c in cases:
        score = 0.0
        if c.dominant_result == "loss":
            score += 5
        elif c.dominant_result == "win":
            score += 4
        elif c.dominant_result == "mixed":
            score += 4
        if c.seed_consistency >= 0.99:
            score += 2
        dm = c.decisive_metric if hasattr(c, 'decisive_metric') else ""
        if dm and dm != "tie":
            score += 2
        bucket = c.case_features.get("size_bucket", "unknown")
        if bucket not in seen_sizes:
            score += 2
            seen_sizes.add(bucket)
        deltas = c.median_deltas if hasattr(c, 'median_deltas') and c.median_deltas else {}
        max_delta = max((abs(v) for v in deltas.values()), default=0)
        score += min(max_delta / 100, 3)
        scored.append((score, c))
    scored.sort(key=lambda x: -x[0])
    return [c for _, c in scored[:max_cases]]


_VERIFICATION_SUGGESTIONS: dict = {
    "V6_feasibility": (
        "检查 operator_interface_spec 中定义的可行性约束，确保输出满足问题适配器的 feasibility oracle。"
    ),
    "V5_solution_consistency": (
        "检查 operator_interface_spec 中定义的解结构一致性约束，确保 solver 输出可被问题适配器正确反序列化和校验。"
    ),
    "V8_nondeterminism": (
        "同 seed 两次 solver run 产出了不同的 objective。常见非确定性来源："
        "(1) 禁止使用 uuid.uuid4() 或系统熵；"
        "(2) 禁止 list(set(...)) 或遍历 set/dict 时依赖顺序，必须 sorted()；"
        "(3) 所有随机性必须来自 operator execute 的 rng 参数；"
        "(4) 避免依赖文件系统、时间、全局状态或未排序容器顺序"
    ),
    "V2_interface": (
        "确保类和 execute 方法签名严格符合 operator_interface_spec。"
    ),
    "V1_syntax": "检查 Python 语法是否正确",
}


def _build_consecutive_failure_diagnosis(branch_steps: List[StepRecord]) -> str:
    """Inject a diagnosis block when 3+ consecutive same-type verification failures occur."""
    if len(branch_steps) < 3:
        return ""
    streak_steps = []
    for s in reversed(branch_steps):
        if s.failure_stage == "verification" and s.failure_detail:
            streak_steps.append(s)
        else:
            break
    if len(streak_steps) < 3:
        return ""

    failure_types: List[str] = []
    details: List[str] = []
    for s in streak_steps:
        fd = s.failure_detail or ""
        vcode = fd.split(":")[0].strip() if ":" in fd else fd.split()[0] if fd else ""
        failure_types.append(vcode)
        if s.verification_detail:
            details.append(s.verification_detail[:150])
        elif fd:
            details.append(fd[:150])

    dominant_type = Counter(failure_types).most_common(1)[0][0] if failure_types else ""
    suggestion = _VERIFICATION_SUGGESTIONS.get(dominant_type, "仔细检查验证失败的原因并修改代码")
    aggregated = " | ".join(dict.fromkeys(details))[:300]

    return (
        f"\n## ⚠️ Consecutive Failure Diagnosis\n"
        f"The last {len(streak_steps)} attempts all failed at verification.\n"
        f"Common failure details: {aggregated}\n"
        f"Suggested approach: {suggestion}"
    )


def _first_line(detail: str) -> str:
    for line in detail.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:180]
    return "contract gate failed"


def _build_what_worked_section(
    branch_steps: List[StepRecord],
    taxonomy: Optional[list] = None,
) -> str:
    """Build 'What Worked' section from screening-derived successes (T26)."""
    high_wr_steps = [
        s for s in branch_steps
        if (
            s.protocol_result is not None
            and s.protocol_result.stage == ExperimentStage.SCREENING
            and s.protocol_result.stats.win_rate >= 0.8
        )
    ]
    successes = high_wr_steps
    if not successes:
        return ""

    lines = ["## What Worked (learn from these)"]
    for s in successes[:5]:
        h = s.hypothesis
        mechanism = extract_mechanism_label(
            h.hypothesis_text or "",
            taxonomy=taxonomy,
            preferred_label=h.change_locus,
        )
        tag = "(high screening case_win_rate)"
        wr_str = ""
        if (
            s.protocol_result
            and s.protocol_result.stage == ExperimentStage.SCREENING
        ):
            wr_str = f", case_wr={s.protocol_result.stats.win_rate:.2f}"
        lines.append(
            f"- {mechanism} ({h.change_locus}/{h.action}) {tag}{wr_str}: "
            f"{(h.hypothesis_text or '')[:100]}"
        )
    return "\n".join(lines)


def _build_champion_baselines(step_history: List[StepRecord]) -> str:
    """Build champion baseline section from most recent screening experiment."""
    last_with_pairs = None
    for step in reversed(step_history):
        if (
            step.protocol_result is not None
            and step.protocol_result.stage == ExperimentStage.SCREENING
            and (
                step.protocol_result.pair_feedback
                or step.protocol_result.case_feedback
            )
        ):
            last_with_pairs = step
            break

    if last_with_pairs is None:
        return ""

    case_champ_metrics: dict = defaultdict(lambda: defaultdict(list))
    for pair in last_with_pairs.protocol_result.pair_feedback:
        oc = getattr(pair, 'objective_comparison', None)
        if oc and hasattr(oc, 'metrics') and oc.metrics:
            for m in oc.metrics:
                case_champ_metrics[pair.case_id][m.name].append(m.champion_value)

    if not case_champ_metrics:
        if last_with_pairs.protocol_result.case_feedback:
            lines = ["## Champion Performance (screening cases)"]
            for cf in last_with_pairs.protocol_result.case_feedback[:8]:
                feature_label = _render_case_feature_label(getattr(cf, "case_features", {}) or {})
                lines.append(
                    f"- {cf.case_id} ({feature_label}): "
                    "champion baseline not available in aggregate"
                )
            return "\n".join(lines)
        return ""

    lines = ["## Champion Performance (screening cases)"]
    for case_id, metrics in sorted(case_champ_metrics.items()):
        parts = []
        for metric_name, vals in sorted(metrics.items()):
            avg = sum(vals) / len(vals)
            parts.append(f"{metric_name}={avg:.1f}")
        lines.append(f"- {case_id}: {', '.join(parts)}")

    return "\n".join(lines)


__all__ = [
    name
    for name in globals()
    if not (name.startswith("__") and name.endswith("__"))
]
