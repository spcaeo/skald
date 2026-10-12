"""`skald upgrade` (upgrade.py, upgrade_files.py): which release, the daily
run's window, the download and its SHA-256, safe unpacking, the dry run
against a local release server, the swap, the health checks, the rollback,
and the automatic levels. Nothing here reaches the internet: the release
server is a ThreadingHTTPServer on 127.0.0.1, or a fetcher passed in; the
skald commands, systemctl and the mail are fakes."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sqlite3
import sys
import tarfile
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import upgrade, upgrade_files as uf  # noqa: E402
from skald.store import History  # noqa: E402
from skald.upgrade_files import Refused, Skipped  # noqa: E402

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "github_release_latest.json"
NOW = datetime(2026, 10, 21, 15, 0, tzinfo=timezone.utc)
UTC = timezone.utc


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def tree(root: Path, version: str) -> Path:
    """The smallest code folder that looks like an install.sh install."""
    write(root / "skald" / "cli.py", "# the command line\n")
    write(root / "bin/skald", "#!/usr/bin/env python3\n")
    write(root / "VERSION", version + "\n")
    write(root / "NAME", "Skald\n")
    return root


def tarball(version: str, files: dict | None = None, link: str | None = None) -> bytes:
    """A release tarball as release.yml makes it: one top folder skald-<version>/."""
    with tempfile.TemporaryDirectory() as tmp:
        code = tree(Path(tmp) / "code", version)
        for rel, text in (files or {}).items():
            write(code / rel, text)
        raw = io.BytesIO()
        with tarfile.open(fileobj=raw, mode="w:gz") as tar:
            for path in sorted(code.rglob("*")):
                if path.is_file():
                    tar.add(path, arcname=f"skald-{version}/{path.relative_to(code).as_posix()}")
            if link:
                info = tarfile.TarInfo(f"skald-{version}/{link}")
                info.type, info.linkname = tarfile.SYMTYPE, "/etc/passwd"
                tar.addfile(info)
        return raw.getvalue()


def sums(name: str, data: bytes) -> bytes:
    return f"{hashlib.sha256(data).hexdigest()}  {name}\n{'0' * 64}  install.sh\n".encode()


class Release:
    """The files of one release, by URL: GitHub's answer and the downloads."""

    def __init__(self, version="2.2.0", data: bytes | None = None, bad_hash=False, **over):
        self.version = version
        self.data = data if data is not None else tarball(version)
        name = f"skald-{version}.tar.gz"
        self.files = {name: self.data,
                      "SHA256SUMS": sums(name, b"other bytes" if bad_hash else self.data)}
        answer = json.loads(FIXTURE.read_text())
        answer.update(tag_name=f"v{version}", name=f"v{version}",
                      html_url=f"https://github.com/spcaeo/skald/releases/tag/v{version}", **over)
        self.answer = json.dumps(answer).encode()
        self.calls: list[str] = []

    def __call__(self, url: str, agent: str) -> bytes:
        self.calls.append(url)
        assert agent.startswith("Skald/"), agent
        if url.startswith("https://api.github.com/"):
            return self.answer
        return self.files[url.rsplit("/", 1)[-1]]


class Server:
    """A local release server (ThreadingHTTPServer) serving a release's files."""

    def __init__(self, release: Release):
        files = release.files

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                body = files.get(self.path.rsplit("/", 1)[-1])
                self.send_response(200 if body is not None else 404)
                self.send_header("Content-Length", str(len(body or b"")))
                self.end_headers()
                self.wfile.write(body or b"")

            def log_message(self, *a):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}/v{release.version}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


class Runner:
    """skald commands: migrate changes the history (as a real migration
    would); the commands in `fail` fail with the new code (or always)."""

    def __init__(self, app: Path, db: Path, fail=(), always=False):
        self.app, self.db, self.fail, self.always = app, db, set(fail), always
        self.calls: list[tuple] = []

    def __call__(self, argv, cwd=None):
        words = tuple(argv[4:])
        version = (self.app / "VERSION").read_text().strip()
        self.calls.append((version, words))
        if words[0] in self.fail and (self.always or version != "2.1.0"):
            return 1, f"{words[0]}: the figures do not reconcile"
        if words[:1] == ("migrate",) and "--check" not in words:
            db = sqlite3.connect(self.db)
            db.execute("INSERT INTO meta (key, value) VALUES ('migrated', 'by the new code')")
            db.commit()
            db.close()
            return 0, "history: schema 11 -> 12 (1 steps)"
        return 0, "ok"


