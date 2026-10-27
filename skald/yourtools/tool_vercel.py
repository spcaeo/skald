"""Vercel Web Analytics: Vercel's own visitors and page views over the last 28 whole
UTC days, and its top pages, referrers and countries (docs/TOOLS.md).

Vercel documents this API (https://vercel.com/docs/analytics/web-analytics-api,
public since May 2026): GET https://api.vercel.com/v1/query/web-analytics/...

  totals     visits/count      {"data": {"pageviews", "visitors"}}: the window's own
                               distinct visitors, as Vercel counts them
  pages      visits/aggregate  by=requestPath      the top VERCEL_TOP rows, the rest
  referrers  visits/aggregate  by=referrerHostname in Vercel's own "Others" row
  countries  visits/aggregate  by=country

`since` and `until` are whole days, both included; Vercel's days are UTC (its rows'
timestamps end in Z). Both endpoints count production only, Vercel's default.
Visitors are never added up across rows: the total is visits/count's.

This is not Skald's count of the site. A site on Vercel reaches Skald through its log
drain (ingest_drain.py): that is the server log Skald counts. Vercel Web Analytics
counts from its own script in the page, so its figures sit apart, labelled "Counted
from: Vercel Web Analytics", and are never added to Skald's.

The key: a Vercel access token. Vercel's tokens cannot be made read-only; the
smallest is one scoped to the project (or its team), with an expiry. Skald only
ever sends GET with it. Options: the project (its ID, prj_..., or its name) and,
for a team's project, the team's ID (team_...).
"""
from __future__ import annotations

import re
import time
import urllib.parse
import urllib.request
from datetime import timedelta, timezone

from ..search import http
from .base import Adapter, Answer, BadKey, Figure, Option, Unreachable, plain_key_words, \
    pointer
from .names import NONE_DIM, VERCEL_DAYS, VERCEL_LABELS, VERCEL_METRICS, VERCEL_REPORTS, \
    VERCEL_TOP

API = "https://api.vercel.com"
COUNT = "/v1/query/web-analytics/visits/count"
AGGREGATE = "/v1/query/web-analytics/visits/aggregate"
TOKEN = re.compile(r"[A-Za-z0-9_-]{20,200}")
OTHERS = "Others"


def _number(raw):
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return int(raw) if float(raw).is_integer() else raw
    raise ValueError("not a number")


