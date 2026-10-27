"""Google Analytics 4: sessions, users, engaged sessions and key events over the
property's own last 28 days, and its top landing pages and sources (docs/TOOLS.md).

The key, read-only, one of:
  * a Google service-account key file (JSON, "type": "service_account"): the
    default. Its robot address is given Viewer on the GA4 property (Admin >
    Property access management), the one click left for the person. It may be
    the install's Search Console key (option key=search): one robot for both.
  * an OAuth "authorized_user" file (client_id, client_secret, refresh_token),
    as `gcloud auth application-default login` writes it: for a person who
    cannot make a service account. Skald trades the refresh token for an access
    token at Google's token address, scope analytics.readonly.

Three runReport calls (Google Analytics Data API v1beta), names in names.py:
  totals   no dimension: sessions, totalUsers, engagedSessions, keyEvents
  landing  landingPage: sessions, keyEvents, the top GA4_TOP, with GA4's TOTAL
  sources  sessionSourceMedium: the same
Dates are GA4's own: "28daysAgo" to "yesterday" in the property's time zone,
which the answer names (metadata.timeZone); the window kept is worked out in
that zone. Users are never added up across rows or days: GA4's own TOTAL (or
the no-dimension row) is the total. GA4's values are strings; a metric GA4 did
not give is NULL, never 0. What GA4 says about its answer (thresholding,
sampling, rows folded into "(other)") is kept as flags and shown.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from ..search import google, http
from .base import Adapter, Answer, BadKey, Figure, Option, Unreachable, plain_key_words, \
    pointer
from .names import GA4_DAYS, GA4_LABELS, GA4_REPORTS, GA4_TOP

SCOPE = "https://www.googleapis.com/auth/analytics.readonly"
DATA_API = "https://analyticsdata.googleapis.com/v1beta"
TOKEN_URL = google.TOKEN_URL
MEASUREMENT = re.compile(r"(?:gtag/js\?id=|gtag\(\s*['\"]config['\"]\s*,\s*['\"])(G-[A-Z0-9]{4,15})")
HEADLINE = ("sessions", "totalUsers", "keyEvents")


def _number(text):
    """GA4's value (a string) as a number; None for nothing."""
    if text is None or text == "":
        return None
    got = float(text)
    return int(got) if got.is_integer() else got


class _Refresh:
    """An access token from an "authorized_user" file's refresh token."""

    def __init__(self, info: dict, opener=None, sleep=time.sleep, clock=time.time,
                 token_url: str = TOKEN_URL) -> None:
        self.info, self.opener, self.sleep, self.clock = info, opener, sleep, clock
        self.token_url = token_url
        self._token, self._until = None, 0.0

    def token(self) -> str:
        if self._token and self.clock() < self._until - 60:
            return self._token
        body = urllib.parse.urlencode({
            "grant_type": "refresh_token", "client_id": self.info["client_id"],
            "client_secret": self.info["client_secret"],
            "refresh_token": self.info["refresh_token"]}).encode()
        request = urllib.request.Request(self.token_url, data=body, method="POST", headers={
            "Content-Type": "application/x-www-form-urlencoded"})
        hide = (self.info["client_secret"], self.info["refresh_token"])
        try:
            got = http.call(request, self.opener, self.sleep, hide=hide)
        except http.Failed as why:
            if why.code in (400, 401):
                raise Unreachable("Google refused the sign-in: its refresh token was revoked "
                                  "or has expired. Make a new one and paste it again.",
                                  why.code) from None
            raise Unreachable(f"Could not get a token from Google: {why}", why.code) from None
        token = got.get("access_token")
        if not token:
            raise Unreachable("Google gave no access token.", 200)
        self._token = str(token)
        self._until = self.clock() + float(got.get("expires_in") or 3600)
        return self._token


