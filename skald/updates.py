"""Is there a newer Skald? One small question to GitHub, at most once a day.

    check(config, now)   asks https://api.github.com/repos/<updates.repo>/releases/latest
                         (default spcaeo/skald) when the last answer is a day
                         old, and keeps it in <history folder>/updates.json.
    notice(config)       the newer release, read from that file only: what the
                         daily and weekly mail, the dashboard banner (/me) and
                         `skald updates` show. Never asks the network.

What leaves the server: one HTTPS GET with the header User-Agent
"Skald/<version>". No site name, no figure, no address, no install id; GitHub
sees the server's address, as for any download. `updates.check: false`
turns it off. A failure (no network, a firewall, GitHub down) is silent: one
line in the log the first time, then nothing until it works again, and the
next try is a day later.

A release is marked a security release when its name has "[security]", or
its notes say "[security]" or have a line "Labels: security". Versions are
compared as semantic versions (2.10.0 is newer than 2.9.3; 2.2.0-rc.1 is
older than 2.2.0). Standard library only.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from html import escape as esc
from pathlib import Path

from .config import setting

REPO = "spcaeo/skald"
API = "https://api.github.com/repos/{repo}/releases/latest"
RELEASES = "https://github.com/{repo}/releases"
FILE = "updates.json"
EVERY = timedelta(days=1)
TIMEOUT = 5
MAX_BYTES = 1_000_000
NOTES = 4                               # lines of "what's new" kept
NOTE_MAX = 200
AUTO_LEVELS = ("off", "patch", "minor")
ADMIN_ROLES = ("owner", "admin")
SEMVER = re.compile(r"^v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
                    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+[0-9A-Za-z.-]+)?$")
REPO_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9._-]{1,100}$")
SECURITY = re.compile(r"\[security\]|^\s*labels?\s*:.*\bsecurity\b", re.I | re.M)


# ------------------------------------------------------------ versions

def parse_version(text) -> tuple | None:
    """(major, minor, patch, pre) for "v2.1.0" or "2.2.0-rc.1"; None when it is not semver."""
    m = SEMVER.match(str(text or "").strip())
    if not m:
        return None
    pre = tuple(m.group(4).split(".")) if m.group(4) else ()
    return int(m.group(1)), int(m.group(2)), int(m.group(3)), pre


def _key(v: tuple) -> tuple:
    major, minor, patch, pre = v
    # A release sorts after its pre-releases; numeric identifiers before alphanumeric ones.
    ids = tuple((0, int(p), "") if p.isdigit() else (1, 0, p) for p in pre)
    return (major, minor, patch, 0 if pre else 1, ids)


def compare(a, b) -> int:
    """-1, 0 or 1 as version a is older than, the same as, or newer than b.
    ValueError when either is not a version."""
    va, vb = parse_version(a), parse_version(b)
    if va is None or vb is None:
        raise ValueError(f"not a version: {a if va is None else b!r}")
    ka, kb = _key(va), _key(vb)
    return (ka > kb) - (ka < kb)


def level(current, target) -> str:
    """How far `target` is from `current`: major, minor, patch, same or older."""
    c = compare(target, current)
    if c == 0:
        return "same"
    if c < 0:
        return "older"
    vc, vt = parse_version(current), parse_version(target)
    if vt[0] != vc[0]:
        return "major"
    if vt[1] != vc[1]:
        return "minor"
    return "patch"


def plain(text) -> str:
    """"v2.1.0" -> "2.1.0"."""
    return str(text or "").strip().lstrip("vV")


# ------------------------------------------------------------ settings

def settings(config: dict) -> dict:
    """{"check": bool, "repo": str, "auto": off|patch|minor} from `updates:`."""
    cfg = config or {}
    on = setting(cfg, "updates", "check", True)
    repo = str(setting(cfg, "updates", "repo", REPO)).strip()
    if not REPO_NAME.match(repo):
        repo = REPO
    auto = setting(cfg, "updates", "auto", "off")
    # YAML 1.1 reads a bare `off` or `no` as false.
    auto = "off" if auto is False else str(auto).strip().lower()
    return {"check": not (on is False or str(on).lower() in ("false", "off", "no", "0")),
            "repo": repo, "auto": auto if auto in AUTO_LEVELS else "off"}


def current_version() -> str:
    from . import brand
    return str(brand.load().get("version") or "")


def product() -> str:
    from . import brand
    return str(brand.load().get("name") or "Skald")


def folder_of(config: dict) -> Path | None:
    """The history's folder, where updates.json lives (Context sets it)."""
    raw = ((config or {}).get("_resolved") or {}).get("history_db")
    return Path(raw).parent if raw else None


# ------------------------------------------------------------ releases

def release_url(repo: str, tag: str) -> str:
    return f"{RELEASES.format(repo=repo)}/tag/{tag}"


