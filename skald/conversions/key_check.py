"""Check a key when it is saved, and take in the deliveries it opens (2.45).

After Settings > Leads & tools saves a hook's key (integrations/hooks/paste,
integrations/secret: make or rotate), check() reads every delivery of that
hook held after a refusal (held.py) and verifies each with the new key, by
the tool's own adapter (adapters/*.verify). The usual time check is replaced:
the delivery must have come within the last 24 hours (held.KEEP), and a signed
time (Calendly's, Stripe's, Skald's own `t=`; HubSpot's timestamp) must be
within 5 minutes of when it came, so the adapter is asked with "now" set to
that moment.

One that matches goes through the receiver's normal road (hooks.Receiver.
process with held_at): the spool line (marked "held"), the adapter's records,
the de-duplication by external ref and stage, the site's event-type filter,
a lead's own `test`, and the store, kept with the time it first came. Its
delivery row is `accepted_held` (roads.ACCEPTED: counted like a delivery
accepted on arrival). Then it leaves the hold. One the store could not keep
(an error) goes back into the hold for the next save. A second save finds
nothing more to take: what was taken is gone from the hold, and a delivery
that came twice is kept once (the store's own de-duplication).

The answer (the paste and secret routes' `check`):

    {held, matched, taken, recorded, refused_last_at, unsigned, verdict}

  held             deliveries waiting when the key was saved (within 24 h)
  matched          of them, those the new key verifies
  taken            of those, the ones taken in (accepted_held rows written)
  recorded         new conversion rows they made (a repeat makes none)
  refused_last_at  the newest refusal for the key (unsigned or bad_signature)
                   in the delivery log, or null
  unsigned         a held delivery came with no signature at all (or, none
                   held, the newest refusal was `unsigned`): no key can match,
                   the tool's webhook must be made again with Skald's key
  verdict          "matches" (some matched), "no_match" (some signed, none
                   matched), "unsigned" (every one held was unsigned),
                   "none_held" (nothing waiting)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from . import held, roads, store
from .adapters import adapter, signed


def check(config: dict, folder, config_path, site: str, tool: str, secret: str,
          now: float | None = None) -> dict:
    """Verify the hook's held deliveries with `secret`, take in the ones that
    match, and say what happened. Purges what is past 24 hours first."""
    from . import hooks
    now = time.time() if now is None else now
    folder = Path(folder)
    keeps = held.keeps(config, folder, site)
    held.purge(folder, now, site, tool, keeps=keeps)
    waiting = held.entries(folder, site, tool, now, keeps=keeps)
    mod = adapter(tool)
    rx = hooks.receiver(config, folder, config_path)
    if site not in rx.sites:
        rx._load_sites()
    matched = taken = recorded = no_signature = 0
    for entry in waiting:
        if not signed(tool, entry["headers"]):
            no_signature += 1
            continue
        if not secret or not mod.verify(entry["headers"], entry["body"], secret,
                                        entry["received"]):
            continue
        matched += 1
        if site not in rx.sites:
            continue                     # not taken by this install: left to the hold
        claimed = held.claim(entry["path"])
        if claimed is None:
            continue                     # another save took it
        try:
            status, got = rx.process(site, tool, dict(entry["headers"]), entry["body"],
                                     secret, verified=True, held_at=entry["received_at"])
        except Exception as why:         # noqa: BLE001 - the delivery stays held
            sys.stderr.write(f"hooks: {site}/{tool}: a held delivery could not be taken in "
                             f"({type(why).__name__})\n")
            status, got = 500, {}
        if status >= 500:
            held.release(claimed)
            continue
        held.drop(claimed)
        if got.get("outcome") == hooks.HELD:
            taken += 1
            recorded += int(got.get("recorded") or 0)
    path = store.path_for(config, folder)
    db = store.connect(path) if path is not None and Path(path).exists() else None
    try:
        last_at = roads.refused_last_at(db, site, tool)
        last = roads.last_refusal(db, site, tool)
    finally:
        if db is not None:
            db.close()
    if not waiting:
        verdict = "none_held"
    elif matched:
        verdict = "matches"
    elif no_signature == len(waiting):
        verdict = "unsigned"
    else:
        verdict = "no_match"
    return {"held": len(waiting), "matched": matched, "taken": taken, "recorded": recorded,
            "refused_last_at": last_at,
            "unsigned": bool(no_signature) or (not waiting and last == "unsigned"),
            "verdict": verdict}
