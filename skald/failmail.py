"""One short mail when the morning run fails, and no other alert.

The owner's rule (2026-10-11): a failed daily run sends one plain mail; alert
mails stay off. Cron calls this only when run-daily exits non-zero:

    skald --config CONFIG run-daily >>LOG 2>&1 ||
        skald --config CONFIG notify-failure --job run-daily --exit $? --log LOG >>LOG 2>&1

What is a failure: a crash, a step that errors, a mail refused for its setup
(an SMTP setting, a password variable not set), a day with no log line at
all, a run that stopped before it could say how it ended. What is not: a day
held back because its figures do not reconcile or the audit's recount
disagrees, or a mail held back because a day in it is withheld, partial or
missing. That is by design. run-daily writes which it was into runs.json
(`last_outcome`: ok, withheld or failed) as its last act; a fresh "withheld"
with the same exit code means no mail. Anything else - no fresh record
included - is mailed.

One mail per failed run: when it mails, failmail-state.json beside runs.json
notes the time, and nothing more goes for that job within COOLDOWN_HOURS. A
mail that cannot be sent is printed to the log and the command exits 1;
nothing retries it, so it cannot loop.

It must work when the rest of the package does not: standard library only,
no import from the package at load time. skald loads this file by its path
for notify-failure, so a broken import elsewhere still sends the mail.
config.py (the config reader) and brand.py (the subject prefix and sender
name) are loaded the same way; both use only the standard library. The mail
settings are read again here, the same keys and rules as mailer.settings.

Recipients: the same as the daily mail's. The Mail page's settings (rows in
accounts.sqlite: recipients that have confirmed, the sender, the SMTP
server) are laid over config.yml by settings_store.apply, as run-daily does.
That needs the package, so it is tried inside a guard (`merged`): when the
package does not import or the accounts file cannot be read, config.yml
alone is used and the log says so. When none of the page's recipients has
confirmed yet, config.yml's own list is used: a failure is never mailed to
nobody.

No secret goes in the mail: the SMTP login is never written, any value of
the login variables found in the log is replaced, addresses are masked.
"""
from __future__ import annotations

import argparse
import importlib.util
import ipaddress
import json
import os
import re
import smtplib
import ssl
import sys
from collections import deque
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import format_datetime, formataddr, make_msgid, parseaddr
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = "runs.json"                  # runs.py's file
STATE = "failmail-state.json"
COOLDOWN_HOURS = 12                 # at most one mail per job in this time
FRESH_MINUTES = 15                  # run-daily's record is seconds old when cron calls us
TAIL_LINES = 20
NAMES = {"run-daily": "Daily run"}


class Refused(Exception):
    """The failure mail cannot be sent with this config or environment."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _sibling(name: str):
    """A standard-library-only module of this package, loaded by its path."""
    key = f"_failmail_{name}"
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[key] = module           # a dataclass in it looks itself up here
    try:
        spec.loader.exec_module(module)
    except BaseException:
        del sys.modules[key]
        raise
    return module


def _brand() -> dict:
    try:
        return _sibling("brand").load()
    except Exception:                   # noqa: BLE001 - the mail matters more
        return {"name": "skald"}


# ------------------------------------------------------------- settings

def state_dir(config: dict, config_path: Path) -> Path:
    """Where runs.json lives: beside the history file (cli.Context.live_dir)."""
    raw = (config.get("history") or {}).get("db") or "history.sqlite"
    db = Path(str(raw)).expanduser()
    if not db.is_absolute():
        db = Path(config_path).resolve().parent / db
    return db.parent


def _stored(config: dict, name: str) -> str | None:
    """A secret from secrets.json beside the history (settings_store.py), read
    here without the package: only when the file is the owner's alone (0600)."""
    import stat
    raw = ((config.get("hooks") or {}).get("secrets")
           or ((config.get("history") or {}).get("db") and
               os.path.join(os.path.dirname(str(config["history"]["db"])), "secrets.json")))
    if not raw or not os.path.isabs(str(raw)):
        return None
    try:
        if stat.S_IMODE(os.stat(str(raw)).st_mode) & 0o077:
            return None
        with open(str(raw), encoding="utf-8") as handle:
            got = json.load(handle)
    except (OSError, ValueError):
        return None
    value = got.get(name) if isinstance(got, dict) else None
    return str(value) if value else None


