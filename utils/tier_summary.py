"""Post one Slack message covering a tiered run of the web portal — sanity, then
smoke, then regression — listing every test each tier ran with its own
pass/fail mark. Same shape as the Android suite's tier report, so the two read
the same in the channel.

    python -m utils.tier_summary sanity=reports/junit_sanity.xml \
                                 smoke=reports/junit_smoke.xml \
                                 regression=reports/junit_regression.xml

Add `--dry-run` to print instead of posting (.env holds the real webhook, so an
unguarded local preview would post to the channel).

A tier whose file is missing is reported as "not run" — a tier that never
executed must never read as green. Exit code is non-zero when any tier failed.
"""
from __future__ import annotations

import datetime
import os
import sys
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

import requests

from config import settings
from data.test_data import SCHOOL_NAME, TEACHER_MOBILE
from utils import app_version, school_enrolment

TIER_ORDER = ["sanity", "smoke", "regression"]

TIER_INTENT = {
    "sanity": "is the portal usable at all",
    "smoke": "do the main happy paths work",
    "regression": "full coverage except `heavy`",
}

BROWSER_FILE = settings.REPORTS_DIR / "browser.txt"

# Plain-English line per test. A test not listed falls back to its name.
DESCRIPTIONS = {
    "test_login_screen_loads": "Login page opens (Sign in, LOG IN, REGISTER, school picker)",
    "test_login_shows_app_version": "Login page shows the version, matching version.json",
    "test_school_picker_finds_sanskruthi": "School search finds the test school",
    "test_login_reaches_home": "Log in with school + mobile reaches the home dashboard",
    "test_login_requires_school": "LOG IN without a school shows 'Please select a school'",
    "test_login_requires_mobile": "LOG IN without a mobile shows 'Mobile number is required'",
    "test_login_rejects_short_mobile": "5-digit mobile is rejected ('Enter a valid 10-digit number')",
    "test_nav_bar_opens_each_destination": "Every nav-bar tab opens its section",
    "test_dashboard_boxes_open_each_section": "Every home dashboard box opens its section",
    "test_drawer_lists_every_menu_item": "Menu lists Profile, Star Arena, Test, Zoom, Logout",
    "test_home_shows_enrolment_counts": "Home shows Registered / Remaining student counts",
    "test_full_smoke_journey": "Full journey: login, boxes, tabs, logout",
    "test_lesson_plan_catalogue_loads": "Lesson Plan loads its lesson plans",
    "test_lesson_plan_count_matches_listed_plans": "Lesson-plan count matches the plans listed",
    "test_lesson_plan_card_expands": "A lesson-plan card expands to its PDFs / videos",
    "test_management_home_lists_every_action": "Management lists all five student actions",
    "test_student_registration_opens": "Student Registration screen opens",
    "test_theme_toggle_switches_and_returns": "Dark / light theme toggle works",
    "test_session_survives_a_reload": "Teacher stays logged in after a page reload",
    "test_layout_works_at_phone_width": "Portal works at phone width",
    "test_catalogue_not_empty": "Lesson catalogue has classes and materials",
    "test_all_pdfs_load": "Every lesson PDF link loads",
    "test_all_videos_load": "Every lesson video link loads",
    "test_all_in_pdf_links_load": "Every link inside the PDFs loads",
}

ICON = {"pass": "✅", "fail": "❌", "skip": "⏭️"}


def load_cases(path: str):
    """(name, seconds, state, first line of the failure) per testcase."""
    root = ET.parse(path).getroot()
    for tc in root.iter("testcase"):
        try:
            seconds = float(tc.get("time", "0") or 0)
        except ValueError:
            seconds = 0.0
        bad = tc.find("failure")
        if bad is None:
            bad = tc.find("error")
        if bad is not None:
            msg = (bad.get("message") or "").strip().splitlines()
            yield tc.get("name", ""), seconds, "fail", (msg[0] if msg else "")
        elif tc.find("skipped") is not None:
            yield tc.get("name", ""), seconds, "skip", ""
        else:
            yield tc.get("name", ""), seconds, "pass", ""


def describe(name: str) -> str:
    base, _, param = name.partition("[")
    param = param.rstrip("]")
    text = DESCRIPTIONS.get(base) or base.removeprefix("test_").replace("_", " ").capitalize()
    return f"{text} [{param}]" if param else text