def _notes(body: str) -> list[str]:
    """The first few lines of the release notes, markdown marks taken off."""
    out = []
    for raw in (body or "").splitlines():
        if raw.lstrip().startswith("#"):    # a heading ("## What's new") says nothing new
            continue
        line = re.sub(r"^\s*(?:#+|[-*+]|\d+[.)])\s*", "", raw).strip()
        line = re.sub(r"\*\*|__|`", "", line)
        line = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", line)
        if not line or SECURITY.fullmatch(raw.strip()) or line.lower().startswith("label"):
            continue
        out.append(line[:NOTE_MAX])
        if len(out) == NOTES:
            break
    return out


def parse_release(data: dict, repo: str = REPO) -> dict:
    """The parts of GitHub's release answer Skald keeps. ValueError when the
    tag is not a version, or it is a draft or pre-release."""
    if not isinstance(data, dict):
        raise ValueError("the answer is not a release")
    tag = str(data.get("tag_name") or "")
    if parse_version(tag) is None:
        raise ValueError(f"the release tag {tag[:40]!r} is not a version")
    if data.get("draft") or data.get("prerelease"):
        raise ValueError("the latest release is a draft or a pre-release")
    name = " ".join(str(data.get("name") or tag).split())[:120]
    body = str(data.get("body") or "")
    url = str(data.get("html_url") or "")
    if not url.startswith(f"https://github.com/{repo}/"):
        url = release_url(repo, tag)
    return {"version": plain(tag), "tag": tag, "name": name, "notes": _notes(body),
            "security": bool(SECURITY.search(name) or SECURITY.search(body)),
            "url": url, "published_at": str(data.get("published_at") or "")[:20] or None}


def _get(url: str, agent: str) -> bytes:
    # The one header Skald adds: its name and version. Nothing else is sent.
    req = urllib.request.Request(url, headers={"User-Agent": agent})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read(MAX_BYTES)


def agent(version: str | None = None) -> str:
    return f"Skald/{version if version is not None else current_version() or 'unknown'}"


# ------------------------------------------------------------ the cache