def _package(name: str):
    """A module of this package, imported only when asked (never at load):
    by its package name when this file was imported as part of it, else
    from the folder this file is in (skald loads it by its path)."""
    if __package__:
        return importlib.import_module(f"{__package__}.{name}")
    if not (HERE / "__init__.py").is_file():
        raise ImportError(f"{HERE} is not a package")
    if str(HERE.parent) not in sys.path:
        sys.path.insert(0, str(HERE.parent))
    return importlib.import_module(f"{HERE.name}.{name}")


def merged(config: dict, config_path: Path, out=print) -> dict:
    """config.yml with the Mail page's settings over it, exactly as the daily
    mail reads them (settings_store.apply for the install's own site), or
    config.yml alone when that cannot be done."""
    try:
        store = _package("settings_store")
        site = _package("config").site_name(config)
        got = store.apply(config, site, state_dir(config, config_path))
    except Exception as why:            # noqa: BLE001 - the mail matters more
        out(f"notify-failure: the Mail page's settings could not be read "
            f"({type(why).__name__}); using config.yml's mail settings")
        return config
    mail = got.get("mail") or {}
    if got is not config and not mail.get("to") and (config.get("mail") or {}).get("to"):
        out("notify-failure: no recipient set on the Mail page has confirmed yet; "
            "using config.yml's recipients")
        got = {**got, "mail": {**mail, "to": config["mail"]["to"]}}
    return got


def mail_settings(config: dict) -> dict:
    """The config's mail section, checked as mailer.settings checks it."""
    mail = config.get("mail") or {}
    host, sender, to = mail.get("host"), mail.get("from"), mail.get("to") or []
    if isinstance(to, str):
        to = [to]
    if not host or not sender or not to:
        raise Refused("mail.host, mail.from and mail.to must all be set")
    port = int(mail.get("port") or 587)
    security = str(mail.get("security") or ("ssl" if port == 465 else "starttls")).lower()
    if security not in ("starttls", "ssl", "none"):
        raise Refused(f"mail.security must be starttls, ssl or none, not {security!r}")

    def secret(key: str) -> str | None:
        name = mail.get(key)
        if not name:
            return None
        value = os.environ.get(str(name)) or _stored(config, str(name))
        if not value:
            raise Refused(f"environment variable {name} (mail.{key}) is not set")
        return value

    # Settings > Mail & reports: a typed user, and the password in secrets.json.
    user = str(mail.get("user") or "").strip() or secret("user_env")
    if mail.get("password_env"):
        password = secret("password_env")
    elif mail.get("user"):
        name = "SKALD_SMTP_PASSWORD"
        password = os.environ.get(name) or _stored(config, name)
        if not password:
            raise Refused(f"the SMTP password is not set ({name} or Settings > Mail & reports)")
    else:
        password = None
    if (user or password) and security == "none":
        raise Refused("refusing to send SMTP credentials without TLS")
    brand = _brand()
    _, address = parseaddr(str(sender))
    name = str(mail.get("from_name") or brand.get("name") or "").strip()
    return {
        "host": str(host), "port": port, "security": security,
        "from": formataddr((name, address)) if address and name else str(sender),
        "to": [str(t) for t in to], "user": user, "password": password,
        "prefix": str(mail.get("subject_prefix") or f"[{brand.get('name')}]").strip(),
    }


# --------------------------------------------------------- what happened

def _when(raw) -> datetime | None:
    try:
        got = datetime.fromisoformat(str(raw))
    except (TypeError, ValueError):
        return None
    return got if got.tzinfo else got.replace(tzinfo=timezone.utc)


def _records(directory: Path, job: str) -> list[dict | None]:
    """The job's runs.json entry for the site, and for every other site of a
    multi-site install (sites/<name>/runs.json); None where there is none."""
    dirs = [directory]
    others = directory / "sites"
    if others.is_dir():
        dirs += sorted(d for d in others.iterdir() if (d / RUNS).is_file())
    out = []
    for d in dirs:
        try:
            got = json.loads((d / RUNS).read_text())
        except (OSError, ValueError):
            got = {}
        entry = got.get(job) if isinstance(got, dict) else None
        out.append(entry if isinstance(entry, dict) else None)
    return out


