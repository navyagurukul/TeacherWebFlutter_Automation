"""Student Management section tests: the hub offers every management action."""
import pytest

from data.test_data import MANAGEMENT_ACTIONS, Text
from pages.management_page import ManagementPage


@pytest.fixture()
def management(home):
    home.go_to(Text.NAV_MANAGE)
    return ManagementPage(home.driver).wait_loaded()


@pytest.mark.smoke
@pytest.mark.management
def test_management_home_lists_every_action(management):
    available = management.available_actions()
    missing = [a for a in MANAGEMENT_ACTIONS if a not in available]
    assert not missing, f"Management home is missing: {missing}"


@pytest.mark.regression
@pytest.mark.management
def test_student_registration_opens(management):
    # Opens the registration screen only - it does not submit, so no student is
    # created against the live school.
    # Assert the new screen's title rather than the hub's absence: Flutter keeps
    # the hub mounted beneath a pushed route, so its header can still be in the
    # semantics tree on a slow runner even though the screen has changed.
    management.open_action(Text.MANAGE_REGISTRATION)
    assert management.is_visible(Text.REGISTER_STUDENT_TITLE, timeout=30), (
        f"STUDENT REGISTRATION did not open the {Text.REGISTER_STUDENT_TITLE!r} screen"
    )
