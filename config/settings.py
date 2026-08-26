"""Central configuration for the Teacher **Web** suite, driven by .env with safe
defaults.

Nothing else in the suite should read os.environ directly - import from here so
there is one source of truth for the site under test, the browser, and timeouts.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# qa_TeacherWeb_Automation/ root, so relative paths resolve regardless of CWD.
ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "").strip() or default)
    except ValueError:
        return default


# Site under test. Trailing slash matters to Flutter's base href routing.
BASE_URL = os.getenv("BASE_URL", "https://teacher.englishgurukul.in/").rstrip("/") + "/"

BROWSER = os.getenv("BROWSER", "chrome").strip().lower()
HEADLESS = _bool("HEADLESS", False)

# The portal lays itself out responsively; this size gives the desktop layout
# the QA team reviews. Narrow it (e.g. 420x900) to exercise the mobile layout.
WINDOW_WIDTH = _int("WINDOW_WIDTH", 1440)
WINDOW_HEIGHT = _int("WINDOW_HEIGHT", 900)

# Explicit-wait budget for a semantics node to appear, in seconds.
DEFAULT_TIMEOUT = _int("DEFAULT_TIMEOUT", 20)
# How long to wait for the Flutter engine to boot and paint its first frame.
APP_LOAD_TIMEOUT = _int("APP_LOAD_TIMEOUT", 60)
# Extra grace for screens that fetch from the API before they render.
DATA_LOAD_TIMEOUT = _int("DATA_LOAD_TIMEOUT", 45)

REPORTS_DIR = ROOT / "reports"
SCREENSHOTS_DIR = REPORTS_DIR / "screenshots"

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "").strip()
APP_VERSION_OVERRIDE = os.getenv("APP_VERSION", "").strip()
