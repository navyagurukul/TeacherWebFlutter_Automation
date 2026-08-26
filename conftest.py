"""pytest fixtures: browser lifecycle + screenshot-on-failure.

Each test gets a fresh browser session. That is deliberate: a successful login
persists an auth token in web storage, after which the splash screen auto-logs-in
and the login screen never appears. A new session starts from a clean profile, so
every test begins logged out - the web counterpart of the Appium suite clearing
app data between tests.
"""
from __future__ import annotations

import pytest

from config import settings
from utils.driver_factory import create_driver, open_app

settings.SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


@pytest.fixture()
def driver():
    """A browser on the login screen, with Flutter's semantics tree enabled.

    Nothing needs clearing first: Selenium starts each session on a throwaway
    profile, so web storage is already empty and the portal opens logged out."""
    drv = create_driver()
    try:
        open_app(drv)
        yield drv
    finally:
        try:
            drv.quit()
        except Exception:
            pass


@pytest.fixture()
def login(driver):
    """Shorthand for the login page object on a freshly loaded portal."""
    from pages.login_page import LoginPage

    return LoginPage(driver)


@pytest.fixture()
def home(login):
    """A logged-in teacher shell, for tests whose subject is past the login."""
    return login.login_or_register()


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    """Capture a screenshot when a test fails, attached under reports/."""
    outcome = yield
    report = outcome.get_result()
    if report.when != "call" or not report.failed:
        return
    drv = item.funcargs.get("driver")
    if drv is None:
        return
    safe = item.nodeid.replace("/", "_").replace("::", "__").replace(".py", "")
    path = settings.SCREENSHOTS_DIR / f"{safe}.png"
    try:
        drv.save_screenshot(str(path))
        print(f"\n[screenshot] {path}")
    except Exception as exc:  # pragma: no cover - best effort
        print(f"\n[screenshot failed] {exc}")
