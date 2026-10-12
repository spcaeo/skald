"""`skald upgrade`: a new release in place of this one, with a way back.

For an install made by install.sh (the code in /opt/skald, a plain
folder). Run as root (`sudo skald upgrade`); the steps:

  1. refuse inside the daily run's window, in a container (pull the new
     image instead) and in a git checkout (pull instead);
  2. which release: the latest (GitHub) or --to vX.Y.Z; a downgrade is
     refused, and a major jump unless --allow-major (--auto: updates.auto);
  3. download the tarball and SHA256SUMS; the SHA-256 must match;
  4. unpack it beside the code, refusing unsafe paths and other layouts;
  5. --dry-run stops here and says what would happen (the new code's
     `migrate --check` included); nothing is changed;
  6. the health checks with the old code (to judge only what the new code
     breaks), then a restore-tested copy of every database;
  7. the current code becomes /opt/skald.prev, the new code
     /opt/skald; the new code's `migrate` upgrades the databases;
  8. the helpers restart (systemctl, when there); health: the helper
     answers, `live`, `check --day today` and `audit --live` exit 0;
  9. any failure in 7-8: the old code goes back, every database is put back
     from the copy, the helpers restart, and it says what happened.

Each outcome is one line in upgrades.log beside the history; a success is
also a deploy marker on the charts. `--auto` (the daily timer) mails the
result to the daily mail's recipients when it upgraded or rolled back.
The cron's `live` waits meanwhile: this holds its lock (live.lock).
"""
from __future__ import annotations

import fcntl
import json
import os
import pwd
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import format_datetime, make_msgid
from pathlib import Path

# Imported now, not inside a function: once the new code is in place the
# package folder on sys.path is the new release, and this run must keep
# using the old one's modules to the end (a rollback included).
from . import backup, brand, failmail, markers, migrations, updates
from . import upgrade_files as uf
from .files import own_like_folder, write_atomic
from .upgrade_files import Refused, Skipped

UNITS = ("skald-refresh.service", "skald-beacon.service")
BEACON_UNIT = UNITS[1]
LOG = "upgrades.log"
LOCK = "live.lock"
HELPER = "http://127.0.0.1:{port}/traffic-auth/login"
HEALTH = (("live", ("live",)), ("check", ("check", "--day", "today")),
          ("audit", ("audit", "--live")))
DOCKER = ("This is the Docker image: an image is never changed in place. Pull the new tag "
          "and start the container again, e.g.\n"
          "  docker pull ghcr.io/spcaeo/skald:2 && docker compose up -d\n"
          "The `:2` tag follows every 2.x release (docs/UPGRADING.md, \"Docker\").")


def in_container() -> bool:
    return Path("/.dockerenv").exists() or Path("/run/.containerenv").exists()


def systemd_up() -> bool:
    return Path("/run/systemd/system").is_dir() and shutil.which("systemctl") is not None


def _owner_prefix(folder: Path) -> list[str]:
    """Run as the history folder's owner (the service user) when root."""
    if not hasattr(os, "geteuid") or os.geteuid() != 0:
        return []
    try:
        uid = Path(folder).stat().st_uid
        name = pwd.getpwuid(uid).pw_name
    except (OSError, KeyError):
        return []
    tool = shutil.which("runuser")
    return [tool, "-u", name, "--"] if uid != 0 and tool else []


def run_command(argv: list[str], cwd: Path, folder: Path) -> tuple[int, str]:
    """A skald command as the service user: (exit code, its last lines)."""
    try:
        done = subprocess.run(_owner_prefix(folder) + argv, cwd=str(cwd), capture_output=True,
                              text=True, timeout=1800)
    except (OSError, subprocess.SubprocessError) as why:
        return 1, f"{type(why).__name__}: {why}"
    lines = (done.stdout + done.stderr).strip().splitlines()
    return done.returncode, "\n".join(lines[-12:])


