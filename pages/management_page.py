"""Student Management section page object.

Management is a hub screen: a MANAGEMENT HOME header over five action tiles
(registration, approval, edit, delete, bulk registration).
"""
from __future__ import annotations

from data.test_data import MANAGEMENT_ACTIONS, Text
from pages.base_page import BasePage


class ManagementPage(BasePage):
    def wait_loaded(self, timeout: int = 45):
        self.find_text(Text.TITLE_MANAGEMENT, timeout=timeout)
        self.find_text(Text.MANAGEMENT_HEADER, timeout=timeout)
        return self

    def is_loaded(self, timeout: int = 30) -> bool:
        return self.is_visible(Text.TITLE_MANAGEMENT, timeout=timeout)

    def available_actions(self) -> list[str]:
        """Which of the five management tiles are on screen."""
        on_screen = set(self.visible_texts())
        return [a for a in MANAGEMENT_ACTIONS if a in on_screen]

    def open_action(self, action: str, timeout: int = 30):
        self.click_button(action, timeout=timeout)
        return self
