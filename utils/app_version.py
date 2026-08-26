"""Resolve the version of the portal build under test.

The web build is far easier to pin down than the Android one: there is no device,
no APK and no installed package - the server states its own version. Resolution
order, most-faithful first:

1. `reports/app_version.txt` - the footer captured live from the login screen
   during this run (written by tests/test_login.py). This is literally what the
   portal displayed to the browser.
2. `APP_VERSION` env / .env override.
3. `<BASE_URL>/version.json` - the manifest Flutter emits at build time, fetched
   straight from the deployed site.

Returns the bare version name (e.g. "2.4.3"); `label()` formats it like the
portal's own footer.
"""
from __future__ import annotations

import re

import requests

from config import settings

CAPTURED = settings.REPORTS_DIR / "app_version.txt"
VERSION_JSON = settings.BASE_URL + "version.json"

_VERSION_RE = re.compile(r"[Vv]?\s*([0-9]+(?:\.[0-9]+)+[0-9A-Za-z.\-+]*)")


def _from_captured() -> str | None:
    """The footer captured from the live login screen, if a UI test ran."""
    if not CAPTURED.exists():
        return None
    text = CAPTURED.read_text(encoding="utf-8").strip()
    if not text:
        return None
    match = _VERSION_RE.search(text)
    return match.group(1) if match else None


def _from_env() -> str | None:
    return settings.APP_VERSION_OVERRIDE or None


def _from_version_json() -> str | None:
    """Ask the deployed site directly. Works with no browser and no login, which
    is what keeps the daily report able to name a build even when the UI run is
    skipped."""
    try:
        response = requests.get(VERSION_JSON, timeout=15)
        response.raise_for_status()
        version = (response.json() or {}).get("version")
    except Exception:
        return None
    return str(version).strip() if version else None


SOURCES = [
    (_from_captured, "login screen"),
    (_from_env, "APP_VERSION override"),
    (_from_version_json, "version.json"),
]


def resolve_with_source() -> tuple[str | None, str]:
    """(version, where it came from) so the report never claims the login screen
    showed a version it actually read out of version.json."""
    for source, origin in SOURCES:
        try:
            version = source()
        except Exception:
            version = None
        if version:
            return version, origin
    return None, "not found"


def resolve() -> str | None:
    return resolve_with_source()[0]


def capture(label: str) -> None:
    """Record the footer a UI test read off the login screen."""
    settings.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    CAPTURED.write_text(label, encoding="utf-8")


def clear_capture() -> None:
    """Drop a previous run's captured footer so today's report cannot inherit
    yesterday's version after a deploy."""
    try:
        CAPTURED.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        pass


def label() -> str:
    """Formatted like the portal footer, e.g. 'V2.4.3' (or 'unknown')."""
    version = resolve()
    return f"V{version}" if version else "unknown"


def label_with_source() -> str:
    """e.g. 'V2.4.3  (login screen)' - version plus where it was read from."""
    version, origin = resolve_with_source()
    return f"V{version}  ({origin})" if version else f"unknown  ({origin})"
