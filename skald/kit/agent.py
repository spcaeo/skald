"""The one line for an AI agent: "set up Skald for <site> — read
<base>/traffic-kit/llms.txt and use code <code> (works once, 24 hours)".

`POST <page>/sites/agentlink` (kit_api.py) makes a sending token and, when
leads are included, gets the site's lead secret, then an **agent code**: an
entry in link.py's store (kit-links.json, 0600, under its lock) with
`kind: "agent"`:

    {"kind": "agent", "site", "made_at", "expires_at", "token_id",
     "sealed", "sealed_lead",   the token, the lead secret and the report key, each
     "sealed_report"            sealed with its own keystream label (link.seal; never
                                the install link's, so no other code can hand them
                                out); null once the keys are taken, the code expired
                                or was cancelled
     "report_key"               the report key's sha256: POST .../report needs the key
     "fields"                   link.FIELDS plus lead_url and tag: nothing secret
     "leads", "lead_note"       leads asked for; "included", "env" or "none"
     "found"                    the site check's facts (site_setup `found`)
     "opened_at", "keys_at", "reported_at", "report", "cancelled_at"}

The code itself is never kept or logged; the dashboard knows the entry by
its link_id, the first 16 hex of the code's sha256 (`sites/agentstatus`).
`cancel` ends a code at once (`sites/agentcancel`), and `make` with
`replace` ends the site's older live codes whose keys were not taken, inside
the same lock (`sites/agentlink`: one live line per site): seals wiped, every
route then answers as for an expired code. Both hand back the ids of tokens
that were never given out, for kit_api.py to revoke.

On the beacon helper (beacon_server.py), `serve` answers:

  GET  /traffic-kit/llms.txt          the public guide for an agent: no code, no secret
  GET  /traffic-kit/<code>            an agent code: to curl or Wget a script that says
                                      "read .../steps" and exits 1 (`| sudo bash` never
                                      runs Markdown); those words to anything else. Never
                                      burns. An install link's code: link.answer_code.
  GET  /traffic-kit/<code>/steps      the site's steps in Markdown, no secret; the first
                                      GET sets opened_at. Valid until expiry or a cancel.
  GET  /traffic-kit/<code>/keys       curl or Wget only: the keys once, as an env file
                                      (values shell-quoted; with SKALD_REPORT_KEY),
                                      then the seals are wiped (keys_at). Again: 410.
                                      Another user agent (a web reader, which may pass the
                                      page through a model): 403 and nothing burned. HEAD:
                                      the status only.
  GET  /traffic-kit/<code>/install.sh the one-file installer without a token (it reads
                                      SKALD_SHIP_TOKEN). Valid until expiry or a cancel.
  GET  /traffic-kit/<code>/leads/<f>  the lead files without a secret (kit/leadfiles.py)
  POST /traffic-kit/<code>/report     JSON, at most 16 KiB, with the header
                                      X-Skald-Report-Key (from the keys file; missing or
                                      wrong: 403, nothing kept): only REPORT's keys are
                                      kept, each cleaned and capped. {"ok": true}

Cache-Control no-store and X-Robots-Tag noindex on every answer (link._answer),
the kit's limit per caller address on every route but llms.txt, and no code,
token or secret is ever logged.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import shlex
import time
from pathlib import Path

from . import link

KIND = "agent"
HERE = Path(__file__).resolve().parent / "agent"
TOKEN_LABEL = b"skald-kit-agent"     # never the install link's label (link.seal's default)
LEAD_LABEL = b"skald-kit-lead"
REPORT_LABEL = b"skald-kit-report"
REPORT_HEADER = "X-Skald-Report-Key"
FOUND_MOST = 120                      # a site check value's length in the steps
LINK_ID = re.compile(r"^[0-9a-f]{16}$")
HOST = re.compile(r"^[A-Za-z0-9.-]{1,253}(?::[0-9]{1,5})?$")
REPORT_MOST = 16 * 1024
NOTES_MOST = 1000
STATES = ("waiting", "opened", "keys_taken", "expired", "cancelled", "unknown")
WEB_READER = ("Fetch this with curl in a shell into a file; never with a web reader, which "
              "would put the keys in a chat. Nothing was used up: the keys are still there.\n")
# What the site check's recommended method means in the steps' cases.
WAYS = {"docker": "case A, the site's own server (the one-file installer)",
        "systemd": "case A, the site's own server (the one-file installer)",
        "cloudflare": "case B, Cloudflare (the Skald Worker)",
        "vercel": "case C, Vercel (a log drain)", "netlify": "case C, Netlify (a log drain)",
        "script": "case D, the script tag only"}
LEAD_WORDS = {
    "included": "The lead secret is `SKALD_LEAD_SECRET` in the keys file (step 3).",
    "env": ("The lead secret is kept in the Skald server's environment, so it is not in the "
            "keys file. Ask the user to get it from whoever runs their Skald."),
    "none": ("Leads were not included in this line, so the keys file has no lead secret. If "
             "the site makes leads, ask the user to make a new line with leads, or to make the "
             "secret in Skald (Settings > Integrations > Lead)."),
}
# A value an agent might paste by mistake: a sending token or a lead secret.
SECRETISH = re.compile(r"skald_[0-9a-f]{4,16}_[A-Za-z0-9_-]{8,}|skh_[A-Za-z0-9_-]{8,}")


def link_id(code: str) -> str:
    return link.digest(code)[:16]


# --------------------------------------------------------------- store

def _key_hash(key: str) -> str:
    return hashlib.sha256(("skald-report-key:" + key).encode()).hexdigest()


def make(folder, site: str, token: str, token_id: str, fields: dict,
         lead_secret: str | None = None, lead_note: str = "none", leads: bool = True,
         found: dict | None = None, now: float | None = None, hours: int = link.HOURS,
         replace: bool = False) -> tuple[str, int, list[tuple[str, str | None, str]]]:
    """(the code, when it expires, ended). Only the code's hash and the sealed
    keys are kept. With `replace`, under the same lock: the site's older live
    codes whose keys were not taken are cancelled, and expired ones whose keys
    were never taken give up their token. `ended`: [(link_id, the token_id to
    revoke or None, "cancelled" or "expired")]."""
    now = time.time() if now is None else now
    code = secrets.token_urlsafe(32)
    report_key = secrets.token_urlsafe(24)
    path = link.path_for(folder)
    keep = {k: str(fields.get(k) or "") for k in (*link.FIELDS, "lead_url", "tag")}
    ended_now = []
    with link._locked(path):
        links = link._load(path)
        if replace:
            ended_now = _replace(links, site, now)
        links[link.digest(code)] = {
            "kind": KIND, "site": site, "made_at": int(now),
            "expires_at": int(now + hours * 3600), "token_id": token_id,
            "sealed": link.seal(token, code, TOKEN_LABEL),
            "sealed_lead": link.seal(lead_secret, code, LEAD_LABEL) if lead_secret else None,
            "sealed_report": link.seal(report_key, code, REPORT_LABEL),
            "report_key": _key_hash(report_key),
            "fields": keep, "leads": bool(leads),
            "lead_note": lead_note if lead_note in LEAD_WORDS else "none",
            "found": found if isinstance(found, dict) else None,
            "opened_at": None, "keys_at": None, "reported_at": None, "report": None}
        link._save(path, links, now)
    return code, int(now + hours * 3600), ended_now


def _replace(links: dict, site: str, now: float) -> list[tuple[str, str | None, str]]:
    """make's sweep, inside its lock: every code already in the store is older
    than the new one, whatever its made_at says (two calls may read the clock
    in one order and take the lock in the other)."""
    out = []
    for key, entry in links.items():
        if entry.get("kind") != KIND or entry.get("site") != site:
            continue
        was = state(entry, now)
        if was in ("waiting", "opened"):
            entry.update(cancelled_at=int(now), sealed=None, sealed_lead=None,
                         sealed_report=None, token_revoked=bool(entry.get("token_id")))
            out.append((key[:16], entry.get("token_id") or None, "cancelled"))
        elif was == "expired" and entry.get("token_id") and not entry.get("token_revoked"):
            entry["token_revoked"] = True
            out.append((key[:16], entry["token_id"], "expired"))
    return out


def find(folder, code: str) -> dict | None:
    """The agent code's entry, or None (unknown, or an install link's code)."""
    if not link.CODE.match(code or ""):
        return None
    entry = link._load(link.path_for(folder)).get(link.digest(code))
    return entry if entry is not None and entry.get("kind") == KIND else None


def state(entry: dict | None, now: float | None = None) -> str:
    """One of STATES. Keys taken stays keys_taken after the expiry: the
    outcome is settled then. A cancelled code is "cancelled" always."""
    now = time.time() if now is None else now
    if entry is None:
        return "unknown"
    if entry.get("cancelled_at"):
        return "cancelled"
    if entry.get("keys_at"):
        return "keys_taken"
    if float(entry.get("expires_at") or 0) <= now:
        return "expired"
    return "opened" if entry.get("opened_at") else "waiting"


def ended(entry: dict, now: float | None = None) -> bool:
    """Expired or cancelled: every route then answers 410."""
    now = time.time() if now is None else now
    return bool(entry.get("cancelled_at")) or float(entry.get("expires_at") or 0) <= now


def _change(folder, code: str, change, now: float):
    """Run `change(entry)` on the code's entry under the store's lock and
    save; (its answer, the entry) or (None, None) when the code is unknown."""
    if not link.CODE.match(code or ""):
        return None, None
    path = link.path_for(folder)
    if not path.exists():
        return None, None
    with link._locked(path):
        links = link._load(path)
        entry = links.get(link.digest(code))
        if entry is None or entry.get("kind") != KIND:
            return None, None
        got = change(entry)
        link._save(path, links, now)
    return got, entry


def opened(folder, code: str, now: float | None = None) -> dict | None:
    """The entry, with opened_at set the first time (until expiry)."""
    now = time.time() if now is None else now

    def change(entry):
        if not entry.get("opened_at") and not ended(entry, now):
            entry["opened_at"] = int(now)
    return _change(folder, code, change, now)[1]


def take(folder, code: str, now: float | None = None):
    """(state, entry, {"token", "lead", "report_key"} or None): the keys once;
    the seals are wiped."""
    now = time.time() if now is None else now

    def change(entry):
        was = state(entry, now)
        if was in ("keys_taken", "expired", "cancelled") or not entry.get("sealed"):
            return "keys_taken" if was == "keys_taken" else "expired", None

        def opened_seal(name, label):
            return link.unseal(entry[name], code, label) if entry.get(name) else None
        keys = {"token": opened_seal("sealed", TOKEN_LABEL),
                "lead": opened_seal("sealed_lead", LEAD_LABEL),
                "report_key": opened_seal("sealed_report", REPORT_LABEL)}
        entry.update(keys_at=int(now), sealed=None, sealed_lead=None, sealed_report=None)
        return "ok", keys
    got, entry = _change(folder, code, change, now)
    if got is None:
        return "unknown", None, None
    return got[0], entry, got[1]


def keep_report(folder, code: str, report: dict, key: str | None,
                now: float | None = None) -> str:
    """"ok", "refused" (no report key, or the wrong one), "expired" (or
    cancelled) or "unknown"; the latest report replaces an earlier one."""
    now = time.time() if now is None else now

    def change(entry):
        want = entry.get("report_key") or ""
        if not key or not want or not hmac.compare_digest(_key_hash(key), want):
            return "refused"
        if ended(entry, now):
            return "expired"
        entry.update(report=report, reported_at=int(now))
        return "ok"
    got, _ = _change(folder, code, change, now)
    return got or "unknown"


def cancel(folder, site: str, lid: str,
           now: float | None = None) -> list[tuple[str, str | None]]:
    """End the agent code of `site` whose link_id is `lid` at once, whatever
    its state. [(link_id, the token_id when its token was never handed out
    and not yet revoked, for the caller to revoke, else None)]."""
    now = time.time() if now is None else now
    path = link.path_for(folder)
    if not LINK_ID.match(lid or "") or not path.exists():
        return []
    done = []
    with link._locked(path):
        links = link._load(path)
        for key, entry in links.items():
            if entry.get("kind") != KIND or entry.get("site") != site \
                    or entry.get("cancelled_at") or not key.startswith(lid):
                continue
            unused = None if entry.get("keys_at") or entry.get("token_revoked") \
                else entry.get("token_id") or None
            entry.update(cancelled_at=int(now), sealed=None, sealed_lead=None,
                         sealed_report=None, token_revoked=bool(unused or
                                                                entry.get("token_revoked")))
            done.append((key[:16], unused))
        if done:
            link._save(path, links, now)
    return done


def status(folder, site: str, lid: str, now: float | None = None) -> dict:
    """The wizard's view of one agent code of `site`, found by its link_id."""
    now = time.time() if now is None else now
    entry = None
    if LINK_ID.match(lid or ""):
        for key, got in link._load(link.path_for(folder)).items():
            if key.startswith(lid) and got.get("kind") == KIND and got.get("site") == site:
                entry = got
                break

    def when(key):
        return link.stamp(entry[key]) if entry and entry.get(key) else None
    return {"state": state(entry, now), "opened_at": when("opened_at"),
            "keys_at": when("keys_at"), "reported_at": when("reported_at"),
            "cancelled_at": when("cancelled_at"),
            "report": (entry or {}).get("report"), "expires_at": when("expires_at")}


