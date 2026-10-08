"""Run the web portal tiers on this PC with a VISIBLE Chrome window, then post
the tier report to Slack.

    python run_tiers.py              # sanity -> smoke -> regression, post to Slack
    python run_tiers.py --dry-run    # same run, print the report instead
    python run_tiers.py --all        # run every tier even if an earlier one failed
    python run_tiers.py --scheduled  # the daily task: coordinate with GitHub first

Mirrors .github/workflows/tiered-suite.yml: each tier runs only when the one
before it passed, and a tier that did not run is reported "not run". Scheduled
daily by the Windows task "TeacherWeb QA Tiers" (run only when the user is
logged on, so the browser shows on screen). When the PC is off, the GitHub
workflow's scheduled run covers the day headless (see utils/run_marker.py).
"""
from __future__ import annotations

import datetime
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"
LOG = REPORTS / "tiers_log.txt"

PY = ROOT / ".venv" / "Scripts" / "python.exe"
PY = str(PY) if PY.exists() else sys.executable

TIERS = [
    ("sanity", ["-m", "sanity"]),
    ("smoke", ["-m", "smoke"]),
    ("regression", ["-m", os.getenv("REGRESSION_MARKERS", "not heavy")]),
]


def log(msg: str) -> None:
    line = f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def main() -> int:
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    run_all = "--all" in args
    scheduled = "--scheduled" in args

    REPORTS.mkdir(parents=True, exist_ok=True)

    if scheduled:
        # The daily task: if the PC was off and GitHub already ran today's tiers
        # headless, don't post a second report; otherwise claim today's run so
        # GitHub's fallback skips.
        from utils import run_marker

        if run_marker.github_ran_today():
            log("skipped: GitHub already ran today's tiers (PC was off)")
            return 0
        if not run_marker.mark_pc_run():
            log("warning: could not record the PC run on GitHub; its fallback may also run")
    env = dict(os.environ, HEADLESS="false", PYTHONIOENCODING="utf-8")

    # Forget the last run's results so the report can only show today's.
    for name, _ in TIERS:
        (REPORTS / f"junit_{name}.xml").unlink(missing_ok=True)
    (REPORTS / "app_version.txt").unlink(missing_ok=True)

    log("=== tiers start (visible browser) ===")
    previous_ok = True
    for name, marker in TIERS:
        if not previous_ok and not run_all:
            log(f"{name}: not run (previous tier failed)")
            continue
        junit = REPORTS / f"junit_{name}.xml"
        code = subprocess.call(
            [PY, "-m", "pytest", *marker, "-p", "no:cacheprovider",
             f"--junitxml={junit}", f"--html=reports/report_{name}.html",
             "--self-contained-html"],
            cwd=ROOT, env=env,
        )
        previous_ok = code == 0
        log(f"{name}: pytest exit {code}")

    summary = [PY, "-X", "utf8", "-m", "utils.tier_summary",
               *[f"{n}=reports/junit_{n}.xml" for n, _ in TIERS]]
    if dry_run:
        summary.append("--dry-run")
    code = subprocess.call(summary, cwd=ROOT, env=env)
    log(f"=== tiers done (report exit {code}) ===")
    return code


if __name__ == "__main__":
    sys.exit(main())
