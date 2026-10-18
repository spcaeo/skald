"""Deploy markers: the things we did, drawn as vertical lines on every chart.

A traffic number moves for two kinds of reason: something happened out
there, or we changed something in here. Without the second kind written
down, the first is guessed at. markers.json (DATA-CONTRACT.md) lists them,
newest first, for the last 180 days, from five places:

  markers.log          one JSON line per event beside the history, appended
                       by `skald mark-deploy` (each skald deploy),
                       by note_config (the config changed) and by
                       refresh_version (the live site shows a new version)
  website releases     the release directories the website's deploy leaves
                       (`markers.releases_dir`, names like 20261007-151422,
                       a UTC time)
  internal addresses   `ours.change_log`, the log of addresses added and
                       removed on the page - by label only, never the address
  config changes       see markers.log
  website version      what the live site's footer says now, cached

build() only reads. Everything that writes or fetches - note_config,
refresh_version, append - is called by a command (live, mark-deploy), so a
render never waits on the network or changes state.

No address is ever written here: the internal-address log holds addresses,
and only its time, action and label are read from it.
"""
from __future__ import annotations

import hashlib
import json
import re
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .files import write_atomic

LOG = "markers.log"
CONFIG_HASH = "config-hash"
VERSION_FILE = "website-version.json"
DAYS = 180
VERSION_EVERY = timedelta(minutes=30)
VERSION_TIMEOUT = 5
VERSION = re.compile(r"v[0-9.]+ · build [0-9]+")
# React writes "v<!-- -->1.4.0<!-- --> · build <!-- -->212": comments out first.
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
# Not "skald...": that agent is the heartbeat's (ours, label heartbeat),
# and a version check counted as a beat would bend the uptime figure. List
# this one in ours.user_agents with its own label.
VERSION_AGENT = "site-version-check/1"
RELEASE_NAME = re.compile(r"^(\d{8})-(\d{6})$")
KINDS = ("website_release", "skald_deploy", "config_change", "ours_change",
         "backfill")
LABEL_MAX = 120
DETAIL_MAX = 400


def _clean(text, limit: int) -> str:
    return " ".join(str(text or "").split())[:limit]


def _aware(when: datetime) -> datetime:
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def _setting(config: dict, section: str, key: str):
    got = ((config or {}).get(section) or {}).get(key)
    return None if got in (None, "", []) else got


# ------------------------------------------------------------------ writing

def append(directory, kind: str, label: str, detail: str = "",
           at: datetime | None = None) -> dict:
    """Add one marker to markers.log beside the history. Returns it."""
    if kind not in KINDS:
        raise ValueError(f"unknown marker kind {kind!r}; one of {', '.join(KINDS)}")
    marker = {"at": _aware(at or datetime.now(timezone.utc)).isoformat(timespec="seconds"),
              "kind": kind, "label": _clean(label, LABEL_MAX) or kind.replace("_", " "),
              "detail": _clean(detail, DETAIL_MAX)}
    path = Path(directory) / LOG
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(marker, ensure_ascii=False) + "\n")
    return marker


def note_config(config_path, directory, now: datetime | None = None) -> dict | None:
    """Append a config_change marker when the config file's text differs
    from the last time this was called. The first call only stores the
    hash. Returns the marker, or None. Never raises on a missing file."""
    try:
        text = Path(config_path).read_bytes()
    except OSError:
        return None
    digest = hashlib.sha256(text).hexdigest()
    state = Path(directory) / CONFIG_HASH
    try:
        before = state.read_text().strip()
    except OSError:
        before = ""
    if before == digest:
        return None
    write_atomic(state, digest + "\n")
    if not before:
        return None
    return append(directory, "config_change", "skald config changed",
                  f"{Path(config_path).name} sha256 {before[:12]} -> {digest[:12]}", now)


def _read_version(directory) -> dict:
    try:
        got = json.loads((Path(directory) / VERSION_FILE).read_text())
    except (OSError, ValueError):
        return {}
    return got if isinstance(got, dict) else {}


def refresh_version(config: dict, directory, now: datetime | None = None,
                    force: bool = False) -> str | None:
    """Fetch the live site's footer version, at most every 30 minutes, into
    website-version.json beside the history; a new version is also a
    website_release marker. Returns the cached version. A failed fetch
    keeps the last good one and records the error."""
    url = _setting(config, "markers", "version_url")
    if not url:
        return None
    now = _aware(now or datetime.now(timezone.utc))
    cached = _read_version(directory)
    try:
        checked = _aware(datetime.fromisoformat(cached.get("checked_at") or ""))
    except ValueError:
        checked = None
    if not force and checked is not None and now - checked < VERSION_EVERY:
        return cached.get("version")
    version, error = cached.get("version"), None
    try:
        request = urllib.request.Request(str(url), headers={
            "User-Agent": VERSION_AGENT})
        with urllib.request.urlopen(request, timeout=VERSION_TIMEOUT) as answer:
            body = answer.read(2_000_000).decode("utf-8", "replace")
        found = VERSION.search(HTML_COMMENT.sub("", body))
        if found:
            version = found.group(0)
        else:
            error = "no version in the page"
    except Exception as why:  # noqa: BLE001 - any failure keeps the last good copy
        error = f"{type(why).__name__}: {_clean(why, 120)}"
    before = cached.get("version")
    write_atomic(Path(directory) / VERSION_FILE, json.dumps({
        "version": version, "checked_at": now.isoformat(timespec="seconds"),
        "changed_at": now.isoformat(timespec="seconds") if version != before
        else cached.get("changed_at"),
        "error": error}, ensure_ascii=False) + "\n")
    if version and before and version != before:
        append(directory, "website_release", f"site now {version}",
               f"the footer said {before}", now)
    return version