# -------------------------------------------------------------- report

def _text(value, most: int) -> str | None:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return None
    got = "".join(ch for ch in " ".join(str(value).split()) if ch.isprintable())
    got = SECRETISH.sub("[removed]", got)[:most].strip()
    return got or None


def _texts(value, many: int, most: int, test=None) -> list[str] | None:
    """At most `many` good values, from the first 5 x `many` given."""
    if not isinstance(value, list):
        return None
    out = []
    for one in value[:many * 5]:
        got = _text(one, most)
        if got and (test is None or test(got)) and got not in out:
            out.append(got)
            if len(out) == many:
                break
    return out


def _privacy(value) -> dict | None:
    if not isinstance(value, dict):
        return None
    out = {}
    if isinstance(value.get("keep_ips"), bool):
        out["keep_ips"] = value["keep_ips"]
    days = value.get("days")
    if isinstance(days, int) and not isinstance(days, bool) and 0 <= days <= 3650:
        out["days"] = days
    url = _text(value.get("notice_url"), 300)
    if url and url.startswith(("https://", "http://")) and " " not in url:
        out["notice_url"] = url
    return out


def _leads(value) -> list[dict] | None:
    if not isinstance(value, list):
        return None
    out = []
    for one in value[:10]:
        if not isinstance(one, dict):
            continue
        got = {k: v for k, v in (("tool", _text(one.get("tool"), 60)),
                                 ("file", _text(one.get("file"), 300))) if v}
        if got:
            out.append(got)
    return out


