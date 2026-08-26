"""Builds the Selenium browser options (the web analogue of the Appium suite's
config/capabilities.py).

The portal is a **Flutter Web / CanvasKit** build: the whole UI is painted into a
single <canvas> with WebGL. That drives two choices here -

  * headless runs must keep a working GL stack (ANGLE + SwiftShader), otherwise
    CanvasKit never paints and every locator times out;
  * a fixed device-scale-factor keeps the responsive layout deterministic across
    machines with different display scaling (a 125%-scaled Windows laptop would
    otherwise get a different layout at the same window size).
"""
from __future__ import annotations

from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions

from config import settings

# Shared Chromium flags. Kept minimal on purpose: every flag here is one more way
# the automated browser can differ from the browser a teacher actually uses.
_CHROMIUM_ARGS = [
    f"--window-size={settings.WINDOW_WIDTH},{settings.WINDOW_HEIGHT}",
    "--force-device-scale-factor=1",
    "--disable-features=Translate",
]

# Software GL, used only when headless - real GPUs are unavailable there.
_HEADLESS_ARGS = [
    "--headless=new",
    "--use-gl=angle",
    "--use-angle=swiftshader",
    "--enable-unsafe-swiftshader",
]


def _chromium(opts):
    for arg in _CHROMIUM_ARGS:
        opts.add_argument(arg)
    if settings.HEADLESS:
        for arg in _HEADLESS_ARGS:
            opts.add_argument(arg)
    # Quieten the "Chrome is being controlled by automated software" infobar and
    # the password-manager bubble, both of which can overlay the canvas.
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option(
        "prefs",
        {
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,
        },
    )
    return opts


def build_options():
    """Options for the browser named by BROWSER (chrome | edge | firefox)."""
    if settings.BROWSER == "chrome":
        return _chromium(ChromeOptions())
    if settings.BROWSER == "edge":
        return _chromium(EdgeOptions())
    if settings.BROWSER == "firefox":
        opts = FirefoxOptions()
        if settings.HEADLESS:
            opts.add_argument("-headless")
        opts.add_argument(f"--width={settings.WINDOW_WIDTH}")
        opts.add_argument(f"--height={settings.WINDOW_HEIGHT}")
        return opts
    raise ValueError(
        f"Unsupported BROWSER={settings.BROWSER!r} (use chrome, edge or firefox)"
    )
