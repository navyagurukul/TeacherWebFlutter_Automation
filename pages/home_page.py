"""Home / teacher-shell page object: header, dashboard boxes, nav, and drawer.

The web build keeps the app's shell: five destinations behind a nav bar, a header
whose title changes per destination, and a drawer holding Profile / Star Arena /
Test / Zoom Training / Logout. It adds a light/dark toggle the Android build has
no counterpart for.
"""
from __future__ import annotations

from data.test_data import Text
from pages.base_page import BasePage

# Nav label -> the header title shown once that destination is active.
NAV_TO_TITLE = {
    Text.NAV_HOME: Text.HOME_TITLE,
    Text.NAV_LESSONS: Text.TITLE_LESSON_PLAN,
    Text.NAV_CLASS: Text.TITLE_CLASS_REPORT,
    Text.NAV_STUDENTS: Text.TITLE_STUDENT_REPORT,
    Text.NAV_MANAGE: Text.TITLE_MANAGEMENT,
}

# Home-dashboard box -> the header title shown after clicking it.
BOX_TO_TITLE = {
    Text.BOX_LESSON_PLAN: Text.TITLE_LESSON_PLAN,
    Text.BOX_CLASS_REPORT: Text.TITLE_CLASS_REPORT,
    Text.BOX_STUDENT_REPORT: Text.TITLE_STUDENT_REPORT,
    Text.BOX_MANAGEMENT: Text.TITLE_MANAGEMENT,
}

# Error states a healthy section must not be showing.
ERROR_STATES = (Text.GENERIC_ERROR, Text.NO_INTERNET)


class HomePage(BasePage):
    def wait_loaded(self, timeout: int = 60):
        """Login posts to the API before the shell paints, so this waits longer
        than an ordinary screen transition."""
        self.find_text(Text.HOME_TITLE, timeout=timeout)
        return self

    def is_loaded(self, timeout: int = 20) -> bool:
        return self.is_visible(Text.HOME_TITLE, timeout=timeout)

    # -- navigation -----------------------------------------------------------

    def go_to(self, nav_label: str, timeout: int = 45):
        self.click_button(nav_label)
        self.find_text(NAV_TO_TITLE[nav_label], timeout=timeout)
        return self

    def go_home(self, timeout: int = 30):
        self.click_button(Text.NAV_HOME)
        self.find_text(Text.HOME_TITLE, timeout=timeout)
        return self

    def current_title_is(self, title: str, timeout: int = 20) -> bool:
        return self.is_visible(title, timeout=timeout)

    def open_box(self, box_label: str, timeout: int = 45):
        """Click a home-dashboard box and wait for its section header."""
        self.click_button(box_label)
        self.find_text(BOX_TO_TITLE[box_label], timeout=timeout)
        return self

    def section_is_healthy(self) -> bool:
        """No error/offline state on the current section."""
        return not any(self.is_visible(state, timeout=2) for state in ERROR_STATES)

    # -- header details -------------------------------------------------------

    def school_name_visible(self, school: str) -> bool:
        return self.is_visible(school, timeout=20)

    def license_code(self) -> str | None:
        """The student license code the home dashboard shows for this school."""
        if not self.is_visible(Text.LICENSE_CODE_LABEL, timeout=10):
            return None
        texts = self.visible_texts()
        try:
            index = texts.index(Text.LICENSE_CODE_LABEL)
        except ValueError:
            return None
        # The code renders as the node immediately after its label.
        return texts[index + 1] if index + 1 < len(texts) else None

    def version_label(self) -> str | None:
        """The shell also carries the version footer; same string as login."""
        try:
            return (self.find_text(Text.VERSION_PREFIX, exact=False, timeout=10).text or "").strip() or None
        except TimeoutError:
            return None

    # -- theme toggle (web only) ---------------------------------------------

    def toggle_theme(self):
        """Flip light/dark. The button's own label names the *target* theme, so
        it reads 'Switch to dark mode' while the portal is light."""
        target = (
            Text.DARK_MODE_TOGGLE
            if self.is_visible(Text.DARK_MODE_TOGGLE, timeout=5)
            else Text.LIGHT_MODE_TOGGLE
        )
        self.click_button(target)
        return self

    def current_theme(self) -> str:
        """'light' or 'dark', read off which way the toggle offers to switch."""
        return "light" if self.is_visible(Text.DARK_MODE_TOGGLE, timeout=5) else "dark"

    # -- drawer ---------------------------------------------------------------

    def open_menu(self):
        self.click_button(Text.MENU_BUTTON)
        self.find_text(Text.MENU_LOGOUT, timeout=20)
        return self

    def open_profile(self):
        self.open_menu()
        self.click_button(Text.MENU_PROFILE)
        return self

    def logout(self):
        self.open_menu()
        self.click_button(Text.MENU_LOGOUT)
        return self