REPORT = {
    "hosting": lambda v: _text(v, 100), "server": lambda v: _text(v, 100),
    "log_path": lambda v: _text(v, 300), "framework": lambda v: _text(v, 60),
    "asset_paths": lambda v: _texts(v, 10, 200,
                                    lambda p: p.startswith("/") and " " not in p),
    "script_tag": lambda v: _text(v, 300),
    "leads": _leads, "privacy": _privacy,
    "nextjs_log_field": lambda v: v if isinstance(v, bool) else None,
    "changed_files": lambda v: _texts(v, 50, 300),
    "left_for_user": lambda v: _texts(v, 20, 300),
    "notes": lambda v: _text(v, NOTES_MOST),
}


def clean_report(raw) -> dict:
    """Only REPORT's keys, each cleaned and capped; an unknown key, a wrong
    kind or anything shaped like a token or lead secret is dropped.
    ValueError when it is not a JSON object."""
    if not isinstance(raw, dict):
        raise ValueError("The report is one JSON object.")
    out = {}
    for key, clean in REPORT.items():
        if key in raw:
            got = clean(raw[key])
            if got is not None and got != {} and got != []:
                out[key] = got
    return out


# --------------------------------------------------------------- pages

def _base(entry: dict | None, base: str) -> str:
    return ((entry or {}).get("fields", {}).get("base") or base or "").rstrip("/")


