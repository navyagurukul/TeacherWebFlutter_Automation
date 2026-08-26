"""End-to-end smoke journey for the teacher web portal (Sanskruthi School -
Nalgonda):

  login
    -> confirm the dashboard shows this school's details and license code
    -> open each dashboard box and confirm the section loads
    -> open each nav destination and confirm it loads
    -> open the drawer and Logout back to the login screen

"Loads with correct data" is asserted at smoke level as: the section's header
renders and no error state is present. Field-level assertions live in the
per-area tests.
"""
import pytest

from data.test_data import SCHOOL_NAME, Text
from pages.home_page import BOX_TO_TITLE, NAV_TO_TITLE
from pages.login_page import LoginPage

BOXES = [
    Text.BOX_LESSON_PLAN,
    Text.BOX_CLASS_REPORT,
    Text.BOX_STUDENT_REPORT,
    Text.BOX_MANAGEMENT,
]

TABS = [Text.NAV_LESSONS, Text.NAV_CLASS, Text.NAV_STUDENTS, Text.NAV_MANAGE]


@pytest.mark.smoke
@pytest.mark.navigation
def test_full_smoke_journey(driver):
    # 1) Login (enrols via SANK48 if the number is not registered).
    login = LoginPage(driver)
    home = login.login_or_register()
    assert home.is_loaded(), "Home dashboard did not load after login"

    # 2) The dashboard identifies the school that was logged into.
    assert home.school_name_visible(SCHOOL_NAME)
    assert home.license_code(), "Home dashboard showed no student license code"

    # 3) Dashboard boxes: open each, confirm its section loads, return home.
    for box in BOXES:
        home.open_box(box)
        assert home.current_title_is(BOX_TO_TITLE[box])
        assert home.section_is_healthy(), f"{box} opened onto an error state"
        home.go_home()

    # 4) Nav destinations: open each and confirm its header title.
    for tab in TABS:
        home.go_to(tab)
        assert home.current_title_is(NAV_TO_TITLE[tab])
    home.go_to(Text.NAV_HOME)

    # 5) Drawer -> Logout -> back on the login screen.
    home.logout()
    assert login.is_loaded(timeout=40), "Logout did not return to the login screen"