class Ctx:
    def __init__(self, root: Path, config: dict, **args):
        self.config = config
        self.config_path = root / "config.yml"
        self.config_path.write_text("site:\n  name: example.com\n")
        self.db_path = root / "data" / "history.sqlite"
        self.live_dir = self.db_path.parent
        History(self.db_path).close()
        base = dict(to=None, dry_run=False, yes=True, allow_major=False, auto=False,
                    source_url=None, dir=None)
        base.update(args)
        self.args = argparse.Namespace(**base)
        self.said, self.warned = [], []
        self.out = lambda *a: self.said.append(" ".join(map(str, a)))
        self.err = lambda *a: self.warned.append(" ".join(map(str, a)))


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.app = tree(self.root / "opt" / "skald", "2.1.0")
        self.restarts, self.mails = [], []

    def tearDown(self):
        self.tmp.cleanup()

    def upgrader(self, ctx, release=None, runner=None, **kw):
        self.runner = runner or Runner(self.app, ctx.db_path)
        return upgrade.Upgrader(
            ctx, app=self.app, fetch=release, run=self.runner,
            restart=lambda: self.restarts.append(1) or [], helper=lambda config: None,
            send=lambda msg, cfg: self.mails.append(msg), cron_text="", local_tz=UTC, now=NOW,
            **kw)

    def version(self, path: Path | None = None) -> str:
        return ((path or self.app) / "VERSION").read_text().strip()

    def log(self, ctx) -> list[dict]:
        path = ctx.db_path.parent / "upgrades.log"
        return [json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []

    def migrated(self, ctx) -> bool:
        db = sqlite3.connect(ctx.db_path)
        try:
            return db.execute("SELECT 1 FROM meta WHERE key = 'migrated'").fetchone() is not None
        finally:
            db.close()


class Target(unittest.TestCase):
    def test_manual(self):
        self.assertEqual(uf.target("2.1.0", "2.2.0"), ("2.2.0", "minor"))
        self.assertEqual(uf.target("2.1.0", "2.9.0", to="v2.1.1"), ("2.1.1", "patch"))
        with self.assertRaisesRegex(Skipped, "nothing to do"):
            uf.target("2.1.0", "2.1.0")
        with self.assertRaisesRegex(Refused, "downgrade"):
            uf.target("2.1.0", None, to="v2.0.5")
        with self.assertRaisesRegex(Refused, "--allow-major"):
            uf.target("2.1.0", "3.0.0")
        self.assertEqual(uf.target("2.1.0", "3.0.0", allow_major=True), ("3.0.0", "major"))
        with self.assertRaisesRegex(Refused, "no release is known"):
            uf.target("2.1.0", None)
        with self.assertRaisesRegex(Refused, "not a version"):
            uf.target("2.1.0", None, to="latest")

    def test_automatic_levels(self):
        self.assertEqual(uf.target("2.1.0", "2.1.3", auto="patch"), ("2.1.3", "patch"))
        self.assertEqual(uf.target("2.1.0", "2.1.3", auto="minor"), ("2.1.3", "patch"))
        self.assertEqual(uf.target("2.1.0", "2.2.0", auto="minor"), ("2.2.0", "minor"))
        with self.assertRaisesRegex(Skipped, "patch releases only"):
            uf.target("2.1.0", "2.2.0", auto="patch")
        for auto in ("patch", "minor"):
            with self.assertRaisesRegex(Skipped, "never applied automatically"):
                uf.target("2.1.0", "3.0.0", allow_major=True, auto=auto)
        with self.assertRaisesRegex(Skipped, "off"):
            uf.target("2.1.0", "2.1.1", auto="off")


class Window(unittest.TestCase):
    def test_run_window_from_the_config(self):
        cfg = {"report": {"run_window": "11:10-11:30", "timezone": "UTC"}}
        at = lambda h, m: datetime(2026, 10, 21, h, m, tzinfo=UTC)  # noqa: E731
        self.assertIn("11:10-11:30", uf.in_window(cfg, at(11, 20), ""))
        self.assertIsNone(uf.in_window(cfg, at(11, 31), ""))
        self.assertIsNone(uf.in_window(cfg, at(11, 9), ""))
        night = {"report": {"run_window": "23:50-00:20", "timezone": "Europe/Berlin"}}
        self.assertTrue(uf.in_window(night, at(22, 5)))     # 00:05 in Berlin (CEST)
        self.assertIsNone(uf.in_window(night, at(22, 25)))

    def test_from_the_cron_line(self):
        cron = ("# skald (install.sh)\n# 15 7 * * * x run-daily\n"
                "*/2 * * * * skald live\n"
                "15 7 * * * skald cd /opt/skald && skald run-daily || "
                "skald notify-failure --job run-daily\n")
        self.assertEqual(uf.cron_time(cron), (7, 15))
        at = lambda h, m: datetime(2026, 10, 21, h, m, tzinfo=UTC)  # noqa: E731
        self.assertTrue(uf.in_window({}, at(7, 5), cron, UTC))
        self.assertTrue(uf.in_window({}, at(7, 25), cron, UTC))
        self.assertIsNone(uf.in_window({}, at(7, 26), cron, UTC))
        self.assertIsNone(uf.in_window({}, at(7, 4), cron, UTC))
        self.assertIsNone(uf.in_window({}, at(7, 15), "", UTC), "no cron line, no window")


class Files(unittest.TestCase):
    def test_sums(self):
        got = uf.sums_of(f"{'a' * 64}  skald-2.2.0.tar.gz\n{'B' * 64} *install.sh\nnot a line\n")
        self.assertEqual(got, {"skald-2.2.0.tar.gz": "a" * 64, "install.sh": "b" * 64})

    def test_hash_mismatch_and_missing_entry_are_refused(self):
        data = b"the release"
        self.assertEqual(uf.check_hash(data, "x.tar.gz", sums("x.tar.gz", data).decode()),
                         hashlib.sha256(data).hexdigest())
        with self.assertRaisesRegex(Refused, "SHA-256"):
            uf.check_hash(data, "x.tar.gz", sums("x.tar.gz", b"other").decode())
        with self.assertRaisesRegex(Refused, "does not list"):
            uf.check_hash(data, "y.tar.gz", sums("x.tar.gz", data).decode())

    def test_unpack_is_safe_and_checks_the_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "new"
            code = uf.unpack(tarball("2.2.0"), dest, "2.2.0")
            self.assertEqual((code / "VERSION").read_text().strip(), "2.2.0")
            self.assertTrue((code / "skald" / "cli.py").is_file())
            with self.assertRaisesRegex(Refused, "link"):
                uf.unpack(tarball("2.2.0", link="skald/evil"), Path(tmp) / "a", "2.2.0")
            with self.assertRaisesRegex(Refused, "says VERSION 2.2.0, not 2.3.0"):
                uf.unpack(tarball("2.2.0"), Path(tmp) / "b", "2.3.0")
            raw = io.BytesIO()
            with tarfile.open(fileobj=raw, mode="w:gz") as tar:
                info = tarfile.TarInfo("skald-2.2.0/../../escape.txt")
                info.size = 1
                tar.addfile(info, io.BytesIO(b"x"))
            with self.assertRaisesRegex(Refused, "unsafe path"):
                uf.unpack(raw.getvalue(), Path(tmp) / "c", "2.2.0")
            self.assertFalse((Path(tmp).parent / "escape.txt").exists())
            raw = io.BytesIO()
            with tarfile.open(fileobj=raw, mode="w:gz") as tar:
                info = tarfile.TarInfo("skald-2.2.0/VERSION")
                info.size = 6
                tar.addfile(info, io.BytesIO(b"2.2.0\n"))
            with self.assertRaisesRegex(Refused, "layout"):
                uf.unpack(raw.getvalue(), Path(tmp) / "d", "2.2.0")
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), ["new"])


