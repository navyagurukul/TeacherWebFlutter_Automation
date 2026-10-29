"""Lesson Plan section page object.

The section shows a class picker, a "<n> LESSON PLANS" count for the selected
class, and one card per lesson plan. Each card carries its title plus the counts
of attached PDFs and videos, and expands to a START action.
"""
from __future__ import annotations

import re

from data.test_data import (
    ASSESSMENT_ACTION_FOR_STATUS,
    ASSESSMENT_STATUS_AFTER_ACTION,
    ASSESSMENT_STATUS_FOR_ACTION,
    Text,
)
from pages.base_page import BasePage, _q


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
            Text.TITLE_LESSON_PLAN, Text.LESSON_START, Text.LESSON_RESTART,
            Text.LESSON_STOP,
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
        """Whether the expanded card exposes its lesson action: START, or
        RESTART / STOP once the lesson has been run."""
        if self.is_visible(Text.LESSON_START, timeout=timeout):
            return True
        return any(self.is_visible(label, timeout=2)
                   for label in (Text.LESSON_RESTART, Text.LESSON_STOP))

    def numbered_plan_titles(self) -> list[str]:
        """Titles of the "<n> - <title>" lesson cards. Programme cards such as
        'Microschedule - Sparkle 1' carry only a PDF and have no START."""
        return [t for t in self.plan_titles() if re.match(r"\d+\s*-\s", t)]

    # -- assessments ----------------------------------------------------------
    # An assessment card sits under its lesson plan. Its name is not a text
    # node: the card is a semantics group whose aria-label is the name, with the
    # START / STOP / RESTART button inside it.

    @staticmethod
    def _assessment_xpath(name: str) -> str:
        return f"//flt-semantics[@aria-label={_q(name)}]"

    @classmethod
    def _assessment_button_xpath(cls, name: str) -> str:
        return cls._assessment_xpath(name) + "//flt-semantics[@role='button']"

    def assessment_names(self) -> list[str]:
        """Names of the assessment cards rendered so far, in list order."""
        return self.driver.execute_script(
            """
            const out = [];
            document.querySelectorAll('flt-semantics[aria-label]').forEach(e => {
              const label = e.getAttribute('aria-label').trim();
              if (label.startsWith(arguments[0]) && !out.includes(label)) out.push(label);
            });
            return out;
            """,
            Text.ASSESSMENT_PREFIX,
        )

    def all_assessment_names(self, max_scrolls: int = 20, step: int = 500) -> list[str]:
        """Every assessment card in the selected class: the list is lazily
        rendered, so wheel through it collecting names, then return to the top."""
        names: list[str] = []
        for _ in range(max_scrolls):
            names += [n for n in self.assessment_names() if n not in names]
            self.scroll_by(step)
        self.scroll_by(-step * max_scrolls)
        return names

    def scroll_to_assessment(self, name: str, max_scrolls: int = 20, step: int = 400):
        """Wheel down until the card's action button is on screen."""
        xpath = self._assessment_button_xpath(name)
        for _ in range(max_scrolls):
            if self._visible_elements(xpath):
                return self
            self.scroll_by(step)
        raise AssertionError(f"assessment {name!r} is not in the lesson plan list")

    def assessment_action(self, name: str, timeout: int = 15) -> str:
        """The action the card offers now: START, STOP or RESTART."""
        xpath = self._assessment_button_xpath(name)
        label = self._poll(
            lambda: next(
                (e.text.strip() for e in self._visible_elements(xpath) if e.text.strip()),
                None,
            ),
            timeout,
            f"assessment {name!r} shows no action button",
        )
        return label

    def assessment_status(self, name: str) -> str:
        """Backend status the card displays: locked / unlocked / completed."""
        action = self.assessment_action(name)
        if action not in ASSESSMENT_STATUS_FOR_ACTION:
            raise AssertionError(f"assessment {name!r} shows unknown action {action!r}")
        return ASSESSMENT_STATUS_FOR_ACTION[action]

    def click_assessment_action(self, name: str, expected_action: str, timeout: int = 30) -> str:
        """Press the card's button and wait until it settles on the next state.

        `expected_action` guards against acting on a card that is not in the
        state the caller believes (e.g. STOP on an assessment already stopped).
        Returns the backend status the card now shows."""
        self.scroll_to_assessment(name)
        current = self.assessment_action(name)
        if current != expected_action:
            raise AssertionError(
                f"assessment {name!r} offers {current!r}, not {expected_action!r}"
            )
        target = ASSESSMENT_STATUS_AFTER_ACTION[expected_action]
        target_action = ASSESSMENT_ACTION_FOR_STATUS[target]
        xpath = self._assessment_button_xpath(name)
        self._click_element(self._poll(
            lambda: next(iter(self._visible_elements(xpath)), None),
            10, f"assessment {name!r} button vanished",
        ))
        # The button spins while the PATCH is in flight, then relabels; the
        # app shows a 'Could not update the test' snackbar if it failed.
        self._poll(
            lambda: self._assessment_label_is(name, target_action),
            timeout,
            f"assessment {name!r} did not change to {target_action!r} "
            f"(snackbar: {self.is_visible(Text.ASSESSMENT_UPDATE_FAILED, timeout=1)})",
        )
        return target

    def _assessment_label_is(self, name: str, action: str) -> bool:
        xpath = self._assessment_button_xpath(name)
        return any(e.text.strip() == action for e in self._visible_elements(xpath))

    def start_assessment(self, name: str) -> str:
        return self.click_assessment_action(name, Text.LESSON_START)

    def stop_assessment(self, name: str) -> str:
        return self.click_assessment_action(name, Text.LESSON_STOP)

    def restart_assessment(self, name: str) -> str:
        return self.click_assessment_action(name, Text.LESSON_RESTART)

    def set_assessment_status(self, name: str, target: str) -> str:
        """Drive the card to `target` (unlocked / completed) with whatever
        button gets it there. A card cannot be returned to locked from the UI."""
        self.scroll_to_assessment(name)
        current = self.assessment_status(name)
        if current == target:
            return current
        if target == "completed":
            if current != "unlocked":
                raise AssertionError(
                    f"assessment {name!r} is {current!r}; only a running one can be stopped"
                )
            return self.stop_assessment(name)
        if target == "unlocked":
            return self.click_assessment_action(name, ASSESSMENT_ACTION_FOR_STATUS[current])
        raise ValueError(f"the portal cannot set an assessment to {target!r}")