def guide(base: str) -> str:
    """llms.txt, filled: no code, no secret."""
    text = (HERE / "llms.txt").read_text(encoding="utf-8")
    return _fill(text, {"BASE": base.rstrip("/") or "the address you read this file from"})


def _fill(text: str, values: dict) -> str:
    """The template filled; ValueError when a placeholder is left."""
    from . import LEFT, fill
    text = fill(text, values)
    left = LEFT.findall(text)
    if left:
        raise ValueError(f"a placeholder is left: {left[0]}")
    return text


def _plain(value) -> str:
    """A site check value as the steps show it: one line, capped, and never
    a placeholder (`__` split) or the end of a code span."""
    got = " ".join(str(value).split())[:FOUND_MOST].replace("`", "'")
    while "__" in got:
        got = got.replace("__", "_ _")
    return got


# Values the site's own answers set (its Server header...): shown as code.
FROM_SITE = ("server", "server_detail", "platform", "framework")


def _found(found: dict | None) -> str:
    if not found:
        return "- Nothing: the check did not run. Find it out in step 1."
    lines = []
    for label, key in (("The site answers", "reachable"), ("HTTPS", "https"),
                       ("Web server", "server"), ("Server details", "server_detail"),
                       ("Hosting", "platform"), ("Framework", "framework"),
                       ("Its addresses", "hosts"),
                       ("Its own files are served from", "asset_prefixes"),
                       ("Why that way", "reason"), ("Note", "assets_note")):
        value = found.get(key)
        if value in (None, "", [], "unknown"):
            continue
        if isinstance(value, bool):
            value = "yes" if value else "no"
        elif isinstance(value, list):
            value = ", ".join(f"`{_plain(v)}`" for v in value[:10])
        elif key in FROM_SITE:
            value = f"`{_plain(value)}`"
        else:
            value = _plain(value)
        lines.append(f"- {label}: {value}")
    return "\n".join(lines) or "- Nothing certain. Find it out in step 1."