class DryRun(Case):
    def test_against_a_local_release_server(self):
        release = Release("2.2.0")
        server = Server(release)
        try:
            ctx = Ctx(self.root, {}, to="v2.2.0", dry_run=True, source_url=server.url)
            code = self.upgrader(ctx).go()
        finally:
            server.close()
        self.assertEqual(code, 0, ctx.warned)
        said = "\n".join(ctx.said)
        self.assertIn("Skald 2.1.0 -> 2.2.0 (a minor release)", said)
        self.assertIn(f"SHA-256 {hashlib.sha256(release.data).hexdigest()} matches SHA256SUMS", said)
        self.assertIn("Nothing was changed.", said)
        self.assertIn("migrate --check (new code): ok", said)
        self.assertEqual(self.runner.calls, [("2.1.0", ("migrate", "--check"))])
        self.assertEqual(self.version(), "2.1.0")
        self.assertEqual(sorted(p.name for p in self.app.parent.iterdir()), ["skald"])
        self.assertEqual(self.restarts, [])
        self.assertFalse((ctx.db_path.parent / "backups").exists())

    def test_a_hash_mismatch_is_refused_and_nothing_changes(self):
        release = Release("2.2.0", bad_hash=True)
        server = Server(release)
        try:
            ctx = Ctx(self.root, {}, to="v2.2.0", source_url=server.url)
            code = self.upgrader(ctx).go()
        finally:
            server.close()
        self.assertEqual(code, 1)
        self.assertIn("upgrade REFUSED", ctx.warned[-1])
        self.assertIn("SHA-256", ctx.warned[-1])
        self.assertEqual(self.version(), "2.1.0")
        self.assertEqual(sorted(p.name for p in self.app.parent.iterdir()), ["skald"])
        self.assertEqual(self.runner.calls, [])
        self.assertEqual([e["outcome"] for e in self.log(ctx)], ["refused"])


