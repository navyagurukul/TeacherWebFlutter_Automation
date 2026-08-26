"""Behaviour that only exists on the web portal, with no Android counterpart:
the light/dark toggle, session survival across a browser reload, and the
responsive layout at a phone-sized viewport.
"""
import pytest

from config import settings
from data.test_data import Text
from utils.driver_factory import enable_semantics, wait_for_engine


@pytest.mark.web
@pytest.mark.smoke
def test_theme_toggle_switches_and_returns(home):
    started = home.current_theme()
    home.toggle_theme()
    assert home.current_theme() != started, "Theme toggle did not change the theme"
    home.toggle_theme()
    assert home.current_theme() == started, "Theme toggle did not switch back"
    assert home.is_loaded(), "Shell did not survive the theme change"


@pytest.mark.web
@pytest.mark.regression
def test_session_survives_a_reload(home):
    # Logging in persists a token in web storage; reloading the tab must land
    # back on the dashboard rather than the login screen.
    driver = home.driver
    driver.refresh()
    wait_for_engine(driver)
    enable_semantics(driver)
    assert home.is_loaded(timeout=60), (
        "Reloading the portal did not restore the logged-in session"
    )
    assert not home.is_visible(Text.SIGN_IN_HEADING, timeout=5), (
        "Reload dropped the session back to the login screen"
    )


@pytest.mark.web
@pytest.mark.regression
def test_layout_works_at_phone_width(home):
    # Teachers open the portal on small laptops and phones; the shell must stay
    # navigable when the viewport is narrow.
    driver = home.driver
    driver.set_window_size(420, 900)
    try:
        assert home.is_loaded(timeout=30), "Shell did not survive the resize"
        home.go_to(Text.NAV_LESSONS)
        assert home.current_title_is(Text.TITLE_LESSON_PLAN), (
            "Navigation broke at phone width"
        )
    finally:
        driver.set_window_size(settings.WINDOW_WIDTH, settings.WINDOW_HEIGHT)
