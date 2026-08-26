# Teacher Web QA Automation

UI automation for the **English Gurukul teacher web portal**
(<https://teacher.englishgurukul.in>), built with **Selenium + pytest**.

This is the web counterpart of `qa_teacherapp_automation/` (the Android/Appium
suite). The two are separate projects on purpose — different driver, different
runner, different failure modes — but they share the same shape, the same test
data, and the same Sanskruthi QA account, so a report from either reads the same.

---

## The one thing to understand before editing this suite

The portal is **the Flutter teacher app compiled for web with the CanvasKit
renderer**. The entire UI — every button, label and list row — is *painted into a
single `<canvas>`*. There is no HTML for `By.ID`, `By.CSS_SELECTOR` or a normal
XPath to grab. Standard web-automation instincts will not work here.

What the suite drives instead is **Flutter's accessibility (semantics) tree**: a
parallel DOM that Flutter publishes for screen readers.

```html
<flt-semantics-host>
  <flt-semantics role="button"><span>LOG IN</span></flt-semantics>
  <input aria-label="10-digit mobile number" type="tel">
</flt-semantics-host>
```

So:

| UI element   | How the suite sees it                                        |
| ------------ | ------------------------------------------------------------ |
| Label / text | `<flt-semantics>` whose text is that label                    |
| Button       | the same, with `role="button"`                                |
| Text field   | a genuine `<input>` carrying the hint as its `aria-label`     |

This is the exact web analogue of the Android accessibility tree the Appium suite
drives (text + `content-desc`), which is why the page objects in the two projects
read almost identically.

**Two consequences that cause nearly every mystery failure:**

1. **Semantics must be switched on.** Flutter builds that tree only once it
   believes assistive tech is present; until then it renders one hidden "Enable
   accessibility" button. `utils/driver_factory.enable_semantics()` clicks it.
   A page reload restarts the engine with semantics *off*, so anything that
   reloads must re-enable it (see `tests/test_web_behaviour.py`).
2. **Nodes go stale constantly.** Flutter rebuilds and recycles semantics nodes
   every frame. Nothing in `pages/base_page.py` holds an element handle across a
   wait — every poll re-queries. Follow that when adding helpers.

There is also a shadow-DOM trap: the canvas itself lives inside
`<flt-glass-pane>`'s **shadow root**, so `document.querySelector('canvas')` never
finds it. `wait_for_engine()` pierces the root.

---

## Setup

```powershell
cd qa_TeacherWeb_Automation
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env      # then edit .env
```

No driver binary to install: Selenium Manager fetches the one matching your
browser. You need Chrome (default), Edge, or Firefox.

## Running

```powershell
.venv\Scripts\python -m pytest                       # everything
.venv\Scripts\python -m pytest -m smoke              # fast happy paths
.venv\Scripts\python -m pytest -m "login or lessons" # by area
.venv\Scripts\python -m pytest tests/test_login.py -k version
```

Reports land in `reports/` — `report.html` plus a screenshot per failed test
under `reports/screenshots/`.

### Headless

```powershell
$env:HEADLESS="true"; .venv\Scripts\python -m pytest -m smoke
```

Headless needs a working GL stack, since CanvasKit renders through WebGL —
`config/browser_options.py` adds the ANGLE/SwiftShader flags for that. Drop them
and a headless run paints nothing and every locator times out.

### Daily Slack report

```powershell
.venv\Scripts\python run_daily.py            # full suite -> Slack
.venv\Scripts\python run_daily.py --smoke    # smoke only
```

Grouped by area — **Login, Navigation, Lesson Plans, Management, Web** — headed
with the version read off the login-screen footer, so every summary names the
exact build the portal served. Set `SLACK_WEBHOOK_URL` in `.env`; leave it blank
and the report prints to the console instead of posting.

Unlike the Android runner there is nothing to skip for — no device, no Appium
server, just a browser. If the browser cannot start, that is a real failure and
is reported as one.

## Running in CI

Because the suite needs only a browser, it runs on ordinary GitHub-hosted
runners — no self-hosted machine and no phone attached, which is what the
Android suite requires.

| Workflow                            | When                                   | Scope                     |
| ----------------------------------- | -------------------------------------- | ------------------------- |
| `.github/workflows/ci.yml`          | push / PR to `main`, or manually       | `-m smoke` + `-m regression` (parallel jobs) |
| `.github/workflows/daily-report.yml`| 02:30 UTC = **08:00 IST**, or manually | full suite + Slack report |

Both can be started by hand from the repo's **Actions** tab, and both upload
`reports/` as a build artifact so a failure can be read after the fact.

**One-time setup for the Slack report:** add the webhook under
*Settings → Secrets and variables → Actions → New repository secret*, named
`SLACK_WEBHOOK_URL`. Without it nothing breaks — the run still happens and the
report prints to the job log instead of posting.

> If you also keep the local Windows Task Scheduler job (`TeacherWeb QA Daily`,
> which runs `run_daily.ps1`), both it and the daily workflow will post to Slack
> each morning. Pick one: the workflow runs whether or not the laptop is on,
> while the scheduled task can reach things a hosted runner cannot.

---

## Layout

```
config/
  settings.py          BASE_URL, browser, viewport, timeouts  (the only place env is read)
  browser_options.py   Chrome/Edge/Firefox options            (web analogue of capabilities.py)
utils/
  driver_factory.py    driver + Flutter engine/semantics readiness
  app_version.py       version: login footer -> APP_VERSION -> /version.json
pages/
  base_page.py         semantics-tree helpers — read this first
  login_page.py        school picker, mobile, LOG IN / REGISTER, version footer
  home_page.py         shell: dashboard boxes, nav, drawer, theme toggle
  lesson_plan_page.py  class picker, plan catalogue, plan cards
  management_page.py   management hub actions
data/test_data.py      Sanskruthi account + all portal copy
tests/                 one module per area
run_daily.py           scheduled run + Slack summary
run_daily.ps1          wrapper the Windows scheduled task calls
.github/workflows/     smoke on push/PR, full suite daily at 08:00 IST
```

## Test data

All tests log into **Sanskruthi School - Nalgonda** with the QA teacher number in
`data/test_data.py`. **Do not switch to another school** (e.g. Navodaya) — it is a
fixed convention for this product's QA, and the license code, class list and
lesson catalogue the assertions rely on are Sanskruthi's.

`Text` in that module holds every string the portal renders. Copy was read off
the live semantics tree; where the web build differs from Android, the constant
says so (`DARK_MODE_TOGGLE` and `COPY_LICENSE` are web-only).

## Coverage

| Area         | Module                    | What it asserts                                                     |
| ------------ | ------------------------- | ------------------------------------------------------------------- |
| Login        | `test_login.py`           | screen loads, version footer, school search, login reaches home, the three validation errors |
| Navigation   | `test_navigation.py`      | all five nav destinations, all four dashboard boxes, drawer contents |
| Smoke        | `test_smoke_flow.py`      | full journey: login → school + license shown → every box → every tab → logout |
| Lesson Plans | `test_lesson_plan.py`     | catalogue loads for the class, header count agrees with the cards, a card expands to START |
| Management   | `test_management.py`      | all five management actions offered; registration screen opens      |
| Web-only     | `test_web_behaviour.py`   | light/dark toggle, session survives a reload, layout at phone width  |

Tests never submit anything that would create or change live data — the
management test opens the registration screen but does not submit it.

## Adding a test

Start by asking the page what it can see:

```python
print(page.visible_texts())    # every label on screen
print(page.visible_buttons())  # only the actionable ones
```

That is the web equivalent of dumping the Android UI hierarchy, and it is the
fastest way to find out why a locator missed. Two gotchas it makes obvious:

* Flutter **merges a widget's lines into one node** — a lesson card reads
  `"3 - Long Vowels\n1\n3"` (title, PDFs, videos). Match a prefix, not the whole
  string.
* Plain labels and controls often share wording (a `CLASS 1` heading above a
  `Class 1` picker). Use `click_button()` / `visible_buttons()` when you mean the
  control.

## Known gaps

* The **REGISTER** path in `login_page.register()` is implemented but not
  exercised: the QA number is already enrolled, so `login_or_register()` never
  takes that branch. It follows the same screens as the Android build — re-verify
  the copy if it ever starts running.
* Class Report and Student Report are covered only at smoke level (the section
  loads without an error state). Field-level assertions for those are the natural
  next area to add.
