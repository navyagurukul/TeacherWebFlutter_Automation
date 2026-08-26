"""Base page object: Flutter-Web-aware element helpers over the semantics tree.

How locating works here
-----------------------
The portal is CanvasKit-rendered, so nothing in the visible UI is real HTML.
What the suite drives instead is Flutter's accessibility tree:

    <flt-semantics-host>
      <flt-semantics role="button"><span>LOG IN</span></flt-semantics>
      <input aria-label="10-digit mobile number" type="tel">
      ...

So the rules are:
  * **text and buttons** -> an `<flt-semantics>` node whose text is that label.
    A leaf node's text is exactly its own label, while an ancestor's text is the
    concatenation of everything beneath it, so an exact match reliably picks the
    leaf and never its container.
  * **text fields** -> a genuine `<input>` carrying the field's hint as its
    `aria-label`, which can be typed into like any ordinary web input.

This mirrors the Appium suite one-to-one (there: visible text + content-desc),
which is why the page objects on top read almost identically.

Everything re-queries on each poll rather than holding element handles: Flutter
rebuilds and recycles semantics nodes on every frame, so a handle held across a
state change goes stale constantly.
"""
from __future__ import annotations

import time
from typing import Optional

from selenium.common.exceptions import (
    ElementClickInterceptedException,
    ElementNotInteractableException,
    NoSuchElementException,
    StaleElementReferenceException,
    WebDriverException,
)
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from config import settings
from utils.driver_factory import enable_semantics

# Errors that mean "the UI moved under us" - always worth one more attempt.
TRANSIENT = (
    StaleElementReferenceException,
    ElementClickInterceptedException,
    ElementNotInteractableException,
    NoSuchElementException,
)


def _q(value: str) -> str:
    """Quote a string for XPath, handling embedded quotes via concat()."""
    if '"' not in value:
        return f'"{value}"'
    if "'" not in value:
        return f"'{value}'"
    parts = value.split('"')
    return "concat(" + ", '\"', ".join(f'"{p}"' for p in parts) + ")"


