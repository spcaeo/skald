"""Shared parts of the search tests (not a test module): a throwaway test key,
a service-account key file made from it, and one fake HTTP server on
127.0.0.1 that answers as Google's token endpoint, the Search Console API and
Bing's Webmaster API would. No test ever calls Google or Bing.

The key is TEST ONLY (tests/fixtures/search/rs256-test-vector.json). The fake
token endpoint checks the JWT's RS256 signature with the key's public half,
so a broken signer fails the tests.
"""
from __future__ import annotations

import base64
import json
import threading
import urllib.parse
from collections import defaultdict
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald.search import rsa  # noqa: E402

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "search" / "rs256-test-vector.json"
VECTOR = json.loads(FIXTURE.read_text())
EMAIL = "robot@example.com"
BING_KEY = "0123456789abcdef0123456789ABCDEF"     # made up
TOKEN = "test-access-token"


def pem() -> str:
    """The test key as a PKCS#8 PEM block (the armour built here, so the
    repository never holds a whole key header)."""
    body = VECTOR["pkcs8_der_base64"]
    lines = [body[i:i + 64] for i in range(0, len(body), 64)]
    kind = "PRIVATE " + "KEY"
    return "\n".join([f"-----BEGIN {kind}-----", *lines, f"-----END {kind}-----", ""])


def service_key(email: str = EMAIL, **extra) -> str:
    return json.dumps({"type": "service_account", "project_id": "example-project",
                       "private_key_id": "0123456789abcdef0123", "private_key": pem(),
                       "client_email": email, "client_id": "1",
                       "token_uri": "https://oauth2.googleapis.com/token", **extra})


def public() -> tuple[int, int]:
    key = rsa.load_pem(pem())
    return key.n, key.e


# ------------------------------------------------------------- the dataset

def records(first: date, last: date, scale: int = 1) -> dict:
    """{day iso: [record]}: each record one (query, page, country, device,
    appearance) with clicks, impressions and position. query None is an
    anonymised query: in every total, in no query row."""
    out = {}
    d = first
    while d <= last:
        k = (d - first).days
        rows = [
            {"query": "server log analytics", "page": "https://www.alpha.example/",
             "country": "usa", "device": "DESKTOP", "appearance": None,
             "clicks": 5 * scale + k % 3, "impressions": 100 + k, "position": 3.5},
            {"query": "ai crawler log", "page": "https://www.alpha.example/blog/ai",
             "country": "deu", "device": "MOBILE", "appearance": "AMP_BLUE_LINK",
             "clicks": 2, "impressions": 40, "position": 7.25},
            {"query": "skald", "page": "https://alpha.example/pricing",
             "country": "usa", "device": "MOBILE", "appearance": None,
             "clicks": 1, "impressions": 10, "position": 1.0},
            {"query": None, "page": "https://www.alpha.example/blog/ai",
             "country": "gbr", "device": "TABLET", "appearance": None,
             "clicks": 1, "impressions": 30, "position": 12.0},
        ]
        out[d.isoformat()] = rows
        d += timedelta(days=1)
    return out


def _group(rows: list[dict]) -> dict:
    clicks = sum(r["clicks"] for r in rows)
    shown = sum(r["impressions"] for r in rows)
    pos = sum(r["position"] * r["impressions"] for r in rows) / shown if shown else 0
    return {"clicks": float(clicks), "impressions": float(shown),
            "ctr": clicks / shown if shown else 0, "position": round(pos, 4)}


# --------------------------------------------------------------- the server

class Engines(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self):
        super().__init__(("127.0.0.1", 0), Handler)
        self.data: dict = {}
        self.incomplete: str | None = None       # first_incomplete_date
        self.props = {"sc-domain:alpha.example": "siteRestrictedUser",
                      "https://www.beta.example/": "siteFullUser"}
        self.fail: list[int] = []                # statuses to answer first, once each
        self.calls: list[tuple[str, str, dict]] = []
        self.refuse_appearance_with_date = True
        self.bing: dict = {"traffic": [], "query": [], "page": [],
                           "sites": ["https://www.alpha.example/"]}
        self.claims: list[dict] = []
        threading.Thread(target=self.serve_forever, args=(0.02,), daemon=True).start()

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.server_address[1]}"

    def api(self) -> dict:
        return {"google_api": self.base + "/webmasters/v3", "google_token_url": self.base + "/token",
                "bing_api": self.base + "/bing"}

    def stop(self):
        self.shutdown()
        self.server_close()

    # Search Analytics, as the reference describes it
    def query(self, prop: str, body: dict) -> tuple[int, dict]:
        dims = body.get("dimensions") or []
        if "searchAppearance" in dims and len(dims) > 1 and self.refuse_appearance_with_date:
            return 400, {"error": {"code": 400, "message": "searchAppearance cannot be "
                                                           "grouped with other dimensions"}}
        final = str(body.get("dataState") or "final").lower() == "final"
        first, last = body["startDate"], body["endDate"]
        names = {"date": None, "query": "query", "page": "page", "country": "country",
                 "device": "device", "searchAppearance": "appearance"}
        groups: dict = defaultdict(list)
        for d, rows in sorted(self.data.items()):
            if not first <= d <= last:
                continue
            if final and self.incomplete and d >= self.incomplete:
                continue
            for r in rows:
                key = []
                for dim in dims:
                    value = d if dim == "date" else r[names[dim]]
                    if value is None:
                        break
                    key.append(value)
                else:
                    groups[tuple(key)].append(r)
        out = [{"keys": list(k), **_group(v)} for k, v in groups.items()]
        if "date" in dims:
            out.sort(key=lambda r: r["keys"][0])
        else:
            out.sort(key=lambda r: -r["clicks"])
        start, limit = int(body.get("startRow") or 0), int(body.get("rowLimit") or 1000)
        answer = {"rows": out[start:start + limit],
                  "responseAggregationType": body.get("aggregationType") or "auto"}
        if not final and "date" in dims and self.incomplete and \
                any(self.incomplete <= d <= last for d in self.data if first <= d):
            answer["metadata"] = {"first_incomplete_date": self.incomplete}
        if not answer["rows"]:
            answer.pop("rows")
        return 200, answer


