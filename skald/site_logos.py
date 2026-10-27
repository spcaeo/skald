"""Each site's own logo: on the site picker, in the menu, in the site
switcher and on the browser tab (2.6.0; docs/SETTINGS.md, "Logo").

Where a logo comes from is a setting per site, `site.logo.source`:

  auto    (the default) asked of the site itself: the icons its home page
          names (<link rel="apple-touch-icon">, then <link rel="icon">), then
          /apple-touch-icon.png, then /favicon.ico. Never an outside icon
          service, which would learn which sites this install reports on.
  upload  a file an admin or owner sent from Settings > Site (logo_api.py):
          PNG, ICO or a safe SVG, square, at least 64 x 64, at most 256 KB.
  letter  the site's first letter on a colour, `site.logo.color`, one of four.
          Also what every place shows while there is no logo.

How the site is asked (Fetcher): https only, the site's own hosts only
(`site.hosts`, and the site's name when it is a host name), never an IP
address or a name that resolves to a private, loopback or link-local
address, and the connection goes to the address that was checked (no second
lookup). At most 3 redirects, each to one of the same hosts; 6 seconds per
request and 20 for the whole check; at most 512 KB of the home page and
256 KB of an image; an image only when its Content-Type says image/ and its
first bytes agree (logo_image.py), an SVG only when it cannot run or load
anything.

Kept beside the history, one folder per site:

  <history folder>/logos/<site>/fetched.<ext>   what the site gave
  <history folder>/logos/<site>/upload.<ext>    what an admin uploaded
  <history folder>/logos/<site>/state.json      when it was checked, the URL
                                                it came from, why not

The daily run checks a site whose source is auto once a week (a failed check
again after a day); Settings' "Check the site again now" asks at once, at
most once a minute (logo_api.py); `skald logo --check` does the same from
the server. A site just added is asked at once, on a thread (2.25,
fetch_now: sites_api, sign-up, `skald site add`), and sites.json is rewritten
so the switcher shows it; the site picker asks again, at most once a day, for
a site that still shows its letter (retry_missing). Nothing here raises into a
run or a request: a logo is a nicety.
"""
from __future__ import annotations

import hashlib
import http.client
import ipaddress
import json
import os
import socket
import ssl
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from . import logo_image
from .files import slug, write_atomic

SOURCES = ("auto", "upload", "letter")
# Letter colours (Settings > Site > Logo): blue, teal, amber, ink.
COLORS = ("#1d4ed8", "#0f766e", "#9a6400", "#17212b")
MAX_IMAGE = 256 * 1024
MAX_HTML = 512 * 1024
MAX_REDIRECTS = 3
TIMEOUT = 6.0
BUDGET = 20.0
REFRESH_OK = timedelta(days=7)
REFRESH_FAILED = timedelta(days=1)
CHECK_GAP = 60                         # seconds between two "check now" presses
AGENT = "Skald-site-logo/1 (the site's own icon, asked by its analytics)"
WELL_KNOWN = ("/apple-touch-icon.png", "/favicon.ico")
FOLDER = "logos"
STATE = "state.json"


class FetchError(Exception):
    """Why the site gave no logo, in plain words."""


def _now(now: datetime | None = None) -> datetime:
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc)


def _iso(when: datetime) -> str:
    return when.isoformat(timespec="seconds")


# --------------------------------------------------------------- the store

def folder(base: Path | str, site: str) -> Path:
    """Where this site's logo files are: <history folder>/logos/<site>/."""
    return Path(base) / FOLDER / slug(site)


def load_state(where: Path) -> dict:
    try:
        got = json.loads((Path(where) / STATE).read_text())
    except (OSError, ValueError):
        return {}
    return got if isinstance(got, dict) else {}


def save_state(where: Path, state: dict) -> None:
    write_atomic(Path(where) / STATE, json.dumps(state, indent=1, sort_keys=True) + "\n")


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


def _keep(where: Path, stem: str, body: bytes, kind: str) -> dict:
    """Write <stem>.<kind>, removing the same stem in another type."""
    for old in Path(where).glob(f"{stem}.*") if Path(where).exists() else ():
        if old.suffix.lstrip(".") in logo_image.CTYPES and old.suffix != f".{kind}":
            old.unlink(missing_ok=True)
    _write_bytes(Path(where) / f"{stem}.{kind}", body)
    return {"kind": kind, "bytes": len(body), "sha": hashlib.sha256(body).hexdigest()[:12]}


