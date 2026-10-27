"""Google Search Console: the service account, its token, and the two calls
Skald makes (docs/INTEGRATIONS.md, "Search Console").

The key. A service account's JSON key file (Google Cloud console > IAM >
Service accounts > Keys > Add key > JSON). It is found, in this order:

  1. SKALD_GSC_KEY_JSON in the environment: the file's text
  2. SKALD_GSC_KEY_FILE in the environment, else `search_console.key_file`
     in config.yml: a path to the file (0600, readable by Skald only)
  3. secrets.json beside the history, key SKALD_GSC_KEY_JSON: what an
     install admin uploaded in Settings > Leads & tools

`check_key` reads it: type "service_account", a client_email, an RSA private
key search/rsa.py can load. Only the client email is ever shown again; the
key never leaves the server and is never printed or logged.

The token. OAuth 2.0's JWT bearer grant (RFC 7523), as Google documents for
service accounts: a JWT {iss: client_email, scope: webmasters.readonly, aud:
the token address, iat, exp: iat + 1 hour}, signed RS256 (search/rsa.py),
posted to https://oauth2.googleapis.com/token; the access token it gives is
kept in memory until a minute before it runs out. The token address is
always Google's: a key file naming another `token_uri` is refused, so a
planted file cannot send a signed assertion elsewhere.

The calls (https://developers.google.com/webmaster-tools/v1/):

  sites()     GET  webmasters/v3/sites: the properties the account was added
              to, with its permission on each
  query()     POST webmasters/v3/sites/<property>/searchAnalytics/query, paged
              by startRow, ROW_LIMIT (25,000, the most Google allows) a page,
              until a short page; at most MAX_PAGES pages

Read-only scope: Skald can never change anything in Search Console.
"""
from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

from . import http, rsa

ENV_JSON = "SKALD_GSC_KEY_JSON"
ENV_FILE = "SKALD_GSC_KEY_FILE"
SECRET = ENV_JSON                       # the key in secrets.json
SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_TOKEN_URLS = (TOKEN_URL, "https://accounts.google.com/o/oauth2/token",
                     "https://www.googleapis.com/oauth2/v4/token")
API = "https://www.googleapis.com/webmasters/v3"
ROW_LIMIT = 25_000
MAX_PAGES = 40
MAX_KEY_BYTES = 20_000


class BadKey(ValueError):
    """The uploaded or configured key is not a usable service-account key."""


# ------------------------------------------------------------------ the key

def check_key(text) -> dict:
    """{"client_email", "project_id", "key_id"} of a service-account key, or
    BadKey with what is wrong in plain words. Never echoes the key."""
    if isinstance(text, bytes):
        text = text.decode("utf-8", "replace")
    if not isinstance(text, str) or not text.strip():
        raise BadKey("The file is empty.")
    if len(text) > MAX_KEY_BYTES:
        raise BadKey("The file is too big to be a service-account key.")
    try:
        got = json.loads(text)
    except ValueError:
        raise BadKey("The file is not JSON. Upload the .json key file Google gave you.") from None
    if not isinstance(got, dict) or got.get("type") != "service_account":
        raise BadKey('This is not a service-account key (its "type" is not "service_account"). '
                     "Make a key for a service account, not an OAuth client.")
    email = str(got.get("client_email") or "")
    if "@" not in email or len(email) > 254:
        raise BadKey("The key has no client_email.")
    token_uri = str(got.get("token_uri") or TOKEN_URL)
    if token_uri not in GOOGLE_TOKEN_URLS:
        raise BadKey("The key names a token address that is not Google's.")
    try:
        rsa.load_pem(str(got.get("private_key") or ""))
    except rsa.BadKey as why:
        raise BadKey(f"The key's private_key cannot be read: {why}.") from None
    return {"client_email": email, "project_id": str(got.get("project_id") or ""),
            "key_id": str(got.get("private_key_id") or "")[:12]}


def compact(text: str) -> str:
    """The key file as one line of JSON, for secrets.json."""
    return json.dumps(json.loads(text), separators=(",", ":"), sort_keys=True)


def _stored(config: dict, live_dir=None) -> str | None:
    from ..settings_store import secrets_path, _load_secrets
    path = secrets_path(config, live_dir)
    got = _load_secrets(path).get(SECRET) if path is not None else None
    return str(got) if got else None


def find_key(config: dict, live_dir=None) -> tuple[str | None, str]:
    """(the key file's text, where it was found). where: "env", "file <path>",
    "uploaded" or "" when there is none. Raises PermissionError when
    secrets.json is readable by others (secrets_store.Exposed)."""
    value = os.environ.get(ENV_JSON, "").strip()
    if value:
        return value, f"env {ENV_JSON}"
    path = os.environ.get(ENV_FILE, "").strip() or \
        str(((config or {}).get("search_console") or {}).get("key_file") or "").strip()
    if path:
        try:
            return Path(path).expanduser().read_text(encoding="utf-8"), f"file {path}"
        except OSError:
            return None, f"file {path} (cannot be read)"
    got = _stored(config, live_dir)
    return (got, "uploaded") if got else (None, "")