def restart_units(units=UNITS) -> list[str]:
    """Restart each helper that is enabled or running; [] when all restarted."""
    if not systemd_up():
        return []
    problems = []
    for unit in units:
        on = any(subprocess.run(["systemctl", verb, "--quiet", unit]).returncode == 0
                 for verb in ("is-active", "is-enabled"))
        if not on and unit == BEACON_UNIT and installed(unit):
            # Since 2.2.2 the beacon helper runs on every install: it also receives
            # the signed tool hooks (hooks only until beacon.origins is set).
            if subprocess.run(["systemctl", "enable", "--now", "--quiet", unit]).returncode != 0:
                problems.append(f"{unit} did not start")
            continue
        if on and subprocess.run(["systemctl", "restart", unit]).returncode != 0:
            problems.append(f"{unit} did not restart")
    return problems


def installed(unit: str) -> bool:
    """True when systemd knows the unit file (install.sh put it there)."""
    got = subprocess.run(["systemctl", "list-unit-files", "--no-legend", unit],
                         capture_output=True, text=True)
    return got.returncode == 0 and unit in got.stdout


def helper_answers(config: dict) -> str | None:
    """None when the refresh helper answers (or is not installed here)."""
    if not systemd_up():
        return None
    unit = UNITS[0]
    if subprocess.run(["systemctl", "is-enabled", "--quiet", unit]).returncode != 0:
        return None
    for _ in range(10):
        if subprocess.run(["systemctl", "is-active", "--quiet", unit]).returncode == 0:
            break
        time.sleep(1)
    else:
        return f"{unit} is not running"
    refresh = (config or {}).get("refresh") or {}
    if refresh.get("socket"):
        return None                     # a Unix socket: running is the check
    port = int(refresh.get("port") or 8765)
    for _ in range(10):
        try:
            with urllib.request.urlopen(HELPER.format(port=port), timeout=5) as r:
                if r.status < 500:
                    return None
        except urllib.error.HTTPError as e:
            if e.code < 500:
                return None
        except OSError:
            pass
        time.sleep(1)
    return f"the helper does not answer on 127.0.0.1:{port}"