def steps(entry: dict, code: str, base: str) -> str:
    """The site's steps in Markdown: addresses and words, never a key."""
    fields = entry.get("fields") or {}
    site, root = entry["site"], _base(entry, base)
    here = f"{root}{link.PREFIX}{code}"
    found = entry.get("found") or None
    way = WAYS.get((found or {}).get("recommended_method") or "")
    note = LEAD_WORDS.get(entry.get("lead_note") or "none", LEAD_WORDS["none"])
    text = (HERE / "steps.md").read_text(encoding="utf-8")
    return _fill(text, {
        "SITE": site, "EXPIRES": link.stamp(entry["expires_at"]).replace("T", " ")[:16],
        "DASHBOARD": fields.get("dashboard") or "", "HELP": fields.get("help") or "",
        "INGEST_URL": fields.get("url") or "", "LEAD_URL": fields.get("lead_url") or "",
        "TAG": fields.get("tag") or "", "FOUND": _found(found),
        "WAY": way or "not settled by the check: find it out in step 1.",
        "ENV_FILE": f"$HOME/.config/skald/{site}.env", "KEYS_URL": f"{here}/keys",
        "INSTALL_URL": f"{here}/install.sh", "LEADS_URL": f"{here}/leads/",
        "REPORT_URL": f"{here}/report", "LEADS": note})


