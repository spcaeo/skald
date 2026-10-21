"""security.json: Security's days for the dashboard (docs/DATA-CONTRACT-SECURITY.md).

Every stored day of the page's 180 with its state and its `security` blob
(security.py), or null when the day kind was not counted ("not recorded",
never 0), and today so far from the live snapshot. The suspect rows (`who`)
are kept in the file for the last WHO_DAYS days only, to keep it small; older
days carry their totals, and say so (`who_kept`: false). The page sums the
chosen period's days itself.

No address is in it. The addresses behind the rows come from the helper's
`people/security`, for owners and admins (security_kept.py).
"""
from __future__ import annotations

from datetime import timedelta

from . import security_names as N

WHO_DAYS = 31


def _lite(blob: dict | None, who: bool, site: str = "") -> dict | None:
    if blob is None:
        return None
    from .security_notify import item_id
    out = dict(blob)
    ex = dict(out.get("exposure") or {})
    ex["rows"] = [{**r, "item": item_id("exposure", site, r["host"], r["path"])}
                  for r in ex.get("rows") or []]
    out["exposure"] = ex
    if not who:
        out.pop("who", None)
    out["who_kept"] = who
    return out


def build(p) -> dict:
    from .people import policy
    from .requests_feed import settings as feed
    from . import alerts_security
    if p.view is not None:
        return {"whole_site_only": True}
    stored = p.history.extras(p.key, p.first, p.anchor, ("security",))
    since = p.anchor - timedelta(days=WHO_DAYS - 1)
    days = []
    for e in p.daily:
        row = p.day_entry(e)
        if p.has_figures(e):
            blob = (stored.get(row["day"]) or {}).get("security")
            row["security"] = _lite(blob, e["day"] >= since, p.site)
        days.append(row)
    today = p.today_block()
    if today is not None and p.live_ok:
        today["security"] = _lite((p.snap.get("extras") or {}).get("security"), True, p.site)
    folder = p.live_dir if p.live_dir is not None else None
    try:
        mode = policy.ip_mode(p.config, folder)
    except Exception:                    # noqa: BLE001 - said as unknown, never guessed
        mode = None
    from . import stack, advisories
    got = stack.latest(p.live_dir, p.site) if p.live_dir is not None else None
    stack_part = None
    if got is not None:
        day, blob = got
        doc = advisories.load(p.live_dir)
        from .security_notify import item_id
        read = dict(blob.get("read") or {})
        read["matches"] = [{**m, "item": item_id("advisory", p.site, m["advisory"], m["host"],
                                                 m["product"])} for m in read.get("matches") or []]
        used = {m["advisory"] for m in read["matches"]}
        stack_part = {"day": day, "checked_at": blob.get("checked_at"), "hosts": [
            {k: h.get(k) for k in ("host", "role", "error", "login", "login_error")}
            for h in blob.get("hosts") or []], **read,
            "advisories": [a for a in doc.get("advisories") or [] if a["id"] in used],
            "list_updated": blob.get("advisories"), "commands": stack.COMMANDS,
            "names": stack.NAMES}
    return {"stack": stack_part,
            "rules": N.settings(p.config),
            "categories": dict(N.CATEGORY_NAMES), "injection": dict(N.INJECTION_NAMES),
            "privacy": {"ip_mode": mode, "keep_days": policy.keep_days(p.config)},
            "requests_hours": feed(p.config)[0], "who_days": WHO_DAYS,
            "alerts": alerts_security.rules(alerts_security.settings(p.config)),
            "days": days, "today": today}