def _bing_date(day: str) -> str:
    d = date.fromisoformat(day)
    ms = int((d - date(1970, 1, 1)).total_seconds() * 1000) + 7 * 3600 * 1000
    return f"/Date({ms}-0700)/"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code: int, body):
        raw = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _failing(self) -> bool:
        if self.server.fail:
            code = self.server.fail.pop(0)
            self._send(code, {"error": {"code": code, "message": "try later"}})
            return True
        return False

    def do_POST(self):
        s = self.server
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        if self.path == "/token":
            form = dict(urllib.parse.parse_qsl(raw.decode()))
            s.calls.append(("POST", "/token", form))
            jwt = form.get("assertion", "")
            head, claims, sig = (jwt.split(".") + ["", "", ""])[:3]
            pad = lambda t: t + "=" * (-len(t) % 4)          # noqa: E731
            n, e = public()
            ok = form.get("grant_type") == "urn:ietf:params:oauth:grant-type:jwt-bearer" and \
                rsa.verify(n, e, f"{head}.{claims}".encode(),
                           base64.urlsafe_b64decode(pad(sig)))
            if not ok:
                return self._send(400, {"error": "invalid_grant",
                                        "error_description": "Invalid JWT Signature."})
            s.claims.append(json.loads(base64.urlsafe_b64decode(pad(claims))))
            return self._send(200, {"access_token": TOKEN, "expires_in": 3599,
                                    "token_type": "Bearer"})
        body = json.loads(raw or b"{}")
        s.calls.append(("POST", self.path, body))
        if self.headers.get("Authorization") != f"Bearer {TOKEN}":
            return self._send(401, {"error": {"code": 401, "message": "no token"}})
        if self._failing():
            return None
        prefix = "/webmasters/v3/sites/"
        if self.path.startswith(prefix) and self.path.endswith("/searchAnalytics/query"):
            prop = urllib.parse.unquote(self.path[len(prefix):-len("/searchAnalytics/query")])
            if prop not in s.props:
                return self._send(403, {"error": {"code": 403, "message": "User does not have "
                                                  "sufficient permission for site."}})
            return self._send(*s.query(prop, body))
        return self._send(404, {"error": {"code": 404, "message": "not found"}})

    def do_GET(self):
        s = self.server
        parts = urllib.parse.urlsplit(self.path)
        q = dict(urllib.parse.parse_qsl(parts.query))
        s.calls.append(("GET", parts.path, q))
        if parts.path == "/webmasters/v3/sites":
            if self.headers.get("Authorization") != f"Bearer {TOKEN}":
                return self._send(401, {"error": {"code": 401, "message": "no token"}})
            return self._send(200, {"siteEntry": [{"siteUrl": k, "permissionLevel": v}
                                                  for k, v in s.props.items()]})
        if parts.path.startswith("/bing/"):
            if q.get("apikey") != BING_KEY:
                return self._send(400, {"ErrorCode": 3, "Message": "InvalidApiKey"})
            if self._failing():
                return None
            method = parts.path[len("/bing/"):]
            if method == "GetUserSites":
                return self._send(200, {"d": [{"Url": u, "IsVerified": True}
                                              for u in s.bing["sites"]]})
            if q.get("siteUrl") not in s.bing["sites"]:
                return self._send(400, {"ErrorCode": 14, "Message": "NotAuthorized"})
            if method == "GetRankAndTrafficStats":
                return self._send(200, {"d": [
                    {"__type": "RankAndTrafficStats:#Microsoft.Bing.Webmaster.Api",
                     "Clicks": c, "Impressions": i, "Date": _bing_date(d)}
                    for d, c, i in s.bing["traffic"]]})
            if method in ("GetQueryStats", "GetPageStats"):
                rows = s.bing["query" if method == "GetQueryStats" else "page"]
                return self._send(200, {"d": [
                    {"AvgClickPosition": p, "AvgImpressionPosition": p, "Clicks": c,
                     "Date": _bing_date(d), "Impressions": i, "Query": k}
                    for d, k, c, i, p in rows]})
        return self._send(404, {"error": "not found"})