class Upgrader:
    """One upgrade. Every outside effect can be replaced (tests): `fetch`
    (the network), `run` (a skald command), `restart`, `helper`, `send`."""

    def __init__(self, ctx, *, app: Path | None = None, fetch=None, run=None, restart=None,
                 helper=None, send=None, ask=None, cron_text: str | None = None,
                 local_tz=None, now: datetime | None = None) -> None:
        self.ctx, self.args = ctx, ctx.args
        self.app = Path(app or brand.ROOT)
        self.prev = self.app.with_name(self.app.name + ".prev")
        self.staging = self.app.with_name(self.app.name + ".new")
        self.folder = Path(ctx.db_path).parent
        self.fetch, self.restart = fetch, restart or restart_units
        self.helper = helper or helper_answers
        self.run_ti = run or (lambda argv, cwd=None: run_command(argv, cwd or self.app,
                                                                 self.folder))
        self.send = send or failmail.send
        self.ask = ask or input
        self.cron_text, self.local_tz = cron_text, local_tz
        self.now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        self.current = updates.plain(brand.load(self.app).get("version"))
        self.target = None
        self.lines: list[str] = []
        self.lock = None

    # -------------------------------------------------------------- output

    def say(self, line: str) -> None:
        self.lines.append(line)
        self.ctx.out(line)

    def warn(self, line: str) -> None:
        self.lines.append(line)
        self.ctx.err(line)

    def log(self, outcome: str, detail: str = "") -> None:
        entry = {"at": self.now.isoformat(timespec="seconds"), "from": self.current,
                 "to": self.target, "outcome": outcome, "auto": bool(self.args.auto),
                 "detail": " ".join(detail.split())[:400]}
        try:
            path = self.folder / LOG
            with open(path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry) + "\n")
            own_like_folder(path)
        except OSError as why:
            self.warn(f"could not write {LOG}: {why}")

    def ti(self, *words: str) -> list[str]:
        return [sys.executable, str(self.app / uf.ENTRY), "--config",
                str(Path(self.ctx.config_path).resolve()), *words]

    # -------------------------------------------------------------- steps

    def preflight(self) -> None:
        if in_container():
            raise Refused(DOCKER)
        if (self.app / ".git").exists():
            raise Refused(f"{self.app} is a git checkout: update it with git, not upgrade")
        if not (self.app / uf.PACKAGE / "cli.py").is_file():
            raise Refused(f"{self.app} is not an install made by install.sh")
        why = uf.in_window(self.ctx.config, self.now, self.cron_text, self.local_tz)
        if why:
            raise Refused(f"now is {why}: try again after it")
        if not self.args.dry_run and not os.access(self.app.parent, os.W_OK):
            raise Refused(f"cannot write {self.app.parent}: run it as root "
                          f"(sudo skald upgrade)")

    def choose(self) -> tuple[str, str, dict | None]:
        cfg = updates.settings(self.ctx.config)
        release = None
        if not self.args.to:
            state = updates.check(self.ctx.config, self.now, folder=self.folder,
                                  fetch=self.fetch, force=not self.args.auto,
                                  current=self.current, log=self.warn)
            release = state.get("latest") if state.get("ok") else None
            if not cfg["check"] and not self.args.auto:
                self.say("updates.check is off: asked GitHub once, because you ran upgrade")
        version, how = uf.target(self.current, (release or {}).get("version"), self.args.to,
                                 self.args.allow_major, cfg["auto"] if self.args.auto else None)
        self.target = version
        return version, how, release

    def health(self, baseline: dict | None = None) -> tuple[dict, list[str]]:
        """{check: ok?} and the failures that count (a check that already
        failed with the old code is reported, not counted)."""
        got, failed = {}, []
        helper = self.helper(self.ctx.config)
        got["helper"] = helper is None
        if helper and (baseline is None or baseline.get("helper")):
            failed.append(helper)
        for name, words in HEALTH:
            if baseline is None and name == "live":
                continue                # the cron's live keeps the snapshot fresh
            code, output = self.run_ti(self.ti(*words))
            got[name] = code == 0
            if code and (baseline is None or baseline.get(name, True)):
                failed.append(f"`{' '.join(words)}` exited {code}: "
                              + " / ".join(output.splitlines()[-3:]))
            elif code and baseline is not None:
                self.warn(f"`{' '.join(words)}` exited {code}, as it did before the upgrade")
        return got, failed

    def take_lock(self) -> None:
        try:
            self.lock = open(self.folder / LOCK, "a")
            own_like_folder(self.folder / LOCK)
        except OSError:
            return
        for _ in range(120):
            try:
                fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return
            except OSError:
                time.sleep(1)
        raise Refused("the live run did not finish within 2 minutes")

    def copy_build(self) -> None:
        out = ((self.ctx.config or {}).get("dashboard") or {}).get("out")
        if not out:
            return
        path = Path(str(out)).expanduser()
        if not path.is_absolute():
            path = Path(self.ctx.config_path).resolve().parent / path
        try:
            if path.is_dir() and (self.app / "build.json").exists():
                write_atomic(path / "build.json", (self.app / "build.json").read_text())
                os.chmod(path / "build.json", 0o644)
                own_like_folder(path / "build.json")
        except OSError as why:
            self.warn(f"build.json not copied to {path}: {why}")

    # -------------------------------------------------------------- the run

    def dry_run(self, data: bytes, version: str) -> int:
        scratch = self.app.with_name(f".{self.app.name}.dry-run")
        shutil.rmtree(scratch, ignore_errors=True)
        try:
            code = uf.unpack(data, scratch / "code", version)
            self.say(f"unpacked and checked: {code}")
            argv = [sys.executable, str(code / uf.ENTRY), "--config",
                    str(Path(self.ctx.config_path).resolve()), "migrate", "--check"]
            rc, output = self.run_ti(argv, code)
            for line in output.splitlines():
                self.say(f"  migrate --check (new code): {line}")
            if rc:
                self.warn("the new code's migrate --check did not pass: the upgrade would stop")
        finally:
            shutil.rmtree(scratch, ignore_errors=True)
        self.say(f"dry run: would back up every database into {self.copies_dir()}, move "
                 f"{self.app} to {self.prev}, put {version} in its place, migrate, restart "
                 f"the helpers and check them. Nothing was changed.")
        return 0

    def copies_dir(self) -> Path:
        stamp = self.now.strftime("%Y%m%dT%H%M%SZ")
        return backup.backup_dir(self.ctx) / f"pre-upgrade-{self.current}-to-{self.target}-{stamp}"

    def go(self) -> int:
        a = self.args
        cfg = updates.settings(self.ctx.config)
        if a.auto and not a.to and (not cfg["check"] or cfg["auto"] == "off"):
            # The daily timer with automatic upgrades off: only the daily question.
            if cfg["check"]:
                updates.check(self.ctx.config, self.now, folder=self.folder, fetch=self.fetch,
                              current=self.current, log=self.warn)
            self.say("automatic upgrades are off (updates.auto); "
                     + ("the daily check ran" if cfg["check"] else "update checks are off"))
            return 0
        try:
            self.preflight()
            version, how, release = self.choose()
            self.say(f"{brand.load(self.app).get('name') or 'Skald'} {self.current} -> {version} "
                     f"(a {how} release)" + (f": {release['url']}" if release else ""))
            if release and release.get("security"):
                self.say("this is a security release")
            repo = updates.settings(self.ctx.config)["repo"]
            data, name, digest = uf.fetch_release(version, repo, self.fetch, a.source_url,
                                                  updates.agent(self.current))
            self.say(f"downloaded {name}: SHA-256 {digest} matches SHA256SUMS")
            if a.dry_run:
                return self.dry_run(data, version)
            if not (a.yes or a.auto):
                if not sys.stdin.isatty():
                    raise Refused("add --yes to upgrade without a question")
                if self.ask(f"Upgrade to {version} now? [y/N] ").strip().lower() not in ("y", "yes"):
                    raise Refused("not upgraded: you said no")
            self.take_lock()
            shutil.rmtree(self.staging, ignore_errors=True)
            uf.unpack(data, self.staging, version)
            write_atomic(self.staging / "build.json", uf.build_json(self.staging, self.now))
        except Skipped as why:
            self.say(str(why))
            return 0
        except Refused as why:
            return self.refused(str(why))
        try:
            return self.swap(version)
        finally:
            if self.lock is not None:
                self.lock.close()

    def refused(self, why: str) -> int:
        self.warn(f"upgrade REFUSED: {why}")
        if self.target:
            self.log("refused", why)
        shutil.rmtree(self.staging, ignore_errors=True)
        return 1

    def swap(self, version: str) -> int:
        baseline, _ = self.health()
        copies = self.copies_dir()
        taken, problems = migrations.snapshot(self.ctx.config, self.ctx.db_path, copies)
        if problems:
            shutil.rmtree(self.staging, ignore_errors=True)
            return self.refused("the copy of the databases did not pass the restore test: "
                                + "; ".join(problems))
        self.say(f"every database copied and restore-tested: {copies}")
        shutil.rmtree(self.prev, ignore_errors=True)
        try:
            os.rename(self.app, self.prev)
        except OSError as why:
            shutil.rmtree(self.staging, ignore_errors=True)
            return self.refused(f"could not move {self.app} aside: {why}")
        try:
            os.rename(self.staging, self.app)
        except OSError as why:
            os.rename(self.prev, self.app)
            shutil.rmtree(self.staging, ignore_errors=True)
            return self.refused(f"could not put the new code in place: {why}")
        self.say(f"code: {self.prev} is the old release, {self.app} the new one")
        try:
            failed = self.migrate_and_check(baseline)
        except Exception as why:        # noqa: BLE001 - anything at all: roll back
            failed = [f"{type(why).__name__}: {why}"]
        if failed:
            return self.rollback(failed, taken, copies)
        self.copy_build()
        try:
            markers.append(self.folder, "skald_deploy",
                           f"upgraded to {version}", f"from {self.current}"
                           + (" (automatic)" if self.args.auto else ""), self.now)
        except (OSError, ValueError) as why:
            self.warn(f"no deploy marker: {why}")
        self.log("ok", f"copies in {copies}")
        self.say(f"upgraded to {version}; the old code stays in {self.prev}")
        self.mail(f"upgraded to {version}")
        return 0

    def migrate_and_check(self, baseline: dict) -> list[str]:
        code, output = self.run_ti(self.ti("migrate", "--no-backup"))
        for line in output.splitlines():
            self.say(f"  migrate: {line}")
        if code:
            return [f"migrate exited {code}"]
        failed = self.restart()
        if failed:
            return failed
        return self.health(baseline)[1]

    def rollback(self, failed: list[str], taken: list[dict], copies: Path) -> int:
        for f in failed:
            self.warn(f"  - {f}")
        self.warn(f"upgrade to {self.target} FAILED: rolling back")
        broken = self.app.with_name(f"{self.app.name}.failed")
        shutil.rmtree(broken, ignore_errors=True)
        os.rename(self.app, broken)
        os.rename(self.prev, self.app)
        shutil.rmtree(broken, ignore_errors=True)
        problems = migrations.restore(taken)
        problems += self.restart()
        self.copy_build()
        for p in problems:
            self.warn(f"  - {p}")
        detail = "; ".join(failed)[:300]
        if problems:
            self.warn(f"ROLLBACK INCOMPLETE: the databases' copies are in {copies}; "
                      "docs/UPGRADING.md, \"Rolling back by hand\"")
            self.log("rollback_incomplete", detail + " | " + "; ".join(problems))
        else:
            self.warn(f"rolled back: {self.current} is running again and every database "
                      f"is as it was (copies kept in {copies})")
            self.log("rolled_back", detail)
        self.mail(f"upgrade to {self.target} rolled back")
        return 1

    def mail(self, what: str) -> None:
        if not self.args.auto:
            return
        try:
            cfg = failmail.mail_settings(self.ctx.config)
        except Exception as why:        # noqa: BLE001 - a mail is a nicety
            self.warn(f"no mail: {why}")
            return
        msg = EmailMessage()
        site = (self.ctx.config.get("site") or {}).get("name") or ""
        msg["Subject"] = f"{cfg['prefix']} {what}" + (f" ({site})" if site else "")
        msg["From"], msg["To"] = cfg["from"], ", ".join(cfg["to"])
        msg["Date"] = format_datetime(self.now)
        msg["Message-ID"] = make_msgid(domain=cfg["from"].rsplit("@", 1)[-1].strip("> ") or None)
        msg["Auto-Submitted"] = "auto-generated"
        msg.set_content("The automatic upgrade (updates.auto) ran:\n\n"
                        + "\n".join(self.lines) + "\n\nupgrades.log beside the history "
                        "has one line per upgrade. docs/UPGRADING.md explains each step.\n")
        try:
            self.send(msg, cfg)
        except Exception as why:        # noqa: BLE001
            self.warn(f"the result mail could not be sent: {type(why).__name__}")


def cmd_upgrade(ctx) -> int:
    return Upgrader(ctx).go()


def add_command(sub) -> None:
    p = sub.add_parser("upgrade", help="install a newer release (install.sh layout): "
                       "check, back up, swap, migrate, health-check, roll back on failure")
    p.add_argument("--to", metavar="vX.Y.Z", help="this release instead of the latest")
    p.add_argument("--dry-run", dest="dry_run", action="store_true",
                   help="download and check it, say what would happen, change nothing")
    p.add_argument("--yes", action="store_true", help="do not ask before upgrading")
    p.add_argument("--allow-major", dest="allow_major", action="store_true",
                   help="allow a new major version (read its notes first)")
    p.add_argument("--auto", action="store_true",
                   help="the daily timer: only what updates.auto allows; mails the result")
    p.add_argument("--source-url", dest="source_url", metavar="URL",
                   help="a folder holding skald-X.Y.Z.tar.gz and SHA256SUMS "
                        "(default: the GitHub release)")
    p.set_defaults(run=cmd_upgrade)
