"""Start / stop / restart an assessment for one school + class from the
Lesson Plan screen, then confirm the backend (what the Student app reads)
agrees.

Each action changes what that class's students see in the Student app:
START / RESTART make the test available, STOP closes it.

    python assessment_ops.py list    --class "Class 1"
    python assessment_ops.py status  --class "Class 1" --assessment "Assessment 1"
    python assessment_ops.py stop    --class "Class 1" --assessment "Assessment 1"
    python assessment_ops.py start   --class "Class 3" --assessment "Assessment 2"
    python assessment_ops.py restart --class "Class 1" --assessment "Assessment 1" \
        --school "Samskruthi School - IMS School - Nalgonda" --mobile 9000000001

`--via api` makes the same PATCH the portal sends, without a browser.
School and mobile default to the suite's Sanskruthi teacher.

Every start / stop / restart (including refusals and failures) is posted to
Slack via SLACK_WEBHOOK_URL. `--dry-run` prints the message instead;
`--no-slack` skips it.
"""
from __future__ import annotations

import argparse
import sys
import traceback

import requests

from config import settings

from data.test_data import (
    ASSESSMENT_ACTION_FOR_STATUS,
    ASSESSMENT_STATUS_AFTER_ACTION,
    SCHOOL_NAME,
    TEACHER_MOBILE,
    Text,
)
from utils.eg_api import EgApi

ACTIONS = {"start": Text.LESSON_START, "stop": Text.LESSON_STOP, "restart": Text.LESSON_RESTART}
STATUS_LABEL = {
    "locked": Text.ASSESSMENT_LOCKED,
    "unlocked": Text.ASSESSMENT_IN_PROGRESS,
    "completed": Text.ASSESSMENT_COMPLETED,
}
# What students of the class see in the Student app once the action lands.
STUDENT_EFFECT = {
    "unlocked": "test is OPEN for students in the Student app",
    "completed": "test is CLOSED for students in the Student app",
}


def _api(school: str, mobile: str) -> tuple[EgApi, str]:
    api = EgApi()
    api.login(mobile, school)
    return api, api.school_id()


def _print_list(api: EgApi, class_id: str, class_name: str) -> None:
    tests = api.assessments(class_id)
    if not tests:
        print(f"{class_name}: no assessments")
        return
    for t in tests:
        s = t.get("summary") or {}
        status = t.get("status", "")
        print(f"{class_name} | {t.get('plan')} | {t.get('display_name')} | {status} "
              f"(button {ASSESSMENT_ACTION_FOR_STATUS.get(status, '?')}) | "
              f"completed {s.get('completed', 0)}, in progress {s.get('in_progress', 0)}, "
              f"{s.get('total_students', 0)} students")


def post_slack(text: str, dry_run: bool) -> None:
    url = "" if dry_run else settings.SLACK_WEBHOOK_URL
    if not url:
        why = "--dry-run" if dry_run else "SLACK_WEBHOOK_URL not set"
        print(f"[assessment_ops] {why} - printing instead of posting:\n{text}")
        return
    try:
        requests.post(url, json={"text": text}, timeout=30).raise_for_status()
        print("[assessment_ops] posted to Slack.")
    except requests.RequestException as exc:
        print(f"[assessment_ops] Slack post failed: {exc}")


def slack_message(args, school: str, test: dict, outcome: str, ok: bool,
                  before: str, after: str | None, note: str = "") -> str:
    icon = "✅" if ok else "❌"
    summary = test.get("summary") or {}
    lines = [
        f"{icon} *Teacher Web — Assessment {args.op.upper()}* ({outcome})",
        f"• School: {school}",
        f"• Class: {args.class_name}  • {args.assessment} (under _{test.get('plan', '?')}_)",
        f"• Status: {STATUS_LABEL.get(before, before)} → "
        f"{STATUS_LABEL.get(after, after) if after else 'unchanged'} (backend)",
        f"• Students: {summary.get('total_students', '?')} • completed "
        f"{summary.get('completed', '?')} • in progress {summary.get('in_progress', '?')}",
        f"• Via: {args.via}  • Teacher: {args.mobile}",
    ]
    if ok and after in STUDENT_EFFECT:
        lines.append(f"• Student app: {STUDENT_EFFECT[after]}")
    if note:
        lines.append(f"• {note}")
    return "\n".join(lines)