def keys_file(entry: dict, keys: dict) -> str:
    """The env file: each value shell-quoted (sourced with `.`)."""
    fields = entry.get("fields") or {}
    values = [("SKALD_SITE", entry["site"]), ("SKALD_INGEST_URL", fields.get("url") or ""),
              ("SKALD_INGEST_TOKEN", keys["token"]),
              ("SKALD_LEAD_URL", fields.get("lead_url") or "")]
    if keys.get("lead"):
        values.append(("SKALD_LEAD_SECRET", keys["lead"]))
    if keys.get("report_key"):
        values.append(("SKALD_REPORT_KEY", keys["report_key"]))
    lines = [f"# Skald keys for {entry['site']}. Keep this file 0600 and out of any "
             "repository;", "# never print it or paste it in a chat."]
    return "\n".join(lines + [f"{k}={shlex.quote(str(v))}" for k, v in values]) + "\n"


def _lead_file(entry: dict, name: str) -> tuple[bytes, str] | None:
    from .leadfiles import PLUGIN, files, plugin_zip
    try:
        got = files(entry["site"], (entry.get("fields") or {}).get("lead_url") or "", None)
    except ValueError:
        return None
    if name == "skald-leads.zip":
        return plugin_zip(got[PLUGIN]), "application/zip"
    return (got[name], "text/plain; charset=utf-8") if name in got else None


def _send(h, code: int, body, kind: str = "text/plain; charset=utf-8") -> None:
    if isinstance(body, bytes):
        h.send_response(code)
        for k, v in (("Content-Type", kind), ("Cache-Control", "no-store"),
                     ("X-Robots-Tag", "noindex, nofollow"), ("X-Content-Type-Options", "nosniff"),
                     ("Content-Length", str(len(body)))):
            h.send_header(k, v)
        h.end_headers()
        if h.command != "HEAD":
            h.wfile.write(body)
        return None
    return link._answer(h, code, body, kind)


def _script(words: str) -> str:
    return "#!/bin/sh\necho '" + words.replace("'", "") + "' >&2\nexit 1\n"


def _expired(entry: dict, base: str) -> str:
    page = (entry.get("fields") or {}).get("dashboard") or f"{_base(entry, base)}/traffic/"
    what = "was cancelled" if entry.get("cancelled_at") else "has expired"
    return (f"This code {what}. Ask the user to make a new line in Skald: "
            f"{page} (Settings > Add or remove sites).\n")


UNKNOWN = ("This code is not known. Ask the user to make a new line in Skald "
           "(Settings > Add or remove sites).\n")


def _own_base(h) -> str:
    """This request's own address, when the install names none (llms.txt only)."""
    host = h.headers.get("Host") or ""
    proto = h.headers.get("X-Forwarded-Proto") or "https"
    if not HOST.match(host) or proto not in ("https", "http"):
        return ""
    return f"{proto}://{host}"


