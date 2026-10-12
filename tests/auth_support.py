"""A real helper on a free port, in sessions mode, for the accounts HTTP tests.
Not a test module itself.

Two organisations: Alpha (site alpha.example: owner, admin, viewer) and
Beta (site beta.example: its own owner). Addresses are example.com, client
addresses RFC 5737. The accounts clock is accounts.db.now, moved with tick().
"""
from __future__ import annotations

import http.client
import json
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald import accounts, auth_api  # noqa: E402
from skald.accounts import db as base, passwords  # noqa: E402
from skald.refresh_server import HelperServer, make_handler  # noqa: E402

PW = "correct horse battery staple"
SAME = {"Sec-Fetch-Site": "same-origin"}
ORIGIN = "https://www.example.com"
A, B = "alpha.example", "beta.example"


class FakeRunner:
    def __init__(self):
        self.calls = []

    def refresh(self, force=False):
        self.calls.append(force)
        return "ran"


class Answer:
    def __init__(self, status, headers, raw):
        self.status, self.headers, self.raw = status, headers, raw
        try:
            self.json = json.loads(raw) if raw[:1] == b"{" else None
        except ValueError:
            self.json = None

    def header(self, name):
        return self.headers.get(name)

    @property
    def cookie(self):
        got = self.headers.get("Set-Cookie") or ""
        return got.split(";", 1)[0].split("=", 1)[1] if got.startswith("skald_session=") else None


class Server(unittest.TestCase):
    MODE = "sessions"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.live = root / "lib"
        self.live.mkdir()
        self.out = root / "www"
        for site in (A, B):
            data = self.out / site / "data"
            data.mkdir(parents=True)
            for name in ("overview", "requests", "funnels"):
                (data / f"{name}.json").write_text(json.dumps({"name": name, "site": site}))
        self.config = {"access": {"mode": self.MODE, "base_url": ORIGIN},
                       "ours": {"file": str(root / "ours.json"),
                                "change_log": str(root / "ours-changes.log")}}
        self._now = datetime(2026, 10, 11, 14, 0, tzinfo=timezone.utc)
        patcher = mock.patch.object(base, "now", lambda: self._now.strftime(base.STAMP))
        patcher.start()
        self.addCleanup(patcher.stop)
        # A cheap scrypt cost for speed; the stored hash carries its own cost, so
        # the code under test runs unchanged.
        cheap = mock.patch.object(passwords, "N", 2 ** 10)
        cheap.start()
        self.addCleanup(cheap.stop)
        self.notes = []
        for target in ("skald.auth_api.note", "skald.team_api.note"):
            quiet = mock.patch(target, side_effect=self.notes.append)
            quiet.start()
            self.addCleanup(quiet.stop)
        self.sent = []
        deliver = mock.patch("skald.accounts.mails.deliver",
                             side_effect=lambda msg, config, to: self.sent.append((to, msg)))
        deliver.start()
        self.addCleanup(deliver.stop)
        self.seed()
        self.runner = FakeRunner()
        self.server = HelperServer(
            ("127.0.0.1", 0), make_handler(self.runner, {ORIGIN}, self.config, self.out,
                                           self.live))
        threading.Thread(target=self.server.serve_forever, args=(0.02,), daemon=True).start()
        self.addCleanup(self._stop)

    def _stop(self):
        auth_api.drain()
        self.server.shutdown()
        self.server.server_close()

    def seed(self):
        db = self.db()
        try:
            self.alpha = accounts.create_org(db, "Alpha", "cli")
            self.beta = accounts.create_org(db, "Beta", "cli")
            accounts.assign_site(db, A, self.alpha["id"], "cli")
            accounts.assign_site(db, B, self.beta["id"], "cli")
            self.uids = {}
            for email, org, role in (("owner@example.com", self.alpha, "owner"),
                                     ("admin@example.com", self.alpha, "admin"),
                                     ("viewer@example.com", self.alpha, "viewer"),
                                     ("bob@example.com", self.beta, "owner")):
                user = accounts.create_user(db, email, email.split("@")[0].title(), PW)
                accounts.add_member(db, org["id"], user["id"], role, "cli")
                self.uids[email] = user["id"]
        finally:
            db.close()

    def db(self):
        return accounts.connect(accounts.path_for(self.config, self.live))

    def tick(self, seconds):
        self._now += timedelta(seconds=seconds)

    def mail_on(self):
        self.config["mail"] = {"host": "smtp.example.com", "from": "skald@example.com"}

    # ------------------------------------------------------------- requests

    def call(self, method, path, body=None, headers=None, cookie=None, csrf=None,
             raw=None) -> Answer:
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1],
                                          timeout=10)
        hdrs = dict(headers or {})
        data = raw
        if body is not None:
            data = json.dumps(body).encode()
            hdrs.setdefault("Content-Type", "application/json")
        if cookie:
            hdrs["Cookie"] = f"skald_session={cookie}"
        if csrf:
            hdrs["X-Skald-CSRF"] = csrf
        try:
            conn.request(method, path, body=data, headers=hdrs)
            got = conn.getresponse()
            return Answer(got.status, dict(got.getheaders()), got.read())
        finally:
            conn.close()

    def login(self, email="owner@example.com", password=PW, **extra) -> Answer:
        return self.call("POST", "/traffic-auth/login",
                         {"email": email, "password": password, **extra}, SAME)

    def session(self, email="owner@example.com") -> tuple[str, str]:
        """(cookie, csrf) of a fresh sign-in."""
        got = self.login(email)
        self.assertEqual(got.status, 200, got.json)
        me = self.call("GET", f"/traffic/{A if email != 'bob@example.com' else B}/me",
                       cookie=got.cookie)
        return got.cookie, me.json["csrf"]

    def check(self, uri, cookie=None, path=None) -> Answer:
        """nginx's auth_request: the raw address and nginx's own (normalised)
        path, which is the raw path unless `path` says otherwise ("" = none)."""
        path = uri.split("?", 1)[0] if path is None else path
        headers = {"X-Original-URI": uri}
        if path:
            headers["X-Original-Path"] = path
        return self.call("GET", "/traffic-auth/check", headers=headers, cookie=cookie)

    def post(self, path, body, cookie, csrf, headers=None) -> Answer:
        return self.call("POST", path, body, {**SAME, **(headers or {})}, cookie=cookie,
                         csrf=csrf)
