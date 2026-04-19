# CLAUDE.md — Scion Project

Behavioral guidelines for coding on this repository. These apply on top of project-specific conventions below. Bias toward caution over speed; for trivial tasks (typo fixes, obvious one-liners), use judgment.

Source: adapted from Andrej Karpathy's observations on LLM coding pitfalls
(https://github.com/multica-ai/andrej-karpathy-skills).

---

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

## Scion-Specific Rules

### Python environment
- **Always** use `/home/clawd/miniconda3/envs/claw/bin/python`. Do not use `python3` (base env is missing deps).
- Install new deps with the claw env's pip, not system pip.

### MILP solver
- Default solver is **HiGHS**, not CBC. CBC is kept only for compatibility (`--solver CBC`).
- MILP solutions must pass `extract_solution_strict` (integrality + C0a structural check). Never trust raw status.
- Oracle (`oracle.py`) must include C0a structural completeness checks before functional validation.

### Randomness
- Never use `uuid.uuid4()` in algorithmic code paths. Use `generate_vehicle_id(rng)` or similar rng-seeded helpers.
- All operator code must go through `rng` passed in; no `random.random()`, no `time.time()`, no `datetime.now()` as a random source.

### Experiments
- Experiment outputs go under `~/research/scion-experiments/`, not in the repo.
- Long-running experiments must be launched as a `systemd --user` transient service or `nohup+setsid`, never bare tmux.
- Each Sprint should produce a summary under `scion/docs/` before moving on.

### Testing
- Run `pytest` with the claw env's python.
- Unit tests live in `scion/tests/`.
- Before any PR/merge: all unit tests must pass. No exceptions.

### Documentation
- Architecture changes → update `scion/design/scion-architecture-v*.md`.
- New failure modes → write postmortem under `scion/postmortem/`.
- Sprint conclusions → `scion/docs/sprint-*.md`.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
