"""Login screen page object.

Flow: click the School field -> a searchable dialog opens -> search + click the
school -> type the 10-digit mobile -> click LOG IN. On success the portal
replaces the login screen with the teacher shell (home).
"""
from __future__ import annotations

import re
import time

from data.test_data import (
    LANGUAGE_ORDER,
    LICENSE_CODE,
    SCHOOL_NAME,
    SCHOOL_SEARCH,
    TEACHER_LANGUAGE,
    TEACHER_MOBILE,
    TEACHER_NAME,
    Text,
)
from pages.base_page import BasePage
from pages.home_page import HomePage


class LoginPage(BasePage):
    def wait_loaded(self, timeout: int = 40):
        self.find_text(Text.SIGN_IN_HEADING, timeout=timeout)
        return self

    def is_loaded(self, timeout: int = 30) -> bool:
        return self.is_visible(Text.SIGN_IN_HEADING, timeout=timeout)

    # -- school picker --------------------------------------------------------

    def open_school_picker(self, current_school: str = SCHOOL_NAME):
        """Open the picker by clicking the school field, which shows the
        'Select school' hint until a school is chosen and its name afterwards."""
        hint = Text.SELECT_SCHOOL_HINT
        self.click_button(hint if self.is_visible(hint, timeout=3) else current_school)
        self.find_input(Text.SEARCH_SCHOOL_FIELD, timeout=20)
        return self

    def select_school(self, school_name: str = SCHOOL_NAME, search: str = SCHOOL_SEARCH):
        self.click_button(Text.SELECT_SCHOOL_HINT)
        # The picker is a modal dialog with a search box over the full school list.
        self.type_into(Text.SEARCH_SCHOOL_FIELD, search)
        # Click the row as a *button*: after the dialog closes the login screen
        # shows the same name on the school field, so a plain text match would be
        # ambiguous on a retry.
        self.click_button(school_name, timeout=30)
        # The dialog must be gone before the mobile field is safe to type into.
        self.is_gone(Text.SEARCH_SCHOOL_FIELD)
        return self

    def selected_school(self) -> str | None:
        """The school currently shown on the field, or None if still unset."""
        if self.is_visible(Text.SELECT_SCHOOL_HINT, timeout=2):
            return None
        for label in self.visible_texts():
            if "School" in label or "school" in label:
                return label
        return None

    # -- credentials ----------------------------------------------------------

    def enter_mobile(self, mobile: str):
        self.type_into(Text.MOBILE_FIELD, mobile)
        return self

    def click_login(self):
        self.click_button(Text.LOGIN_BUTTON)
        return self

    def click_register(self):
        self.click_button(Text.REGISTER_BUTTON)
        return self

    # -- journeys -------------------------------------------------------------

    def login(self, mobile: str = TEACHER_MOBILE, school_name: str = SCHOOL_NAME) -> HomePage:
        self.select_school(school_name)
        self.enter_mobile(mobile)
        self.click_login()
        return HomePage(self.driver).wait_loaded()

    def login_or_register(
        self,
        mobile: str = TEACHER_MOBILE,
        name: str = TEACHER_NAME,
        language: str = TEACHER_LANGUAGE,
        license_code: str = LICENSE_CODE,
    ) -> HomePage:
        """Try to log in; if the number isn't enrolled, enrol it via the license
        code. Mirrors real teacher onboarding - and mirrors the Appium suite, so
        the two suites stay comparable."""
        self.select_school()
        self.enter_mobile(mobile)
        self.click_login()

        home = HomePage(self.driver)
        if self._login_reached_home(home):
            return home

        # The request came back and left us on the login screen: the number is
        # not enrolled. School and mobile are already filled in.
        self.register(mobile, name, language, license_code, mobile_already_entered=True)
        return home.wait_loaded()

    def _login_reached_home(self, home: HomePage, timeout: int = 120) -> bool:
        """Wait out the LOG IN request. True once the shell is up.

        False means the request genuinely came back without navigating, which is
        what an unenrolled number looks like - never merely that a deadline
        passed. The difference matters because the caller answers a False by
        enrolling a teacher for real, and login is slower than it looks: it
        chains login -> me -> school before it swaps the shell in, so on a
        loaded CI runner a fixed budget expires mid-request and sends the suite
        into a registration it was never asked to do.

        The signal is the button's own: LOG IN swaps its label for a spinner
        while the request is out, so the label being back is the request
        reporting itself finished. It has to stay back across consecutive polls
        - the label is still up for the frame between the click and the
        spinner."""
        end = time.monotonic() + timeout
        settled = 0
        while time.monotonic() < end:
            if home.is_loaded(timeout=1):
                return True
            if self.is_visible(Text.LOGIN_BUTTON, timeout=1):
                settled += 1
                if settled >= 3:
                    return False
            else:
                settled = 0  # spinner up, request still in flight
            time.sleep(0.5)
        raise TimeoutError(
            f"LOG IN neither reached the teacher shell nor came back within "
            f"{timeout}s - the portal is not responding, so the suite is not "
            "going to guess at registering instead"
        )

    def register(
        self,
        mobile: str = TEACHER_MOBILE,
        name: str = TEACHER_NAME,
        language: str = TEACHER_LANGUAGE,
        license_code: str = LICENSE_CODE,
        mobile_already_entered: bool = False,
    ) -> HomePage:
        """REGISTER path: license code -> name + language -> submit -> home.

        NOTE: the QA number is already enrolled at Sanskruthi, so this branch is
        exercised only if that ever stops being true. It follows the same screens
        as the Android build; re-verify the copy here if it starts failing."""
        if not mobile_already_entered:
            self.enter_mobile(mobile)
        self.click_register()

        # License dialog.
        self.find_text(Text.LICENSE_TITLE, timeout=25)
        self._type_first_visible_input(license_code)
        self.click_button(Text.LICENSE_CONTINUE)

        # "Create your account" screen.
        self.find_text(Text.REGISTER_TITLE, timeout=30)
        self._type_first_visible_input(name)
        self.click_button(Text.SELECT_LANGUAGE_HINT)
        # Positional, not by label: the open menu's rows carry no text at all
        # (see BasePage.click_menu_item). The field does show the chosen
        # language once the menu closes, so the pick is verified there.
        self.click_menu_item(LANGUAGE_ORDER.index(language), timeout=25)
        if not self.is_visible(language, timeout=20):
            raise AssertionError(
                f"picked language row {LANGUAGE_ORDER.index(language)} but the "
                f"field does not show {language!r} - LANGUAGE_ORDER is out of "
                "step with the app's dropdown"
            )
        self.click_button(Text.REGISTER_SUBMIT)
        return HomePage(self.driver).wait_loaded()

    def _type_first_visible_input(self, value: str) -> None:
        """Type into whichever field the current dialog/screen just focused.

        Dialog fields do not always carry a stable aria-label, so this targets
        the one input Flutter has on screen at that moment."""
        from selenium.webdriver.common.by import By

        def attempt():
            fields = [
                e
                for e in self.driver.find_elements(By.CSS_SELECTOR, "input, textarea")
                if e.is_displayed()
            ]
            if not fields:
                return None
            fields[0].click()
            fields[0].send_keys(value)
            return True

        self._poll(attempt, 20, "no text field to type into")

    # -- app version ----------------------------------------------------------

    def version_label(self) -> str | None:
        """The footer at the bottom of the login screen, e.g.
        'ENGLISH GURUKUL TEACHER PORTAL V2.4.3'.

        The daily report ties its summary to this exact string, so it always
        names the build the portal actually served. Returns None if the footer
        is missing."""
        try:
            el = self.find_text(Text.VERSION_PREFIX, exact=False, timeout=15)
        except TimeoutError:
            return None
        label = (el.text or "").strip()
        return label or None

    def version_number(self) -> str | None:
        """Just the dotted version from the footer, e.g. '2.4.3'."""
        label = self.version_label()
        if not label:
            return None
        match = re.search(r"[Vv]?\s*([0-9]+(?:\.[0-9]+)+[0-9A-Za-z.\-+]*)", label)
        return match.group(1) if match else None

    # -- validation helpers ---------------------------------------------------

    def validation_error_visible(self, message: str, timeout: int = 12) -> bool:
        """Validation text and snackbars both surface as ordinary semantics
        nodes, so one check covers both."""
        return self.is_visible(message, timeout=timeout)