def serve(h, folder, base: str, limiter, address: str) -> None:
    """Every /traffic-kit/ request on the beacon helper (GET, HEAD, POST)."""
    path = h.path.split("?", 1)[0][len(link.PREFIX):]
    if path == "llms.txt":
        if h.command == "POST":
            return _send(h, 405, "Read this with GET.\n")
        return _send(h, 200, guide((base or "").rstrip("/") or _own_base(h)))
    if not limiter.allow(address):
        return _send(h, 429, "Too many tries. Wait a minute and try again.\n")
    code, _, sub = path.partition("/")
    if h.command == "POST":
        if sub != "report":
            return _send(h, 405, "Only the report is sent with POST.\n")
        return _report(h, folder, code)
    entry = find(folder, code)
    if not sub:
        if entry is None:                          # an install link, or unknown: as before
            return link.answer_code(h, folder, base, code)
        return _bare(h, entry, code, base)
    if entry is None:
        return _send(h, 404, UNKNOWN)
    now = time.time()
    if sub == "keys":
        return _keys(h, folder, entry, code, base, now)
    if ended(entry, now):
        return _send(h, 410, _expired(entry, base))
    if sub == "steps":
        if h.command == "GET" and not entry.get("opened_at"):
            entry = opened(folder, code, now) or entry
        try:
            text = steps(entry, code, base)
        except ValueError:
            return _send(h, 500, "The steps could not be made. Ask the user to make a new line "
                                 "in Skald, and to tell whoever runs their Skald.\n")
        return _send(h, 200, text, "text/markdown; charset=utf-8")
    if sub == "install.sh":
        from . import one_file
        fields = entry.get("fields") or {}
        try:
            data = one_file(entry["site"], fields["url"], fields["dashboard"], fields["help"],
                            fields.get("image") or None, fields.get("ship_path") or None, None)
        except (ValueError, KeyError, OSError):
            return _send(h, 500, _script("The installer could not be made. Ask the user to "
                                         "make a new line in Skald."))
        return _send(h, 200, data)
    if sub.startswith("leads/"):
        got = _lead_file(entry, sub[len("leads/"):])
        if got is None:
            return _send(h, 404, "No such lead file. See leads/README.md.\n")
        return _send(h, 200, got[0], got[1])
    return _send(h, 404, "No such page for this code. Read its steps: "
                         f"{_base(entry, base)}{link.PREFIX}{code}/steps\n")


def _bare(h, entry: dict, code: str, base: str) -> None:
    """The bare code of an agent: never an installer, never Markdown to curl."""
    tool = (h.headers.get("User-Agent") or "").lower().startswith(link.AGENTS)
    if ended(entry):
        words = _expired(entry, base).strip()
        return _send(h, 200, _script(words)) if tool else _send(h, 410, words + "\n")
    words = f"This code is for an AI agent: read {_base(entry, base)}{link.PREFIX}{code}/steps"
    return _send(h, 200, _script(words) if tool else words + "\n")


def _keys(h, folder, entry: dict, code: str, base: str, now: float) -> None:
    tool = (h.headers.get("User-Agent") or "").lower().startswith(link.AGENTS)
    was = state(entry, now)
    if was == "keys_taken":
        return _send(h, 410, "The keys were taken already: they work once. Ask the user to make "
                             "a new line in Skald (Settings > Add or remove sites).\n")
    if was in ("expired", "cancelled"):
        return _send(h, 410, _expired(entry, base))
    if not tool:
        return _send(h, 403, WEB_READER)
    if h.command != "GET":                          # HEAD: the status only, never burned
        return _send(h, 200, "")
    got, entry, keys = take(folder, code, now)
    if got != "ok":
        return _send(h, 410, "The keys were taken already: they work once.\n")
    return _send(h, 200, keys_file(entry, keys))


def _json(h, code: int, body: dict) -> None:
    link._answer(h, code, json.dumps(body) + "\n", "application/json; charset=utf-8")


def _report(h, folder, code: str) -> None:
    try:
        length = int(h.headers.get("Content-Length") or -1)
    except ValueError:
        length = -1
    if length < 0:
        return _json(h, 411, {"ok": False, "error": "Send the report with a Content-Length."})
    if length > REPORT_MOST:
        return _json(h, 413, {"ok": False, "error": "The report is at most 16 KiB."})
    try:
        report = clean_report(json.loads(h.rfile.read(length).decode("utf-8") or "null"))
    except (ValueError, UnicodeDecodeError, RecursionError):
        return _json(h, 400, {"ok": False, "error": "The report is one JSON object."})
    got = keep_report(folder, code, report, (h.headers.get(REPORT_HEADER) or "").strip())
    if got == "refused":
        return _json(h, 403, {"ok": False, "error": f"Send the {REPORT_HEADER} header with "
                                                    "SKALD_REPORT_KEY from the keys file."})
    if got == "unknown":
        return _json(h, 404, {"ok": False, "error": UNKNOWN.strip()})
    if got == "expired":
        return _json(h, 410, {"ok": False, "error": "This code has expired or was cancelled."})
    return _json(h, 200, {"ok": True})