class Upgrading(Case):
    def test_success_swaps_migrates_restarts_and_marks(self):
        www = self.root / "www"
        www.mkdir()
        ctx = Ctx(self.root, {"dashboard": {"out": str(www)}})
        release = Release("2.2.0")
        code = self.upgrader(ctx, release).go()
        self.assertEqual(code, 0, ctx.warned)
        self.assertEqual(self.version(), "2.2.0")
        self.assertEqual(self.version(self.app.with_name("skald.prev")), "2.1.0")
        self.assertEqual(release.calls[0], "https://api.github.com/repos/spcaeo/skald/releases/latest")
        build = json.loads((self.app / "build.json").read_text())
        self.assertEqual((build["name"], build["version"]), ("Skald", "2.2.0"))
        self.assertEqual(json.loads((www / "build.json").read_text())["version"], "2.2.0")
        self.assertEqual(self.runner.calls, [
            ("2.1.0", ("check", "--day", "today")), ("2.1.0", ("audit", "--live")),
            ("2.2.0", ("migrate", "--no-backup")), ("2.2.0", ("live",)),
            ("2.2.0", ("check", "--day", "today")), ("2.2.0", ("audit", "--live"))])
        self.assertEqual(self.restarts, [1])
        self.assertTrue(self.migrated(ctx))
        copies = list((ctx.db_path.parent / "backups").glob("pre-upgrade-2.1.0-to-2.2.0-*"))
        self.assertEqual(len(copies), 1)
        self.assertTrue((copies[0] / "history.sqlite").is_file())
        marker = json.loads((ctx.db_path.parent / "markers.log").read_text().splitlines()[-1])
        self.assertEqual((marker["kind"], marker["label"]), ("skald_deploy", "upgraded to 2.2.0"))
        self.assertEqual([(e["from"], e["to"], e["outcome"]) for e in self.log(ctx)],
                         [("2.1.0", "2.2.0", "ok")])
        self.assertEqual(self.mails, [], "only --auto mails")
        self.assertEqual(sorted(p.name for p in self.app.parent.iterdir()),
                         ["skald", "skald.prev"])

    def test_rollback_on_a_failing_health_check(self):
        ctx = Ctx(self.root, {})
        runner = Runner(self.app, ctx.db_path, fail={"audit"})
        code = self.upgrader(ctx, Release("2.2.0"), runner).go()
        self.assertEqual(code, 1)
        self.assertEqual(self.version(), "2.1.0", "the old code is back")
        self.assertEqual(sorted(p.name for p in self.app.parent.iterdir()), ["skald"])
        self.assertFalse(self.migrated(ctx), "the database is as it was before")
        self.assertEqual(self.restarts, [1, 1], "restarted on the new code, then on the old")
        warned = "\n".join(ctx.warned)
        self.assertIn("`audit --live` exited 1", warned)
        self.assertIn("rolled back: 2.1.0 is running again", warned)
        self.assertEqual([e["outcome"] for e in self.log(ctx)], ["rolled_back"])

    def test_a_check_that_failed_before_does_not_roll_back(self):
        ctx = Ctx(self.root, {})
        runner = Runner(self.app, ctx.db_path, fail={"check"}, always=True)
        self.assertEqual(self.upgrader(ctx, Release("2.2.0"), runner).go(), 0, ctx.warned)
        self.assertEqual(self.version(), "2.2.0")
        self.assertIn("as it did before the upgrade", "\n".join(ctx.warned))

    def test_a_failed_migration_rolls_back(self):
        ctx = Ctx(self.root, {})
        runner = Runner(self.app, ctx.db_path, fail={"migrate"})
        self.assertEqual(self.upgrader(ctx, Release("2.2.0"), runner).go(), 1)
        self.assertEqual(self.version(), "2.1.0")
        self.assertEqual(self.restarts, [1], "only the rollback's restart")
        self.assertIn("migrate exited 1", "\n".join(ctx.warned))

    def test_major_needs_allow_major(self):
        ctx = Ctx(self.root, {})
        self.assertEqual(self.upgrader(ctx, Release("3.0.0")).go(), 1)
        self.assertIn("--allow-major", ctx.warned[-1])
        self.assertEqual(self.version(), "2.1.0")
        ctx = Ctx(self.root, {}, allow_major=True)
        self.assertEqual(self.upgrader(ctx, Release("3.0.0")).go(), 0, ctx.warned)
        self.assertEqual(self.version(), "3.0.0")


