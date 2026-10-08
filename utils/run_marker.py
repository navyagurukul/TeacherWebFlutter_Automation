"""Who ran today's daily tiers — the QA PC (visible browser) or GitHub (hidden).

The daily run prefers the QA PC so the Chrome window is visible. When the PC is
off, the scheduled GitHub workflow runs the same tiers headless instead. The two
coordinate through one GitHub Actions repo variable, LAST_TIER_RUN, holding
"<IST date> pc":

* run_tiers.py writes it when the PC run starts, and first checks the Actions
  API: if GitHub's scheduled run already ran today (the PC was switched on
  late), the PC skips rather than posting a second report.
* tiered-suite.yml reads it (vars.LAST_TIER_RUN) on its schedule and skips
  when the PC already ran today.

The token is the github.com credential stored in git on this PC.
"""
from __future__ import annotations

import datetime
import subprocess

import requests

REPO = "navyagurukul/TeacherWebFlutter_Automation"
API = f"https://api.github.com/repos/{REPO}"
VARIABLE = "LAST_TIER_RUN"
WORKFLOW = "tiered-suite.yml"
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))


def today_ist() -> str:
    return datetime.datetime.now(IST).strftime("%Y-%m-%d")


def _token() -> str | None:
    try:
        out = subprocess.run(
            ["git", "credential", "fill"],
            input="protocol=https\nhost=github.com\n\n",
            capture_output=True, text=True, timeout=20,
        ).stdout
    except Exception:
        return None
    for line in out.splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1].strip() or None
    return None


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json"}


def github_ran_today() -> bool:
    """True when GitHub's *scheduled* tier run already started today (IST)."""
    token = _token()
    if not token:
        return False
    try:
        r = requests.get(f"{API}/actions/workflows/{WORKFLOW}/runs",
                         params={"event": "schedule", "per_page": 5},
                         headers=_headers(token), timeout=20)
        r.raise_for_status()
        runs = r.json().get("workflow_runs", [])
    except Exception:
        return False
    today = today_ist()
    for run in runs:
        started = datetime.datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
        if started.astimezone(IST).strftime("%Y-%m-%d") != today:
            continue
        # A scheduled run that found the PC had already run still exists, with
        # its `tiers` job skipped; count only runs whose tiers job ran.
        try:
            jobs = requests.get(run["jobs_url"], headers=_headers(token),
                                timeout=20).json().get("jobs", [])
        except Exception:
            return True
        if any(j["name"] == "tiers" and j.get("conclusion") != "skipped" for j in jobs):
            return True
    return False


def mark_pc_run() -> bool:
    """Record that the PC is running today's tiers. False if GitHub could not be
    reached — the run still goes ahead, GitHub may then run a duplicate."""
    token = _token()
    if not token:
        return False
    try:
        r = requests.patch(f"{API}/actions/variables/{VARIABLE}",
                           json={"name": VARIABLE, "value": f"{today_ist()} pc"},
                           headers=_headers(token), timeout=20)
        return r.status_code in (200, 204)
    except Exception:
        return False
