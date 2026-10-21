"""POST /traffic-hooks/<site>/leads/test: a site's server marks its own
leads as test (its team's accounts, a QA run), or takes the mark off, without
the server admin (2.19). The same mark as `skald conversions mark-test`:
the rows stay, are listed under "Left out" and are never counted.

Signed exactly like the lead POST (adapters/lead.py verify): the `lead`
hook's own secret, over the raw body, the same 5-minute window and
constant-time compare:

    X-Skald-Signature: t=<unix seconds>,v1=<hex HMAC-SHA256(secret, "<t>.<raw body>")>

Body: {"refs": ["L-1001", ...], "test": true}

    refs   1 to MAX_REFS external refs, each read as the lead body reads
           `external_ref` (text, trimmed, at most 120); a ref given twice
           counts once
    test   a JSON boolean, true when left out; false takes the mark off
    any other key is refused, so a misspelt `test` cannot mark by default

Only rows of that site that came through the `lead` tool, every stage of
each ref; marked rows are TEST_MARKED, so a later stage the site sends for
a marked ref is test too (store.record_conversion). Answer:

    {"ok": true, "test": true, "marked": <rows changed>,
     "already": <rows already so>, "not_found": [refs with no row]}

hooks.Receiver.mark answers it: 404 a site Skald does not measure, or no lead secret (the
same body), 411/413 as the POST, 401 a bad signature (the sender's pre-auth
bucket), 429 past `hooks.leads_per_minute` per site (a bucket apart from the
GET's), 400 a bad body. Each answered call writes one delivery row
(MARKED/UNMARKED, the counts, never a ref) and one audit-log entry (actor
ACTOR, the counts and the refs: the sender's own ids). The audit's cached
beacon days are dropped (audit_conversions.forget_cache), as the CLI does;
conversions.json and the second count read the store again on the next run.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from . import store
from .adapters import text

PATH = re.compile(r"^/traffic-hooks/([A-Za-z0-9][A-Za-z0-9._-]{0,99})/leads/test$")
TOOL = "lead"
MAX_REFS = 100
REF_LIMIT = 120                      # as adapters/lead.py reads external_ref
KEYS = ("refs", "test")
ACTOR = "hook:lead"
MARKED, UNMARKED = "marked_test", "unmarked_test"


class BadBody(ValueError):
    """A body the call refuses (400)."""


def site_of(path: str) -> str | None:
    found = PATH.match(path.split("?", 1)[0])
    return found.group(1) if found else None


def read_body(body: bytes) -> tuple[list[str], bool]:
    """(the refs, in order and once each; True to mark). Raises BadBody."""
    try:
        got = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise BadBody("not JSON") from None
    if not isinstance(got, dict):
        raise BadBody('the body is a JSON object: {"refs": [...], "test": true}')
    if any(k not in KEYS for k in got):
        raise BadBody(f"a key it does not take: the body takes only {' and '.join(KEYS)}")
    on = got.get("test", True)
    if not isinstance(on, bool):
        raise BadBody("test is true or false")
    raw = got.get("refs")
    if not isinstance(raw, list) or not raw:
        raise BadBody("refs is a list of 1 to 100 external refs")
    if len(raw) > MAX_REFS:
        raise BadBody(f"at most {MAX_REFS} refs in one call")
    refs: list[str] = []
    for item in raw:
        ref = text(item, REF_LIMIT)
        if not ref:
            raise BadBody("each ref is an external_ref: text, not empty")
        if ref not in refs:
            refs.append(ref)
    return refs, on


def apply(db_path: Path, site: str, refs: list[str], on: bool) -> dict:
    """Mark (or unmark) the refs; the answer's body. Writes the delivery
    row in the same transaction as the marks."""
    db = store.connect(db_path)
    try:
        with store.tx(db):
            got = store.mark_refs(db, site, TOOL, refs, on)
            store.log_delivery(db, site, TOOL, MARKED if on else UNMARKED, 200,
                               f"{len(refs)} ref(s): {got['changed']} row(s) changed, "
                               f"{got['already']} already, {len(got['not_found'])} not found")
    finally:
        db.close()
    return {"ok": True, "test": on, "marked": got["changed"], "already": got["already"],
            "not_found": got["not_found"]}


def audit_entry(config: dict, folder, action: str, site: str, detail: str,
                actor: str = "cli", key: str = "ids") -> None:
    """One audit entry: a row in the accounts audit log when there is one
    (its org from the site), else a line in privacy.log beside the history.
    `conversions mark-test` (actor "cli") and leads/test (ACTOR) write here."""
    from ..settings_store import accounts_file
    path = accounts_file(config, folder)
    if path is None:                     # basic mode: privacy.log beside the history
        from ..privacy import LOG
        log = Path(folder) / LOG
        with open(log, "a", encoding="utf-8") as handle:
            handle.write(f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} "
                         f"{action} site={site} {key}={detail[:400]} by={actor}\n")
        log.chmod(0o640)
        return
    from ..accounts import auditlog, connect
    db = connect(path)
    try:
        org = db.execute("SELECT org_id FROM sites WHERE name = ?", (site,)).fetchone()
        auditlog.record(db, org[0] if org else None, actor, action, site, detail[:500])
    finally:
        db.close()


def audit(config: dict, folder, site: str, refs: list[str], answer: dict) -> None:
    """The call's audit entry: who (ACTOR), how many rows, the refs."""
    on = answer["test"]
    detail = (f"{answer['marked']} row(s) {'marked' if on else 'unmarked'}, "
              f"{answer['already']} already, {len(answer['not_found'])} not found; "
              f"refs={','.join(refs)}")
    audit_entry(config, folder, "conversions.test" if on else "conversions.untest", site,
                detail, ACTOR, "detail")


def recount(folder) -> None:
    """After a mark: the audit's cached beacon days are counted again, as
    after `conversions mark-test` (the store itself is read on each run)."""
    from ..audit_conversions import forget_cache
    forget_cache(Path(folder))
