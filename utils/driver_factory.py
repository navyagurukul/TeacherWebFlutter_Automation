"""Creates the Selenium driver and gets the Flutter Web app into a state the
suite can actually see.

Why this file is more than a two-liner
--------------------------------------
teacher.englishgurukul.in is the Flutter teacher app compiled for web with the
**CanvasKit** renderer. Every button, label and list row is *painted into a
<canvas>* - there is no HTML for the suite to select.

Flutter does publish a parallel DOM tree for screen readers: `<flt-semantics>`
nodes carrying the visible text, `role="button"`, and real `<input>` elements for
text fields. That tree is the exact web counterpart of the Android accessibility
tree the Appium suite drives, so the page objects stay recognisable.

The catch: Flutter builds that tree only once it believes assistive technology is
present. Until then it renders a single hidden "Enable accessibility" button. So
every session must click that placeholder first - `enable_semantics()` below -
and the tree must be re-enabled after any reload, because a reload restarts the
engine with semantics off again.
"""
from __future__ import annotations

import time

from selenium import webdriver
from selenium.common.exceptions import WebDriverException

from config import settings
from config.browser_options import build_options

# Flutter's own DOM landmarks. Stable across Flutter 3.x web builds.
SEMANTICS_HOST = "flt-semantics-host"
SEMANTICS_PLACEHOLDER = "flt-semantics-placeholder"
FLUTTER_VIEW = "flutter-view"

_ENABLE_SEMANTICS_JS = f"""
const p = document.querySelector({SEMANTICS_PLACEHOLDER!r});
if (!p) return 'no-placeholder';
p.click();
return 'clicked';
"""

_SEMANTICS_READY_JS = f"""
const host = document.querySelector({SEMANTICS_HOST!r});
return !!host && host.querySelectorAll('flt-semantics').length > 0;
"""

# Flutter mounts <flutter-view>, then renders the scene *inside the shadow root*
# of <flt-glass-pane>. A plain document.querySelector('canvas') never sees it -
# shadow DOM is exactly what a shadow root hides - so this pierces the root.
_ENGINE_PAINTED_JS = f"""
const view = document.querySelector({FLUTTER_VIEW!r});
if (!view) return false;
const pane = view.querySelector('flt-glass-pane');
const root = (pane && pane.shadowRoot) ? pane.shadowRoot : view;
return !!root.querySelector('flt-scene, canvas') ||
       !!document.querySelector({SEMANTICS_PLACEHOLDER!r});
"""


def create_driver():
    """A fresh browser session. Selenium Manager resolves the matching driver
    binary, so there is nothing to install or keep in sync by hand."""
    options = build_options()
    if settings.BROWSER == "chrome":
        driver = webdriver.Chrome(options=options)
    elif settings.BROWSER == "edge":
        driver = webdriver.Edge(options=options)
    else:
        driver = webdriver.Firefox(options=options)

    # Deliberately 0: the semantics tree is rebuilt constantly, so an implicit
    # wait would silently return stale nodes. All waiting is explicit and
    # re-queries every poll (see pages/base_page.py).
    driver.implicitly_wait(0)
    driver.set_page_load_timeout(settings.APP_LOAD_TIMEOUT)
    return driver


def wait_for_engine(driver, timeout: int | None = None) -> None:
    """Block until the Flutter engine has mounted and begun rendering.

    This only gets the app off the blank page; the gate the suite really depends
    on is the semantics tree, which `enable_semantics()` waits for next."""
    timeout = timeout or settings.APP_LOAD_TIMEOUT
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            if driver.execute_script(_ENGINE_PAINTED_JS):
                return
        except WebDriverException:
            pass  # engine still bootstrapping; the document can swap under us
        time.sleep(0.5)
    raise TimeoutError(
        f"Flutter engine did not paint within {timeout}s at {driver.current_url}"
    )


def semantics_ready(driver) -> bool:
    try:
        return bool(driver.execute_script(_SEMANTICS_READY_JS))
    except WebDriverException:
        return False


def enable_semantics(driver, timeout: int | None = None) -> None:
    """Turn on Flutter's accessibility tree, the suite's only view of the UI.

    Clicks the hidden "Enable accessibility" placeholder and waits for the first
    `<flt-semantics>` nodes to appear. Safe to call again at any time: once the
    tree exists this returns immediately, which is what makes it cheap to call
    after every navigation.

    The click and the tree are two separate events, and the gap between them is
    the whole app booting: the placeholder is in the DOM long before Flutter has
    a widget tree to describe, so an early click enables semantics but populates
    nothing. That is why this keeps re-clicking for the full engine-boot budget
    rather than giving up after a few seconds - on a loaded machine (an
    unattended run sharing the box with another suite) boot alone can outlast a
    short timeout, and failing there would report a healthy portal as broken."""
    timeout = settings.APP_LOAD_TIMEOUT if timeout is None else timeout
    if semantics_ready(driver):
        return

    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            driver.execute_script(_ENABLE_SEMANTICS_JS)
        except WebDriverException:
            pass
        # Give Flutter a frame or two to build the tree before re-checking.
        for _ in range(10):
            if semantics_ready(driver):
                return
            time.sleep(0.3)

    raise TimeoutError(
        f"Flutter never built its semantics tree within {timeout}s - the suite "
        "cannot see the UI. Check that the page really loaded and that the build "
        f"still renders the '{SEMANTICS_PLACEHOLDER}' element."
    )


def open_app(driver, url: str | None = None) -> None:
    """Load the portal and leave it ready to drive: engine painted, semantics on."""
    driver.get(url or settings.BASE_URL)
    wait_for_engine(driver)
    enable_semantics(driver)


def log_out_of_storage(driver) -> None:
    """Drop stored auth on an already-loaded page, then reload logged out.

    A successful login persists a token in web storage, after which the splash
    screen auto-logs-in and the login screen never appears - the behaviour the
    Appium suite defeats with `mobile: clearApp`. Tests do not normally need this
    (each gets a throwaway browser profile), but it is what to reach for when one
    session has to log in twice.

    Must run with the portal loaded: web storage is per-origin, so calling it on
    a blank tab clears nothing."""
    try:
        driver.execute_script("window.localStorage.clear(); window.sessionStorage.clear();")
    except WebDriverException:
        pass
    try:
        driver.delete_all_cookies()
    except WebDriverException:
        pass
    driver.refresh()
    wait_for_engine(driver)
    enable_semantics(driver)