class Refusals(Case):
    def test_the_daily_run_window(self):
        ctx = Ctx(self.root, {"report": {"run_window": "14:50-15:20", "timezone": "UTC"}})
        release = Release("2.2.0")
        self.assertEqual(self.upgrader(ctx, release).go(), 1)
        self.assertIn("the daily run's window", ctx.warned[-1])
        self.assertEqual(release.calls, [], "nothing asked, nothing downloaded")
        self.assertEqual(self.version(), "2.1.0")

    def test_docker_says_pull_the_new_tag(self):
        ctx = Ctx(self.root, {})
        with mock.patch("skald.upgrade.in_container", return_value=True):
            self.assertEqual(self.upgrader(ctx, Release("2.2.0")).go(), 1)
        self.assertIn("docker pull ghcr.io/spcaeo/skald:2", "\n".join(ctx.warned))

    def test_a_git_checkout(self):
        (self.app / ".git").mkdir()
        ctx = Ctx(self.root, {})
        self.assertEqual(self.upgrader(ctx, Release("2.2.0")).go(), 1)
        self.assertIn("git checkout", ctx.warned[-1])

    def test_already_on_the_latest(self):
        ctx = Ctx(self.root, {})
        self.assertEqual(self.upgrader(ctx, Release("2.1.0")).go(), 0)
        self.assertIn("already on 2.1.0", ctx.said[-1])


