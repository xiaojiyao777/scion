#!/usr/bin/env python3
"""Scion v0.3 closure validation — 6-campaign launcher.

Runs `run_validation_campaign.py` × 6 (sonnet/gpt × synthetic × seed 11/29/47)
with a concurrency limit (default 2, matching the server's 2 cores).

Each campaign is a fully independent subprocess launched in its own session
(start_new_session=True = setsid equivalent) so terminal disconnection or
launcher crash does not take the campaigns down.

Usage
-----
Typical invocation under nohup+setsid (survives terminal disconnect):

    cd ~/research/or-autoresearch-agent/scion
    nohup setsid /home/clawd/miniconda3/envs/claw/bin/python \
        run_closure_validation.py \
        --base-dir v03-closure-validation \
        --max-concurrent 2 \
        --max-rounds 100 \
        > ~/research/scion-experiments/v03-closure-validation/launcher.log 2>&1 &
    disown

Or wrap with `launch_closure_validation.sh`.

Resume semantics: campaigns whose output dir already contains
`campaign_summary.json` are skipped (--skip-existing, default on). Delete
the summary or pass --no-skip-existing to force re-run.

Status file: <base-dir>/status.json is updated on every state change and
holds the list of pending / running / done campaigns.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Fixed job matrix (v0.3 closure validation)
# ---------------------------------------------------------------------------

JOBS = [
    {"model": "claude-sonnet-4-6", "seed": 11},
    {"model": "claude-sonnet-4-6", "seed": 29},
    {"model": "claude-sonnet-4-6", "seed": 47},
    {"model": "gpt-5.4-mini",      "seed": 11},
    {"model": "gpt-5.4-mini",      "seed": 29},
    {"model": "gpt-5.4-mini",      "seed": 47},
]


def job_name(job: dict) -> str:
    m = job["model"].replace("claude-", "").replace(".", "")
    return f"{m}_synthetic_seed{job['seed']}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="v0.3 closure validation launcher")
    parser.add_argument("--base-dir", default="v03-closure-validation",
                        help="subdir under ~/research/scion-experiments/")
    parser.add_argument("--max-concurrent", type=int, default=2,
                        help="max parallel campaigns (server is 2-core)")
    parser.add_argument("--max-rounds", type=int, default=100)
    parser.add_argument("--splits-weight", type=int, default=1000)
    parser.add_argument("--poll-interval", type=int, default=30,
                        help="seconds between completion polls")
    parser.add_argument("--skip-existing", action=argparse.BooleanOptionalAction,
                        default=True,
                        help="skip campaigns whose campaign_summary.json exists")
    args = parser.parse_args()

    scion_dir = Path(__file__).parent.resolve()
    script = scion_dir / "run_validation_campaign.py"
    if not script.exists():
        print(f"ERROR: {script} not found", file=sys.stderr)
        return 2

    out_base = Path.home() / "research" / "scion-experiments" / args.base_dir
    out_base.mkdir(parents=True, exist_ok=True)
    launcher_log = out_base / "launcher.log"
    status_file = out_base / "status.json"

    def log(msg: str) -> None:
        line = f"{datetime.now().isoformat(timespec='seconds')} {msg}"
        print(line, flush=True)
        with open(launcher_log, "a") as fh:
            fh.write(line + "\n")

    # Build pending list (skip already-done)
    pending: list[dict] = []
    skipped: list[str] = []
    for job in JOBS:
        name = job_name(job)
        summary = out_base / name / "campaign_summary.json"
        if args.skip_existing and summary.exists():
            skipped.append(name)
            continue
        pending.append(job)

    if skipped:
        log(f"SKIP {len(skipped)} already-done: {', '.join(skipped)}")

    if not pending:
        log("Nothing to run; all campaigns already have campaign_summary.json")
        return 0

    running: dict[str, subprocess.Popen] = {}
    done: list[str] = list(skipped)

    def write_status() -> None:
        status_file.write_text(json.dumps({
            "base_dir": str(out_base),
            "pending": [job_name(j) for j in pending],
            "running": [
                {"name": name, "pid": p.pid}
                for name, p in running.items()
            ],
            "done": done,
            "skipped": skipped,
            "updated_at": datetime.now().isoformat(),
        }, indent=2))

    def shutdown(signum: int, _frame) -> None:
        log(f"SIGNAL {signum} received — terminating {len(running)} running campaigns")
        for name, p in list(running.items()):
            try:
                # send SIGTERM to the process group (setsid created one)
                os.killpg(os.getpgid(p.pid), signal.SIGTERM)
                log(f"  SIGTERM → {name} pgid={os.getpgid(p.pid)}")
            except ProcessLookupError:
                pass
            except Exception as exc:
                log(f"  warn: {name} signal failed: {exc}")
        # brief grace then hard-kill leftovers
        time.sleep(5)
        for name, p in list(running.items()):
            if p.poll() is None:
                try:
                    os.killpg(os.getpgid(p.pid), signal.SIGKILL)
                    log(f"  SIGKILL → {name}")
                except Exception:
                    pass
        write_status()
        sys.exit(1)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    log("=" * 70)
    log(f"Scion v0.3 closure validation launcher")
    log(f"  base_dir       : {out_base}")
    log(f"  max_concurrent : {args.max_concurrent}")
    log(f"  max_rounds     : {args.max_rounds}")
    log(f"  splits_weight  : {args.splits_weight}")
    log(f"  to_run         : {len(pending)} campaigns")
    log(f"  skipped        : {len(skipped)}")
    log("=" * 70)

    write_status()

    # Main dispatch loop
    while pending or running:
        # Fill free slots
        while pending and len(running) < args.max_concurrent:
            job = pending.pop(0)
            name = job_name(job)
            cmd = [
                "/home/clawd/miniconda3/envs/claw/bin/python",
                str(script),
                "--model", job["model"],
                "--seed", str(job["seed"]),
                "--max-rounds", str(args.max_rounds),
                "--splits-weight", str(args.splits_weight),
                "--base-dir", args.base_dir,
            ]
            # Each campaign writes its own campaign.log; discard stdout/stderr here.
            proc = subprocess.Popen(
                cmd,
                cwd=str(scion_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,  # new process group; not affected by launcher signals
            )
            running[name] = proc
            log(f"START {name} pid={proc.pid} cmd={' '.join(cmd[-8:])}")
            write_status()

        # Poll
        time.sleep(args.poll_interval)
        finished_this_tick: list[str] = []
        for name, proc in list(running.items()):
            rc = proc.poll()
            if rc is None:
                continue
            finished_this_tick.append(name)
            elapsed = "?"  # could track start time; keep minimal
            log(f"FINISH {name} pid={proc.pid} exit_code={rc}")
            del running[name]
            done.append(name)
        if finished_this_tick:
            write_status()

    log(f"ALL DONE — {len(done)} campaigns completed")
    log("=" * 70)
    write_status()
    return 0


if __name__ == "__main__":
    sys.exit(main())
