"""Small icons for the sites that send us readers, fetched and kept on our side.

The page shows a referring site with its favicon. Asking a third-party
favicon service for them would tell that service which sites link to us and
who is looking, so the icons are fetched here, from each site itself, and
served from the dashboard's own directory (same origin, behind the same
password):

  <dashboard.out>/<site>/data/favicons/<host>.<ext>
  <dashboard.out>/<site>/data/favicons.json   {"schema_version": 1,
                                               "generated_at": ISO,
                                               "hosts": {host: "favicons/<file>"}}

favicons.json lists only hosts that have a file, so the page never asks for
one that is not there. A host is listed under its name with and without
"www.", because the referrer lists drop it and the request log keeps it.

How one is fetched: https://<host>/favicon.ico; failing that, the icon the
home page names in <link rel="icon">. At most 2 redirects, and only between
the host and its www/apex twin. At most 50 KB, a raster image type by its
Content-Type and by its first bytes (no SVG: it can carry script). Resized
to a 32x32 PNG when Pillow is installed, kept as it came otherwise. At most
`limit` hosts are fetched per call, 3 seconds each; a host that answered is
fetched again after 30 days, one that failed after 7 (favicons-state.json
beside the history). IP addresses, private names, app ids and the site's own
hosts are never fetched. Nothing here raises: a failure is a missing icon.
"""
from __future__ import annotations

import ipaddress
import json
import os
import re
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable, Iterable
from urllib.parse import urljoin, urlsplit

from .files import slug, write_atomic

STATE = "favicons-state.json"
MANIFEST = "favicons.json"
FOLDER = "favicons"
MAX_BYTES = 50_000
MAX_HTML = 300_000
MAX_REDIRECTS = 2
REFRESH_OK = timedelta(days=30)
REFRESH_FAILED = timedelta(days=7)
AGENT = "site-favicon-fetch/1"

# Raster types only, by Content-Type, then proven by the first bytes.
TYPES = {"image/png", "image/x-icon", "image/vnd.microsoft.icon", "image/gif",
         "image/jpeg", "image/webp"}
MAGIC = (
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"\x00\x00\x01\x00", "ico"),
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
    (b"\xff\xd8\xff", "jpg"),
)

HOSTNAME = re.compile(r"^(?=.{4,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
PRIVATE = (".local", ".internal", ".lan", ".home", ".arpa", ".localhost", ".test",
           ".example", ".invalid", ".corp", ".intranet")
# Android app referrers (android-app://com.google.android.gm/) look like a
# host spelled backwards.
APP_ID = re.compile(r"^(?:com|org|net|io|de|fr|uk|ca|jp|ru|cn)\.[a-z0-9-]+\.")
NOT_HOSTS = {"(none)", "(this site)", "(all others)", ""}


def _now(now: datetime | None) -> datetime:
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc)


def _iso(when: datetime) -> str:
    return when.isoformat(timespec="seconds")


def kind_of(body: bytes) -> str | None:
    """The raster type these bytes really are, or None."""
    for magic, kind in MAGIC:
        if body.startswith(magic):
            return kind
    if body[:4] == b"RIFF" and body[8:12] == b"WEBP":
        return "webp"
    return None


def usable(host: str, own: Iterable[str] = ()) -> bool:
    """A public host name worth asking for its icon."""
    host = (host or "").strip().lower().rstrip(".")
    if host in NOT_HOSTS or "." not in host:
        return False
    try:
        ipaddress.ip_address(host.strip("[]"))
        return False
    except ValueError:
        pass
    if host == "localhost" or host.endswith(PRIVATE) or APP_ID.match(host):
        return False
    if not HOSTNAME.match(host):
        return False
    mine = {h.lower().lstrip(".") for h in own}
    bare = host[4:] if host.startswith("www.") else host
    return not (host in mine or bare in mine or "www." + bare in mine)


def twins(host: str) -> set[str]:
    bare = host[4:] if host.startswith("www.") else host
    return {bare, "www." + bare}


# ------------------------------------------------------------------ fetching