def read(folder) -> dict:
    try:
        got = json.loads((Path(folder) / FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return got if isinstance(got, dict) else {}


def _write(folder: Path, state: dict) -> None:
    from .files import own_like_folder, write_atomic
    path = Path(folder) / FILE
    try:
        write_atomic(path, json.dumps(state, sort_keys=True, indent=1) + "\n")
        own_like_folder(path)
    except OSError:
        pass


def _when(text) -> datetime | None:
    try:
        got = datetime.fromisoformat(str(text))
    except (TypeError, ValueError):
        return None
    return got if got.tzinfo else got.replace(tzinfo=timezone.utc)


def check(config: dict, now: datetime | None = None, *, folder=None, fetch=None,
          force: bool = False, current: str | None = None, log=None) -> dict:
    """Ask GitHub for the latest release when the last try is a day old (or
    `force`). Returns the state kept in updates.json; never raises.

    `fetch(url, user_agent) -> bytes` is the network (tests pass their own)."""
    cfg = settings(config)
    folder = Path(folder) if folder is not None else folder_of(config)
    if folder is None:
        return {}
    state = read(folder)
    if not cfg["check"]:
        return {**state, "off": True}
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    tried = _when(state.get("checked_at"))
    if not force and tried is not None and timedelta(0) <= now - tried < EVERY \
            and state.get("repo") == cfg["repo"]:
        return state
    version = current if current is not None else current_version()
    state.update(repo=cfg["repo"], checked_at=now.isoformat(timespec="seconds"),
                 current=version)
    url = API.format(repo=cfg["repo"])
    try:
        raw = (fetch or _get)(url, agent(version))
        state["latest"] = parse_release(json.loads(raw), cfg["repo"])
        state.update(ok=True, error=None, failing_since=None)
    except Exception as why:            # noqa: BLE001 - silent: a notice is a nicety
        error = f"{type(why).__name__}: {why}"[:200]
        if not state.get("failing_since"):
            # Logged once; the next line is when it works again.
            (log or (lambda m: print(m, file=sys.stderr)))(
                f"updates: could not ask {url}: {error} (said once; tried again daily)")
            state["failing_since"] = now.isoformat(timespec="seconds")
        state.update(ok=False, error=error)
    _write(folder, state)
    return state


def notice(config: dict, folder=None, current: str | None = None) -> dict | None:
    """The newer release from updates.json, or None (up to date, checks off,
    never asked, or the file unreadable). Reads only; no network."""
    if not settings(config)["check"]:
        return None
    folder = Path(folder) if folder is not None else folder_of(config)
    if folder is None:
        return None
    latest = read(folder).get("latest")
    if not isinstance(latest, dict):
        return None
    current = current if current is not None else current_version()
    try:
        how = level(current, latest.get("version"))
    except ValueError:
        return None
    if how in ("same", "older"):
        return None
    url = str(latest.get("url") or "")
    if not url.startswith("https://github.com/"):
        return None
    return {"product": product(), "current": plain(current),
            "latest": plain(latest.get("version")), "name": str(latest.get("name") or ""),
            "notes": [str(n) for n in (latest.get("notes") or [])][:NOTES],
            "security": bool(latest.get("security")), "level": how, "url": url,
            "published_at": latest.get("published_at")}


def deployed() -> bool:
    """An installed copy (build.json beside the code: install.sh, Docker, a
    deploy), not a checkout or the tests: only it asks by itself."""
    from .brand import ROOT
    return (ROOT / "build.json").exists()


def daily(ctx) -> int:
    """run-daily's step: refresh the answer once a day. Never fails the run."""
    try:
        if deployed():
            check(ctx.config, folder=ctx.db_path.parent, log=ctx.err)
    except Exception as why:            # noqa: BLE001
        ctx.err(f"updates: {type(why).__name__}: {why}")
    return 0


# ------------------------------------------------------------ where it shows

def headline(n: dict) -> str:
    return (f"{n['product']} {n['latest']} is available (you run {n['current']})"
            + (": a security release" if n["security"] else ""))


def mail_notice(config: dict) -> tuple[str, str]:
    """(text, html) for the daily and weekly mail; ("", "") when up to date.
    Never raises: a section, never the mail."""
    try:
        n = notice(config)
    except Exception:                   # noqa: BLE001
        return "", ""
    if n is None:
        return "", ""
    from . import mail_html as m
    notes = n["notes"][:2]
    text = (f"{headline(n)}.\n" + "".join(f"  {line}\n" for line in notes)
            + f"What's new: {n['url']}\nHow to upgrade: run `skald upgrade` "
            f"(install script) or pull the new image (Docker).\n\n")
    colour = m.BAD if n["security"] else m.PEOPLE
    rows = "".join(f'<div class="s-ink2" style="font:400 13px/1.5 {m.FONT};color:{m.INK2}">'
                   f"{esc(line)}</div>" for line in notes)
    body = (f'<div class="s-ink" style="font:400 14px/1.5 {m.FONT};color:{m.INK};'
            f'border-left:3px solid {colour};padding:0 0 0 10px">{esc(headline(n))}.{rows}'
            f'<div style="padding-top:6px"><a href="{esc(n["url"], quote=True)}" '
            f'style="color:{colour};font-weight:600;text-decoration:none">'
            f"What's new &rarr;</a></div></div>")
    title = "Security update available" if n["security"] else "Update available"
    return text, m._card(title, body, "Upgrade with <code>skald upgrade</code> (install "
                         "script), or pull the new image (Docker).")


def for_me(body: dict, config: dict, folder) -> dict:
    """Add `update` to the helper's /me answer, for an owner or admin only."""
    try:
        if body.get("role") in ADMIN_ROLES:
            n = notice(config, folder)
            if n is not None:
                body["update"] = n
    except Exception:                   # noqa: BLE001 - /me must answer
        pass
    return body


# ------------------------------------------------------------ the command

def describe(state: dict, n: dict | None, current: str) -> list[str]:
    lines = [f"you run {product()} {current or 'unknown'}"]
    if state.get("off"):
        return lines + ["update checks are off (updates.check: false)"]
    if not state.get("checked_at"):
        return lines + ["not asked yet: `skald updates --check-now` asks GitHub once"]
    lines.append(f"last asked {state['checked_at']} ({state.get('repo') or REPO})"
                 + ("" if state.get("ok") else f": FAILED, {state.get('error')}"))
    if n is None:
        latest = (state.get("latest") or {}).get("version")
        return lines + [f"up to date (latest release {latest})" if latest else
                        "no release known yet"]
    lines.append(headline(n) + f", a {n['level']} release")
    lines += [f"  {line}" for line in n["notes"]]
    lines.append(f"what's new: {n['url']}")
    lines.append("upgrade: `skald upgrade --dry-run`, then `skald upgrade` "
                 "(docs/UPGRADING.md)")
    return lines


def cmd_updates(ctx, fetch=None) -> int:
    a = ctx.args
    folder = ctx.db_path.parent
    if a.check_now:
        state = check(ctx.config, folder=folder, fetch=fetch, force=True, log=ctx.err)
    else:
        state = check(ctx.config, folder=folder, fetch=fetch, log=ctx.err) \
            if deployed() else read(folder)
        if not settings(ctx.config)["check"]:
            state = {**state, "off": True}
    current = current_version()
    n = notice(ctx.config, folder, current)
    if a.json:
        ctx.out(json.dumps({"current": current, "state": state, "update": n},
                           sort_keys=True, indent=1))
    else:
        for line in describe(state, n, current):
            ctx.out(line)
    return 0


def add_command(sub) -> None:
    p = sub.add_parser("updates", help="is a newer release out? (asks GitHub at most "
                       "once a day; updates.check)")
    p.add_argument("--check-now", dest="check_now", action="store_true",
                   help="ask GitHub now, whatever the time of the last answer")
    p.add_argument("--json", action="store_true")
    p.set_defaults(run=cmd_updates)