class Vercel(Adapter):
    id = "vercel"
    name = "Vercel Web Analytics"
    key_words = "a Vercel access token"
    permission = ("a token scoped to this project (or its team), with an expiry. Vercel's "
                  "tokens cannot be made read-only: the token can do what its scope allows. "
                  "Skald only reads with it (GET), and only Web Analytics")
    make_key = ("Vercel > Account settings > Tokens > Create, scope: the project or its team, "
                "with an expiry (https://vercel.com/account/settings/tokens); Web Analytics "
                "must be on for the project")
    env_names = ("VERCEL_TOKEN", "VERCEL_ACCESS_TOKEN", "VERCEL_API_TOKEN")
    find_more = ("The project's `.vercel/project.json` holds `projectId` (prj_...) and "
                 "`orgId` (team_... for a team's project): not secret, never the token.")
    options = {
        "project": Option("Project ID", r"[A-Za-z0-9._-]{1,100}",
                          "The project's ID (prj_..., Project > Settings > General) or its "
                          "name.", env=("VERCEL_PROJECT_ID",), example="prj_AbC123"),
        "team": Option("Team ID", r"team_[A-Za-z0-9]{1,60}",
                       "For a team's project: the team's ID (team_..., Team > Settings > "
                       "General). Leave it empty for a project of your own account.",
                       required=False, env=("VERCEL_TEAM_ID", "VERCEL_ORG_ID"),
                       example="team_AbC123")}
    key_most = 400
    latest_only = True
    notes = ("Skald's own figures for this site come from Vercel's log drain: the server "
             "log Skald counts. These are Vercel Web Analytics' own counts, from its script "
             "in the page, over Vercel's own days (UTC). They are shown apart and never "
             "added to Skald's.",
             "Vercel's tokens cannot be made read-only. Make one scoped to this project, "
             "with an expiry; Skald only reads with it.")

    def __init__(self, api: str = API) -> None:
        self.api = api.rstrip("/")

    def check_key(self, text: str) -> dict:
        got = plain_key_words(text, self.key_most)
        if not TOKEN.fullmatch(got):
            raise BadKey("That is not a Vercel access token: letters and digits, 20 or more, "
                         "with no spaces. Make one in Vercel > Account settings > Tokens.")
        return {"who": f"a Vercel token ending ...{got[-4:]}"}

    def _get(self, path: str, params: list, key: str, opener, sleep) -> dict:
        request = urllib.request.Request(
            f"{self.api}{path}?{urllib.parse.urlencode(params)}", method="GET",
            headers={"Authorization": f"Bearer {key}", "Accept": "application/json"})
        try:
            return http.call(request, opener, sleep, hide=(key,))
        except http.Failed as why:
            raise Unreachable(_words(why), why.code) from None

    def fetch(self, key, options, now, opener=None, sleep=None) -> list[Answer]:
        project = str((options or {}).get("project") or "")
        if not project:
            raise Unreachable("Vercel needs the project: set it in Settings > Leads & tools > "
                              "Vercel Web Analytics.", 0)
        sleep = sleep or time.sleep
        today = now.astimezone(timezone.utc).date()
        start, end = today - timedelta(days=VERCEL_DAYS), today - timedelta(days=1)
        base = [("projectId", project)]
        if (options or {}).get("team"):
            base.append(("teamId", options["team"]))
        span = [("since", start.isoformat()), ("until", end.isoformat())]
        out = []
        for report, dim in VERCEL_REPORTS.items():
            if dim is None:
                params, path = base + span, COUNT
            else:
                params, path = base + span + [("by", dim), ("limit", VERCEL_TOP)], AGGREGATE
            got = self._get(path, params, key, opener, sleep)
            data = got.get("data")
            if not isinstance(data, list if dim else dict):
                raise Unreachable("Vercel's answer was not in the shape its documentation "
                                  "gives (no data). The API may have changed; Skald keeps the "
                                  "last good figures.", 200)
            others = bool(dim) and any(isinstance(r, dict) and r.get(dim) == OTHERS
                                       for r in data)
            out.append(Answer(report=report, period=f"{start}..{end}", start=start.isoformat(),
                              end=end.isoformat(),
                              request={"path": path, **{k: str(v) for k, v in params}},
                              body=got, flags={"others": others},
                              note="Vercel's own days, UTC, production only"))
        return out

    def figures(self, answer: Answer) -> list[Figure]:
        dim = VERCEL_REPORTS[answer.report]
        data = answer.body.get("data")
        out = []
        if dim is None:
            for m in VERCEL_METRICS:
                value = _number(data.get(m))
                out.append(Figure(name=m, value=value, label=VERCEL_LABELS[m],
                                  src=pointer("data", m) if value is not None else None))
            return out
        for i, row in enumerate(data):
            raw = row.get(dim)
            named = raw not in (None, "")
            for m in VERCEL_METRICS:
                value = _number(row.get(m))
                out.append(Figure(name=m, value=value, label=VERCEL_LABELS[m],
                                  dim=str(raw) if named else NONE_DIM, rank=i,
                                  src=pointer("data", i, m) if value is not None else None,
                                  dim_src=pointer("data", i, dim) if named else None))
        return out

    def headline(self, figures: list[Figure]) -> list[Figure]:
        by = {f.name: f for f in figures if f.dim is None}
        return [by[m] for m in VERCEL_METRICS if m in by]


def _words(why: http.Failed) -> str:
    detail = f" (Vercel said: {why.detail})" if why.detail else ""
    if why.code in (401, 403):
        return ("Vercel refused the token: it may have expired or been revoked, or its scope "
                "does not hold this project. Make a token scoped to the project and paste it "
                "again." + detail)
    if why.code == 402:
        return ("Vercel asks for a paid plan, or the days asked for are older than the plan's "
                "reporting window." + detail)
    if why.code == 404:
        return ("Vercel has no such project for this token, or Web Analytics is not on for "
                "it. Check the project ID (and the team ID for a team's project)." + detail)
    if why.code == 400:
        return "Vercel refused the question as asked." + detail
    if why.code == 429:
        return "Vercel's rate limit is reached for now; the next sync tries again." + detail
    if why.code == 0:
        return f"Could not reach Vercel: {why}"
    return f"Vercel answered {why.code}." + detail


ADAPTER = Vercel()
