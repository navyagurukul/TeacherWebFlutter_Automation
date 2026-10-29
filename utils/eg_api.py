"""Minimal Python client for the English Gurukul backend — the same endpoints
the app's services call. Used for data-level QA (e.g. validating that every
lesson-plan PDF and video URL actually loads), independent of the UI.

Endpoints (see lib/services/*):
  GET  backend/v1/schools/list/             -> {data:[{id, school_name}]}
  POST accounts/v1/auth/instructor-login/  {mobile_number, school_id} -> {data:{access,refresh}}
  GET  accounts/v1/auth/me/                -> {data:{..., school:{id,...}}}
  GET  management/v1/schools/<sid>/classes/ -> {data:[{id, class_name, ...}]}
  GET  backend/v1/lesson-plans/<cid>/       -> {data:[{id, display_name, ...}]}
  GET  backend/v1/lesson-plans/<pid>/detail/-> {data:{pdfs:[...], videos:[...]}}
"""
from __future__ import annotations

import time

import requests

# Since v2.5.4 the portal resolves its backend at startup from this remote
# config (EgTeacherApp.<env>.base_url) rather than a hardcoded URL, so the
# suite reads the same file and follows backend moves (Azure -> GCP, Oct 2026).
# PROD is the fallback when the config can't be fetched.
BASE_URL_CONFIG = "https://storage.googleapis.com/eg_videos/base_url_config_gcp.json"
CONFIG_APP = "EgTeacherApp"
PROD = "https://eg-infra-api-541085401763.asia-south1.run.app"
DEV = "https://eg-360-dev.englishgurukul.in"
API_VERSION = "v1"


def resolve_base_url(env: str = "prod") -> str:
    """The backend the live portal uses for `env`, as its ConfigResolver finds it."""
    fallback = PROD if env == "prod" else DEV
    try:
        r = requests.get(BASE_URL_CONFIG, timeout=15)
        r.raise_for_status()
        url = r.json()[CONFIG_APP][env]["base_url"]
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return fallback
    return str(url).rstrip("/") or fallback


