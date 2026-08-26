"""Test data for the teacher **web portal** regression suite.

IMPORTANT: All tests use the **Sanskruthi** school. Do not switch to any other
school (e.g. Navodaya) - this is a fixed convention for this product's QA.

The copy below was read off the live portal's semantics tree, which is the same
widget text the Android app renders. Where the web build differs from the app,
that is called out on the constant.
"""
from __future__ import annotations

# The one school every test logs into. SCHOOL_SEARCH is what we type into the
# picker's search box; SCHOOL_NAME is the exact list row we click.
SCHOOL_SEARCH = "Sanskruthi"
SCHOOL_NAME = "Sanskruthi School - Nalgonda"

# Teacher used for login. This number is already enrolled at Sanskruthi; the
# login-or-register flow enrols it via the license code below if that changes.
TEACHER_MOBILE = "9000000001"
TEACHER_NAME = "QA Automation"
TEACHER_LANGUAGE = "English"

# The language dropdown in the order the app declares it. Positions matter:
# Flutter publishes the open menu's rows without any text, so the register flow
# picks a language by index and then confirms it by the label the field shows
# once the menu has closed.
LANGUAGE_ORDER = [
    "Hindi",
    "English",
    "Marathi",
    "Tamil",
    "Telugu",
    "Kannada",
    "Malayalam",
    "Bengali",
    "Gujarati",
    "Punjabi",
    "Odia",
    "Urdu",
    "Assamese",
    "Sanskrit",
]

# License code for Sanskruthi School - Nalgonda (used by the REGISTER flow).
LICENSE_CODE = "SANK48"

# Inputs used by login validation tests.
INVALID_MOBILE_SHORT = "12345"
NON_DIGIT_MOBILE = "abcdefghij"


class Text:
    """Copy the portal renders, used for locating and for assertions."""

    # -- login screen ---------------------------------------------------------
    SIGN_IN_HEADING = "Sign in to continue"
    LOGIN_BUTTON = "LOG IN"
    REGISTER_BUTTON = "REGISTER"
    SCHOOL_LABEL = "SCHOOL"
    MOBILE_LABEL = "MOBILE NUMBER"
    SELECT_SCHOOL_HINT = "Select school"
    # aria-labels of the two text fields (this is how they are located).
    MOBILE_FIELD = "10-digit mobile number"
    SEARCH_SCHOOL_FIELD = "Search school"

    # Validation / snackbar messages.
    MOBILE_REQUIRED = "Mobile number is required"
    MOBILE_INVALID = "Enter a valid 10-digit number"
    SCHOOL_REQUIRED = "Please select a school"

    # License dialog (REGISTER flow).
    LICENSE_TITLE = "Enter License Code"
    LICENSE_CONTINUE = "CONTINUE"
    LICENSE_CANCEL = "CANCEL"

    # Register screen ("Create your account").
    REGISTER_TITLE = "Create your account"
    SELECT_LANGUAGE_HINT = "Select language"
    REGISTER_SUBMIT = "REGISTER"
    BACK_TO_LOGIN = "BACK TO LOGIN"

    # Version footer, shown on both the login screen and the drawer, e.g.
    # "ENGLISH GURUKUL TEACHER PORTAL V2.4.3".
    VERSION_PREFIX = "ENGLISH GURUKUL TEACHER PORTAL"

    # -- home / shell ---------------------------------------------------------
    HOME_TITLE = "Welcome!"
    HOME_HEADER = "TEACHER HOME"

    # Home-dashboard boxes (labels are rendered UPPERCASE).
    BOX_LESSON_PLAN = "LESSON PLAN"
    BOX_CLASS_REPORT = "CLASS REPORT"
    BOX_STUDENT_REPORT = "STUDENT REPORT"
    BOX_MANAGEMENT = "MANAGEMENT"

    # Section header titles shown in the shell app-bar per destination.
    TITLE_LESSON_PLAN = "Lesson Plan"
    TITLE_CLASS_REPORT = "Class Report"
    TITLE_STUDENT_REPORT = "Student Report"
    TITLE_MANAGEMENT = "Student Management"

    # Bottom-nav labels.
    NAV_HOME = "Home"
    NAV_LESSONS = "Lessons"
    NAV_CLASS = "Class"
    NAV_STUDENTS = "Students"
    NAV_MANAGE = "Manage"

    # Drawer menu items.
    MENU_BUTTON = "Menu"
    MENU_PROFILE = "Profile"
    MENU_STAR_ARENA = "Star Arena"
    MENU_TEST = "Test"
    MENU_ZOOM = "Zoom Training"
    MENU_LOGOUT = "Logout"
    MENU_DISMISS = "Dismiss"  # the drawer scrim, web-only

    # Web-only chrome, absent from the Android build.
    DARK_MODE_TOGGLE = "Switch to dark mode"
    LIGHT_MODE_TOGGLE = "Switch to light mode"
    COPY_LICENSE = "Copy license code"
    LICENSE_CODE_LABEL = "STUDENT LICENSE CODE"

    # -- section content ------------------------------------------------------
    # Lesson Plan: a class picker plus a "<n> LESSON PLANS" count.
    LESSON_PLANS_SUFFIX = "LESSON PLANS"
    LESSON_START = "START"

    # Class / Student Report filters.
    FILTER_BY_CATEGORY = "FILTER BY CATEGORY"
    FILTER_BY_COURSE = "FILTER BY COURSE"
    SEARCH_TOPICS_FIELD = "Search topics by name"

    # Management home actions.
    MANAGEMENT_HEADER = "MANAGEMENT HOME"
    MANAGE_REGISTRATION = "STUDENT REGISTRATION"
    MANAGE_APPROVAL = "STUDENT APPROVAL"
    MANAGE_EDIT = "EDIT STUDENT"
    MANAGE_DELETE = "DELETE STUDENT"
    MANAGE_BULK = "STUDENT BULK REGISTRATION"

    # Error / empty states worth asserting are absent on a healthy screen.
    GENERIC_ERROR = "Something went wrong"
    NO_INTERNET = "No internet connection"


# Management-home actions, in the order the portal lists them.
MANAGEMENT_ACTIONS = [
    Text.MANAGE_REGISTRATION,
    Text.MANAGE_APPROVAL,
    Text.MANAGE_EDIT,
    Text.MANAGE_DELETE,
    Text.MANAGE_BULK,
]