# ------------------------------------------------------------------ reading

def _from_log(directory) -> list[dict]:
    out = []
    try:
        lines = (Path(directory) / LOG).read_text(encoding="utf-8").splitlines()
    except OSError:
        return out
    for raw in lines:
        try:
            m = json.loads(raw)
            when = _aware(datetime.fromisoformat(m["at"]))
        except (ValueError, KeyError, TypeError):
            continue
        if m.get("kind") not in KINDS:
            continue
        out.append({"at": when, "kind": m["kind"],
                    "label": _clean(m.get("label"), LABEL_MAX),
                    "detail": _clean(m.get("detail"), DETAIL_MAX)})
    return out


def _releases(config: dict) -> list[dict]:
    """One marker per release directory: the name is its UTC time; a name
    of another shape is dated by the directory's modification time."""
    folder = _setting(config, "markers", "releases_dir")
    if not folder:
        return []
    try:
        entries = [p for p in Path(str(folder)).iterdir() if p.is_dir()]
    except OSError:
        return []
    out = []
    for p in entries:
        m = RELEASE_NAME.match(p.name)
        when = None
        if m:
            try:
                when = datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S") \
                    .replace(tzinfo=timezone.utc)
            except ValueError:
                when = None
        if when is None:
            try:
                when = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
            except OSError:
                continue
        out.append({"at": when, "kind": "website_release",
                    "label": _clean(f"website release {p.name}", LABEL_MAX), "detail": ""})
    return out


OURS_WORDS = {"add": "added", "remove": "removed", "pause": "paused", "resume": "resumed",
              "edit": "edited"}


def _ours_changes(config: dict) -> list[dict]:
    """ours_store's change log: time, action, label, ADDRESS, from. The
    address (fourth field) is never read into a marker."""
    raw = _setting(config, "ours", "change_log")
    if not raw:
        return []
    try:
        lines = Path(str(raw)).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        try:
            when = _aware(datetime.fromisoformat(parts[0]))
        except ValueError:
            continue
        action = OURS_WORDS.get(parts[1], _clean(parts[1], 20))
        label = _clean(parts[2], 60)
        source = _clean(parts[4], 30) if len(parts) > 4 else ""
        out.append({"at": when, "kind": "ours_change",
                    "label": f"internal address {action}: {label}",
                    "detail": f"from the {source}" if source else ""})
    return out


def collect(config: dict, directory, now: datetime, tz, days: int = DAYS) -> list[dict]:
    """Every marker from every source in the last `days`, newest first,
    times ISO in `tz`. Read-only."""
    since = _aware(now) - timedelta(days=days)
    found = []
    if directory is not None:
        found += _from_log(directory)
    found += _releases(config) + _ours_changes(config)
    found = [m for m in found if since <= m["at"] <= _aware(now) + timedelta(minutes=5)]
    found.sort(key=lambda m: (m["at"], m["kind"], m["label"]), reverse=True)
    return [{**m, "at": m["at"].astimezone(tz).isoformat(timespec="seconds")} for m in found]


def _directory(page) -> Path | None:
    """Beside the history: where the live snapshot and these logs live."""
    from .config import setting
    raw = setting(page.config, "history", "db")
    if not raw:
        return None
    return Path(str(raw)).expanduser().parent


def build(page) -> dict:
    """markers.json (DATA-CONTRACT.md): the same on every page."""
    directory = getattr(page, "live_dir", None) or _directory(page)
    version = _read_version(directory).get("version") if directory is not None else None
    return {"markers": collect(page.config, directory, page.now, page.tz),
            "website_version": version}


# ----------------------------------------------------------------- commands

def cmd_mark_deploy(ctx) -> int:
    marker = append(ctx.live_dir, "skald_deploy",
                    ctx.args.label or "skald deployed", ctx.args.detail or "")
    ctx.out(f"marker {marker['at']}: {marker['label']}")
    return 0


def cmd_markers(ctx) -> int:
    got = collect(ctx.config, ctx.live_dir, ctx.now, ctx.tz)
    version = _read_version(ctx.live_dir).get("version")
    if ctx.args.json:
        ctx.out(json.dumps({"markers": got, "website_version": version},
                           ensure_ascii=False, indent=1))
        return 0
    ctx.out(f"website version now: {version or 'not known'}")
    for m in got:
        ctx.out(f"{m['at']}  {m['kind']:<21} {m['label']}"
                + (f"  ({m['detail']})" if m["detail"] else ""))
    if not got:
        ctx.out("no markers in the last 180 days")
    return 0


def add_command(sub) -> None:
    p = sub.add_parser("mark-deploy", help="add a skald deploy marker "
                       "to the charts (run from the deploy procedure)")
    p.add_argument("--label", help="what was deployed, e.g. 'release 2: requests feed'")
    p.add_argument("--detail", help="one more line, e.g. the commit")
    p.set_defaults(run=cmd_mark_deploy)
    p = sub.add_parser("markers", help="list the chart markers of the last 180 days")
    p.add_argument("--json", action="store_true")
    p.set_defaults(run=cmd_markers)
