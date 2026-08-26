"""Lesson Plan section page object.

The section shows a class picker, a "<n> LESSON PLANS" count for the selected
class, and one card per lesson plan. Each card carries its title plus the counts
of attached PDFs and videos, and expands to a START action.
"""
from __future__ import annotations

import re

from data.test_data import Text
from pages.base_page import BasePage


class LessonPlanPage(BasePage):
    def wait_loaded(self, timeout: int = 45):
        self.find_text(Text.TITLE_LESSON_PLAN, timeout=timeout)
        # The plan list arrives from the API after the header paints.
        self.find_text(Text.LESSON_PLANS_SUFFIX, exact=False, timeout=timeout)
        return self

    def is_loaded(self, timeout: int = 30) -> bool:
        return self.is_visible(Text.TITLE_LESSON_PLAN, timeout=timeout)

    # -- class selection ------------------------------------------------------

    def selected_class(self) -> str | None:
        """The class the picker currently shows, e.g. 'Class 1'.

        Read off the picker *button*, not the page text: the section also prints
        the same class as an uppercase heading ('CLASS 1')."""
        for label in self.visible_buttons():
            if re.fullmatch(r"Class \d+", label.strip()):
                return label.strip()
        return None

    def select_class(self, class_label: str):
        current = self.selected_class()
        if current == class_label:
            return self
        if current is None:
            raise AssertionError("Lesson Plan has no class picker on screen")
        self.click_button(current)
        self.click_button(class_label, timeout=25)
        self.find_text(Text.LESSON_PLANS_SUFFIX, exact=False, timeout=45)
        return self

    # -- plan list ------------------------------------------------------------

    def plan_count(self) -> int | None:
        """The count the header states, from e.g. '12 LESSON PLANS'."""
        for label in self.visible_texts():
            match = re.fullmatch(rf"(\d+)\s+{Text.LESSON_PLANS_SUFFIX}", label)
            if match:
                return int(match.group(1))
        return None

    def plan_titles(self) -> list[str]:
        """Titles of the plan cards currently on screen.

        Each card is one semantics node stacking the title over its PDF and video
        counts - "3 - Long Vowels\\n1\\n3" - so only the first line is the title.
        Plans are named either "<n> - <title>" or a bare programme name (e.g.
        'Microschedule - Sparkle 1'), so cards are identified by elimination:
        every button that is not the shell's own chrome or the class picker."""
        chrome = {
            Text.NAV_HOME, Text.NAV_LESSONS, Text.NAV_CLASS,
            Text.NAV_STUDENTS, Text.NAV_MANAGE, Text.MENU_BUTTON,
            Text.TITLE_LESSON_PLAN, Text.LESSON_START,
            Text.DARK_MODE_TOGGLE, Text.LIGHT_MODE_TOGGLE,
        }
        titles = []
        for label in self.visible_buttons():
            title = label.split("\n")[0].strip()
            if not title or title in chrome or title.isdigit():
                continue
            if re.fullmatch(r"Class \d+", title, re.IGNORECASE):
                continue
            if title.endswith(Text.LESSON_PLANS_SUFFIX):
                continue
            titles.append(title)
        return titles

    def open_plan(self, title: str, timeout: int = 30):
        """Expand a plan card by its title.

        Matched as a prefix, not exactly: the card's node text carries its media
        counts after the title."""
        if self.scroll_to_text(title, exact=False) is None:
            raise AssertionError(f"lesson plan {title!r} is not in the list")
        self.click_button(title, exact=False, timeout=timeout)
        return self

    def start_visible(self, timeout: int = 15) -> bool:
        """Whether the expanded card exposes its START action."""
        return self.is_visible(Text.LESSON_START, timeout=timeout)