class Automatic(Case):
    MAIL = {"mail": {"host": "smtp.example.com", "from": "skald@example.com",
                     "to": ["owner@example.com"]}}

    def test_off_only_checks(self):
        ctx = Ctx(self.root, {}, auto=True, yes=False)
        release = Release("2.1.1")
        self.assertEqual(self.upgrader(ctx, release).go(), 0)
        self.assertEqual(release.calls, ["https://api.github.com/repos/spcaeo/skald/releases/latest"])
        self.assertIn("automatic upgrades are off", ctx.said[-1])
        self.assertEqual(self.version(), "2.1.0")

    def test_checks_off_ask_nothing(self):
        ctx = Ctx(self.root, {"updates": {"check": False, "auto": "minor"}}, auto=True)
        release = Release("2.1.1")
        self.assertEqual(self.upgrader(ctx, release).go(), 0)
        self.assertEqual(release.calls, [])

    def test_patch_level_skips_a_minor_release(self):
        ctx = Ctx(self.root, {"updates": {"auto": "patch"}}, auto=True, yes=False)
        release = Release("2.2.0")
        self.assertEqual(self.upgrader(ctx, release).go(), 0)
        self.assertIn("allows patch releases only", ctx.said[-1])
        self.assertEqual(len(release.calls), 1, "nothing downloaded")
        self.assertEqual(self.version(), "2.1.0")
        self.assertEqual(self.mails, [])

    def test_never_a_major(self):
        ctx = Ctx(self.root, {"updates": {"auto": "minor"}}, auto=True, allow_major=True)
        self.assertEqual(self.upgrader(ctx, Release("3.0.0")).go(), 0)
        self.assertIn("never applied automatically", ctx.said[-1])
        self.assertEqual(self.version(), "2.1.0")

    def test_minor_level_upgrades_and_mails(self):
        ctx = Ctx(self.root, {"updates": {"auto": "minor"}, **self.MAIL}, auto=True, yes=False)
        self.assertEqual(self.upgrader(ctx, Release("2.2.0")).go(), 0, ctx.warned)
        self.assertEqual(self.version(), "2.2.0")
        self.assertEqual(len(self.mails), 1)
        self.assertIn("upgraded to 2.2.0", self.mails[0]["Subject"])
        self.assertEqual(self.mails[0]["To"], "owner@example.com")
        self.assertIn("SHA256SUMS", self.mails[0].get_content())
        self.assertTrue(self.log(ctx)[-1]["auto"])

    def test_a_rollback_is_mailed(self):
        ctx = Ctx(self.root, {"updates": {"auto": "patch"}, **self.MAIL}, auto=True)
        runner = Runner(self.app, ctx.db_path, fail={"live"})
        self.assertEqual(self.upgrader(ctx, Release("2.1.1"), runner).go(), 1)
        self.assertEqual(self.version(), "2.1.0")
        self.assertEqual(len(self.mails), 1)
        self.assertIn("upgrade to 2.1.1 rolled back", self.mails[0]["Subject"])


class Wiring(unittest.TestCase):
    ROOT = Path(__file__).resolve().parent.parent

    def test_install_sh_installs_the_timer_and_keeps_upgrade_as_root(self):
        text = (self.ROOT / "install.sh").read_text()
        self.assertIn("skald-upgrade.service skald-upgrade.timer", text)
        self.assertIn("  install_upgrade_timer\n", text[text.index("main() {"):])
        self.assertIn('[ "\\${1:-}" = upgrade ]', text)
        timer = (self.ROOT / "systemd" / "skald-upgrade.timer").read_text()
        self.assertRegex(timer, r"(?m)^OnCalendar=\*-\*-\* \d\d:\d\d:00$")
        service = (self.ROOT / "systemd" / "skald-upgrade.service").read_text()
        self.assertIn("skald --config /etc/skald/config.yml upgrade --auto", service)

    def test_the_commands_are_registered(self):
        from skald import cli
        parser = cli.parser()
        for argv in (["upgrade", "--dry-run", "--to", "v2.2.0"], ["updates", "--check-now"],
                     ["migrate", "--check"]):
            self.assertTrue(callable(parser.parse_args(argv).run), argv)


if __name__ == "__main__":
    unittest.main()