def _file(where: Path, entry: dict | None) -> Path | None:
    if not isinstance(entry, dict) or entry.get("kind") not in logo_image.CTYPES:
        return None
    stem = "upload" if entry.get("uploaded") else "fetched"
    path = Path(where) / f"{stem}.{entry['kind']}"
    return path if path.is_file() else None


def store_upload(base: Path, site: str, body: bytes, by: str, now: datetime | None = None) -> dict:
    """Check and keep an uploaded logo; logo_image.Refused when it is not one."""
    kind, size = logo_image.check_upload(body, MAX_IMAGE)
    where = folder(base, site)
    entry = {**_keep(where, "upload", body, kind), "size": list(size) if size else None,
             "uploaded": True, "at": _iso(_now(now)), "by": by}
    state = load_state(where)
    state["upload"] = entry
    save_state(where, state)
    return entry


# ----------------------------------------------------------- the settings

def letter(name: str) -> str:
    """The site's first letter or digit, upper case ("www." left out)."""
    name = str(name or "").lower()
    name = name[4:] if name.startswith("www.") else name
    return next((c.upper() for c in name if c.isalnum()), "?")


def default_color(name: str) -> str:
    """One of COLORS, the same for a name every time."""
    return COLORS[int(hashlib.sha256(str(name).encode()).hexdigest(), 16) % len(COLORS)]


def prefs(config: dict, site: str, base: Path | None = None) -> dict:
    """{"source", "color"}: the site's settings rows, else config.yml
    (`site.logo_source`, `site.logo_color`), else auto and the name's colour."""
    from . import settings_store as store
    got = {}
    try:
        got = store.effective(config, site, live_dir=base)
    except Exception:                   # noqa: BLE001 - no accounts file, an old one
        site_part = (config or {}).get("site") or {}
        got = {"site.logo.source": site_part.get("logo_source"),
               "site.logo.color": site_part.get("logo_color")}
    source = got.get("site.logo.source")
    color = got.get("site.logo.color")
    return {"source": source if source in SOURCES else "auto",
            "color": color if color in COLORS else default_color(site)}


def chosen(config: dict, site: str, base: Path | None) -> tuple[Path, dict] | None:
    """(file, its state entry) the pages show now, or None for the letter.
    An upload only when the source is upload; what the site gave for auto,
    and for upload while no file was uploaded."""
    if base is None:
        return None
    pref = prefs(config, site, base)["source"]
    if pref == "letter":
        return None
    where = folder(base, site)
    state = load_state(where)
    order = (state.get("upload"), state.get("fetched")) if pref == "upload" \
        else (state.get("fetched"),)
    for entry in order:
        path = _file(where, entry)
        if path is not None:
            return path, entry
    return None


def stored(base: Path | None, site: str, which: str) -> tuple[Path, dict] | None:
    """(file, entry) of what the site gave ("fetched") or the upload ("upload"),
    whatever the setting says: Settings' preview of each choice."""
    if base is None or which not in ("fetched", "upload"):
        return None
    where = folder(base, site)
    got = load_state(where).get(which)
    path = _file(where, got)
    return (path, got) if path is not None else None


def entry(config: dict, site: str, base: Path | None) -> dict:
    """sites.json's `logo` for one site: {"url" (relative to the dashboard's
    root, with the file's hash so a new logo is fetched again) or null for
    the letter, "letter", "color", "source", "kind"}."""
    pref = prefs(config, site, base)
    got = chosen(config, site, base)
    url = f"{slug(site)}/logo?v={got[1]['sha']}" if got else None
    return {"url": url, "letter": letter(site), "color": pref["color"],
            "source": pref["source"], "kind": got[1]["kind"] if got else None}


