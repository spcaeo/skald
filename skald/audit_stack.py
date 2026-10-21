"""The second count of Security > Your stack (stack.py, advisories.py).

Registered in audit_more.DAILY (`stack`): after the daily run's check, it reads the kept
check (stack-<site>.json beside the live files) and works out again, with its own code,
what stack.read stored from the kept evidence:

  products   from the Server, X-Powered-By, generator and markers kept for each host:
             nginx/openresty, Apache and LiteSpeed by the Server header's first word and
             its "/x.y.z"; PHP by "PHP" in X-Powered-By and its "PHP/x.y.z"; WordPress by
             a generator starting "WordPress" or its paths (and so PHP, version not
             shown); Next.js by X-Powered-By, the generator or its paths (and so Node.js)
  logins     open when the kept status of /wp-login.php is 2xx
  matches    each product against each advisory of the list the check names (the shipped
             list, or the kept newer copy), by splitting versions on dots, padding them to
             three numbers and comparing them as numbers

It shares with the main road only the advisories file (data, like a name list) and the
stored check. A problem never changes the check: the run's outcome says it differs.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ORDER = ("update_needed", "no_fix", "check_version", "fixed", "not_listed")


def set_up(ctx) -> bool:
    sec = ((getattr(ctx, "config", None) or {}).get("security") or {})
    return not (sec.get("stack_check") is False or str(sec.get("stack_check")).lower() == "false")


def _nums(text) -> list[int] | None:
    text = str(text or "").strip().lstrip("v")
    parts = []
    for bit in text.split("."):
        digits = ""
        for ch in bit:
            if not ch.isdigit():
                break
            digits += ch
        if not digits:
            break
        parts.append(int(digits))
        if len(digits) != len(bit):
            break
    return parts[:3] or None


def _pad(v: list[int]) -> list[int]:
    return (v + [0, 0, 0])[:3]


def state(adv: dict, shown) -> str:
    v = _nums(shown) if shown else None
    width = 2 if adv["branch"] == "minor" else 1
    if v is None or len(v) < width:
        return "check_version"
    mine = v[:width]
    table = {}
    for b, fix in adv["fixed"].items():
        table[tuple((_nums(b) or [])[:width])] = _pad(_nums(fix) or [])
    if tuple(mine) in table:
        return "fixed" if _pad(v) >= table[tuple(mine)] else "update_needed"
    floor = _nums(adv.get("no_fix_below"))
    if floor is not None and mine < floor[:width]:
        return "no_fix"
    if table and tuple(mine) < max(table):
        return "no_fix"
    return "not_listed"


def products(host: str, ev: dict) -> list[dict]:
    got = []
    server = (ev.get("server") or "").strip()
    first = server.split(" ")[0] if server else ""
    name, _, ver = first.partition("/")
    kind = {"nginx": "nginx", "openresty": "nginx", "apache": "apache",
            "litespeed": "litespeed"}.get(name.lower())
    if kind:
        got.append((kind, _clean(ver) if ver[:1].isdigit() else None))
    powered = ev.get("powered_by") or ""
    php = re.search(r"(?:^|[^A-Za-z0-9_])PHP/([0-9][0-9.]*)", powered, re.I)
    has_php = bool(php) or bool(re.search(r"(^|[^A-Za-z0-9_])PHP([^A-Za-z0-9_]|$)", powered, re.I))
    if has_php:
        got.append(("php", _clean(php.group(1)) if php else None))
    gen = (ev.get("generator") or "").strip()
    marks = set(ev.get("markers") or [])
    if gen.lower().startswith("wordpress") or marks & {"wp-content", "wp-includes", "wp-json link"}:
        words = gen.split()
        wv = words[1] if gen.lower().startswith("wordpress") and len(words) > 1 and \
            words[1][:1].isdigit() else None
        got.append(("wordpress", _clean(wv) if wv else None))
        if not php:
            got.append(("php", None))
    nx = re.search(r"Next\.js\s+([0-9.]+)", powered, re.I)
    nx_gen = gen.lower().startswith("next.js")
    if "next.js" in powered.lower() or nx_gen or marks & {"_next", "__NEXT_DATA__"}:
        nv = _clean(nx.group(1)) if nx else (_clean(gen.split()[1]) if nx_gen and len(gen.split()) > 1
                                             and gen.split()[1][:1].isdigit() else None)
        got.append(("nextjs", nv))
        got.append(("nodejs", None))
    out, seen = [], set()
    for product, ver in got:
        if product not in seen:
            seen.add(product)
            out.append({"product": product, "version": ver, "host": host})
    return out


def _clean(v):
    n = _nums(v)
    return ".".join(str(x) for x in n) if n else None


def recheck(blob: dict, doc: dict) -> list[str]:
    problems = []
    mine = []
    for h in blob.get("hosts") or []:
        if h.get("evidence"):
            mine += products(h["host"], h["evidence"])
    kept = (blob.get("read") or {})
    stored = [{"product": p["product"], "version": p["version"], "host": p["host"]}
              for p in kept.get("products") or []]
    key = lambda p: (p["host"], p["product"])  # noqa: E731
    if sorted(stored, key=key) != sorted(mine, key=key):
        problems.append(f"stack products: kept {len(stored)}, read again {len(mine)}, or a "
                        "version differs")
    logins = {h["host"]: (h.get("login") is not None and 200 <= int(h["login"]) <= 299)
              for h in blob.get("hosts") or [] if "login" in h}
    if {x["host"]: x["open"] for x in kept.get("logins") or []} != logins:
        problems.append("stack: the login pages' state differs")
    want = []
    for p in mine:
        for a in doc.get("advisories") or []:
            if a["product"] == p["product"]:
                want.append((a["id"], p["product"], p["host"], p["version"], state(a, p["version"])))
    have = [(m["advisory"], m["product"], m["host"], m["version"], m["state"])
            for m in kept.get("matches") or []]
    if sorted(have, key=str) != sorted(want, key=str):
        problems.append(f"stack advisories: kept {len(have)} matches, worked out {len(want)}, "
                        "or a state differs")
    return problems


def advisory_list(folder, updated) -> dict:
    """The list the check used: the shipped one, or the kept copy of that date."""
    ship = Path(__file__).resolve().parent / "data" / "advisories.json"
    for path in (Path(folder) / "advisories.json", ship):
        try:
            doc = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if doc.get("updated") == updated:
            return doc
    return json.loads(ship.read_text())


def daily(ctx, day) -> list[str] | None:
    safe = re.sub(r"[^a-z0-9.-]", "_", str(ctx.site).lower())
    try:
        days = json.loads((Path(ctx.live_dir) / f"stack-{safe}.json").read_text())["days"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not days:
        return None
    blob = days[max(days)]
    return recheck(blob, advisory_list(ctx.live_dir, blob.get("advisories")))