def verdict(directory: Path, job: str, code: int | None, now: datetime) -> str | None:
    """None when this run stopped by design (a withheld day: no mail);
    otherwise what went wrong, in words, for the mail."""
    entries = _records(directory, job)
    oldest = now - timedelta(minutes=FRESH_MINUTES)
    exits, withheld = [], False
    for entry in entries:
        at = entry and _when(entry.get("last_ok") if entry.get("last_exit") == 0
                             else entry.get("last_fail"))
        if not at or at < oldest:
            return (f"{job} left no record of this run: it stopped before its end "
                    f"(a crash, or the code did not load)")
        outcome = entry.get("last_outcome")
        if outcome not in ("ok", "withheld"):
            return f"{job} ended with exit {entry.get('last_exit')}: a step failed"
        withheld = withheld or outcome == "withheld"
        exits.append(entry.get("last_exit"))
    if code is not None and max(exits) != code:
        return f"{job} exited {code}, but its record says {max(exits)}"
    if withheld:
        return None
    return f"{job} exited {code}" if code is not None else f"{job} reported no failure"


# ----------------------------------------------------------------- mail

_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_IPV6 = re.compile(r"[0-9A-Fa-f]{0,4}(?::[0-9A-Fa-f]{0,4}){2,7}")


def _v6(match: re.Match) -> str:
    try:
        ipaddress.IPv6Address(match.group(0))
    except ValueError:
        return match.group(0)
    return "[address]"


def clean(text: str, hidden: list[str]) -> str:
    """A log line fit for the mail: secrets replaced, addresses masked."""
    for value in hidden:
        if value:
            text = text.replace(value, "[hidden]")
    return _IPV6.sub(_v6, _IPV4.sub("[address]", text))[:300]


def tail(path: str | None, hidden: list[str], count: int = TAIL_LINES) -> list[str]:
    if not path:
        return ["(no log named)"]
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            lines = list(deque(handle, count))
    except OSError as why:
        return [f"(could not read the log: {why.strerror})"]
    return [clean(line.rstrip("\n"), hidden) for line in lines] or ["(the log is empty)"]


def build(cfg: dict, config: dict, job: str, code: int | None, why: str,
          log: str | None, directory: Path, now: datetime) -> EmailMessage:
    name = NAMES.get(job, f"Job {job}")
    site = (config.get("site") or {}).get("name") or ""
    hidden = [cfg["user"], cfg["password"]]
    text = "\n".join([
        f"{name} failed: {job}" + (f" for {site}" if site else "")
        + f", {now:%Y-%m-%d %H:%M} UTC" + (f", exit {code}" if code is not None else "") + ".",
        f"Why: {why}.",
        "Today's dashboard and mail may be missing or out of date.",
        "",
        f"Last {TAIL_LINES} lines of {log or 'the log'}:",
        *("  " + line for line in tail(log, hidden)),
        "",
        "What to check:",
        f"1. The whole log of the run: {log or 'the log'}.",
        f"2. {directory / RUNS}: last_exit and last_outcome of {job}.",
        "3. Fix the cause, then run it again by hand (operations guide,",
        "   DEPLOY.md).",
        "",
        "One mail per failed run. A day withheld because its figures do not",
        "reconcile is by design and sends no mail.",
    ])
    msg = EmailMessage()
    msg["Subject"] = f"{cfg['prefix']} {name} failed {now:%Y-%m-%d}".strip()
    msg["From"] = cfg["from"]
    msg["To"] = ", ".join(cfg["to"])
    msg["Date"] = format_datetime(now)
    domain = cfg["from"].rsplit("@", 1)[-1].strip("> ") or None
    msg["Message-ID"] = make_msgid(domain=domain)
    msg["Auto-Submitted"] = "auto-generated"
    msg.set_content(text + "\n")
    return msg


def send(msg: EmailMessage, cfg: dict) -> None:
    """Hand the message to the configured SMTP server (as mailer.send)."""
    context = ssl.create_default_context()
    if cfg["security"] == "ssl":
        server = smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=30, context=context)
    else:
        server = smtplib.SMTP(cfg["host"], cfg["port"], timeout=30)
    try:
        if cfg["security"] == "starttls":
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
        if cfg["user"]:
            server.login(cfg["user"], cfg["password"] or "")
        server.send_message(msg)
    finally:
        try:
            server.quit()
        except smtplib.SMTPException:
            pass


