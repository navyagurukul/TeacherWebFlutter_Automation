"""Run the Teacher **Web** QA pass and post a per-area summary to Slack. Built
for a daily scheduled run, and deliberately shaped like the Android suite's
run_daily.py so the two reports read the same in the channel.

The report is grouped by area - **Login, Navigation, Lesson Plans, Management,
Web** - each with its own PASS/FAIL, and headed with the **version shown on the
login screen** (e.g. V2.4.3). Overall PASS only when every area passes.

Unlike the Android runner there is nothing to skip for: the portal needs no
device and no Appium server, only a browser. If Chrome cannot start, that is a
genuine failure and is reported as one.

Usage (with the venv python):
    python run_daily.py                  # full suite -> Slack
    python run_daily.py --smoke          # smoke markers only
    python run_daily.py tests/test_x.py  # an explicit pytest scope instead

Config (.env or environment):
    SLACK_WEBHOOK_URL   Slack Incoming Webhook URL (required to post)
    BASE_URL            site under test
    HEADLESS            true for unattended runs
"""
from __future__ import annotations

import datetime
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

sys.path.insert(0, str(ROOT))
from config import settings  # noqa: E402
from data.test_data import SCHOOL_NAME, TEACHER_MOBILE  # noqa: E402
from utils import app_version  # noqa: E402

# Windows consoles default to cp1252, which cannot print the emoji in the report.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

PY = str(ROOT / ".venv" / "Scripts" / "python.exe")
if not os.path.exists(PY):
    PY = sys.executable
REPORTS = ROOT / "reports"

# Report order. Every run shows all five so a missing area is visible, not silent.
AREAS = ["Login", "Navigation", "Lesson Plans", "Management", "Web"]

AREA_BY_MODULE = {
    "test_login": "Login",
    "test_navigation": "Navigation",
    "test_smoke_flow": "Navigation",
    "test_lesson_plan": "Lesson Plans",
    "test_management": "Management",
    "test_web_behaviour": "Web",
}


def classify(classname: str) -> str:
    """Map a junit testcase to its report area."""
    module = (classname or "").replace(".", "/").lower()
    for key, area in AREA_BY_MODULE.items():
        if key in module:
            return area
    return "Web"


# ---- running pytest ---------------------------------------------------------

# One retry, only on this unattended path. A browser launch or a Flutter engine
# boot can lose a race with whatever else the machine is doing at 8am, and a
# single flake should not put a red FAIL in the team channel. Local runs get no
# retries, so genuine flakiness is still visible while you work.
RETRY_ARGS = ["--reruns", "1", "--reruns-delay", "5"]


def run_pytest(args, junit_name: str) -> Path:
    REPORTS.mkdir(parents=True, exist_ok=True)
    junit = REPORTS / junit_name
    if junit.exists():
        junit.unlink()
    cmd = [
        PY, "-m", "pytest", *args, *RETRY_ARGS,
        f"--junitxml={junit}", "-p", "no:cacheprovider",
    ]
    subprocess.run(cmd, cwd=str(ROOT))
    return junit


def parse_junit(path: Path):
    """Return per-testcase records: area, name, outcome."""
    if not path or not path.exists():
        return []
    root = ET.parse(path).getroot()
    suites = root.findall("testsuite") or [root]
    out = []
    for suite in suites:
        for case in suite.findall("testcase"):
            failed = case.find("failure") is not None or case.find("error") is not None
            skipped = case.find("skipped") is not None
            out.append(
                {
                    "area": classify(case.get("classname")),
                    "name": case.get("name"),
                    "ok": not failed and not skipped,
                    "failed": failed,
                    "skipped": skipped,
                    "time": float(case.get("time", 0) or 0),
                }
            )
    return out


# ---- report building --------------------------------------------------------

def area_line(area: str, records) -> str:
    recs = [r for r in records if r["area"] == area]
    if not recs:
        return f"• {area:<13} ⤼ not run"
    passed = sum(1 for r in recs if r["ok"])
    failed = [r["name"] for r in recs if r["failed"]]
    icon = "✅" if not failed else "❌"
    line = f"• {area:<13} {icon} {passed}/{len(recs)}"
    if failed:
        line += "  — " + ", ".join(failed[:3])
        if len(failed) > 3:
            line += f" +{len(failed) - 3} more"
    return line


def post_slack(text: str) -> None:
    url = settings.SLACK_WEBHOOK_URL
    if not url:
        print("[run_daily] SLACK_WEBHOOK_URL not set — printing report instead:\n")
        print(text)
        return
    response = requests.post(url, json={"text": text}, timeout=30)
    response.raise_for_status()
    print("[run_daily] posted to Slack.")


# ---- main -------------------------------------------------------------------

def main() -> None:
    argv = sys.argv[1:]
    explicit = [a for a in argv if not a.startswith("--")]
    smoke_only = "--smoke" in argv

    # Forget the footer captured by an earlier run: after a deploy that stale
    # file would make today's report show the previous build's version.
    app_version.clear_capture()

    args = explicit or (["-m", "smoke"] if smoke_only else [])
    records = parse_junit(run_pytest(args, "junit_daily.xml"))

    # Resolve the version *after* the run, so a UI login can have written the
    # live footer to reports/app_version.txt.
    version = app_version.label_with_source()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    if not records:
        post_slack(
            f"*Teacher Web QA — Daily* ({now})   ⚠️ could not run any tests\n"
            f"Portal: {settings.BASE_URL}  •  Version: {version}"
        )
        sys.exit(1)

    total = len(records)
    passed = sum(1 for r in records if r["ok"])
    failed = sum(1 for r in records if r["failed"])
    skipped = sum(1 for r in records if r["skipped"])
    runtime = sum(r["time"] for r in records)
    status = "✅ PASS" if failed == 0 else "❌ FAIL"

    lines = [
        f"*Teacher Web QA — Daily* ({now})   {status}",
        f"Portal: {settings.BASE_URL}  •  Version: *{version}*",
        f"Account: Mobile: *{TEACHER_MOBILE}*  •  School: *{SCHOOL_NAME}*",
        f"Passed {passed}/{total}  •  Failed {failed}  •  Skipped {skipped}  •  {runtime:.0f}s",
        "",
    ]
    lines += [area_line(area, records) for area in AREAS]

    post_slack("\n".join(lines))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
