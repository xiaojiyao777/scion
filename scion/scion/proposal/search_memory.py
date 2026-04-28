"""CampaignSearchMemory — cross-branch search history for LLM context injection (J1)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional

from scion.core.models import StepRecord, HypothesisProposal


# ---------------------------------------------------------------------------
# Mechanism label extraction (shared with context_manager.py)
# ---------------------------------------------------------------------------

_MECHANISM_KEYWORDS: List[tuple] = [
    (["destroy", "rebuild"], "destroy_rebuild"),
    (["subcategor", "consolidat", "merge"], "subcategory_consolidation"),
    (["swap"], "order_swap"),
    (["redistribute", "rebalance"], "rebalance"),
    (["split"], "split_operator"),
    (["cost", "downsize", "vehicle type", "upgrade"], "cost_reduction"),
    (["drain", "evacuate", "evict", "purif"], "intra_subcat_repack"),
    (["eliminate", "remove_vehicle", "kill"], "vehicle_elimination"),
]
_DEFAULT_MECHANISM = "generic"


def _extract_mechanism_label(hypothesis_text: str, taxonomy: Optional[List[str]] = None) -> str:
    text_lower = hypothesis_text.lower()
    if taxonomy:
        for label in taxonomy:
            if label.lower() in text_lower:
                return label
    for keywords, label in _MECHANISM_KEYWORDS:
        if any(kw in text_lower for kw in keywords):
            return label
    return _DEFAULT_MECHANISM


def _make_family_key(mechanism_label: str, action: str, locus: str, target_file: str = "") -> str:
    if target_file:
        fname = target_file.split("/")[-1].replace(".py", "")
        return f"{mechanism_label}/{action}/{locus}/{fname}"
    return f"{mechanism_label}/{action}/{locus}"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class FamilyEntry:
    """Aggregated stats for one hypothesis family across all branches."""
    label: str                          # mechanism label
    locus: str                          # change_locus
    action: str                         # action type
    target_file: str = ""               # target file (filename only, no path)
    total_attempts: int = 0
    best_wr: float = 0.0
    consecutive_fails: int = 0
    is_exhausted: bool = False          # total_attempts >= 5 AND best_wr < 0.35
    last_failure_reason: str = ""
    champion_version_at_discovery: int = 0
    promoted: bool = False              # whether this family was ever promoted
    recent_failure_details: List[str] = field(default_factory=list)  # last 3 verification failure details

    @property
    def family_key(self) -> str:
        return _make_family_key(self.label, self.action, self.locus, self.target_file)


@dataclass
class CampaignSearchMemory:
    """Cross-branch search memory for the entire campaign.

    Updated incrementally after each step. Rendered into LLM context
    by ContextManager with optional token budget for tiered compression.
    """
    champion_evolution: List[str] = field(default_factory=list)
    families: Dict[str, FamilyEntry] = field(default_factory=dict)
    coverage_counts: Dict[str, int] = field(default_factory=dict)  # locus/action → count
    recent_hypotheses: List[str] = field(default_factory=list)     # last N hypothesis texts for loop detection

    # ---------------------------------------------------------------
    # Incremental update
    # ---------------------------------------------------------------

    def update(self, step: StepRecord) -> None:
        """Update search memory from a completed step. O(1)."""
        hyp = step.hypothesis
        if hyp is None:
            return

        mechanism = _extract_mechanism_label(hyp.hypothesis_text or "")
        key = _make_family_key(mechanism, hyp.action, hyp.change_locus, hyp.target_file or "")

        # Update coverage counts
        coverage_key = f"{hyp.change_locus}/{hyp.action}"
        self.coverage_counts[coverage_key] = self.coverage_counts.get(coverage_key, 0) + 1

        # Track recent hypotheses for loop detection
        if hyp.hypothesis_text:
            self.recent_hypotheses.append(hyp.hypothesis_text)
            if len(self.recent_hypotheses) > 20:
                self.recent_hypotheses = self.recent_hypotheses[-20:]

        # Get or create family entry
        if key not in self.families:
            self.families[key] = FamilyEntry(
                label=mechanism,
                locus=hyp.change_locus,
                action=hyp.action,
                target_file=hyp.target_file or "",
            )
        fam = self.families[key]
        fam.total_attempts += 1

        # Determine outcome
        is_promoted = step.decision is not None and step.decision.value == "promote"

        if is_promoted:
            fam.promoted = True
            fam.consecutive_fails = 0

        if step.protocol_result is not None:
            wr = step.protocol_result.stats.win_rate
            fam.best_wr = max(fam.best_wr, wr)
            if wr < 0.35 and not is_promoted:
                fam.consecutive_fails += 1
            else:
                fam.consecutive_fails = 0
        elif step.failure_stage is not None:
            # Failed before reaching protocol — counts as a fail
            fam.consecutive_fails += 1
            fam.last_failure_reason = step.failure_detail or step.failure_stage or ""
            if step.failure_detail and step.failure_stage == "verification":
                fam.recent_failure_details.append(step.failure_detail[:200])
                if len(fam.recent_failure_details) > 3:
                    fam.recent_failure_details = fam.recent_failure_details[-3:]

        # Exhaustion: total_attempts >= 5 AND best_wr < 0.35 (uniform for all families)
        fam.is_exhausted = (fam.total_attempts >= 5 and fam.best_wr < 0.35)

    def record_champion_promotion(
        self,
        description: str,
        champion_version: int,
    ) -> None:
        """Record a champion promotion event in evolution history."""
        self.champion_evolution.append(description)

    # ---------------------------------------------------------------
    # Semantic loop detection
    # ---------------------------------------------------------------

    def _detect_hypothesis_loop(self, threshold: int = 3) -> Optional[str]:
        """Detect if recent hypotheses are semantically looping.

        Compares recent hypothesis texts pairwise using keyword overlap.
        Returns a warning string if ≥ threshold similar pairs found, else None.
        """
        if len(self.recent_hypotheses) < 4:
            return None

        recent = self.recent_hypotheses[-10:]  # last 10

        def _keyword_set(text: str) -> set:
            stop = {"the", "a", "an", "to", "for", "of", "in", "on", "and", "or", "is", "by", "with"}
            return {w for w in text.lower().split() if len(w) > 2 and w not in stop}

        similar_pairs = 0
        for i in range(len(recent)):
            for j in range(i + 1, len(recent)):
                kw_i = _keyword_set(recent[i])
                kw_j = _keyword_set(recent[j])
                if not kw_i or not kw_j:
                    continue
                overlap = len(kw_i & kw_j) / max(len(kw_i | kw_j), 1)
                if overlap >= 0.6:
                    similar_pairs += 1

        if similar_pairs >= threshold:
            return (
                f"⚠ SEMANTIC LOOP DETECTED: {similar_pairs} similar hypothesis pairs in "
                f"last {len(recent)} proposals. You are revisiting the same idea. "
                f"Try a fundamentally different mechanism or locus."
            )
        return None

    # ---------------------------------------------------------------
    # Rendering
    # ---------------------------------------------------------------

    @property
    def exhausted_families(self) -> List[FamilyEntry]:
        return [f for f in self.families.values() if f.is_exhausted]

    @property
    def promising_families(self) -> List[FamilyEntry]:
        return [
            f for f in self.families.values()
            if not f.is_exhausted and f.best_wr >= 0.25 and not f.promoted
        ]

    def _build_coverage_gaps(self) -> Dict[str, str]:
        """Identify over/under-explored locus/action combos."""
        if not self.coverage_counts:
            return {}
        total = sum(self.coverage_counts.values())
        if total == 0:
            return {}
        gaps: Dict[str, str] = {}
        for key, count in sorted(self.coverage_counts.items(), key=lambda x: -x[1]):
            ratio = count / total
            if ratio > 0.4:
                gaps[key] = f"{count}次 ← 过度探索"
            elif count <= 3:
                gaps[key] = f"{count}次 ← 严重不足"
            elif count <= 5:
                gaps[key] = f"{count}次 ← 不足"
        return gaps

    def render(self, available_tokens: Optional[int] = None) -> str:
        """Render search memory as text for LLM injection.

        Args:
            available_tokens: If None, render full. If int, compress to fit.

        Compression priority (higher = harder to drop):
            L0: champion evolution + AVOID labels
            L1: AVOID last_failure_reason
            L2: promising directions
            L3: coverage_gaps details
        """
        sections = []

        # L0: Champion evolution (always included)
        if self.champion_evolution:
            sections.append(
                "### Champion 演化\n" +
                "\n".join(self.champion_evolution)
            )

        # Loop detection (before AVOID)
        loop_warning = self._detect_hypothesis_loop()
        if loop_warning:
            sections.append("### Hypothesis Loop Warning\n" + loop_warning)

        # L0+L1: Exhausted families (AVOID list)
        exhausted = self.exhausted_families
        if exhausted:
            lines = []
            for f in sorted(exhausted, key=lambda x: -x.total_attempts):
                line = f"{f.label} [{f.total_attempts}次, best_wr={f.best_wr:.2f}]"
                if f.last_failure_reason:
                    line += f": {f.last_failure_reason[:100]}"
                if f.recent_failure_details:
                    line += "\n  Recent failures: " + "; ".join(f.recent_failure_details[-2:])
                lines.append(line)
            sections.append(
                "### 已耗尽方向（AVOID — 全局失败 ≥5 次，best_wr < 0.35）\n" +
                "\n".join(lines)
            )

        # L2: Promising families
        promising = self.promising_families
        if promising:
            lines = []
            for f in sorted(promising, key=lambda x: -x.best_wr):
                lines.append(f"{f.label} [wr={f.best_wr:.2f}, {f.total_attempts}次]")
            sections.append(
                "### 有信号方向（值得参考）\n" +
                "\n".join(lines)
            )

        # L3: Coverage gaps
        gaps = self._build_coverage_gaps()
        if gaps:
            lines = [f"{k}: {v}" for k, v in gaps.items()]
            sections.append(
                "### 搜索覆盖缺口（OPPORTUNITY）\n" +
                "\n".join(lines)
            )

        if not sections:
            return ""

        full_text = "## Campaign Search Memory\n\n" + "\n\n".join(sections)

        if available_tokens is None:
            return full_text

        # Tiered compression
        estimated = len(full_text) // 4
        if estimated <= available_tokens:
            return full_text

        # Drop L3 (coverage gaps)
        if gaps:
            sections = sections[:-1]
        text = "## Campaign Search Memory\n\n" + "\n\n".join(sections)
        if len(text) // 4 <= available_tokens:
            return text

        # Drop L2 (promising)
        if promising:
            sections = [s for s in sections if "有信号方向" not in s]
        text = "## Campaign Search Memory\n\n" + "\n\n".join(sections)
        if len(text) // 4 <= available_tokens:
            return text

        # Drop L1 (failure reasons from AVOID) — keep just labels
        if exhausted:
            lines = []
            for f in sorted(exhausted, key=lambda x: -x.total_attempts):
                lines.append(f"{f.label} [{f.total_attempts}次, best_wr={f.best_wr:.2f}]")
            avoid_section = (
                "### 已耗尽方向（AVOID）\n" +
                "\n".join(lines)
            )
            # Rebuild sections with compact AVOID
            sections = []
            if self.champion_evolution:
                sections.append(
                    "### Champion 演化\n" +
                    "\n".join(self.champion_evolution)
                )
            sections.append(avoid_section)

        text = "## Campaign Search Memory\n\n" + "\n\n".join(sections)
        return text

    def estimate_tokens(self, level: Literal["full", "compact", "minimal"] = "full") -> int:
        """Estimate token count for different compression levels."""
        if level == "minimal":
            # L0 only
            parts = []
            if self.champion_evolution:
                parts.extend(self.champion_evolution)
            exhausted = self.exhausted_families
            for f in exhausted:
                parts.append(f"{f.label}")
            return len(" ".join(parts)) // 4

        rendered = self.render(available_tokens=None)
        return len(rendered) // 4
