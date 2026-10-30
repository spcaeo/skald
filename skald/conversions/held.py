"""Refused hook deliveries, held for 24 hours (2.44.1), so a key saved late
still takes them in.

Why: a site's Calendly sent eight real bookings that Skald refused (the key
saved in Skald was not the one Calendly signed with), while every Test of
Skald's own passed. The tool does not send a refused booking again, so those
leads were lost. Now a delivery refused as `unsigned` (none of the tool's
signature headers) or `bad_signature` (a signature that did not match) is
held here; when someone saves a key (Settings > Leads & tools: paste, make,
rotate), key_check.py verifies every held delivery of that hook with it and
takes in the ones that match, with the time they first arrived.

What is kept, one file per delivery, 0600, in a 0700 folder:

    <history folder>/hooks-held/<site>/<tool>/<ms>-<random>.json
    {"received": <unix seconds>, "received_at": "...Z", "why": "unsigned" |
     "bad_signature", "headers": {only what verifying needs}, "body": <base64>}

`headers` holds only the tool's signature headers (adapters SIGNED, and
HubSpot's timestamp), the content type, and the method and public address
the tool called (HubSpot signs them). Never `Authorization`: a `lead` or
`json` delivery sent with the plain key is not held at all, since holding it
would mean keeping the key it sent. A test of Skald's own (X-Skald-Test: 1)
is never held.

Limits: at most CAP files a hook (the oldest go first), each at most the
receiver's own body limit (conversions.MAX_BODY, refused before this), and
none older than KEEP seconds: purged on every write, on every key save, and
in the daily run (jobs.py). Never logged, never in a backup (backup.py copies
only the databases), never in a site's archive, never shown on any page:
only counted. A person's deletion request (`forget --email`, privacy.py)
removes every held body holding their email, visitor ID or lead ref
(forget()); clearing or deleting a site's data removes its folder
(drop_site()).

A site that keeps everything (keep_everything.py: internal and enterprise sites, the
owner's rule) has nothing deleted by itself, so its held deliveries are never purged by
age or by CAP: they wait until a saved key takes them in or a person deletes them. Past
KEEP_ALL_CAP a hook holds no more (new ones are refused as before, never old ones deleted).
"""
from __future__ import annotations

import base64
import json
import os
import secrets
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from . import LEAD_SHAPED, TOOLS

ROOT = "hooks-held"
KEEP = 24 * 3600          # seconds a refused delivery is held
CAP = 200                 # held deliveries a hook, the newest kept
KEEP_ALL_CAP = 2000       # a keep-everything site: none deleted; past this, no more held
WHY = ("unsigned", "bad_signature")
TAKING = ".taking"        # a file being taken in (claim): readers pass it by
EXTRA_HEADERS = {"hubspot": ("x-hubspot-request-timestamp",)}
KEPT_ALWAYS = ("content-type", ":method", ":uri")
# The start of every delivery row a taken-in delivery writes (hooks.process with
# held_at): its received_at is when it first came, so roads.since_saved knows it.
NOTE = "held after a refusal, taken in once the saved key matched"


def keeps(config: dict, folder, site: str) -> bool:
    """True when the site keeps everything: its held deliveries are never deleted by
    age or count. A rule that cannot be read keeps (deleting by mistake is worse)."""
    try:
        from ..keep_everything import Keeper
        return Keeper(config, folder).why(site) is not None
    except Exception:                    # noqa: BLE001 - unreadable rule: keep
        return True


def _keeps(keeps, site: str) -> bool:
    return bool(keeps(site) if callable(keeps) else keeps)


def root(folder) -> Path:
    return Path(folder) / ROOT


def hook_dir(folder, site: str, tool: str) -> Path:
    if tool not in TOOLS or not site or "/" in site or site.startswith("."):
        raise ValueError("not a hook")
    return root(folder) / site / tool