def status(config: dict, site: str, base: Path, now: datetime | None = None) -> dict:
    """What Settings > Site > Logo shows: the choice, what the site gave,
    when it was checked and when it will be again, the upload."""
    where = folder(base, site)
    state = load_state(where)
    fetched = state.get("fetched") if _file(where, state.get("fetched")) else None
    upload = state.get("upload") if _file(where, state.get("upload")) else None
    nxt = None
    if state.get("checked_at"):
        try:
            nxt = _iso(datetime.fromisoformat(state["checked_at"])
                       + (REFRESH_OK if state.get("ok") else REFRESH_FAILED))
        except ValueError:
            nxt = None
    pref = prefs(config, site, base)
    return {"logo": entry(config, site, base), "source": pref["source"], "color": pref["color"],
            "colors": list(COLORS), "letter": letter(site),
            "found": {k: fetched.get(k) for k in ("url", "kind", "size", "sha")} if fetched else None,
            "checked_at": state.get("checked_at"), "next_check": nxt, "error": state.get("error"),
            "upload": {k: upload.get(k) for k in ("kind", "size", "at", "sha")} if upload else None,
            "hosts": hosts_of(config, site), "max_kb": MAX_IMAGE // 1024}


# --------------------------------------------------------------- fetching

def hosts_of(config: dict, site: str) -> list[str]:
    """The site's own host names, the site's name first when it is one."""
    raw = [str(h).strip().lower().rstrip(".") for h in
           (((config or {}).get("site") or {}).get("hosts") or [])]
    names = [h.split(":")[0] for h in raw if h]
    name = str(site or "").strip().lower()
    if name and "." in name and name not in names:
        names.insert(0, name)
    elif name in names:
        names.remove(name)
        names.insert(0, name)
    out = []
    for host in names:
        try:
            ipaddress.ip_address(host.strip("[]"))
            continue                    # never an IP address
        except ValueError:
            pass
        if host and "." in host and host not in out and not reserved(host):
            out.append(host)
    return out


# Names that are never a real site (RFC 2606, 6761, 6762): never asked.
RESERVED_TLDS = ("example", "test", "invalid", "localhost", "local", "internal", "lan")


def reserved(host: str) -> bool:
    labels = host.split(".")
    return labels[-1] in RESERVED_TLDS or host.endswith(".home.arpa") or (
        len(labels) >= 2 and labels[-2] == "example" and labels[-1] in ("com", "net", "org"))


def _public(ip: str) -> bool:
    addr = ipaddress.ip_address(ip)
    return addr.is_global and not addr.is_multicast


class _Pinned(http.client.HTTPSConnection):
    """https to the address that was checked, with the host's name for TLS."""

    def __init__(self, host, ip, port, timeout, context):
        super().__init__(host, port, timeout=timeout, context=context)
        self._ip = ip

    def connect(self):
        sock = socket.create_connection((self._ip, self.port), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


class _PinnedPlain(http.client.HTTPConnection):
    """Plain http, for the tests' local server only (Fetcher scheme="http")."""

    def __init__(self, host, ip, port, timeout):
        super().__init__(host, port, timeout=timeout)
        self._ip = ip

    def connect(self):
        self.sock = socket.create_connection((self._ip, self.port), self.timeout)


class Fetcher:
    """GETs on the site's own hosts only, by the rules in the module's text.
    `scheme`, `port` and `allow_private` exist for the tests' local server."""

    def __init__(self, hosts, scheme: str = "https", port: int | None = None,
                 timeout: float = TIMEOUT, budget: float = BUDGET, allow_private: bool = False,
                 clock=time.monotonic):
        self.hosts = [h.lower() for h in hosts]
        self.scheme, self.port, self.timeout = scheme, port, timeout
        self.allow_private, self.clock = allow_private, clock
        self.deadline = clock() + budget
        self.context = ssl.create_default_context()

    def _address(self, host: str, port: int) -> str:
        try:
            found = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except (OSError, UnicodeError):
            raise FetchError(f"{host} could not be found") from None
        ips = [f[4][0] for f in found]
        if not ips:
            raise FetchError(f"{host} could not be found")
        if not self.allow_private and not all(_public(ip) for ip in ips):
            raise FetchError(f"{host} points to a private address; it is not asked")
        return ips[0]

    def _allowed(self, url: str):
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        if parts.scheme != self.scheme:
            raise FetchError(f"{url[:120]} is not {self.scheme}")
        if host not in self.hosts:
            raise FetchError(f"{host or url[:60]} is not one of the site's hosts")
        try:
            port = parts.port
        except ValueError:
            raise FetchError(f"{url[:120]} has a broken port") from None
        usual = 443 if self.scheme == "https" else 80
        if port not in (None, self.port) and not (self.port is None and port == usual):
            raise FetchError(f"{url[:120]} uses another port")
        return parts, host

    def get(self, url: str, limit: int) -> tuple[int, str, bytes, str]:
        """(status, content type, body of at most `limit` bytes, final URL).
        Raises FetchError for anything outside the rules, a body over
        `limit`, or a timeout."""
        for _ in range(MAX_REDIRECTS + 1):
            parts, host = self._allowed(url)
            left = self.deadline - self.clock()
            if left <= 0:
                raise FetchError("the site took too long")
            port = parts.port or self.port or (443 if self.scheme == "https" else 80)
            ip = self._address(host, port)
            wait = min(self.timeout, left)
            conn = (_Pinned(host, ip, port, wait, self.context) if self.scheme == "https"
                    else _PinnedPlain(host, ip, port, wait))
            path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
            try:
                conn.request("GET", path, headers={"User-Agent": AGENT, "Accept":
                                                   "image/*,text/html;q=0.8,*/*;q=0.1",
                                                   "Accept-Encoding": "identity"})
                resp = conn.getresponse()
                if resp.status in (301, 302, 303, 307, 308):
                    where = resp.getheader("Location") or ""
                    resp.close()
                    if not where:
                        raise FetchError("a redirect without a target")
                    url = urljoin(url, where)
                    continue
                ctype = (resp.getheader("Content-Type") or "").split(";")[0].strip().lower()
                declared = resp.getheader("Content-Length")
                if declared and declared.isdigit() and int(declared) > limit:
                    raise FetchError(f"over {limit // 1024} KB")
                body = resp.read(limit + 1)
                if len(body) > limit:
                    raise FetchError(f"over {limit // 1024} KB")
                return resp.status, ctype, body, url
            except (OSError, http.client.HTTPException, ssl.SSLError) as why:
                raise FetchError(f"{host}: {type(why).__name__}") from None
            finally:
                conn.close()
        raise FetchError(f"more than {MAX_REDIRECTS} redirects")


class _Icons(HTMLParser):
    """<link rel="apple-touch-icon" | "icon"> in the page's head."""

    def __init__(self) -> None:
        super().__init__()
        self.found: list[tuple[str, str, str, str]] = []      # rel, href, sizes, type
        self.done = False

    def handle_starttag(self, tag, attrs):
        if tag == "body":
            self.done = True
        if tag != "link" or self.done:
            return
        got = {k.lower(): (v or "") for k, v in attrs}
        rel = set(got.get("rel", "").lower().split())
        href = got.get("href", "").strip()
        if not href:
            return
        if rel & {"apple-touch-icon", "apple-touch-icon-precomposed"}:
            self.found.append(("apple", href, got.get("sizes", ""), got.get("type", "")))
        elif "icon" in rel:
            self.found.append(("icon", href, got.get("sizes", ""), got.get("type", "")))


def _largest(sizes: str) -> int:
    best = 0
    for part in sizes.lower().split():
        if part == "any":
            return 1024
        w, _, h = part.partition("x")
        if w.isdigit() and h.isdigit():
            best = max(best, min(int(w), int(h)))
    return best


def icon_links(html: str, base_url: str) -> list[str]:
    """The icons the page names, best first: app icons (largest first), then
    icons (largest first; SVG as large, a PNG before an ICO)."""
    parser = _Icons()
    try:
        parser.feed(html)
    except Exception:                   # noqa: BLE001 - broken markup is no icon
        pass
    ranked = []
    for i, (rel, href, sizes, ctype) in enumerate(parser.found):
        if href.lower().startswith(("data:", "javascript:")):
            continue
        size = _largest(sizes) or (1024 if "svg" in ctype or href.lower().endswith(".svg")
                                   else 180 if rel == "apple" else 0)
        png = "png" in ctype or href.lower().split("?")[0].endswith(".png")
        ranked.append((0 if rel == "apple" else 1, -size, 0 if png else 1, i,
                       urljoin(base_url, href)))
    out = []
    for *_, url in sorted(ranked):
        if url not in out:
            out.append(url)
    return out


def _image(fetcher: Fetcher, url: str) -> dict:
    status_code, ctype, body, final = fetcher.get(url, MAX_IMAGE)
    if status_code != 200:
        raise FetchError(f"{urlsplit(url).path or '/'}: status {status_code}")
    if not ctype.startswith("image/"):
        raise FetchError(f"{urlsplit(url).path}: not an image ({ctype or 'no type'})")
    try:
        kind, size = logo_image.check(body)
    except logo_image.Refused as why:
        raise FetchError(f"{urlsplit(url).path}: {why}") from None
    return {"body": body, "kind": kind, "size": size, "url": final}


def find(fetcher: Fetcher, host: str) -> dict:
    """The site's best icon, {"body","kind","size","url"}, or FetchError
    with the first reason (and how many places were tried)."""
    home = f"{fetcher.scheme}://{host}" + (f":{fetcher.port}" if fetcher.port else "") + "/"
    tried, reasons, page = [], [], None
    try:
        status_code, ctype, body, final = fetcher.get(home, MAX_HTML)
        if status_code == 200 and "html" in ctype:
            tried += icon_links(body.decode("utf-8", "replace"), final)[:4]
        else:
            page = f"the home page answered {status_code} ({ctype or 'no type'})"
    except FetchError as why:
        page = f"the home page: {why}"
    tried += [urljoin(home, p) for p in WELL_KNOWN]
    for url in tried:
        try:
            return _image(fetcher, url)
        except FetchError as why:
            reasons.append(str(why))
            if "took too long" in str(why):
                break
    # A file that was there but refused says most, then a missing one; the home
    # page's reason when no icon was reached.
    told = [r for r in reasons if not r.endswith("status 404")] or reasons
    raise FetchError(told[0] if told else page or "no icon found")


def check(config: dict, site: str, base: Path, now: datetime | None = None,
          fetcher: Fetcher | None = None) -> dict:
    """Ask the site for its logo now and keep what it gave (or why not).
    Returns the new state; never raises."""
    now = _now(now)
    where = folder(base, site)
    state = load_state(where)
    hosts = fetcher.hosts if fetcher is not None else hosts_of(config, site)
    try:
        if not hosts:
            raise FetchError("the site has no host name to ask (Settings > Site, Host names)")
        got = find(fetcher or Fetcher(hosts), hosts[0])
        kept = _keep(where, "fetched", got["body"], got["kind"])
        state.update(fetched={**kept, "url": got["url"],
                              "size": list(got["size"]) if got["size"] else None},
                     ok=True, error=None)
    except FetchError as why:
        state.update(ok=False, error=str(why)[:200])
    except Exception as why:            # noqa: BLE001 - a logo never fails a run
        state.update(ok=False, error=f"{type(why).__name__}"[:200])
    state["checked_at"] = _iso(now)
    try:
        save_state(where, state)
    except OSError:
        pass
    return state


def due(state: dict, now: datetime | None = None) -> bool:
    try:
        at = datetime.fromisoformat(state["checked_at"])
    except (KeyError, TypeError, ValueError):
        return True
    return _now(now) - at >= (REFRESH_OK if state.get("ok") else REFRESH_FAILED)


def checked_recently(base: Path, site: str, now: datetime | None = None) -> int:
    """Seconds to wait before "check now" may ask the site again (0: now)."""
    state = load_state(folder(base, site))
    try:
        at = datetime.fromisoformat(state["checked_at"])
    except (KeyError, TypeError, ValueError):
        return 0
    left = CHECK_GAP - (_now(now) - at).total_seconds()
    return max(0, int(left + 0.999))


# ------------------------------------------------- a new site, the picker

_ASKING: set[str] = set()              # sites whose check runs now (one at a time each)
_ASKING_LOCK = threading.Lock()


def write_sites_json(out, site: str, logo: dict) -> int:
    """Put `site`'s logo entry into every sites.json already written (the
    dashboard's root and each site's data folder), so the switcher shows it
    before the next run. The number of files changed; never raises."""
    if out is None:
        return 0
    root = Path(out)
    changed = 0
    for path in [root / "sites.json", *sorted(root.glob("*/data/sites.json"))]:
        try:
            body = json.loads(path.read_text())
            listed = [x for x in body.get("sites") or []
                      if isinstance(x, dict) and x.get("name") == site]
            if not listed or all(x.get("logo") == logo for x in listed):
                continue
            for x in listed:
                x["logo"] = logo
            write_atomic(path, json.dumps(body, separators=(",", ":")) + "\n")
            changed += 1
        except (OSError, ValueError, AttributeError, TypeError):
            continue
    return changed


def fetch_now(config: dict, site: str, base, out=None, now: datetime | None = None,
              fetcher=None) -> dict:
    """A site just added (Settings > Sites, the Add a site wizard, sign-up,
    `skald site add`): ask it for its logo now, when its source is auto, then
    rewrite sites.json. The new state ({} when not asked); never raises."""
    try:
        if base is None or prefs(config, site, Path(base))["source"] != "auto":
            return {}
        got = check(config, site, Path(base), now, fetcher)
        write_sites_json(out, site, entry(config, site, Path(base)))
        return got
    except Exception as why:            # noqa: BLE001 - a logo never fails an add
        return {"ok": False, "error": f"{type(why).__name__}"}


def retry_missing(config: dict, site: str, base, out=None, spawn=None,
                  now: datetime | None = None) -> bool:
    """The site picker: a site still showing its letter (source auto, nothing
    fetched) whose last check failed a day ago or more (REFRESH_FAILED), or was
    never made, is asked again on a thread. At most once a day per site; one
    check at a time per site. True when a check was started; never raises."""
    try:
        if base is None or prefs(config, site, Path(base))["source"] != "auto":
            return False
        if chosen(config, site, Path(base)) is not None or not hosts_of(config, site):
            return False
        if not due(load_state(folder(Path(base), site)), now):
            return False
    except Exception:                   # noqa: BLE001 - the picker never fails for a logo
        return False
    with _ASKING_LOCK:
        if site in _ASKING:
            return False
        _ASKING.add(site)

    def work():
        try:
            fetch_now(config, site, base, out)
        finally:
            with _ASKING_LOCK:
                _ASKING.discard(site)
    if spawn is None:
        threading.Thread(target=work, daemon=True).start()
    else:
        spawn(work)
    return True


# ------------------------------------------------------- the daily run, CLI

def daily(ctx) -> int:
    """run-daily's step: a site whose logo comes from the site is asked again
    once a week. Always 0."""
    try:
        base = ctx.db_path.parent
        if prefs(ctx.config, ctx.site, base)["source"] != "auto":
            return 0
        if not due(load_state(folder(base, ctx.site)), ctx.now):
            return 0
        got = check(ctx.config, ctx.site, base, ctx.now)
        ctx.out(f"logo: {got.get('fetched', {}).get('url') if got.get('ok') else got.get('error')}")
    except Exception as why:            # noqa: BLE001 - a logo never fails the run
        ctx.err(f"logo: {type(why).__name__}: {why}")
    return 0


def cmd_logo(ctx) -> int:
    base = ctx.db_path.parent
    if ctx.args.check:
        got = check(ctx.config, ctx.site, base, ctx.now)
        if not got.get("ok"):
            ctx.err(f"logo: {ctx.site}: none found: {got.get('error')}")
    info = status(ctx.config, ctx.site, base, ctx.now)
    found = info["found"]
    ctx.out(f"{ctx.site}: source {info['source']}; shown: "
            + (f"{info['logo']['kind']} file" if info["logo"]["url"] else
               f"the letter {info['letter']} on {info['color']}"))
    ctx.out(f"  from the site: {found['url'] if found else 'nothing'}"
            + (f" (checked {info['checked_at']})" if info["checked_at"] else " (never checked)")
            + (f"; last error: {info['error']}" if info["error"] else ""))
    return 0


def add_command(sub) -> None:
    p = sub.add_parser("logo", help="the site's logo: where it comes from, and --check to "
                       "ask the site for it now (never an outside icon service)")
    p.add_argument("--check", action="store_true", help="ask the site for its icon now")
    p.set_defaults(run=cmd_logo)
