"""Lesson Plan section tests: the catalogue loads for the selected class and the
plan cards carry real content."""
import pytest

from data.test_data import (
    ASSESSMENT_ACTION_FOR_STATUS,
    ASSESSMENT_CLASS,
    TEACHER_MOBILE,
    Text,
)
from pages.lesson_plan_page import LessonPlanPage
from utils.eg_api import EgApi


@pytest.fixture()
def lessons(home):
    home.go_to(Text.NAV_LESSONS)
    return LessonPlanPage(home.driver).wait_loaded()


@pytest.mark.smoke
@pytest.mark.lessons
def test_lesson_plan_catalogue_loads(lessons):
    assert lessons.selected_class(), "Lesson Plan showed no selected class"
    count = lessons.plan_count()
    assert count and count > 0, f"Lesson Plan header reported no plans (got {count!r})"


@pytest.mark.smoke
@pytest.mark.lessons
def test_lesson_plan_count_matches_listed_plans(lessons):
    # The header states "<n> LESSON PLANS"; the list must actually hold plans.
    # Only the cards rendered so far are on screen, so this asserts the list is
    # populated and never exceeds what the header promised, rather than
    # demanding an exact match against a virtualised list.
    count = lessons.plan_count()
    titles = lessons.plan_titles()
    assert titles, "Lesson Plan listed no plan cards"
    assert len(titles) <= count, (
        f"Listed {len(titles)} plans but the header claims only {count}"
    )


@pytest.mark.regression
@pytest.mark.lessons
def test_lesson_plan_card_expands(lessons):
    titles = lessons.numbered_plan_titles()
    assert titles, "no numbered lesson plans to open"
    lessons.open_plan(titles[0])
    assert lessons.start_visible(), (
        f"Opening plan {titles[0]!r} did not reveal its {Text.LESSON_START} action"
    )


@pytest.fixture()
def class_assessments(lessons):
    """The Lesson Plan screen on ASSESSMENT_CLASS, plus the backend's view of
    that class's assessments (what the Student app reads)."""
    api = EgApi()
    api.login(TEACHER_MOBILE)
    class_id = api.class_id_for(api.school_id(), ASSESSMENT_CLASS)
    lessons.select_class(ASSESSMENT_CLASS)
    return lessons, api, class_id


@pytest.mark.regression
@pytest.mark.lessons
def test_assessment_cards_match_backend(class_assessments):
    # Read-only: every assessment the backend lists for the class has a card,
    # and the card's button matches the backend status.
    lessons, api, class_id = class_assessments
    tests = api.assessments(class_id)
    if not tests:
        pytest.skip(f"{ASSESSMENT_CLASS} has no assessments")
    for test in tests:
        name = test["display_name"]
        lessons.scroll_to_assessment(name)
        shown = lessons.assessment_action(name)
        expected = ASSESSMENT_ACTION_FOR_STATUS[test["status"]]
        assert shown == expected, (
            f"{name} (under {test['plan']!r}) is {test['status']!r} in the backend "
            f"but its card offers {shown!r}, not {expected!r}"
        )


@pytest.mark.assessment_ops
@pytest.mark.heavy
@pytest.mark.lessons
def test_assessment_stop_then_restart(class_assessments):
    # Changes live state: students of the class see the test close and reopen
    # in the Student app. Runs only on an assessment that is already in
    # progress and always leaves it in progress again.
    lessons, api, class_id = class_assessments
    running = [t for t in api.assessments(class_id) if t["status"] == "unlocked"]
    if not running:
        pytest.skip(f"no in-progress assessment in {ASSESSMENT_CLASS} to stop safely")
    test = running[0]
    name = test["display_name"]
    try:
        assert lessons.stop_assessment(name) == "completed"
        assert lessons.assessment_action(name) == Text.LESSON_RESTART
        assert api.assessment(class_id, name)["status"] == "completed", (
            f"STOP on {name} did not reach the backend"
        )

        assert lessons.restart_assessment(name) == "unlocked"
        assert lessons.assessment_action(name) == Text.LESSON_STOP
        assert api.assessment(class_id, name)["status"] == "unlocked", (
            f"RESTART on {name} did not reach the backend"
        )
    finally:
        if api.assessment(class_id, name)["status"] != "unlocked":
            api.set_assessment_status(class_id, str(test["id"]), "unlocked")