class EgApi:
    def __init__(self, base_url: str | None = None, timeout: int = 30):
        self.base_url = (base_url or resolve_base_url()).rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.access = None
        self.mobile = None
        self._me = None

    # -- url + request helpers ------------------------------------------------

    def _url(self, path: str, module: str = "backend") -> str:
        return f"{self.base_url}/api/{module}/{API_VERSION}/{path}"

    def _headers(self) -> dict:
        h = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.access:
            h["Authorization"] = f"Bearer {self.access}"
        return h

    def _get(self, path: str, module: str = "backend") -> dict:
        # The catalogue crawl makes hundreds of calls; the API answers bursts
        # with 429. Back off (honouring Retry-After) instead of failing the run.
        for attempt in range(6):
            r = self.session.get(self._url(path, module), headers=self._headers(), timeout=self.timeout)
            if r.status_code != 429 or attempt == 5:
                break
            try:
                wait = float(r.headers.get("Retry-After", ""))
            except ValueError:
                wait = 5 * 2 ** attempt
            time.sleep(min(wait, 120))
        r.raise_for_status()
        return r.json()

    @staticmethod
    def _data(body: dict):
        return body.get("data", body) if isinstance(body, dict) else body

    # -- auth -----------------------------------------------------------------

    def schools(self) -> list:
        """The login screen's school picker (no auth): [{id, school_name}]."""
        data = self._data(self._get("schools/list/"))
        return data if isinstance(data, list) else []

    def school_id_for(self, school_name: str) -> str:
        for school in self.schools():
            if str(school.get("school_name", "")).strip().lower() == school_name.strip().lower():
                return str(school["id"])
        raise RuntimeError(f"school not in schools/list/: {school_name!r}")

    def login(self, mobile_number: str, school_name: str | None = None) -> str:
        """Teacher login as the portal does it since v2.5: `auth/instructor-login/`
        with the school picked on the login screen (the server rejects a number
        not registered with that school)."""
        if school_name is None:
            from data.test_data import SCHOOL_NAME
            school_name = SCHOOL_NAME
        r = self.session.post(
            self._url("auth/instructor-login/", module="accounts"),
            json={"mobile_number": mobile_number,
                  "school_id": self.school_id_for(school_name)},
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=self.timeout,
        )
        r.raise_for_status()
        data = self._data(r.json())
        self.access = data.get("access") or data.get("access_token")
        if not self.access:
            raise RuntimeError(f"login returned no access token: {r.text[:200]}")
        self.mobile = mobile_number
        self._me = None
        return self.access

    def me(self) -> dict:
        """The logged-in teacher's profile, fetched once per client."""
        if self._me is None:
            self._me = self._data(self._get("auth/me/", module="accounts")) or {}
        return self._me

    def school(self) -> dict:
        return self.me().get("school") or {}

    def school_name(self) -> str:
        """Display name of the logged-in teacher's school ("" if absent)."""
        school = self.school()
        for key in ("school_name", "name", "display_name", "title"):
            value = school.get(key) or self.me().get(key)
            if value:
                return str(value)
        return ""

    def teacher_name(self) -> str:
        me = self.me()
        for key in ("full_name", "name", "display_name", "first_name"):
            if me.get(key):
                return str(me[key])
        return ""

    def school_id(self) -> str:
        me = self.me()
        sid = self.school().get("id") or me.get("school_id")
        if not sid:
            raise RuntimeError(f"could not find school id in auth/me: {me}")
        return str(sid)

    # -- lesson-plan data -----------------------------------------------------

    def school_summary(self, school_id: str) -> dict:
        """The school detail the home dashboard's summary card is built from —
        `total_strength` and `total_registered_students`. Lets the daily report
        name the enrolment even when no browser run captured it."""
        data = self._data(self._get(f"schools/{school_id}/", module="management"))
        return data if isinstance(data, dict) else {}

    def classes(self, school_id: str) -> list:
        """Every class of the school. The endpoint is paged (`?page=N`, `next`),
        mirroring the app's class_service.dart."""
        out = []
        for page in range(1, 51):
            path = f"schools/{school_id}/classes/" + (f"?page={page}" if page > 1 else "")
            body = self._get(path, module="management")
            data = self._data(body)
            if not isinstance(data, list) or not data:
                break
            out.extend(data)
            if not (isinstance(body, dict) and body.get("next")):
                break
        return out

    def plans(self, class_id: str) -> list:
        data = self._data(self._get(f"lesson-plans/{class_id}/"))
        return data if isinstance(data, list) else []

    def plan_detail(self, plan_id: str) -> dict:
        data = self._data(self._get(f"lesson-plans/{plan_id}/detail/"))
        return data if isinstance(data, dict) else {}

    # -- assessments ----------------------------------------------------------

    def class_id_for(self, school_id: str, class_name: str) -> str:
        for cls in self.classes(school_id):
            if str(cls.get("class_name", "")).strip().lower() == class_name.strip().lower():
                return str(cls["id"])
        raise RuntimeError(f"class {class_name!r} not found in school {school_id}")

    def assessments(self, class_id: str) -> list:
        """Assessment cards of a class as the Lesson Plan screen draws them: each
        plan's `test_assessments`, tagged with the plan it sits under. Status is
        per class (the same assessment id can be shared by several classes)."""
        out = []
        for plan in self.plans(class_id):
            for test in plan.get("test_assessments") or []:
                out.append({**test, "plan": plan.get("display_name", "")})
        return out

    def assessment(self, class_id: str, name: str) -> dict:
        for test in self.assessments(class_id):
            if str(test.get("display_name", "")).strip().lower() == name.strip().lower():
                return test
        raise RuntimeError(f"assessment {name!r} not found in class {class_id}")

    def set_assessment_status(self, class_id: str, assessment_id: str, status: str) -> None:
        """PATCH `class-tests/update-status/` exactly as the portal's START /
        STOP / RESTART buttons do: `unlocked` runs it, `completed` stops it."""
        r = self.session.patch(
            self._url("class-tests/update-status/"),
            json={"class_id": class_id, "test_assessment_id": assessment_id,
                  "status": status},
            headers=self._headers(),
            timeout=self.timeout,
        )
        r.raise_for_status()


def best_video_urls(video: dict) -> list:
    """All non-empty MP4 URLs for a video (one per language, best quality),
    mirroring VideoLanguage.bestUrl (prefer 720, then 144, then any)."""
    out = []
    for lang in video.get("languages", []) or []:
        urls = lang.get("urls", {}) or {}
        pick = urls.get("720") or urls.get("144") or next(
            (u for u in urls.values() if u), ""
        )
        if pick:
            out.append((lang.get("language", ""), pick))
    return out
