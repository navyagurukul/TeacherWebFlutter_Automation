"""Class Report, Student Report, Star Arena and Test Report screens (web).

The web counterpart of the Appium suite's ReportsPage. These screens lay their
numbers out as tiles: a value node sits directly above its caption node
("74.4%" over "AVG. ACCURACY"), as separate siblings in the semantics tree. So
values are read geometrically - the node right above a caption, in the same
column - from one snapshot of every `<flt-semantics>` node and its rect.

Web specifics, read off the live portal:
  * a node's label is its own `<span>` text; a button's is its whole text, with
    lines kept ("All\\n63", "Class 1\\nSPARKLE 1 / LEVEL 1 - EDITION 4");
  * the whole student / leaderboard list is in the tree at once (rects run far
    below the viewport), so nothing needs scrolling into view to be read;
  * a dropdown opens *inline* as a list of buttons under its header. The
    option rows can sit outside the list's own clip, so they are activated
    with a semantics (DOM) click rather than a pointer click at their centre;
  * Star Arena and Test Report are pushed pages: a Back button, no Menu.
"""
from __future__ import annotations

import re
import time
from decimal import ROUND_HALF_UP, Decimal

from selenium.webdriver.common.actions.wheel_input import ScrollOrigin
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By

from data.test_data import Text
from pages.base_page import BasePage

_PCT = re.compile(r"^(\d+(\.\d+)?%|-)$")

# Every labelled node with its rect, in tree order. `idx` lets a caller click
# the very node it read (by position in the same query), not a look-alike.
_NODES_JS = """
const out = [];
document.querySelectorAll('flt-semantics').forEach((e, i) => {
  const span = e.querySelector(':scope > span');
  let t = (span ? span.textContent : '').trim();
  const role = e.getAttribute('role') || '';
  if (!t && role === 'button') t = (e.textContent || '').trim();
  if (!t || t.length > 200) return;
  const r = e.getBoundingClientRect();
  out.push([t, role, i, r.left, r.top, r.right, r.bottom]);
});
return out;
"""


def pct(value) -> str:
    """How the portal prints a percentage: one decimal + '%', or '-' when <= 0.
    Dart's toStringAsFixed rounds a half up (91.25 -> 91.3), unlike Python's
    format, which rounds it to even (91.2)."""
    try:
        v = Decimal(str(value))
    except (TypeError, ValueError, ArithmeticError):
        return "-"
    return f"{v.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)}%" if v > 0 else "-"


class Node:
    def __init__(self, desc, role, idx, x1, y1, x2, y2):
        self.desc, self.role, self.idx = desc, role, idx
        self.x1, self.y1, self.x2, self.y2 = x1, y1, x2, y2

    @property
    def cx(self):
        return (self.x1 + self.x2) / 2

    @property
    def cy(self):
        return (self.y1 + self.y2) / 2

    @property
    def first_line(self) -> str:
        return self.desc.split("\n")[0].strip()

    def __repr__(self):
        return f"Node({self.desc!r}, {self.role or 'text'}, y={self.y1:.0f})"


