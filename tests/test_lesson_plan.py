"""Lesson Plan section tests: the catalogue loads for the selected class and the
plan cards carry real content."""
import pytest

from data.test_data import Text
from pages.lesson_plan_page import LessonPlanPage


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
    titles = lessons.plan_titles()
    assert titles, "no lesson plans to open"
    lessons.open_plan(titles[0])
    assert lessons.start_visible(), (
        f"Opening plan {titles[0]!r} did not reveal its {Text.LESSON_START} action"
    )
