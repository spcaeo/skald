"""Release 3: named users and roles, read-only API tokens, the API and
funnel routes on the helper, and the funnel counts themselves."""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import access, funnels, tokens  # noqa: E402
from skald.refresh_server import make_handler  # noqa: E402

SAME = {"Sec-Fetch-Site": "same-origin"}


class FakeRunner:
    def __init__(self):
        self.calls = []

    def refresh(self, force=False):
        self.calls.append(force)
        return "ran"


class Box(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.live = self.root / "lib"
        self.live.mkdir()
        self.out = self.root / "www"
        data = self.out / "example.com" / "data"
        data.mkdir(parents=True)
        for name in ("overview", "requests", "funnels"):
            (data / f"{name}.json").write_text(json.dumps({"name": name}))
        self.pw = self.root / "htpasswd"
        self.pw.write_text("morgan:$apr1$x$y\n")
        self.config = {"ours": {"file": str(self.root / "ours.json"),
                                "change_log": str(self.root / "ours-changes.log")},
                       "access": {"htpasswd": str(self.pw)}}

    def tearDown(self):
        self._tmp.cleanup()

    def roles(self, **users):
        (self.live / "users.json").write_text(json.dumps(
            {"users": {u: {"role": r} for u, r in users.items()}}))

    def request(self, method, path, headers=None, body=b"", peer="127.0.0.1"):
        runner = FakeRunner()
        handler = make_handler(runner, {"https://www.example.com"}, self.config, self.out,
                               self.live)
        raw = (f"{method} {path} HTTP/1.1\r\nHost: x\r\nContent-Length: {len(body)}\r\n"
               + "".join(f"{k}: {v}\r\n" for k, v in (headers or {}).items())
               + "\r\n").encode() + body
        out = io.BytesIO()

        class Socket:
            def makefile(self, mode, *a, **k):
                return io.BytesIO(raw)

            def sendall(self, data):
                out.write(data)

        handler(Socket(), (peer, 5555), None)
        head, _, data = out.getvalue().partition(b"\r\n\r\n")
        return int(head.split()[1]), (json.loads(data) if data.startswith(b"{") else None)


class TestRoles(Box):
    def test_one_shared_login_is_admin_until_roles_exist(self):
        self.assertEqual(access.role_of(self.config, self.live, "anyone"), "admin")
        self.roles(morgan="admin", sam="viewer")
        self.assertEqual(access.role_of(self.config, self.live, "morgan"), "admin")
        self.assertEqual(access.role_of(self.config, self.live, "sam"), "viewer")
        self.assertEqual(access.role_of(self.config, self.live, "stranger"), "viewer")

    def test_viewers_read_admins_change(self):
        self.roles(morgan="admin", sam="viewer")
        code, body = self.request("GET", "/traffic/example.com/me", {"X-Skald-User": "sam"})
        self.assertEqual((code, body["user"], body["role"]), (200, "sam", "viewer"))
        add = json.dumps({"ip": "203.0.113.5", "label": "Home"}).encode()
        hdr = {**SAME, "Content-Type": "application/json"}
        code, body = self.request("POST", "/traffic/example.com/ours/add",
                                  {**hdr, "X-Skald-User": "sam"}, add)
        self.assertEqual((code, body["error"]), (403, "admins only"))
        code, body = self.request("POST", "/traffic/example.com/ours/add",
                                  {**hdr, "X-Skald-User": "morgan"}, add)
        self.assertEqual(code, 200, body)
        line = (self.root / "ours-changes.log").read_text().strip().split("\t")
        self.assertEqual((line[1], line[-1]), ("add", "morgan"))

    def test_the_user_header_is_believed_from_nginx_only(self):
        self.roles(morgan="admin")
        code, body = self.request("GET", "/traffic/example.com/me", {"X-Skald-User": "morgan"},
                                  peer="198.51.100.9")
        self.assertEqual((body["user"], body["role"]), (None, "viewer"))


class TestUserCommand(Box):
    def ctx(self, *argv, stdin=""):
        out = []
        args = SimpleNamespace(action=argv[0], name=argv[1] if len(argv) > 1 else None,
                               role=argv[2] if len(argv) > 2 else "viewer",
                               password_stdin=True)
        return SimpleNamespace(args=args, config=self.config, live_dir=self.live,
                               out=out.append, err=out.append), out

    def run_cmd(self, *argv, password="correct horse battery"):
        ctx, out = self.ctx(*argv)
        with mock.patch("sys.stdin", io.StringIO(password + "\n")), \
                mock.patch.object(access, "hash_password",
                                  side_effect=lambda n, p: f"{n}:$6$salt$hash"):
            return access.cmd_user(ctx), out

    def test_add_list_role_remove_and_the_guards(self):
        self.assertEqual(self.run_cmd("role", "morgan", "admin")[0], 0)
        code, out = self.run_cmd("add", "morgan", "viewer")
        self.assertEqual(code, 1)
        self.assertIn("never changed", out[0])            # the owner's password stays
        self.assertEqual(self.run_cmd("add", "sam", "viewer", password="short")[0], 1)
        self.assertEqual(self.run_cmd("add", "sam", "viewer")[0], 0)
        self.assertEqual(self.pw.read_text().splitlines(),
                         ["morgan:$apr1$x$y", "sam:$6$salt$hash"])
        code, out = self.run_cmd("list")
        self.assertEqual(out, ["morgan               admin", "sam                  viewer"])
        self.assertEqual(self.run_cmd("remove", "morgan")[0], 1)    # the last admin
        self.assertEqual(self.run_cmd("remove", "sam")[0], 0)
        self.assertEqual(self.pw.read_text().splitlines(), ["morgan:$apr1$x$y"])
        log = (self.live / "access.log").read_text().splitlines()
        self.assertEqual([l.split("\t")[1] for l in log], ["role", "add", "remove"])

    def test_the_password_goes_by_stdin_never_argv(self):
        calls = []

        def run(cmd, **kw):
            calls.append((cmd, kw.get("input")))
            return SimpleNamespace(stdout="$6$s$h\n")
        with mock.patch("shutil.which", side_effect=lambda b: "/usr/bin/openssl"
                        if b == "openssl" else None):
            self.assertEqual(access.hash_password("sam", "secret pw 123", run), "sam:$6$s$h")
        self.assertNotIn("secret pw 123", " ".join(calls[0][0]))
        self.assertEqual(calls[0][1], "secret pw 123")


class TestApi(Box):
    def test_files_behind_the_password_and_by_token(self):
        code, body = self.request("GET", "/traffic/example.com/api/v1/")
        self.assertEqual((code, body["files"]), (200, ["funnels", "overview", "requests"]))
        code, body = self.request("GET", "/traffic/example.com/api/v1/overview")
        self.assertEqual(body, {"name": "overview"})
        self.assertEqual(self.request("GET", "/traffic/example.com/api/v1/nothing")[0], 404)
        self.assertEqual(self.request("GET", "/traffic/../api/v1/overview")[0], 405)
        path = tokens.path_for(self.config, self.live)
        plain = tokens.create(path, "a script")
        private = tokens.create(path, "ops", private=True)
        url = "/traffic-api/v1/example.com/"
        self.assertEqual(self.request("GET", url + "overview")[0], 401)
        auth = {"Authorization": f"Bearer {plain}"}
        self.assertEqual(self.request("GET", url + "overview", auth)[1], {"name": "overview"})
        code, body = self.request("GET", url + "requests", auth)
        self.assertEqual(code, 401)
        self.assertIn("addresses", body["error"])
        self.assertEqual(self.request("GET", url + "requests",
                                      {"Authorization": f"Bearer {private}"})[0], 200)
        stored = path.read_text()
        self.assertNotIn(plain.split("_", 2)[2], stored)          # only the hash is kept
        tid = plain.split("_")[1]
        args = SimpleNamespace(action="revoke", name=tid, site=None, private=False)
        tokens.cmd_token(SimpleNamespace(args=args, config=self.config, live_dir=self.live,
                                         out=lambda *a: None, err=lambda *a: None))
        self.assertEqual(self.request("GET", url + "overview", auth)[0], 401)


class TestFunnels(Box):
    J = [  # three visits
        {"source": "AI assistant", "via": "ChatGPT", "landing": "/",
         "trail": [["/", "page"], ["/pricing/", "app"], ["/signup/", "page"]]},
        {"source": "Search engine", "via": "google.com", "landing": "/blog/x",
         "trail": [["/blog/x", "page"], ["/pricing/", "page"]]},
        {"source": "Direct or unknown", "via": "", "landing": "/signup/",
         "trail": [["/signup/", "page"], ["/pricing/", "page"]]},
    ]

    def test_steps_in_order_and_drop_off(self):
        f = funnels.defaults()[0]
        result, _ = funnels.compute(f, self.J, date(2026, 10, 1), date(2026, 10, 8), None, None)
        n = [s["n"] for s in result["steps"]]
        self.assertEqual(n[:3], [3, 3, 1])     # the third visit saw sign-up before pricing
        self.assertEqual(result["steps"][2]["drop"], 2)
        self.assertEqual(result["steps"][2]["of_first_pct"], 33.3)
        self.assertIsNone(result["steps"][3]["n"])      # no CMS here: "not recorded"
        mine = {**f, "source": "ChatGPT"}
        result, _ = funnels.compute(mine, self.J, date(2026, 10, 1), date(2026, 10, 8), None, None)
        self.assertEqual([s["n"] for s in result["steps"][:3]], [1, 1, 1])

    def test_contains_and_the_visit_start(self):
        f = {"name": "x", "source": None, "steps": [
            {"label": "Any visit", "kind": "any"},
            {"label": "Pricing", "kind": "path", "match": "contains", "paths": ["pric"]}]}
        result, _ = funnels.compute(f, self.J, date(2026, 10, 1), date(2026, 10, 8), None, None)
        self.assertEqual([s["n"] for s in result["steps"]], [3, 3])
        self.assertEqual(funnels.clean(f)["steps"][0], {"label": "Any visit", "kind": "any"})
        with self.assertRaises(funnels.Invalid):
            funnels.clean({"name": "y", "steps": [f["steps"][1], {"kind": "any"}]})

    def test_event_steps_count_events_beside_the_visits(self):
        f = funnels.clean({"name": "Hero to sign-up", "steps": [
            {"label": "Landed", "kind": "path", "match": "starts_with", "paths": ["/"]},
            {"label": "Clicked Start free", "kind": "event", "events": ["cta_click"]}]})
        self.assertEqual(f["steps"][1], {"label": "Clicked Start free", "kind": "event",
                                         "events": ["cta_click"]})
        rows = [("2026-10-07", "cta_click", "Search engine", 2),
                ("2026-10-07", "cta_click", "Direct or unknown", 1),
                ("2026-10-07", "scroll_75", "Search engine", 5)]
        result, _ = funnels.compute(f, self.J, date(2026, 10, 1), date(2026, 10, 8), None, None,
                                    None, rows)
        self.assertEqual((result["steps"][1]["kind"], result["steps"][1]["n"]), ("event", 3))
        self.assertIsNone(result["steps"][1]["of_previous_pct"])
        mine = {**f, "source": "Search engine"}
        result, _ = funnels.compute(mine, self.J, date(2026, 10, 1), date(2026, 10, 8), None,
                                    None, None, rows)
        self.assertEqual(result["steps"][1]["n"], 2)
        result, _ = funnels.compute(f, self.J, date(2026, 10, 1), date(2026, 10, 8), None, None)
        self.assertIsNone(result["steps"][1]["n"])          # beacon off: not recorded
        with self.assertRaises(funnels.Invalid):
            funnels.clean({"name": "x", "steps": [f["steps"][0], {"kind": "event", "events": ["Bad!"]}]})

    def test_saving_is_checked_logged_and_for_admins(self):
        self.roles(morgan="admin", sam="viewer")
        body = json.dumps({"name": "Blog to pricing", "steps": [
            {"label": "Blog", "match": "starts_with", "paths": ["/blog/"]},
            {"label": "Pricing", "match": "segment", "paths": ["pricing"]}]}).encode()
        hdr = {**SAME, "Content-Type": "application/json"}
        url = "/traffic/example.com/funnels/save"
        self.assertEqual(self.request("POST", url, {**hdr, "X-Skald-User": "sam"}, body)[0], 403)
        code, got = self.request("POST", url, {**hdr, "X-Skald-User": "morgan"}, body)
        self.assertEqual(code, 200, got)
        self.assertEqual(funnels.saved(self.live)[0]["saved_by"], "morgan")
        bad = json.dumps({"name": "x", "steps": [{"paths": ["/a"]}]}).encode()
        self.assertEqual(self.request("POST", url, {**hdr, "X-Skald-User": "morgan"}, bad)[0], 400)
        self.assertEqual(self.request("POST", url, {"Content-Type": "application/json",
                                                    "X-Skald-User": "morgan"}, body)[0], 403)
        log = (self.live / "funnels-changes.log").read_text().split("\t")
        self.assertEqual((log[1], log[-1].strip()), ("save", "morgan"))


if __name__ == "__main__":
    unittest.main()


class TestLeadsBySourceAndAssistant(unittest.TestCase):
    def test_types_by_source_and_assistant_add_up_and_recount(self):
        import sqlite3
        from datetime import date, datetime, timezone
        from zoneinfo import ZoneInfo
        from skald import audit_leads, leads
        tz = ZoneInfo("America/New_York")
        with tempfile.TemporaryDirectory() as tmp:
            db_file = Path(tmp) / "payload.db"
            db = sqlite3.connect(db_file)
            db.execute("CREATE TABLE submissions (id INTEGER PRIMARY KEY, type TEXT, status TEXT, "
                       "created_at TEXT, page TEXT, locale TEXT, ai_source TEXT, "
                       "first_touch TEXT, last_touch TEXT)")
            gpt = json.dumps({"aiSource": "ChatGPT", "referrerHost": "chatgpt.com"})
            goo = json.dumps({"referrerHost": "www.google.com"})
            rows = [("demo_booked", "new", gpt, goo), ("signup", "new", gpt, gpt),
                    ("contact", "new", goo, goo), ("signup", "spam", gpt, gpt)]
            for i, (t, st, ft, lt) in enumerate(rows):
                db.execute("INSERT INTO submissions (type, status, created_at, page, locale, "
                           "first_touch, last_touch) VALUES (?, ?, ?, '/', 'en-us', ?, ?)",
                           (t, st, f"2026-10-0{5 + i % 2}T15:00:00.000Z", ft, lt))
            db.commit()
            db.close()
            blob = leads.blob({"leads": {"db": str(db_file)}}, tz, date(2026, 10, 8), [],
                              date(2026, 10, 1))
            self.assertTrue(blob["available"], blob.get("error"))
            got = blob["by_source_type"]
            self.assertEqual(got["first_touch"]["AI assistant"], {"demo_booked": 1, "signup": 1})
            self.assertEqual(got["last_touch"]["Search engine"], {"demo_booked": 1, "contact": 1})
            self.assertEqual(got["ai_first"]["chatgpt"], {"demo_booked": 1, "signup": 1})
            audit = audit_leads.audit_leads(db_file, tz, date.fromisoformat(blob["period"]["first"]),
                                            date.fromisoformat(blob["period"]["last"]))
            self.assertEqual(audit_leads.compare(blob, audit), [])
            blob["by_source_type"]["ai_first"]["chatgpt"]["signup"] += 1
            self.assertTrue(audit_leads.compare(blob, audit))
            self.assertTrue(leads.check(blob))