class ReportsPage(BasePage):
    # -- reading -----------------------------------------------------------------

    def nodes(self) -> list[Node]:
        return [Node(*row) for row in self.driver.execute_script(_NODES_JS)]

    def buttons(self, nodes: list[Node] | None = None) -> list[Node]:
        return [n for n in (nodes or self.nodes()) if n.role == "button"]

    def value_above(self, caption: str, nodes: list[Node] | None = None,
                    below_y: float = -1e9) -> str | None:
        """Text of the node right above `caption` in the same column. With
        `below_y`, only captions under that y count (e.g. inside one card)."""
        nodes = nodes or self.nodes()
        caps = [n for n in nodes if n.desc == caption and n.y1 >= below_y]
        if not caps:
            return None
        cap = min(caps, key=lambda n: n.y1)
        above = [n for n in nodes if n.y2 <= cap.y1 + 2 and n.x1 <= cap.cx <= n.x2
                 and cap.y1 - n.y2 < 160 and n is not cap and n.role != "group"]
        if not above:
            return None
        return max(above, key=lambda n: n.y2).desc

    def tiles(self, captions, tries: int = 3) -> dict[str, str | None]:
        """Tile values by caption; re-read while a reload has them blank."""
        got = {}
        for _ in range(tries):
            nodes = self.nodes()
            got = {c: self.value_above(c, nodes) for c in captions}
            if all(v is not None for v in got.values()):
                return got
            self.settle(2)
        return got

    def wait_desc(self, desc: str, timeout: float = 30, exact: bool = True) -> bool:
        end = time.time() + timeout
        while True:
            if any((n.desc == desc) if exact else (desc in n.desc) for n in self.nodes()):
                return True
            if time.time() >= end:
                return False
            time.sleep(0.5)

    def settle(self, seconds: float = 2.5):
        """Let a filter/class switch finish its API call and repaint."""
        time.sleep(seconds)
        return self

    # -- clicking by snapshot ------------------------------------------------------

    def _semantic_click(self, node: Node) -> None:
        """Activate the exact node read in `nodes()` (by its index in the same
        query). A DOM click fires Flutter's semantics tap for that node, which
        works even for a dropdown row clipped by its list's viewport."""
        el = self.driver.find_elements(By.CSS_SELECTOR, "flt-semantics")[node.idx]
        self.driver.execute_script("arguments[0].click();", el)

    def tap_button(self, label: str, first_line: bool = False, below_y: float = -1e9,
                   timeout: float = 20) -> Node:
        """Click the topmost button reading `label` (or whose first line does)."""
        end = time.time() + timeout
        while True:
            hits = [b for b in self.buttons() if b.y1 >= below_y and
                    ((b.first_line if first_line else b.desc) == label)]
            if hits:
                hit = min(hits, key=lambda n: n.y1)
                try:
                    self._semantic_click(hit)
                    return hit
                except Exception:
                    pass  # the tree rebuilt between read and click
            if time.time() >= end:
                raise AssertionError(f"no button {label!r} on screen")
            time.sleep(0.5)

    # -- dropdowns / pills ---------------------------------------------------------

    def _header(self, label: str) -> Node | None:
        hits = [b for b in self.buttons() if b.desc == label]
        return min(hits, key=lambda n: n.y1) if hits else None

    def _options(self, header: Node) -> list[Node]:
        """Option rows of the open dropdown under `header`: buttons below it,
        in the same column, before the next unrelated control."""
        return [b for b in self.buttons() if b.y1 >= header.y2 - 2
                and abs(b.x1 - header.x1) < 5 and b.y1 - header.y2 < 4000]

    def choose(self, current_label: str, option: str):
        """Open the dropdown showing `current_label` and pick `option` (a row
        may carry a second line with the class's program, so match line one).
        Confirms the header now reads `option`."""
        if current_label == option:
            return self
        for _ in range(2):
            header = self._header(current_label)
            if header is None:
                raise AssertionError(f"no dropdown showing {current_label!r}")
            self._semantic_click(header)
            time.sleep(1.2)
            # The student picker has its own search box: narrowing the list
            # keeps the row in reach and the pick unambiguous.
            search = [e for e in self.driver.find_elements(
                By.CSS_SELECTOR, 'input[aria-label="Search student"]') if e.is_displayed()]
            if search:
                search[0].send_keys(option)
                time.sleep(1)
            row = None
            end = time.time() + 10
            while row is None and time.time() < end:
                header = self._header(current_label) or header
                rows = [b for b in self._options(header)
                        if b.first_line == option and b.y1 > header.y2 - 2]
                row = min(rows, key=lambda n: n.y1) if rows else None
                if row is None:
                    time.sleep(0.5)
            if row is None:
                raise AssertionError(
                    f"option {option!r} not found in the dropdown under {current_label!r}")
            self._semantic_click(row)
            self.settle()
            if self._header(option) is not None and self._header(current_label) is None:
                return self
        raise AssertionError(f"dropdown under {current_label!r} did not switch to {option!r}")

    def dropdown_options(self, current_label: str) -> list[str]:
        """Open the dropdown showing `current_label`, list every option's first
        line, then close it again."""
        header = self._header(current_label)
        if header is None:
            raise AssertionError(f"no dropdown showing {current_label!r}")
        self._semantic_click(header)
        time.sleep(1.5)
        header = self._header(current_label) or header
        seen = []
        for b in self._options(header):
            if b is header or b.y1 < header.y2 - 2:
                continue
            if "\n" in b.desc and b.first_line not in seen:
                seen.append(b.first_line)
        self._semantic_click(self._header(current_label) or header)
        time.sleep(1)
        return seen

    def tap_pill(self, label: str):
        """Filter pills; Student Report pills read 'Fun Learn\\n35' (label +
        topic count). The topmost match is the pill row - the STATUS row below
        it has its own 'All'."""
        self.tap_button(label, first_line=True)
        self.settle()
        return self

    def pill_text(self, label: str) -> str:
        hits = [b for b in self.buttons() if b.first_line == label]
        return min(hits, key=lambda n: n.y1).desc if hits else ""

    def card_accuracy(self, student_name: str, tries: int = 3) -> str | None:
        """The ACCURACY value on a student's card in the Class Report list (the
        list reloads after a filter switch, so retry while it repaints)."""
        for _ in range(tries):
            nodes = self.nodes()
            names = [n for n in nodes if n.desc == student_name and n.role != "button"]
            if names:
                name = names[0]
                caps = [n for n in nodes if n.desc == "ACCURACY" and n.y1 >= name.y1 - 80]
                if caps:
                    cap = min(caps, key=lambda n: n.y1)
                    below = [n for n in nodes if n.y1 >= cap.y2 - 2 and n.y1 - cap.y2 < 120
                             and n.x2 >= cap.x1 - 20 and n.x1 <= cap.x2 + 20
                             and n is not cap and _PCT.match(n.desc)]
                    if below:
                        return min(below, key=lambda n: n.y1).desc
            self.settle(2)
        return None

    # -- navigation ----------------------------------------------------------------

    def open_drawer_item(self, label: str):
        self.click_button(Text.MENU_BUTTON)
        self.find_text(Text.MENU_LOGOUT, timeout=20)
        self.click_button(label)
        self.settle(3)
        return self

    def scroll_to_top(self):
        """Wheel the page back up over the content column."""
        try:
            size = self.driver.get_window_size()
            origin = ScrollOrigin.from_viewport(size["width"] // 2, size["height"] // 2)
            ActionChains(self.driver).scroll_from_origin(origin, 0, -20000).perform()
            time.sleep(0.5)
        except Exception:
            pass
        return self

    def back(self):
        self.click_button("Back")
        self.settle(2)
        return self
