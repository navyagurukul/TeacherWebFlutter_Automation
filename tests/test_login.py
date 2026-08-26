"""Login flow tests for the web portal. All logins use the Sanskruthi school."""
import pytest

from data.test_data import INVALID_MOBILE_SHORT, SCHOOL_NAME, TEACHER_MOBILE, Text
from pages.login_page import LoginPage
from utils import app_version


@pytest.mark.smoke
@pytest.mark.login
def test_login_screen_loads(driver):
    login = LoginPage(driver)
    assert login.is_loaded(), "Login screen did not show 'Sign in to continue'"
    assert login.is_visible(Text.LOGIN_BUTTON)
    assert login.is_visible(Text.REGISTER_BUTTON)
    assert login.is_visible(Text.SELECT_SCHOOL_HINT)


@pytest.mark.smoke
@pytest.mark.login
def test_login_shows_app_version(driver):
    # The footer reads "ENGLISH GURUKUL TEACHER PORTAL V<version>". Assert it is
    # shown and record it, so the daily report can tie its summary to the exact
    # build the portal served (utils/app_version.py reads this).
    login = LoginPage(driver)
    assert login.is_loaded()

    label = login.version_label()
    assert label and Text.VERSION_PREFIX in label, (
        f"login screen did not show the version footer (got: {label!r})"
    )
    assert login.version_number(), f"footer carried no version number: {label!r}"
    app_version.capture(label)


@pytest.mark.smoke
@pytest.mark.login
def test_school_picker_finds_sanskruthi(driver):
    login = LoginPage(driver)
    login.click_button(Text.SELECT_SCHOOL_HINT)
    login.type_into(Text.SEARCH_SCHOOL_FIELD, "Sanskruthi")
    assert login.is_visible(SCHOOL_NAME, timeout=20), (
        f"Searching 'Sanskruthi' did not list {SCHOOL_NAME!r}"
    )


@pytest.mark.smoke
@pytest.mark.login
def test_login_reaches_home(driver):
    # Select the school, enter the teacher number and LOG IN; enrol via the
    # SANK48 license code if the number is not registered. Either path must land
    # on the home dashboard.
    login = LoginPage(driver)
    home = login.login_or_register(TEACHER_MOBILE)
    assert home.is_loaded(), "Home dashboard ('Welcome!') did not load after login"
    assert home.school_name_visible(SCHOOL_NAME), (
        "Home dashboard did not show the school that was logged into"
    )


@pytest.mark.regression
@pytest.mark.login
def test_login_requires_school(driver):
    login = LoginPage(driver)
    login.enter_mobile(TEACHER_MOBILE)
    login.click_login()
    assert login.validation_error_visible(Text.SCHOOL_REQUIRED), (
        "Expected the 'Please select a school' message"
    )


@pytest.mark.regression
@pytest.mark.login
def test_login_requires_mobile(driver):
    login = LoginPage(driver)
    login.select_school(SCHOOL_NAME)
    login.click_login()
    assert login.validation_error_visible(Text.MOBILE_REQUIRED), (
        "Expected the 'Mobile number is required' validation error"
    )


@pytest.mark.regression
@pytest.mark.login
def test_login_rejects_short_mobile(driver):
    login = LoginPage(driver)
    login.select_school(SCHOOL_NAME)
    login.enter_mobile(INVALID_MOBILE_SHORT)
    login.click_login()
    assert login.validation_error_visible(Text.MOBILE_INVALID), (
        "Expected the 'Enter a valid 10-digit number' validation error"
    )