def _stamp(t: float) -> str:
    return datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def kept_headers(tool: str, headers: dict) -> dict:
    """Only what verifying needs: never Authorization, never anything else."""
    from .adapters import adapter
    mod = adapter(tool)
    names = [n for n in (getattr(mod, "SIGNED", None) or (mod.HEADER,)) if n != "authorization"]
    names += list(EXTRA_HEADERS.get(tool, ())) + list(KEPT_ALWAYS)
    return {n: str(headers[n])[:2000] for n in names if headers.get(n) not in (None, "")}


def _mkdir(folder, site: str, tool: str) -> Path:
    """The hook's folder, each level made 0700."""
    from ..files import own_like_folder
    Path(folder).mkdir(parents=True, exist_ok=True)
    base = root(folder)
    for part in (base, base / site, base / site / tool):
        if not part.is_dir():
            part.mkdir(mode=0o700, exist_ok=True)
            own_like_folder(part)
        os.chmod(part, 0o700)
    return base / site / tool


def keep(folder, site: str, tool: str, headers: dict, body: bytes, received: float,
         why: str, keeps: bool = False) -> Path | None:
    """Hold one refused delivery; None when it must not be held (a test, the
    plain key of `lead`/`json`, an unknown reason). Purges the hook first."""
    from .adapters.lead import keyed
    if why not in WHY or headers.get("x-skald-test") == "1":
        return None
    if tool in LEAD_SHAPED and keyed(headers):
        return None
    hook_dir(folder, site, tool)                    # a site or tool that is not one: refused
    where = _mkdir(folder, site, tool)
    if keeps and len(_files(where)) >= KEEP_ALL_CAP:
        return None                                 # never delete to make room
    data = {"received": float(received), "received_at": _stamp(received), "why": why,
            "headers": kept_headers(tool, headers),
            "body": base64.b64encode(bytes(body)).decode("ascii")}
    name = f"{int(received * 1000):013d}-{secrets.token_hex(4)}.json"
    fd, tmp = tempfile.mkstemp(dir=where, prefix=".new-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(data, separators=(",", ":")))
        os.chmod(tmp, 0o600)
        os.replace(tmp, where / name)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    from ..files import own_like_folder
    own_like_folder(where / name)
    purge(folder, received, site, tool, keeps=keeps)
    return where / name


def _files(where: Path) -> list[Path]:
    """The held files of one hook, oldest first (by the name's stamp)."""
    if not where.is_dir():
        return []
    return sorted(p for p in where.iterdir() if p.suffix == ".json"
                  and not p.name.startswith(".") and p.is_file())


def _ms(path: Path) -> int | None:
    head = path.name.split("-", 1)[0].lstrip(".")
    return int(head) if head.isdigit() else None


def read(path: Path) -> dict | None:
    """One held delivery: {path, received, received_at, why, headers, body
    (bytes)}, or None for a file that is not one."""
    try:
        got = json.loads(Path(path).read_text(encoding="utf-8"))
        body = base64.b64decode(str(got["body"]), validate=True)
        received = float(got["received"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    headers = got.get("headers") if isinstance(got.get("headers"), dict) else {}
    return {"path": Path(path), "received": received,
            "received_at": str(got.get("received_at") or _stamp(received)),
            "why": got.get("why") if got.get("why") in WHY else "bad_signature",
            "headers": {str(k): str(v) for k, v in headers.items()}, "body": body}


def entries(folder, site: str, tool: str, now: float, keeps: bool = False) -> list[dict]:
    """The hook's held deliveries still within KEEP (all of them when the site keeps
    everything), oldest first."""
    out = []
    for path in _files(hook_dir(folder, site, tool)):
        got = read(path)
        if got is not None and (keeps or now - got["received"] <= KEEP):
            out.append(got)
    return out


def count(folder, site: str, tool: str, now: float, keeps: bool = False) -> int:
    """How many deliveries of the hook are held (within KEEP); 0 when none."""
    try:
        files = _files(hook_dir(folder, site, tool))
    except ValueError:
        return 0
    if keeps:
        return len(files)
    edge = (now - KEEP) * 1000
    return sum(1 for p in files if (_ms(p) or 0) >= edge)


def _hooks(folder, site: str | None = None, tool: str | None = None) -> list[Path]:
    base = root(folder)
    if not base.is_dir():
        return []
    sites = [base / site] if site else [p for p in base.iterdir() if p.is_dir()]
    out = []
    for s in sites:
        if not s.is_dir():
            continue
        out += [s / tool] if tool else [p for p in s.iterdir() if p.is_dir()]
    return [p for p in out if p.is_dir()]


def purge(folder, now: float, site: str | None = None, tool: str | None = None,
          keeps=False) -> int:
    """Delete what is past KEEP (a claim or a half-written file too) and,
    past CAP, a hook's oldest. Files deleted. `keeps` (a bool, or site -> bool):
    a site that keeps everything loses only half-written files, never a delivery."""
    gone = 0
    edge = (now - KEEP) * 1000
    for where in _hooks(folder, site, tool):
        for path in where.iterdir():
            if path.name.startswith(".") and path.is_file():
                try:
                    old = path.stat().st_mtime < now - KEEP
                except OSError:
                    continue
                if old:
                    path.unlink(missing_ok=True)
                    gone += 1
        if _keeps(keeps, where.parent.name):
            continue
        files = _files(where)
        for path in files:
            if (_ms(path) or 0) < edge:
                path.unlink(missing_ok=True)
                gone += 1
        files = _files(where)
        for path in files[:max(0, len(files) - CAP)]:
            path.unlink(missing_ok=True)
            gone += 1
    return gone


def claim(path: Path) -> Path | None:
    """Take one file for taking in: renamed so no other save takes it too.
    None when another got it first."""
    path = Path(path)
    to = path.with_name("." + path.name + TAKING)
    try:
        os.rename(path, to)
    except OSError:
        return None
    return to


def release(claimed: Path) -> None:
    """Put a claimed file back (it could not be kept: try again later)."""
    claimed = Path(claimed)
    name = claimed.name[1:-len(TAKING)] if claimed.name.endswith(TAKING) else claimed.name
    try:
        os.rename(claimed, claimed.with_name(name))
    except OSError:
        pass


def drop(path: Path) -> None:
    Path(path).unlink(missing_ok=True)


def drop_site(folder, site: str) -> int:
    """Every held delivery of a site (its data cleared or deleted). Files."""
    where = root(folder) / site
    if not site or "/" in site or site.startswith(".") or not where.is_dir():
        return 0
    n = sum(1 for p in where.rglob("*") if p.is_file())
    shutil.rmtree(where, ignore_errors=True)
    return n


def _texts(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from _texts(item)
    elif isinstance(value, list):
        for item in value:
            yield from _texts(item)
    elif isinstance(value, (str, int)) and not isinstance(value, bool):
        yield str(value)


def forget(folder, values, site: str | None = None, dry_run: bool = False) -> int:
    """Delete every held body holding one of `values` (an email, a visitor
    ID, a lead ref; compared trimmed and lower-cased) as a JSON value, or an
    email anywhere in its text. Files deleted (or that would be)."""
    wanted = {str(v).strip().lower() for v in values if v and str(v).strip()}
    emails = [v for v in wanted if "@" in v]
    if not wanted:
        return 0
    gone = 0
    for where in _hooks(folder, site):
        for path in where.iterdir():
            if not path.is_file():
                continue
            got = read(path)
            if got is None:
                continue
            raw = got["body"].decode("utf-8", "replace")
            try:
                texts = {t.strip().lower() for t in _texts(json.loads(raw))}
            except ValueError:
                texts = set()
            low = raw.lower()
            if wanted & texts or any(e in low for e in emails):
                gone += 1
                if not dry_run:
                    path.unlink(missing_ok=True)
    return gone