def key_state(config: dict, live_dir=None) -> dict:
    """What Settings may show: {"set", "where", "client_email", "problem"}."""
    try:
        text, where = find_key(config, live_dir)
    except PermissionError:
        return {"set": False, "where": "uploaded", "client_email": None,
                "problem": "secrets.json can be read by others; it must be 0600."}
    if not text:
        return {"set": False, "where": where, "client_email": None,
                "problem": "cannot be read" if where else None}
    try:
        info = check_key(text)
    except BadKey as why:
        return {"set": True, "where": where, "client_email": None, "problem": str(why)}
    return {"set": True, "where": where, "client_email": info["client_email"],
            "project_id": info["project_id"], "problem": None}


# ---------------------------------------------------------------- the client

class Client:
    """One service account's calls. `opener` and `sleep` are for tests;
    `token_url` and `api` too (a fake server on 127.0.0.1)."""

    def __init__(self, key_text: str, opener=None, sleep=time.sleep, clock=time.time,
                 token_url: str = TOKEN_URL, api: str = API, scope: str = SCOPE) -> None:
        check_key(key_text)
        got = json.loads(key_text)
        self.email = got["client_email"]
        self._key = rsa.load_pem(got["private_key"])
        self._key_id = str(got.get("private_key_id") or "")
        self.opener, self.sleep, self.clock = opener, sleep, clock
        self.token_url, self.api, self.scope = token_url, api.rstrip("/"), scope
        self._token: str | None = None
        self._until = 0.0
        self.calls = 0

    def __repr__(self) -> str:
        return f"<Search Console client {self.email}>"

    def assertion(self) -> str:
        now = int(self.clock())
        header = {"alg": "RS256", "typ": "JWT"}
        if self._key_id:
            header["kid"] = self._key_id
        claims = {"iss": self.email, "scope": self.scope, "aud": TOKEN_URL, "iat": now,
                  "exp": now + 3600}
        signing = (rsa.b64url(json.dumps(header, separators=(",", ":")).encode()) + "." +
                   rsa.b64url(json.dumps(claims, separators=(",", ":")).encode()))
        return signing + "." + rsa.b64url(rsa.sign(self._key, signing.encode("ascii")))

    def token(self) -> str:
        if self._token and self.clock() < self._until - 60:
            return self._token
        body = urllib.parse.urlencode({
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": self.assertion()}).encode()
        request = urllib.request.Request(self.token_url, data=body, method="POST", headers={
            "Content-Type": "application/x-www-form-urlencoded"})
        try:
            got = http.call(request, self.opener, self.sleep)
        except http.Failed as why:
            raise http.Failed(why.code, words_for(why, self.email, token=True), why.detail) \
                from None
        token = got.get("access_token")
        if not token:
            raise http.Failed(200, "Google gave no access token.")
        self._token = str(token)
        self._until = self.clock() + float(got.get("expires_in") or 3600)
        return self._token

    def _call(self, method: str, path: str, body: dict | None = None) -> dict:
        for again in (False, True):
            token = self.token()
            request = urllib.request.Request(
                f"{self.api}/{path}", method=method,
                data=json.dumps(body).encode() if body is not None else None,
                headers={"Authorization": f"Bearer {token}",
                         "Content-Type": "application/json"})
            self.calls += 1
            try:
                return http.call(request, self.opener, self.sleep, hide=(token,))
            except http.Failed as why:
                if why.code == 401 and not again:
                    self._token = None          # a token Google no longer takes
                    continue
                raise http.Failed(why.code, words_for(why, self.email), why.detail) from None
        raise AssertionError("unreachable")

    def sites(self) -> list[dict]:
        """[{"siteUrl", "permissionLevel"}] the account can see."""
        got = self._call("GET", "sites")
        return [{"siteUrl": str(s.get("siteUrl") or ""),
                 "permissionLevel": str(s.get("permissionLevel") or "")}
                for s in got.get("siteEntry") or [] if s.get("siteUrl")]

    def query(self, prop: str, body: dict) -> tuple[list[dict], dict]:
        """Every row of one Search Analytics query (paged), and the first
        answer's metadata."""
        path = f"sites/{urllib.parse.quote(prop, safe='')}/searchAnalytics/query"
        rows: list[dict] = []
        meta: dict = {}
        for page in range(MAX_PAGES):
            ask = {**body, "rowLimit": ROW_LIMIT, "startRow": page * ROW_LIMIT}
            got = self._call("POST", path, ask)
            if page == 0:
                meta = dict(got.get("metadata") or {})
                meta["aggregation"] = got.get("responseAggregationType")
            batch = got.get("rows") or []
            rows.extend(batch)
            if len(batch) < ROW_LIMIT:
                return rows, meta
        meta["truncated"] = True
        return rows, meta


def words_for(why: http.Failed, email: str, token: bool = False) -> str:
    """A failed call in plain words, with what to do about it."""
    detail = f" (Google said: {why.detail})" if why.detail else ""
    if token:
        if why.code in (400, 401):
            return ("Google refused the service account's key: it may have been deleted or "
                    "disabled in Google Cloud. Upload a new key in Settings > Leads & tools > Search Console & Bing."
                    + detail)
        return f"Could not get a token from Google: {why}"
    if why.code == 403:
        return (f"Search Console refused: {email} has no access to this property. In Search "
                "Console > Settings > Users and permissions, add it with Restricted access. "
                "If it is there, check the Search Console API is enabled in the key's Google "
                "Cloud project." + detail)
    if why.code == 404:
        return "Search Console has no such property. Check its address in Settings." + detail
    if why.code == 429:
        return "Google's quota is used up for now; the next sync tries again." + detail
    if why.code == 0:
        return f"Could not reach Google: {why}"
    return f"Search Console answered {why}"
