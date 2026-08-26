"""Navigation smoke: log in once, then visit every destination and assert the
header title each one shows. Uses the Sanskruthi school.

Structured as a single test that walks all five destinations rather than one test
per tab: a web session costs a browser launch plus a Flutter engine boot plus a
login, so parametrising would pay that five times over for the same coverage.
"""
import pytest

from data.test_data import Text
from pages.home_page import BOX_TO_TITLE, NAV_TO_TITLE

TABS = [Text.NAV_LESSONS, Text.NAV_CLASS, Text.NAV_STUDENTS, Text.NAV_MANAGE, Text.NAV_HOME]

BOXES = [
    Text.BOX_LESSON_PLAN,
    Text.BOX_CLASS_REPORT,
    Text.BOX_STUDENT_REPORT,
    Text.BOX_MANAGEMENT,
]


@pytest.mark.smoke
@pytest.mark.navigation
def test_nav_bar_opens_each_destination(home):
    for tab in TABS:
        home.go_to(tab)
        assert home.current_title_is(NAV_TO_TITLE[tab]), (
            f"Tab {tab!r} did not show title {NAV_TO_TITLE[tab]!r}"
        )
        assert home.section_is_healthy(), f"Tab {tab!r} rendered an error state"


@pytest.mark.smoke
@pytest.mark.navigation
def test_dashboard_boxes_open_each_section(home):
    for box in BOXES:
        home.open_box(box)
        assert home.current_title_is(BOX_TO_TITLE[box]), (
            f"Box {box!r} did not open {BOX_TO_TITLE[box]!r}"
        )
        home.go_home()


@pytest.mark.regression
@pytest.mark.navigation
def test_drawer_lists_every_menu_item(home):
    home.open_menu()
    for item in (
        Text.MENU_PROFILE,
        Text.MENU_STAR_ARENA,
        Text.MENU_TEST,
        Text.MENU_ZOOM,
        Text.MENU_LOGOUT,
    ):
        assert home.is_visible(item, timeout=10), f"Drawer is missing {item!r}"