class BasePage:
    def __init__(self, driver):
        self.driver = driver

    # -- locator builders -----------------------------------------------------

    @staticmethod
    def node_xpath(text: str, exact: bool = True, role: Optional[str] = None) -> str:
        """XPath for the semantics node showing `text`.

        `normalize-space()` matters: Flutter merges a widget's lines into one
        node, so a two-line button reads as "257 of 348" here."""
        role_pred = f"[@role={_q(role)}]" if role else ""
        match = (
            f"normalize-space(.)={_q(text)}"
            if exact
            else f"contains(normalize-space(.),{_q(text)})"
        )
        return f"//flt-semantics{role_pred}[{match}]"

    @staticmethod
    def input_css(label: str) -> str:
        return f'input[aria-label="{label}"], textarea[aria-label="{label}"]'

    # -- low-level polling ----------------------------------------------------

    def _poll(self, fn, timeout: int, what: str):
        """Call `fn` until it returns something truthy. Swallows the transient
        DOM churn Flutter causes; anything else is a real failure and re-raised."""
        end = time.monotonic() + timeout
        last = None
        while time.monotonic() < end:
            try:
                if got := fn():
                    return got
            except TRANSIENT as exc:
                last = exc
            except WebDriverException as exc:
                last = exc
            time.sleep(0.25)
        raise TimeoutError(f"{what} (waited {timeout}s)" + (f" - last error: {last}" if last else ""))

    def _visible_elements(self, xpath: str):
        return [e for e in self.driver.find_elements(By.XPATH, xpath) if e.is_displayed()]

    # -- finding --------------------------------------------------------------

    def ensure_semantics(self):
        """Re-assert the accessibility tree. Cheap when it is already on."""
        enable_semantics(self.driver)
        return self

    def find_text(
        self,
        text: str,
        exact: bool = True,
        role: Optional[str] = None,
        timeout: int | None = None,
    ):
        timeout = settings.DEFAULT_TIMEOUT if timeout is None else timeout
        xpath = self.node_xpath(text, exact, role)
        return self._poll(
            lambda: next(iter(self._visible_elements(xpath)), None),
            timeout,
            f"no visible node showing {text!r}",
        )

    def is_visible(self, text: str, exact: bool = True, timeout: int = 5) -> bool:
        try:
            self.find_text(text, exact=exact, timeout=timeout)
            return True
        except TimeoutError:
            return False

    def is_gone(self, text: str, exact: bool = True, timeout: int = 15) -> bool:
        """True once nothing on screen shows `text` (dialog closed, sheet
        dismissed, spinner finished)."""
        xpath = self.node_xpath(text, exact)
        try:
            self._poll(
                lambda: not self._visible_elements(xpath),
                timeout,
                f"{text!r} still on screen",
            )
            return True
        except TimeoutError:
            return False

    def visible_texts(self) -> list[str]:
        """Every label currently on screen, in tree order.

        The web counterpart of dumping the Android UI hierarchy - the fastest way
        to work out why a locator missed, and handy for coarse assertions."""
        return self.driver.execute_script(
            """
            const host = document.querySelector('flt-semantics-host');
            if (!host) return [];
            const seen = new Set();
            host.querySelectorAll('flt-semantics').forEach(e => {
              const span = e.querySelector(':scope > span');
              const t = (span ? span.textContent : '').trim();
              if (t) seen.add(t);
              else if (e.getAttribute('role') === 'button') {
                const b = (e.textContent || '').trim();
                if (b && b.length < 120) seen.add(b);
              }
            });
            return [...seen];
            """
        )

    def visible_buttons(self) -> list[str]:
        """The label of every node Flutter exposes as a button, in tree order.

        Kept separate from `visible_texts()` because plain labels and actionable
        controls often share wording (a 'CLASS 1' heading above a 'Class 1'
        picker), and a list built from both cannot tell them apart.

        Labels arrive exactly as Flutter merged them: a widget that stacks a
        title over two counts is one node reading "Title\\n2\\n3"."""
        return self.driver.execute_script(
            """
            const host = document.querySelector('flt-semantics-host');
            if (!host) return [];
            const out = [];
            host.querySelectorAll('flt-semantics[role="button"]').forEach(e => {
              const t = (e.textContent || '').trim();
              if (t && t.length < 200) out.push(t);
            });
            return out;
            """
        )

    # -- clicking -------------------------------------------------------------

    def _click_element(self, el) -> None:
        """Click, falling back to a direct DOM click.

        The native click is preferred - it exercises the same hit-testing path a
        teacher's mouse does. But the semantics nodes are transparent overlays
        stacked on the canvas, so a neighbouring node can intercept the point;
        dispatching the event straight at the node still runs Flutter's tap
        handler for it, which keeps a legitimate test from failing on geometry."""
        try:
            el.click()
        except (ElementClickInterceptedException, ElementNotInteractableException):
            self.driver.execute_script("arguments[0].click();", el)

    def click_text(
        self,
        text: str,
        exact: bool = True,
        role: Optional[str] = None,
        timeout: int | None = None,
    ):
        timeout = settings.DEFAULT_TIMEOUT if timeout is None else timeout
        xpath = self.node_xpath(text, exact, role)

        def attempt():
            el = next(iter(self._visible_elements(xpath)), None)
            if el is None:
                return None
            self._click_element(el)
            return el

        return self._poll(attempt, timeout, f"could not click {text!r}")

    def click_button(self, text: str, exact: bool = True, timeout: int | None = None):
        """Click a node Flutter exposes as a button. Prefer this over
        `click_text` when a plain label of the same wording also exists (e.g. the
        'Sanskruthi School - Nalgonda' row and the header echoing it)."""
        return self.click_text(text, exact=exact, role="button", timeout=timeout)

    def click_menu_item(self, index: int, timeout: int | None = None):
        """Click the nth row of an open Material dropdown menu, counting from 0.

        Positional because there is nothing else to go on: Flutter publishes the
        menu as `role="menu"` over `role="menuitem"` rows, and on this build the
        rows carry **no text at all** in the accessibility tree - a
        `DropdownMenuItem`'s child label never reaches the DOM. Every text-based
        locator is therefore guaranteed to miss, and the rows come out in the
        order the widget declares them.

        The chosen value *is* readable once the menu closes, so callers should
        confirm the selection by its label rather than trusting the index."""
        timeout = settings.DEFAULT_TIMEOUT if timeout is None else timeout

        def attempt():
            rows = [
                e
                for e in self.driver.find_elements(
                    By.CSS_SELECTOR, 'flt-semantics[role="menuitem"]'
                )
                if e.is_displayed()
            ]
            if len(rows) <= index:
                return None
            self._click_element(rows[index])
            return rows[index]

        return self._poll(
            attempt, timeout, f"no dropdown menu row at index {index}"
        )

    # -- typing ---------------------------------------------------------------

    def find_input(self, label: str, timeout: int | None = None):
        """The `<input>` Flutter publishes for a text field, found by its hint."""
        timeout = settings.DEFAULT_TIMEOUT if timeout is None else timeout
        css = self.input_css(label)
        return self._poll(
            lambda: next(
                (e for e in self.driver.find_elements(By.CSS_SELECTOR, css) if e.is_displayed()),
                None,
            ),
            timeout,
            f"no text field labelled {label!r}",
        )

    def type_into(self, label: str, value: str, clear: bool = True, timeout: int | None = None):
        """Type into the field whose hint is `label`.

        Clearing goes through select-all + overwrite rather than `.clear()`:
        Flutter mirrors the DOM input into its own editing state through input
        events, and a programmatic `.clear()` does not always raise one, leaving
        the widget still holding the old text."""
        field = self.find_input(label, timeout=timeout)
        field.click()
        if clear and field.get_attribute("value"):
            field.send_keys(Keys.CONTROL, "a")
            field.send_keys(Keys.BACKSPACE)
        field.send_keys(value)
        return field

    def input_value(self, label: str) -> str:
        return self.find_input(label).get_attribute("value") or ""

    # -- scrolling ------------------------------------------------------------

    def scroll_by(self, delta_y: int = 400) -> None:
        """Wheel over the canvas. Flutter handles the wheel event itself, so this
        scrolls the list under the cursor exactly as a real scroll would."""
        ActionChains(self.driver).scroll_by_amount(0, delta_y).perform()
        time.sleep(0.4)

    def scroll_to_text(
        self, text: str, exact: bool = True, max_scrolls: int = 12, step: int = 400
    ):
        """Wheel down until `text` is on screen. Returns the node, or None."""
        for _ in range(max_scrolls):
            if self.is_visible(text, exact=exact, timeout=1):
                return self.find_text(text, exact=exact, timeout=5)
            self.scroll_by(step)
        return None

    # -- misc -----------------------------------------------------------------

    def press_escape(self) -> None:
        ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()

    def screenshot(self, name: str) -> str:
        settings.SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        path = settings.SCREENSHOTS_DIR / f"{name}.png"
        self.driver.save_screenshot(str(path))
        return str(path)