class SameSiteRedirects(urllib.request.HTTPRedirectHandler):
    """Follows at most MAX_REDIRECTS redirects, over https, and only between
    a host and its www/apex twin. Anything else is refused."""

    max_redirections = MAX_REDIRECTS

    def __init__(self, host: str) -> None:
        super().__init__()
        self.allowed = twins(host)

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urlsplit(newurl)
        if target.scheme != "https" or (target.hostname or "").lower() not in self.allowed:
            raise urllib.error.HTTPError(newurl, code, "redirect to another site refused",
                                         headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _fetch(url: str, timeout: float, limit: int) -> tuple[int, str, bytes]:
    """(status, content type, at most limit + 1 bytes). Raises on failure."""
    host = (urlsplit(url).hostname or "").lower()
    opener = urllib.request.build_opener(SameSiteRedirects(host))
    req = urllib.request.Request(url, headers={"User-Agent": AGENT,
                                               "Accept": "image/*,text/html;q=0.5"})
    with opener.open(req, timeout=timeout) as resp:
        ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        return resp.status, ctype, resp.read(limit + 1)


class _Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.icons: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag != "link":
            return
        got = {k.lower(): (v or "") for k, v in attrs}
        rel = set(got.get("rel", "").lower().split())
        if rel & {"icon", "apple-touch-icon"} and got.get("href"):
            self.icons.append(got["href"])


def icon_links(html: str, base: str) -> list[str]:
    """Icon URLs the page names, on the same site, https only."""
    parser = _Links()
    try:
        parser.feed(html)
    except Exception:            # noqa: BLE001 - broken markup is no icon
        return []
    allowed = twins((urlsplit(base).hostname or "").lower())
    out = []
    for href in parser.icons:
        url = urljoin(base, href.strip())
        parts = urlsplit(url)
        if parts.scheme == "https" and (parts.hostname or "").lower() in allowed \
                and not parts.path.lower().endswith(".svg"):
            out.append(url)
    return out


def _image(fetch, url: str, timeout: float) -> tuple[bytes, str] | str:
    """(bytes, kind) of a good icon at url, or why not."""
    try:
        status, ctype, body = fetch(url, timeout, MAX_BYTES)
    except Exception as why:     # noqa: BLE001
        return f"{type(why).__name__}"
    if status != 200:
        return f"status {status}"
    if ctype not in TYPES:
        return f"not a raster image ({ctype or 'no type'})"
    if len(body) > MAX_BYTES:
        return "over 50 KB"
    kind = kind_of(body)
    if kind is None:
        return "bytes are not an image"
    return body, kind


def get_icon(host: str, timeout: float = 3, fetch: Callable | None = None) -> tuple[bytes, str] | str:
    """The host's icon as (bytes, kind), or the reason there is none."""
    fetch = fetch or _fetch
    got = _image(fetch, f"https://{host}/favicon.ico", timeout)
    if not isinstance(got, str):
        return got
    first_reason = got
    try:
        status, ctype, body = fetch(f"https://{host}/", timeout, MAX_HTML)
    except Exception:            # noqa: BLE001
        return first_reason
    if status != 200 or "html" not in ctype:
        return first_reason
    for url in icon_links(body[:MAX_HTML].decode("utf-8", "replace"), f"https://{host}/")[:3]:
        got = _image(fetch, url, timeout)
        if not isinstance(got, str):
            return got
    return first_reason


def _pillow():
    try:
        from PIL import Image  # type: ignore
        return Image
    except ImportError:
        return None


def to_png(body: bytes) -> bytes | None:
    """32x32 PNG with Pillow, or None when it is missing or cannot read it."""
    image_mod = _pillow()
    if image_mod is None:
        return None
    import io
    try:
        with image_mod.open(io.BytesIO(body)) as im:
            im = im.convert("RGBA")
            im.thumbnail((32, 32))
            out = io.BytesIO()
            im.save(out, "PNG")
            return out.getvalue()
    except Exception:            # noqa: BLE001
        return None


def _write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ------------------------------------------------------------------ refresh

def folder_for(out_dir: Path, site: str) -> Path:
    return Path(out_dir) / slug(site) / "data"


def load_state(live_dir: Path | None) -> dict:
    if live_dir is None:
        return {}
    try:
        got = json.loads((Path(live_dir) / STATE).read_text())
    except (OSError, ValueError):
        return {}
    return got.get("hosts", {}) if isinstance(got, dict) else {}


def _due(entry: dict | None, data: Path, now: datetime) -> bool:
    if not entry:
        return True
    try:
        at = datetime.fromisoformat(entry["at"])
    except (KeyError, TypeError, ValueError):
        return True
    if entry.get("ok"):
        if not entry.get("file") or not (data / entry["file"]).exists():
            return True
        return now - at > REFRESH_OK
    return now - at > REFRESH_FAILED


def write_manifest(data: Path, state: dict, now: datetime) -> dict:
    """favicons.json: only hosts whose file is there, under both twins."""
    hosts: dict[str, str] = {}
    for host, entry in sorted(state.items()):
        if entry.get("ok") and entry.get("file") and (data / entry["file"]).exists():
            for name in twins(host):
                hosts.setdefault(name, entry["file"])
    body = {"schema_version": 1, "generated_at": _iso(now), "hosts": hosts}
    write_atomic(data / MANIFEST, json.dumps(body, sort_keys=True) + "\n")
    return hosts


def refresh(config: dict, out_dir: Path, site: str, hosts: Iterable[str],
            now: datetime | None = None, limit: int = 10, timeout: float = 3,
            fetch: Callable | None = None, live_dir: Path | None = None,
            convert: bool | None = None) -> dict:
    """Fetch the icons of up to `limit` hosts that are due; rewrite
    favicons.json. Never raises. {"fetched","failed","skipped","cached"}."""
    summary = {"fetched": 0, "failed": 0, "skipped": 0, "cached": 0}
    try:
        now = _now(now)
        data = folder_for(out_dir, site)
        own = [str(h) for h in (((config or {}).get("site") or {}).get("hosts") or [])]
        state = load_state(live_dir)
        seen: set[str] = set()
        for raw in hosts:
            host = (raw or "").strip().lower().rstrip(".")
            if host in seen:
                continue
            seen.add(host)
            if not usable(host, own):
                summary["skipped"] += 1
                continue
            entry = state.get(host)
            if not _due(entry, data, now):
                summary["cached" if entry.get("ok") else "skipped"] += 1
                continue
            if summary["fetched"] + summary["failed"] >= limit:
                continue
            got = get_icon(host, timeout, fetch)
            if isinstance(got, str):
                state[host] = {"at": _iso(now), "ok": False, "file": None, "error": got[:100]}
                summary["failed"] += 1
                continue
            body, kind = got
            use_png = _pillow() is not None if convert is None else convert
            png = to_png(body) if use_png else None
            if png is not None:
                body, kind = png, "png"
            name = f"{host}.{kind}"
            for old in (data / FOLDER).glob(f"{host}.*") if (data / FOLDER).exists() else ():
                if old.name != name and old.name.rsplit(".", 1)[0] == host:
                    old.unlink(missing_ok=True)
            _write_bytes(data / FOLDER / name, body)
            state[host] = {"at": _iso(now), "ok": True, "file": f"{FOLDER}/{name}", "error": None}
            summary["fetched"] += 1
        if live_dir is not None:
            write_atomic(Path(live_dir) / STATE,
                         json.dumps({"hosts": state}, indent=1, sort_keys=True) + "\n")
        write_manifest(data, state, now)
    except Exception as why:     # noqa: BLE001 - a missing icon, never a failed run
        summary["error"] = f"{type(why).__name__}: {why}"[:200]
    return summary


def hosts_from(snap: dict | None, history=None, key: str = "", first=None, last=None) -> list[str]:
    """Referring hosts: today's snapshot (readers by referrer, campaigns'
    referring hosts) and history's readers by referrer over [first, last]."""
    found: list[str] = []
    if snap:
        by = ((snap.get("breakdowns") or {}).get("by") or {}).get("referrer") or {}
        found += list(by)
        rows = ((((snap.get("extras") or {}).get("campaigns") or {}).get("rows") or {})
                .get("ref_host") or [])
        found += [r.get("name", "") for r in rows if isinstance(r, dict)]
    if history is not None and first is not None and last is not None:
        found += [r[0] for r in history.db.execute(
            "SELECT name FROM counts WHERE site = ? AND kind = 'reader_referrer' "
            "AND day BETWEEN ? AND ? GROUP BY name ORDER BY SUM(n) DESC",
            (key, str(first), str(last)))]
    out, seen = [], set()
    for host in found:
        host = (host or "").strip().lower()
        if host not in NOT_HOSTS and host not in seen:
            seen.add(host)
            out.append(host)
    return out


# ------------------------------------------------------------------ command

def cmd_favicons(ctx) -> int:
    from . import live
    from .cli import _path
    out = _path(ctx.config, ctx.config_path, "dashboard", "out", None)
    if out is None:
        ctx.err("favicons: set dashboard.out first")
        return 2
    snap = live.load(live.path_for(ctx.live_dir, ctx.site))
    today = ctx.now.date()
    with ctx.history() as history:
        hosts = hosts_from(snap, history, ctx.site, (today - timedelta(days=90)).isoformat(),
                           today.isoformat())
    got = refresh(ctx.config, out, ctx.site, hosts, ctx.now, limit=ctx.args.limit,
                  live_dir=ctx.live_dir)
    ctx.out(f"favicons: {len(hosts)} referring hosts; " + ", ".join(
        f"{k} {v}" for k, v in got.items()))
    return 0


def add_command(sub) -> None:
    p = sub.add_parser("favicons", help="fetch the icons of referring sites into the "
                       "dashboard's data/favicons/ (never from a third-party service)")
    p.add_argument("--limit", type=int, default=10, help="most hosts fetched (default 10)")
    p.set_defaults(run=cmd_favicons)
