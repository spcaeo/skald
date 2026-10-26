"""POST /traffic-kit/<code>/searchkey: a Google Search Console service-account
key file, handed to Skald by the AI agent of a line with the search job
(agent.py serves it; docs/plans/2026-10-26-agent-everywhere.md, "Integrations
an agent can do").

The agent makes the key with `gcloud` only when the user agrees (search.md),
into a 0600 file, and sends that file as the request body from stdin
(`curl --data-binary @- < file`): never on a command line, never in a chat.
Then the user gives the key's robot address read-only access in Search
Console: the one click a person makes.

curl or Wget only (anything else: 403, nothing kept), the header
X-Skald-Report-Key (SKALD_REPORT_KEY from the keys file; missing or wrong:
403), the key file itself as the body (JSON, at most MOST bytes, with a
Content-Length). Kept exactly as Settings > Leads & integrations > Search Console & Bing's upload
keeps it (search/api.py google_key: google.check_key, then google.compact into
the secrets file, 0600). Answers {"ok": true, "client_email"}: the robot's
address, never the key.

Refused: no search job on the line (403); the line's maker is no longer an
install admin (403: the key serves every site of the install, and only an
install admin may set it); a key already there (409: Skald never replaces a
working key from a code; the answer names its robot address, which is what
the user adds in Search Console); not a service-account key (400, in plain
words, never echoing it); an expired or cancelled code (410). Each kept key
writes one audit row, search.key, actor "ai-agent", with the link id and the
robot's address; the key is never logged or kept anywhere else.
"""
from __future__ import annotations

import hmac
import sqlite3
import sys
from pathlib import Path

from . import agent, agent_jobs, link

MOST = 8192                    # a service-account key file is about 2.4 KB
ACTOR = "ai-agent"


def _no(h, code: int, error: str, **more) -> None:
    agent._json(h, code, {"ok": False, "error": error, **more})


def _body(h) -> tuple[str | None, tuple[int, str] | None]:
    try:
        length = int(h.headers.get("Content-Length") or -1)
    except ValueError:
        length = -1
    if length < 0:
        return None, (411, "Send the key file with a Content-Length (curl --data-binary @-).")
    if length > MOST:
        return None, (413, "The request is at most 8 KiB: send only the key file.")
    try:
        return h.rfile.read(length).decode("utf-8"), None
    except UnicodeDecodeError:
        return None, (400, "The key file is not text. Send the .json key file.")


def _accounts(config: dict, folder):
    from ..accounts import db as base
    path = base.path_for(config, Path(folder))
    return base.connect(path) if path is not None and Path(path).is_file() else None


def install_admin(config: dict, folder, who) -> bool:
    """The line's maker may set an install-level key: the server ("cli"), or
    a person who is still an enabled install admin."""
    who = str(who or "")
    if who == "cli":
        return True
    if not who.isdigit():
        return False
    db = _accounts(config, folder)
    if db is None:
        return False
    try:
        row = db.execute("SELECT install_admin, disabled_at FROM users WHERE id = ?",
                         (int(who),)).fetchone()
    finally:
        db.close()
    return row is not None and bool(row[0]) and not row[1]


def answer(h, folder, code: str, config: dict | None) -> None:
    if not (h.headers.get("User-Agent") or "").lower().startswith(link.AGENTS):
        return _no(h, 403, "Send this with curl in a shell, the key file from stdin; never with "
                           "a web reader or fetch tool. Nothing was kept.")
    raw, why = _body(h)
    if why:
        return _no(h, *why)
    entry = agent.find(folder, code)
    if entry is None:
        return _no(h, 404, agent.UNKNOWN.strip())
    key = (h.headers.get(agent.REPORT_HEADER) or "").strip()
    want = entry.get("report_key") or ""
    if not key or not want or not hmac.compare_digest(agent._key_hash(key), want):
        return _no(h, 403, f"Send the {agent.REPORT_HEADER} header with SKALD_REPORT_KEY from "
                           "the keys file.")
    if agent.ended(entry):
        return _no(h, 410, "This code has expired or was cancelled.")
    if "search" not in agent_jobs.of(entry):
        return _no(h, 403, "This line has no search job, so it cannot set a Search Console key.")
    if config is None:
        return _no(h, 503, "A search key cannot be set through this server. Ask the user to "
                           "upload it in Skald (Settings > Leads & integrations > Search Console & Bing).")
    return _keep(h, folder, code, entry, raw, config)


def _keep(h, folder, code: str, entry: dict, raw: str, config: dict) -> None:
    from ..conversions import secrets_store
    from ..search import google
    from ..settings_store import secrets_path
    if not install_admin(config, folder, entry.get("made_by")):
        return _no(h, 403, "The key serves every site of this Skald, so only an install admin "
                           "may set it, and this line was not made by one. Tell the user: whoever "
                           "runs their Skald uploads it in Settings > Leads & integrations > Search Console & Bing.")
    have = google.key_state(config, folder)
    if have.get("set"):
        return _no(h, 409, "Skald has a Search Console key already, so it keeps that one. Ask "
                           "the user to add its robot address in Search Console (Settings > "
                           "Users and permissions > Add user, Restricted).",
                   client_email=have.get("client_email"))
    try:
        info = google.check_key(raw)
    except google.BadKey as no:
        return _no(h, 400, str(no))
    path = secrets_path(config, folder)
    if path is None:
        return _no(h, 503, "Skald's server has no secrets file. Ask whoever runs it.")
    try:
        secrets_store.put(path, google.SECRET, google.compact(raw))
    except secrets_store.Exposed:
        return _no(h, 500, "Skald's secrets file is not private on its server, so nothing was "
                           "kept. Ask whoever runs the user's Skald to fix it.")
    _audit(config, folder, entry["site"],
           f"service account {info['client_email']} uploaded (AI agent set-up, link "
           f"{agent.link_id(code)}, for {entry['site']})")
    return agent._json(h, 200, {"ok": True, "client_email": info["client_email"]})


def _audit(config: dict, folder, site: str, detail: str) -> None:
    """One audit row (never the key). A failure is one line on stderr."""
    from ..accounts import auditlog
    from ..accounts.orgs import org_of_site
    try:
        db = _accounts(config, folder)
        if db is None:
            return
        try:
            org = org_of_site(db, site)
            auditlog.record(db, org["id"] if org else None, ACTOR, "search.key", "google", detail)
        finally:
            db.close()
    except (sqlite3.Error, OSError) as why:
        print(f"kit searchkey: the audit row for {site} could not be written "
              f"({type(why).__name__})", file=sys.stderr)
