"""The drill-down cube: readers' visits by country, landing page, source,
assistant and device, per day (cube.json).

History keeps each breakdown on its own (readers by country, by device, ...),
so "Canada AND mobile AND from ChatGPT" over 30 or 90 days was not in it.
This keeps, per day, one row per combination seen - from the day's journeys,
so it adds up to the day's visits - for as long as history keeps totals:

    [country, landing, source, assistant, device, visits]

`assistant` is the assistant's name when the source is "AI assistant", else
"". A day with more than CAP combinations keeps the CAP largest and folds
the rest into one row of "(all others)" in every field: its visits are real
(the sums still hold) but cannot be sliced, and the day says `folded`.

`check()` holds the sums: the rows add up to the visits, and while a day is
not folded each field's totals are exactly the readers breakdowns (country,
device, source and landing page), which verify and the audit already hold.
"""
from __future__ import annotations

from collections import Counter
from datetime import timedelta

DIMS = ("country", "landing", "source", "assistant", "device")
CAP = 300
OTHER = "(all others)"
DAYS = 90


def rows(journeys: list[dict], cap: int = CAP) -> dict:
    """{"rows": [[...labels, visits]], "folded": bool, "visits": int}."""
    combos: Counter = Counter()
    for j in journeys:
        source = j.get("source", "")
        combos[(j.get("country", ""), j.get("landing", ""), source,
                j.get("via", "") if source == "AI assistant" else "",
                j.get("device", ""))] += 1
    ordered = sorted(combos.items(), key=lambda kv: (-kv[1], kv[0]))
    kept, rest = ordered[:cap], ordered[cap:]
    out = [[*k, n] for k, n in kept]
    if rest:
        out.append([OTHER] * len(DIMS) + [sum(n for _, n in rest)])
    return {"rows": out, "folded": bool(rest), "visits": len(journeys)}


def marginals(blob: dict) -> dict[str, Counter]:
    """Each field's visits, from the rows."""
    out = {d: Counter() for d in DIMS}
    for row in blob.get("rows") or []:
        for i, d in enumerate(DIMS):
            out[d][row[i]] += row[-1]
    return out


# The readers breakdown each cube field must equal (aggregate.READER_DIMS).
SAME_AS = {"country": "country", "device": "device", "source": "source", "landing": "landing"}


def against(blob: dict, by: dict) -> list[str]:
    """Where the cube's fields disagree with readers breakdowns `by`
    ({dimension: {label: readers}}, possibly folded into "(all others)")."""
    if not blob or blob.get("folded"):
        return []
    found = []
    marg = marginals(blob)
    for field, dim in SAME_AS.items():
        stored = Counter(by.get(dim) or {})
        mine = marg[field]
        kept = [k for k in stored if k != OTHER]
        for label in kept:
            if stored[label] != mine.get(label, 0):
                found.append(f"cube {field} {label}: {mine.get(label, 0)} against "
                             f"{stored[label]} readers")
        rest = sum(mine.values()) - sum(mine.get(k, 0) for k in kept)
        if rest != stored.get(OTHER, 0):
            found.append(f"cube {field} (all others): {rest} against {stored.get(OTHER, 0)}")
    return found


def check(totals, blob: dict | None, differs, problems: list) -> None:
    from .classify import Group
    from .verify import Problem
    if blob is None:
        return
    stats = getattr(totals, "visits", None)
    if stats is not None:
        differs("cube rows", sum(r[-1] for r in blob.get("rows") or []), stats.visits, "visits")
    people = totals.groups.get(Group.PEOPLE)
    if people is not None and people.by:
        for why in against(blob, people.by):
            problems.append(Problem("drill-down cube", why))


# ------------------------------------------------- the compare report's cube

VISIT_DIMS = ("country", "landing", "source", "assistant", "device", "browser", "os",
              "campaign")
VISIT_CAP = 20_000


def visit_rows(counter: Counter) -> dict:
    """{"rows": [[...VISIT_DIMS labels, visits]], "visits": n} - every
    combination seen, biggest first (a safety cap of VISIT_CAP rows, the rest
    one "(all others)" row, `folded` then true)."""
    ordered = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
    kept, rest = ordered[:VISIT_CAP], ordered[VISIT_CAP:]
    rows = [[*k, n] for k, n in kept]
    if rest:
        rows.append([OTHER] * len(VISIT_DIMS) + [sum(n for _, n in rest)])
    return {"rows": rows, "visits": sum(counter.values()), "folded": bool(rest)}


VISIT_SAME_AS = {"country": "country", "landing": "landing", "source": "source",
                 "device": "device", "browser": "browser", "os": "os", "campaign": "campaign"}


def visit_check(totals, blob: dict | None, differs, problems: list) -> None:
    """Rows add up to the readers; each field to its readers breakdown."""
    from .classify import Group
    from .verify import Problem
    if blob is None:
        return
    people = totals.groups.get(Group.PEOPLE)
    readers = people.readers if people and people.readers is not None else 0
    differs("visit cube rows", sum(r[-1] for r in blob.get("rows") or []), readers, "readers")
    if blob.get("folded") or not people or not people.by:
        return
    for i, field in enumerate(VISIT_DIMS):
        dim = VISIT_SAME_AS.get(field)
        if dim is None:
            continue
        mine, stored = Counter(), Counter(people.by.get(dim) or {})
        if sum(stored.values()) != readers:
            continue                    # verify already says that breakdown is wrong
        for r in blob["rows"]:
            mine[r[i]] += r[-1]
        kept = [k for k in stored if k != OTHER]
        bad = [k for k in kept if stored[k] != mine.get(k, 0)]
        rest = sum(mine.values()) - sum(mine.get(k, 0) for k in kept)
        if bad or rest != stored.get(OTHER, 0):
            problems.append(Problem("visit cube", f"{field} differs from readers by {dim}: "
                                    + ", ".join(bad[:3] or ["(all others)"])))


# ---------------------------------------------------------------- cube.json

def build(p) -> dict:
    first = p.anchor - timedelta(days=DAYS - 1)
    extras = p.history.extras(p.key, first, p.anchor, ("cube",))
    days = []
    for e in p.daily:
        if e["day"] < first:
            continue
        row = p.day_entry(e)
        if p.has_figures(e):
            blob = (extras.get(e["day"].isoformat()) or {}).get("cube")
            row.update({"rows": blob.get("rows") if blob else None,
                        "folded": blob.get("folded") if blob else None})
        days.append(row)
    today = p.today_block()
    if today is not None:
        blob = ((p.snap.get("extras") or {}).get("cube")) if p.live_ok else None
        today.update({"rows": blob.get("rows") if blob else None,
                      "folded": blob.get("folded") if blob else None})
    return {"dims": [*DIMS, "visits"], "cap": CAP, "days_kept": DAYS,
            "days": days, "today": today}
