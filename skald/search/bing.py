"""Bing Webmaster Tools: the API key and the calls Skald makes
(docs/INTEGRATIONS.md, "Bing Webmaster Tools").

The key. An API key from Bing Webmaster Tools (Settings > API access > API
key). It is found in BING_WEBMASTER_API_KEY in the environment, else in
secrets.json beside the history under the same name (typed by an install
admin in Settings > Integrations). It travels in the query string, as Bing's
API requires, so every error text is scrubbed of it.

The calls (Bing's JSON endpoint, https://ssl.bing.com/webmaster/api.svc/json/,
IWebmasterApi in Microsoft's reference):

  GetUserSites            the sites the key's account holds (the picker)
  GetRankAndTrafficStats  clicks and impressions per day for the site
  GetQueryStats           the top queries: clicks, impressions, average click
                          and impression position, per date Bing gives
  GetPageStats            the same for the top pages (the URL is in "Query")

Bing says these are "updated every week" and gives only top rows, with no
total beside them, so a Bing query or page table is what Bing returned: its
rows add up to themselves, never claimed to be the site's whole traffic.
Bing's AI Performance report (Copilot citations) had no documented API
method when this was written (2026-10-18), so it is not imported.

Dates come as "/Date(1316156400000-0700)/": milliseconds since 1970 UTC and
the offset Bing meant; the day is read in that offset.
"""
from __future__ import annotations

import os
import re
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

from . import http

ENV = "BING_WEBMASTER_API_KEY"
SETTING = "search.bing_api_key"
API = "https://ssl.bing.com/webmaster/api.svc/json"
KEY = re.compile(r"^[A-Za-z0-9]{16,64}$")
_DATE = re.compile(r"/Date\((-?\d+)([+-]\d{4})?\)/")


class BadKey(ValueError):
    pass


def check_key(value) -> str:
    value = str(value or "").strip()
    if not KEY.match(value):
        raise BadKey("A Bing API key is 16 to 64 letters and digits (Bing Webmaster Tools > "
                     "Settings > API access).")
    return value


def find_key(config: dict, live_dir=None) -> tuple[str | None, str]:
    """(key, where): "env", "uploaded" or ""."""
    value = os.environ.get(ENV, "").strip()
    if value:
        return value, f"env {ENV}"
    from ..settings_store import secrets_path, _load_secrets
    path = secrets_path(config, live_dir)
    got = _load_secrets(path).get(ENV) if path is not None else None
    return (str(got), "uploaded") if got else (None, "")


def key_state(config: dict, live_dir=None) -> dict:
    try:
        value, where = find_key(config, live_dir)
    except PermissionError:
        return {"set": False, "where": "uploaded",
                "problem": "secrets.json can be read by others; it must be 0600."}
    return {"set": bool(value), "where": where,
            "hint": ("…" + value[-4:]) if value and len(value) >= 16 else None, "problem": None}


def parse_date(raw) -> date | None:
    """The day of a "/Date(ms±hhmm)/" value, in the offset it names."""
    m = _DATE.search(str(raw or ""))
    if not m:
        return None
    zone = timezone.utc
    if m.group(2):
        sign = -1 if m.group(2)[0] == "-" else 1
        zone = timezone(sign * timedelta(hours=int(m.group(2)[1:3]),
                                         minutes=int(m.group(2)[3:5])))
    return datetime.fromtimestamp(int(m.group(1)) / 1000, timezone.utc).astimezone(zone).date()


class Client:
    def __init__(self, key: str, opener=None, sleep=time.sleep, api: str = API) -> None:
        self.key = check_key(key)
        self.opener, self.sleep, self.api = opener, sleep, api.rstrip("/")
        self.calls = 0

    def __repr__(self) -> str:
        return "<Bing Webmaster client>"

    def _get(self, method: str, **params) -> list:
        query = urllib.parse.urlencode({**params, "apikey": self.key})
        request = urllib.request.Request(f"{self.api}/{method}?{query}",
                                         headers={"Accept": "application/json"})
        self.calls += 1
        try:
            got = http.call(request, self.opener, self.sleep, hide=(self.key,))
        except http.Failed as why:
            raise http.Failed(why.code, words_for(why), why.detail) from None
        rows = got.get("d")
        return rows if isinstance(rows, list) else []

    def sites(self) -> list[dict]:
        return [{"siteUrl": str(s.get("Url") or ""), "verified": bool(s.get("IsVerified"))}
                for s in self._get("GetUserSites") if s.get("Url")]

    def traffic(self, site_url: str) -> list[dict]:
        """[{"day", "clicks", "impressions"}] per day."""
        out = []
        for r in self._get("GetRankAndTrafficStats", siteUrl=site_url):
            day = parse_date(r.get("Date"))
            if day is not None:
                out.append({"day": day, "clicks": _num(r.get("Clicks")),
                            "impressions": _num(r.get("Impressions"))})
        return out

    def stats(self, site_url: str, kind: str) -> list[dict]:
        """[{"day", "key", "clicks", "impressions", "position", "click_position"}]
        for kind "query" (GetQueryStats) or "page" (GetPageStats)."""
        method = "GetQueryStats" if kind == "query" else "GetPageStats"
        out = []
        for r in self._get(method, siteUrl=site_url):
            day = parse_date(r.get("Date"))
            key = str(r.get("Query") or "")
            if day is None or not key:
                continue
            out.append({"day": day, "key": key[:500], "clicks": _num(r.get("Clicks")),
                        "impressions": _num(r.get("Impressions")),
                        "position": _pos(r.get("AvgImpressionPosition")),
                        "click_position": _pos(r.get("AvgClickPosition"))})
        return out


def _num(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    return int(value) if float(value).is_integer() else round(float(value), 2)


def _pos(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        return None                     # Bing writes -1 for "no position"
    return round(float(value), 2)


def words_for(why: http.Failed) -> str:
    detail = f" (Bing said: {why.detail})" if why.detail else ""
    if why.code in (400, 401, 403) and "key" in (why.detail or "").lower():
        return "Bing refused the API key. Check it in Settings > Integrations." + detail
    if why.code in (400, 401, 403):
        return ("Bing refused: the key's account may not hold this site, or the site is not "
                "verified in Bing Webmaster Tools." + detail)
    if why.code == 0:
        return f"Could not reach Bing: {why}"
    return f"Bing Webmaster Tools answered {why}"