def _run_ui(args, school: str, mobile: str, action: str) -> str:
    from pages.lesson_plan_page import LessonPlanPage
    from pages.login_page import LoginPage
    from utils.driver_factory import create_driver, open_app

    driver = create_driver()
    try:
        open_app(driver)
        home = LoginPage(driver).login(mobile, school)
        home.go_to(Text.NAV_LESSONS)
        lessons = LessonPlanPage(driver).wait_loaded().select_class(args.class_name)
        try:
            return lessons.click_assessment_action(args.assessment, action)
        except Exception:
            print(f"screenshot: {lessons.screenshot('assessment_ops_failure')}")
            raise
    finally:
        driver.quit()


def main() -> int:
    # The Slack text carries emoji; a redirected Windows console is cp1252.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("op", choices=["list", "status", *ACTIONS])
    parser.add_argument("--class", dest="class_name", help='e.g. "Class 1" (list: all classes if omitted)')
    parser.add_argument("--assessment", help='e.g. "Assessment 1"')
    parser.add_argument("--school", default=SCHOOL_NAME)
    parser.add_argument("--mobile", default=TEACHER_MOBILE)
    parser.add_argument("--via", choices=["ui", "api"], default="ui")
    parser.add_argument("--dry-run", action="store_true", help="print the Slack message, don't post")
    parser.add_argument("--no-slack", action="store_true", help="don't report to Slack")
    args = parser.parse_args()

    api, school_id = _api(args.school, args.mobile)
    school = api.school_name() or args.school
    print(f"school: {school}  teacher: {args.mobile}")

    if args.op == "list":
        classes = api.classes(school_id)
        if args.class_name:
            classes = [c for c in classes
                       if str(c.get("class_name", "")).lower() == args.class_name.lower()]
            if not classes:
                parser.error(f"class {args.class_name!r} not found")
        for cls in classes:
            _print_list(api, str(cls["id"]), cls.get("class_name", ""))
        return 0

    if not (args.class_name and args.assessment):
        parser.error(f"{args.op} needs --class and --assessment")
    try:
        class_id = api.class_id_for(school_id, args.class_name)
        before = api.assessment(class_id, args.assessment)
    except RuntimeError as exc:
        names = [t["display_name"] for t in api.assessments(class_id)] if "class_id" in locals() else []
        parser.error(f"{exc}" + (f" - available: {', '.join(names)}" if names else ""))
    print(f"{args.class_name} / {args.assessment} (under {before.get('plan')!r}): {before.get('status')}")
    if args.op == "status":
        return 0

    def report(outcome: str, ok: bool, after: str | None, note: str = "") -> None:
        if not args.no_slack:
            post_slack(slack_message(args, school, before, outcome, ok,
                                     before.get("status", ""), after, note), args.dry_run)

    action = ACTIONS[args.op]
    expected = ASSESSMENT_ACTION_FOR_STATUS.get(before.get("status", ""))
    if expected != action:
        print(f"refused: the card offers {expected}, not {action} - nothing changed")
        report("refused", False, None, f"Card offers {expected}, not {action} - nothing changed")
        return 2

    target = ASSESSMENT_STATUS_AFTER_ACTION[action]
    try:
        if args.via == "api":
            api.set_assessment_status(class_id, str(before["id"]), target)
        else:
            _run_ui(args, args.school, args.mobile, action)
    except Exception as exc:
        traceback.print_exc()
        after = api.assessment(class_id, args.assessment).get("status")
        report("failed", False, after, f"Error: {type(exc).__name__}: {str(exc)[:300]}")
        return 1

    after = api.assessment(class_id, args.assessment).get("status")
    ok = after == target
    print(f"{action} via {args.via}: backend now {after!r} "
          f"({'OK' if ok else f'expected {target!r}'}) - Student app reads this state")
    report("done" if ok else "backend mismatch", ok, after,
           "" if ok else f"Expected {STATUS_LABEL[target]} in the backend")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