def _state(directory: Path) -> dict:
    try:
        got = json.loads((directory / STATE).read_text())
    except (OSError, ValueError):
        return {}
    return got if isinstance(got, dict) else {}


def _save(directory: Path, state: dict, out) -> None:
    try:
        path = directory / STATE
        temp = path.with_name(path.name + ".tmp")
        temp.write_text(json.dumps(state, indent=1, sort_keys=True) + "\n")
        os.replace(temp, path)
    except OSError as why:
        out(f"notify-failure: could not write {STATE}: {why.strerror}")


# --------------------------------------------------------------- command

def notify(args, out=print) -> int:
    """0 mailed, or nothing to mail; 1 the mail could not be sent; 2 no config."""
    job, code = args.job, args.exit
    if code == 0:
        out(f"notify-failure: {job} exited 0; nothing to mail")
        return 0
    config_path = Path(args.config)
    try:
        config = _sibling("config").load_config(config_path) if config_path.exists() else {}
    except Exception as why:            # noqa: BLE001 - say it, do not crash
        out(f"notify-failure: cannot read {config_path}: {type(why).__name__}")
        return 2
    if not config:
        out(f"notify-failure: no config at {config_path}; no mail sent")
        return 2
    directory = state_dir(config, config_path)
    now = _now()
    why = verdict(directory, job, code, now)
    if why is None:
        out(f"notify-failure: {job} stopped by design (a withheld day); no mail")
        return 0
    state = _state(directory)
    last = _when((state.get(job) or {}).get("mailed_at"))
    if (last and now - last < timedelta(hours=COOLDOWN_HOURS)
            and not args.force and not args.dry_run):
        out(f"notify-failure: already mailed for {job} at {last:%Y-%m-%d %H:%M} UTC; "
            f"not again within {COOLDOWN_HOURS} hours")
        return 0
    try:
        cfg = mail_settings(merged(config, config_path, out))
        msg = build(cfg, config, job, code, why, args.log, directory, now)
    except Refused as refused:
        out(f"notify-failure: NOT SENT: {refused}")
        return 1
    if args.dry_run:
        out("\n".join(f"{k}: {v}" for k, v in msg.items()) + "\n\n" + msg.get_content())
        return 0
    # Noted before sending: a second call never sends a second mail, even
    # when this one fails half-way.
    state[job] = {"mailed_at": now.isoformat(timespec="seconds"), "error": None}
    _save(directory, state, out)
    try:
        send(msg, cfg)
    except Exception as failed:         # noqa: BLE001 - say it once, never retry
        state[job]["error"] = f"{type(failed).__name__}"
        _save(directory, state, out)
        out(f"notify-failure: NOT SENT: {type(failed).__name__}: "
            + clean(str(failed), [cfg["user"], cfg["password"]]))
        return 1
    out(f"notify-failure: mailed '{msg['Subject']}' to {len(cfg['to'])} recipient(s)")
    return 0


def add_command(sub) -> None:
    p = sub.add_parser("notify-failure", help="one short mail when a scheduled run "
                       "failed (cron, after run-daily); never for a withheld day")
    p.add_argument("--job", default="run-daily", help="the job that failed")
    p.add_argument("--exit", type=int, default=None, metavar="CODE",
                   help="its exit status (cron passes $?)")
    p.add_argument("--log", help="its log; the last lines go in the mail")
    p.add_argument("--dry-run", action="store_true", help="print the mail, send nothing")
    p.add_argument("--force", action="store_true",
                   help="mail even if one went for this job within the cooldown")
    p.set_defaults(run=lambda ctx: notify(ctx.args, ctx.out))


def main(argv: list[str] | None = None) -> int:
    """skald's entry for notify-failure, without importing the package."""
    ap = argparse.ArgumentParser(prog="skald")
    ap.add_argument("--config", default="config.yml")
    ap.add_argument("--today", help=argparse.SUPPRESS)
    ap.add_argument("--site", help=argparse.SUPPRESS)
    add_command(ap.add_subparsers(dest="command", required=True))
    args = ap.parse_args(argv)
    if args.command != "notify-failure":
        ap.error("only notify-failure runs here")
    return notify(args)