class GA4(Adapter):
    id = "ga4"
    name = "Google Analytics"
    key_words = ("a Google service-account key file (JSON), or the install's Search Console "
                 "key; or an OAuth \"authorized_user\" file")
    permission = ("Viewer on the Google Analytics 4 property (read-only), and the Google "
                  "Analytics Data API turned on in the key's Google Cloud project")
    make_key = ("Google Cloud console > IAM & Admin > Service accounts > Create, then Keys > "
                "Add key > JSON (https://console.cloud.google.com/iam-admin/serviceaccounts); "
                "turn on the Google Analytics Data API (APIs & Services > Library)")
    env_names = ("GOOGLE_APPLICATION_CREDENTIALS", "GA4_SERVICE_ACCOUNT_JSON",
                 "GOOGLE_SERVICE_ACCOUNT_KEY", "GA_CREDENTIALS_JSON")
    find_more = ("A key file is often named `*service-account*.json` or `*credentials*.json`; "
                 "GOOGLE_APPLICATION_CREDENTIALS names a file's path. The GA4 tag's G- "
                 "measurement ID in the site's code is not the property ID: the property ID "
                 "is digits, in Admin > Property details.")
    options = {"property": Option(
        "Property ID", r"[0-9]{4,15}",
        "The digits of the Google Analytics 4 property: Admin > Property details > Property "
        "ID (not the G- measurement ID).",
        env=("GA4_PROPERTY_ID", "GA_PROPERTY_ID", "GOOGLE_ANALYTICS_PROPERTY_ID"),
        example="123456789")}
    key_most = google.MAX_KEY_BYTES
    shares_key = "search"

    def __init__(self, data_api: str = DATA_API, token_url: str = TOKEN_URL) -> None:
        self.data_api, self.token_url = data_api.rstrip("/"), token_url

    # ------------------------------------------------------------- the key

    def check_key(self, text: str) -> dict:
        got = plain_key_words(text, self.key_most)
        try:
            info = json.loads(got)
        except ValueError:
            raise BadKey("That is not JSON. Paste the .json key file Google gave you.") from None
        kind = info.get("type") if isinstance(info, dict) else None
        if kind == "service_account":
            try:
                return {"who": google.check_key(got)["client_email"]}
            except google.BadKey as why:
                raise BadKey(str(why)) from None
        if kind == "authorized_user":
            for field in ("client_id", "client_secret", "refresh_token"):
                if not isinstance(info.get(field), str) or not info[field].strip():
                    raise BadKey(f"The sign-in file has no {field}.")
            client = info["client_id"].split(".")[0][-12:]
            return {"who": f"a Google sign-in (OAuth client ...{client})"}
        raise BadKey('This is not a Google key: its "type" is neither "service_account" nor '
                     '"authorized_user".')

    def grant(self, who: str | None) -> str:
        if who and "@" in who:
            return (f"In Google Analytics > Admin > Property access management, add {who} "
                    "with the role Viewer.")
        return ""

    def suggest(self, found: dict | None) -> dict:
        tags = ((found or {}).get("tags") or {}).get("ga4") or []
        return {"measurement_id": tags[0]} if tags else {}

    def send_steps(self, curl: str, url: str, site: str, env_dir: str, robot=None) -> str:
        key = f"{env_dir}/{site}.ga4-key.json"
        lines = []
        if robot:
            lines.append(
                f"Skald has a Google robot already (`{robot}`). The simplest way, with the "
                f"user's yes: use it, no new key (put the property's digits in the address):\n\n"
                f"    {curl} '{url}&key=search' < /dev/null\n\n"
                f"Then the user's one click: in Google Analytics > Admin > Property access "
                f"management, add `{robot}` as a Viewer. Also turn on the Google Analytics Data "
                f"API in that robot's Google Cloud project (with `gcloud`: `gcloud services "
                f"enable analyticsdata.googleapis.com --project <its project>`).")
        lines.append(
            f"A key file the project has (its path, never its text), with the user's yes:\n\n"
            f"    {curl} '{url}' < '<the key file>'\n\n"
            f"A key kept in the project's .env as one line of JSON, often in single quotes (the "
            f"variable's real name in place of `GA4_SERVICE_ACCOUNT_JSON`; a value that is "
            f"base64, starting `ey`, needs `| base64 -d` before the curl):\n\n"
            f"    grep -h '^GA4_SERVICE_ACCOUNT_JSON=' .env* 2>/dev/null | head -1 | cut -d= -f2- "
            f"| sed -e \"s/^'//\" -e \"s/'$//\" | {curl} '{url}'\n\n"
            f"No key yet, `gcloud` installed and signed in, and the user's yes (\"May I make a "
            f"Google Cloud service account for Skald, with one key that can only read Google "
            f"Analytics?\"):\n\n"
            f"    P='<project id>'\n"
            f"    gcloud services enable analyticsdata.googleapis.com --project \"$P\"\n"
            f"    gcloud iam service-accounts create skald-ga4 --display-name 'Skald (reads "
            f"Google Analytics)' --project \"$P\"\n"
            f"    umask 077 && mkdir -p {env_dir} && gcloud iam service-accounts keys create "
            f"{key} --iam-account \"skald-ga4@$P.iam.gserviceaccount.com\"\n"
            f"    {curl} '{url}' < {key}; rm -f {key}\n\n"
            f"Never `cat` a key file. After HTTP 200, Skald's answer names the robot (`who`): "
            f"the user adds it as a Viewer in Google Analytics > Admin > Property access "
            f"management. Put that click in `left_for_user`.")
        return "\n\n".join(lines)

    # ------------------------------------------------------------- the calls

    def _bearer(self, key: str, opener, sleep):
        info = json.loads(key)
        if info.get("type") == "authorized_user":
            return _Refresh(info, opener, sleep, token_url=self.token_url), "the Google sign-in"
        client = google.Client(key, opener=opener, sleep=sleep, token_url=self.token_url,
                               scope=SCOPE)
        return client, client.email

    def _token(self, bearer) -> str:
        try:
            return bearer.token()
        except http.Failed as why:              # the service account's token
            if why.code in (400, 401):
                raise Unreachable("Google refused the service account's key: it may have been "
                                  "deleted or disabled in Google Cloud. Paste a new key.",
                                  why.code) from None
            raise Unreachable(f"Could not get a token from Google: {why}", why.code) from None

    def _run(self, bearer, who: str, prop: str, body: dict, opener, sleep) -> dict:
        for again in (False, True):
            token = self._token(bearer)
            request = urllib.request.Request(
                f"{self.data_api}/properties/{prop}:runReport", method="POST",
                data=json.dumps(body).encode(),
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
            try:
                return http.call(request, opener, sleep, hide=(token,))
            except http.Failed as why:
                if why.code == 401 and not again:
                    bearer._token = None
                    continue
                raise Unreachable(_words(why, who, prop), why.code) from None
        raise AssertionError("unreachable")

    def fetch(self, key, options, now, opener=None, sleep=None) -> list[Answer]:
        prop = str((options or {}).get("property") or "")
        if not re.fullmatch(r"[0-9]{4,15}", prop):
            raise Unreachable("Google Analytics needs its property ID (digits): set it in "
                              "Settings > Leads & tools > Google Analytics.", 0)
        sleep = sleep or time.sleep
        bearer, who = self._bearer(key, opener, sleep)
        out = []
        for report, (dims, metrics) in GA4_REPORTS.items():
            body = request_body(dims, metrics)
            got = self._run(bearer, who, prop, body, opener, sleep)
            start, end, note = window(got, now)
            out.append(Answer(report=report, period=f"{start}..{end}", start=start, end=end,
                              request={"property": prop, **body}, body=got,
                              flags=flags(got), note=note))
        return out

    # ------------------------------------------------------------- the figures

    def figures(self, answer: Answer) -> list[Figure]:
        body = answer.body
        dims, metrics = GA4_REPORTS[answer.report]
        heads = [str((m or {}).get("name") or "") for m in body.get("metricHeaders") or []]
        rows = body.get("rows") or []
        out = []
        for metric in metrics:
            if metric not in heads:            # asked for, not answered: unknown
                out.append(Figure(name=metric, value=None, label=GA4_LABELS.get(metric, metric)))
                continue
            i = heads.index(metric)
            label = GA4_LABELS.get(metric, metric)
            name_src = pointer("metricHeaders", i, "name")
            if not dims:
                value = _number(rows[0]["metricValues"][i].get("value")) if rows else None
                out.append(Figure(name=metric, value=value, label=label, name_src=name_src,
                                  src=pointer("rows", 0, "metricValues", i, "value")
                                  if rows else None))
                continue
            totals = body.get("totals") or []
            tot = (totals[0].get("metricValues") or []) if totals else []
            value = _number(tot[i].get("value")) if i < len(tot) else None
            out.append(Figure(name=metric, value=value, label=label, name_src=name_src,
                              src=pointer("totals", 0, "metricValues", i, "value")
                              if value is not None else None))
            for r, row in enumerate(rows):
                out.append(Figure(
                    name=metric, value=_number(row["metricValues"][i].get("value")), label=label,
                    dim=str(row["dimensionValues"][0].get("value")), rank=r, name_src=name_src,
                    src=pointer("rows", r, "metricValues", i, "value"),
                    dim_src=pointer("rows", r, "dimensionValues", 0, "value")))
        return out

    def headline(self, figures: list[Figure]) -> list[Figure]:
        by = {f.name: f for f in figures if f.dim is None}
        return [by[n] for n in HEADLINE if n in by]


def request_body(dims, metrics) -> dict:
    body = {"dateRanges": [{"startDate": f"{GA4_DAYS}daysAgo", "endDate": "yesterday"}],
            "metrics": [{"name": m} for m in metrics]}
    if dims:
        body.update(dimensions=[{"name": d} for d in dims], limit=GA4_TOP,
                    metricAggregations=["TOTAL"],
                    orderBys=[{"metric": {"metricName": metrics[0]}, "desc": True}])
    return body


def window(got: dict, now: datetime) -> tuple[str, str, str]:
    """The 28 days as GA4 counted them: in the property's own time zone."""
    zone = str((got.get("metadata") or {}).get("timeZone") or "")
    tz, note = timezone.utc, "the property's own days"
    if zone:
        try:
            from zoneinfo import ZoneInfo
            tz = ZoneInfo(zone)
            note = f"the property's own days, {zone}"
        except Exception:                       # noqa: BLE001 - no tz data: say so
            note = f"the property's own days ({zone}; read here as UTC)"
    today = now.astimezone(tz).date()
    return (today - timedelta(days=GA4_DAYS)).isoformat(), \
        (today - timedelta(days=1)).isoformat(), note


def flags(got: dict) -> dict:
    meta = got.get("metadata") or {}
    return {"subjectToThresholding": meta.get("subjectToThresholding") is True,
            "samplingMetadatas": bool(meta.get("samplingMetadatas")),
            "dataLossFromOtherRow": meta.get("dataLossFromOtherRow") is True}


def _words(why: http.Failed, who: str, prop: str) -> str:
    detail = f" (Google said: {why.detail})" if why.detail else ""
    if why.code == 403:
        return (f"Google Analytics refused: {who} has no access to property {prop}. In Google "
                "Analytics > Admin > Property access management, add it as a Viewer. If it is "
                "there, turn on the Google Analytics Data API in the key's Google Cloud project."
                + detail)
    if why.code in (400, 404):
        return (f"Google Analytics has no property {prop} for this key. Use the digits of Admin "
                "> Property details > Property ID, not the G- measurement ID." + detail)
    if why.code == 429:
        return "Google Analytics' quota is used up for now; the next sync tries again." + detail
    if why.code == 0:
        return f"Could not reach Google Analytics: {why}"
    return f"Google Analytics answered {why.code}." + detail


ADAPTER = GA4()
