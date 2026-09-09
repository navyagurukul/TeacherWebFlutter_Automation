"""Registration flow page objects: the license-code dialog and the
"Create your account" screen.

Reached from the login screen's REGISTER button. The license code resolves the
school (read-only badge), then the teacher supplies name + language; a successful
submit signs them straight into the TeacherShell.
"""
from __future__ import annotations

from data.test_data import LANGUAGE_ORDER, TEACHER_LANGUAGE, Text
from pages.base_page import BasePage
from pages.home_page import HomePage


class LicenseDialog(BasePage):
    def is_open(self, timeout: int = 25) -> bool:
        return self.is_visible(Text.LICENSE_TITLE, timeout=timeout)

    def wait_open(self, timeout: int = 25):
        self.find_text(Text.LICENSE_TITLE, timeout=timeout)
        return self

    def enter_code_and_continue(self, code: str):
        # The dialog's field carries no stable aria-label, so it is targeted as
        # the one input the dialog has just put on screen.
        self.type_first_visible_input(code)
        self.click_button(Text.LICENSE_CONTINUE)
        return self


class RegisterPage(BasePage):
    def wait_loaded(self, timeout: int = 30):
        self.find_text(Text.REGISTER_TITLE, timeout=timeout)
        return self

    def is_loaded(self, timeout: int = 20) -> bool:
        return self.is_visible(Text.REGISTER_TITLE, timeout=timeout)

    def enter_name(self, name: str):
        # Name is the first field on this screen; mobile is pre-filled from the
        # login screen.
        self.type_first_visible_input(name)
        return self

    def select_language(self, language: str = TEACHER_LANGUAGE):
        """Open the language dropdown and pick `language`.

        By position, not by label. Flutter publishes the open menu as
        `role="menu"` over `role="menuitem"` rows that carry **no text at all**
        - a `DropdownMenuItem`'s child label never reaches the DOM - so every
        text locator misses. The field does show the chosen language once the
        menu closes, which is where the pick gets verified."""
        self.click_button(Text.SELECT_LANGUAGE_HINT)
        self.click_menu_item(LANGUAGE_ORDER.index(language), timeout=25)
        if not self.is_visible(language, timeout=20):
            raise AssertionError(
                f"picked language row {LANGUAGE_ORDER.index(language)} but the "
                f"field does not show {language!r} - LANGUAGE_ORDER is out of "
                "step with the app's dropdown"
            )
        return self

    def submit(self) -> HomePage:
        self.click_button(Text.REGISTER_SUBMIT)
        return HomePage(self.driver).wait_loaded()