def tier_report(tier: str, path: str | None) -> dict:
    if not path or not os.path.isfile(path):
        return {"tier": tier, "ran": False}
    cases = list(load_cases(path))
    if not cases:
        return {"tier": tier, "ran": False}
    return {
        "tier": tier,
        "ran": True,
        "total": len(cases),
        "passed": sum(1 for c in cases if c[2] == "pass"),
        "failed": sum(1 for c in cases if c[2] == "fail"),
        "skipped": sum(1 for c in cases if c[2] == "skip"),
        "runtime": sum(c[1] for c in cases),
        "tests": [(c[2], describe(c[0]), c[3]) for c in cases],
    }


def tier_lines(rep: dict) -> list[str]:
    tier = rep["tier"].capitalize()
    intent = TIER_INTENT.get(rep["tier"], "")
    if not rep["ran"]:
        return [f"*{tier}* ⤼ not run  —  _{intent}_"]
    icon = "✅" if not rep["failed"] else "❌"
    counts = f"{rep['passed']}/{rep['total']} passed"
    if rep["failed"]:
        counts += f", {rep['failed']} failed"
    if rep["skipped"]:
        counts += f", {rep['skipped']} skipped"
    lines = [f"*{tier}* {icon} {counts}  •  {rep['runtime']:.0f}s  —  _{intent}_"]
    for state, text, msg in rep["tests"]:
        line = f"      {ICON[state]} {text}"
        if state == "fail" and msg:
            line += f"\n            ↳ _{msg[:140]}_"
        lines.append(line)
    return lines


def deployed() -> dict:
    """version.json as the live site serves it: version + build_number."""
    try:
        r = requests.get(app_version.VERSION_JSON, timeout=15)
        r.raise_for_status()
        return r.json() or {}
    except Exception:
        return {}


def build_line(info: dict) -> str:
    host = urlparse(settings.BASE_URL).netloc
    if not info.get("version"):
        return f"Web portal · {host} · version.json unreachable"
    line = f"Web portal · {host} V{info['version']}"
    if info.get("build_number"):
        line += f" (build {info['build_number']})"
    return line


def version_check(info: dict) -> str:
    """The version the login page displayed vs the version the deployed site
    reports. A mismatch means a stale cached bundle or the wrong environment."""
    shown = app_version._from_captured()
    live = info.get("version")
    if shown and live:
        if shown == live:
            return f"✅ login page shows V{shown} = deployed V{live}"
        return f"❌ login page shows V{shown} but deployed is V{live}"
    if live:
        return f"⚠️ deployed V{live}; login-page version not captured"
    if shown:
        return f"⚠️ login page shows V{shown}; version.json unreachable"
    return "⚠️ no version read"


def build_message(paths: dict[str, str]) -> tuple[str, int]:
    reports = [tier_report(t, paths.get(t)) for t in TIER_ORDER]
    ran = [r for r in reports if r["ran"]]
    total_failed = sum(r["failed"] for r in ran)
    missing = [r["tier"] for r in reports if not r["ran"]]

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    if not ran:
        status = "⚠️ NOTHING RAN"
    elif total_failed:
        status = "❌ FAIL"
    elif missing:
        status = "⚠️ PARTIAL"
    else:
        status = "✅ PASS"

    info = deployed()
    lines = [
        f"*Teacher Web QA — Sanity / Smoke / Regression* ({now})   {status}",
        f"Build tested: *{build_line(info)}*",
        f"App version: *{app_version.label_with_source()}*",
        f"Version check: {version_check(info)}",
        f"School: *{SCHOOL_NAME}*  •  Mobile: *{TEACHER_MOBILE}*",
        f"Enrolment: {school_enrolment.label_with_source()}",
    ]
    try:
        browser = BROWSER_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        browser = ""
    if browser:
        lines.append(f"Browser: {browser}")
    lines.append("")
    for rep in reports:
        lines += tier_lines(rep)
        lines.append("")
    if missing:
        lines.append(f"⚠️ Not run: {', '.join(missing)} — this run does not cover them.")
    return "\n".join(lines).rstrip(), total_failed


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    dry_run = "--dry-run" in sys.argv[1:]
    paths: dict[str, str] = {}
    for arg in sys.argv[1:]:
        if "=" in arg:
            tier, path = arg.split("=", 1)
            if tier.strip().lower() in TIER_ORDER:
                paths[tier.strip().lower()] = path.strip()
    if not paths:
        print("usage: python -m utils.tier_summary sanity=<junit> smoke=<junit> regression=<junit>")
        return 0

    text, failed = build_message(paths)
    url = "" if dry_run else settings.SLACK_WEBHOOK_URL
    if not url:
        why = "--dry-run" if dry_run else "SLACK_WEBHOOK_URL not set"
        print(f"[tier_summary] {why} — printing instead of posting:\n")
    else:
        requests.post(url, json={"text": text}, timeout=30).raise_for_status()
        print("[tier_summary] posted to Slack.")
    print(text)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
