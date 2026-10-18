"""The figures of one client report (client_reports.py), read from verified
history only, before any of it is drawn as mail (client_report_html.py) or
PDF (client_report_pdf.py) - so the two cannot disagree.

The rules every Skald report keeps:

  * a sum covers the period's verified, whole days only; a withheld day (its
    figures did not reconcile), a partial day and a day never collected are
    listed by date, drawn as gaps in the chart, and never counted as zero
  * the summed figures must pass verify.check, and the headline must match
    the second count of audit_client_reports.py (the stored days read again
    by another road); otherwise the report is refused, not sent smaller
  * a breakdown (sources, countries, cities) is shown only when every summed
    day recorded it; otherwise the section says so
  * a change against the period before is given only when both are whole
  * Search Console (when the site is connected, search/sync.py): its own
    figures for the period's days, final days only; a provisional day and a
    day not yet in Search Console are listed by date and never counted

Nothing is read for another site: every query names this report's site.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import date, timedelta

from .classify import AI_ASKED, Group
from .conversions_leads import LEAD_RULE
from .dimensions import OTHER
from .labels import shown
from .visits import assistant_label

ROWS = 8


class Refused(Exception):
    """The report cannot be honest for this period; the words say why."""


def _days(dates) -> list[str]:
    return [d.isoformat() for d in dates]


def _share(n: int, total: int) -> float | None:
    return n / total if total else None


def _ranked(counter, total: int, label=lambda x: x, n: int = ROWS, more=None) -> list[dict]:
    """The biggest rows; `more(name)` adds keys (a country's flag and full name)."""
    rows = []
    for name, count in Counter(counter or {}).most_common(n + 1):
        if name == OTHER or not count:
            continue
        rows.append({"name": label(name), "n": int(count), "share": _share(count, total),
                     **(more(name) if more else {})})
    return rows[:n]


def change(now, before) -> str | None:
    """"+12%", "-5%", "same", "new", or None (not comparable)."""
    if now is None or before is None:
        return None
    if before == 0:
        return "same" if now == 0 else "new"
    pct = (now - before) / before * 100
    return "same" if round(pct) == 0 else f"{'+' if pct > 0 else '-'}{abs(pct):.0f}%"


def _leads(config: dict, history, site: str, tz, first: date, last: date) -> dict | None:
    """The dashboard's leads (conversions_leads.period_leads: Overview's Leads tile),
    with a row per kind: None when the site records no conversions; a
    "not_recorded" state when the period starts before they were recorded."""
    from .conversions_leads import ACTION_WORDS, period_leads
    got = period_leads(config, history, site, tz, first, last)
    if got is None or got["state"] != "ok":
        return got
    total = got["total"]
    rows = sorted(got["by_action"].items(), key=lambda kv: (-kv[1], kv[0]))
    return {**got, "rows": [{"name": ACTION_WORDS.get(k, k.replace("_", " ").capitalize()),
                             "n": n, "share": _share(n, total)} for k, n in rows]}


def leads_missing(leads: dict | None) -> str:
    """Why the Leads section has no figures, or "" when it has them."""
    if leads is None:
        return ("Leads are not recorded for this site: no lead database, hook or script tag "
                "sends them (Settings > Integrations).")
    if leads.get("state") == "not_recorded":
        since = leads.get("since")
        return (f"Leads are recorded from {date.fromisoformat(since).day} "
                f"{date.fromisoformat(since):%b %Y}; this period starts before that, so no "
                f"sum is given." if since else "No lead has been recorded for this site yet.")
    return ""


def _returning(totals) -> int | None:
    got = getattr(totals, "returning", None)
    return int(got["returning"]) if got else None


def _headline(totals, leads: dict | None) -> dict:
    people = totals.groups.get(Group.PEOPLE)
    return {"visitors": people.readers if people else 0,
            "pages": people.views if people else 0,
            "ai": people.cited_visits if people else 0,
            "leads": leads["total"] if leads and leads.get("state") == "ok" else None,
            "returning": _returning(totals)}


def _ai(totals) -> dict:
    engines = totals.groups.get(Group.ANSWER_ENGINE)
    search = totals.groups.get(Group.SEARCH_ENGINE)
    bots = totals.groups.get(Group.BOTS)
    people = totals.groups.get(Group.PEOPLE)
    names, kinds = Counter(), {}
    if engines:
        names.update(engines.engines)
        kinds = {n: ("asked" if AI_ASKED.fullmatch(n) else "training") for n in names}
    if search:
        for n, c in search.engines.items():
            names[n] += c
            kinds.setdefault(n, "search")
    words = {"asked": "fetched because someone asked it", "training": "to train or index",
             "search": "search engine crawler"}
    return {"asked": int(engines.tiers.get("asked", 0)) if engines else 0,
            "training": int(engines.tiers.get("training", 0)) if engines else 0,
            "search": search.hits if search else 0,
            "bots": bots.hits if bots else 0,
            "crawlers": [{"name": n, "kind": words[kinds[n]], "n": int(c)}
                         for n, c in names.most_common(ROWS)],
            "cited_by": _ranked(people.cited_by if people else {},
                                people.cited_visits if people else 0, assistant_label)}


SC_ROWS = 10


def search_console(config: dict, history, site: str, first: date, last: date) -> dict:
    """The Search Console section: {"connected": None} when the site has no
    property; else the property, the period's final days summed (clicks,
    impressions, CTR, position; top queries and pages), and the days left
    out: "provisional" (Google may still change them) and "missing" (not
    synced yet). Search Console's days are Pacific Time, as Google gives
    them; the figures are Google's, never added to a Skald figure."""
    from .search.sync import google_property
    prop = google_property(config)
    if not prop:
        return {"connected": None}
    from .search import days as sd
    from .search.data import _sum_kind
    try:
        stored, finals = sd.read(history.db, site, "google", first, last,
                                 ("total", "query", "page"))
    except Exception:                   # noqa: BLE001 - an older history: no search_days
        stored, finals = {}, {}
    span = [(first + timedelta(days=i)).isoformat() for i in range((last - first).days + 1)]
    final = [d for d in span if d in stored and finals.get(d) and "total" in stored[d]]
    out = {"connected": prop, "final": final,
           "provisional": [d for d in span if d in stored and d not in final],
           "missing": [d for d in span if d not in stored],
           "totals": None, "queries": [], "pages": [],
           "unattributed_clicks": 0}

    def rows(kind):
        got = _sum_kind([stored[d][kind] for d in final if kind in stored[d]], SC_ROWS)
        return [{"name": r[0], "clicks": r[1], "impressions": r[2], "ctr": r[3],
                 "position": r[4]} for r in got["rows"]], got

    if final:
        out["totals"] = _sum_kind([stored[d]["total"] for d in final], 1)["total"]
        out["queries"], q = rows("query")
        out["pages"], _ = rows("page")
        out["unattributed_clicks"] = q["unattributed"]["clicks"] if q["rows"] else 0
    return out


# Places as the app shows them (js/tabs/readers.js): "USA", "Toronto, Ontario, CAN",
# with the flag and the full name kept apart ("flag", "title"): the mail draws the flag
# and puts the full name in a tooltip; the PDF (WinAnsi, no flags) and the text part
# show the name alone.
_CITY_CODE = re.compile(r", ([A-Z]{2})$")


def _country(code: str) -> str:
    from .countries import UNKNOWN, code3
    from .labels import shown
    return shown(UNKNOWN) if not code or code == UNKNOWN else code3(code) if len(code) == 2 else code


def _country_more(code: str) -> dict:
    from .countries import flag, name
    return {"flag": flag(code), "title": name(code)} if code and len(code) == 2 else {}


def _city(label: str) -> str:
    from .countries import code3
    from .labels import shown
    m = _CITY_CODE.search(label or "")
    return f"{label[:m.start()]}, {code3(m.group(1))}" if m else shown(label)


def _city_more(label: str) -> dict:
    from .countries import flag, name
    m = _CITY_CODE.search(label or "")
    return {"flag": flag(m.group(1)), "title": f"{label[:m.start()]}, {name(m.group(1))}"} if m else {}


def build(config: dict, history, site: str, spec: dict, first: date, last: date, tz,
          leads: dict | None = None, use_leads: bool = True) -> dict:
    """Everything the report shows, or Refused. `leads` may be passed in
    (tests); else read when the report has a leads section."""
    from .verify import check
    from . import audit_client_reports
    period = history.period(site, first, last)
    if not period.recorded:
        raise Refused(f"no verified whole day between {first} and {last}")
    problems = check(period.totals)
    if problems:
        raise Refused("the period's figures do not reconcile: "
                      + "; ".join(str(p) for p in problems))
    totals = period.totals
    people = totals.groups.get(Group.PEOPLE)
    sections = spec["sections"]
    if leads is None and use_leads and ("leads" in sections or "summary" in sections):
        leads = _leads(config, history, site, tz, first, last)
    head = _headline(totals, leads)
    daily = [{"day": e["day"].isoformat(), "state": e["state"],
              "visitors": e["groups"][Group.PEOPLE]["readers"]
              if e["state"] == "ok" else None} for e in history.daily(site, first, last)]
    # The period before, the same length: compared only when both are whole.
    span = (last - first).days + 1
    before = history.period(site, first - timedelta(days=span), first - timedelta(days=1))
    whole = period.complete and not period.partial
    prev = None
    if whole and before.complete and not before.partial and not check(before.totals):
        prev = _headline(before.totals, None)
    changes = {k: change(head[k], prev[k]) if prev else None
               for k in ("visitors", "pages", "ai", "returning")}
    by = (people.by or {}) if people and totals.breakdowns else {}
    readers = people.readers or 0 if people else 0
    data = {
        "site": site, "name": spec["name"], "first": first.isoformat(), "last": last.isoformat(),
        "days": span, "timezone": getattr(tz, "key", str(tz)),
        "coverage": {"recorded": len(period.recorded), "withheld": _days(period.withheld),
                     "partial": _days(period.partial),
                     "missing": [e["day"] for e in daily if e["state"] in ("missing", "before")]},
        "sections": list(sections), "headline": head, "changes": changes,
        "compared": prev is not None, "daily": daily,
        "breakdowns": bool(totals.breakdowns),
        "sources": _ranked(by.get("source"), readers, shown) if by else None,
        "pages": _ranked(people.pages if people else {}, people.views if people else 0, n=10),
        "countries": _ranked(by.get("country"), readers, _country, more=_country_more) if by else None,
        "cities": _ranked(by.get("city"), readers, _city, more=_city_more) if by.get("city") else None,
        "ai": _ai(totals), "leads": leads, "notes": spec.get("notes") or "",
        "footer": spec.get("footer") or "",
        "search_console": search_console(config, history, site, first, last)
        if "search_console" in sections else None,
    }
    from .conversions_leads import store_of
    found = audit_client_reports.recount(history.path, site, first, last, data)
    found += audit_client_reports.check_leads(store_of(config, history), site, first=first,
                                              last=last, tz=tz, leads=leads)
    if found:
        raise Refused("the report's figures do not match their second count: "
                      + "; ".join(found))
    return data


def period_words(first: str, last: str) -> str:
    a, b = date.fromisoformat(first), date.fromisoformat(last)
    if a == b:
        return f"{a.day} {a:%b %Y}"
    if a.year == b.year:
        left = f"{a.day} {a:%b}" if a.month != b.month else f"{a.day}"
        return f"{left} – {b.day} {b:%b %Y}"
    return f"{a.day} {a:%b %Y} – {b.day} {b:%b %Y}"


def coverage_lines(data: dict) -> list[str]:
    """The days the figures leave out, in words: one line each kind."""
    cov = data["coverage"]
    short = lambda days: ", ".join(f"{date.fromisoformat(d).day} {date.fromisoformat(d):%b}"
                                   for d in days)
    out = [f"{cov['recorded']} of {data['days']} days in the figures (verified, whole days)."]
    if cov["withheld"]:
        out.append(f"Withheld, not counted (the figures did not reconcile): {short(cov['withheld'])}.")
    if cov["partial"]:
        out.append(f"Partial, not counted (the logs did not cover the whole day): "
                   f"{short(cov['partial'])}.")
    if cov["missing"]:
        out.append(f"Not recorded: {short(cov['missing'])}.")
    return out


SC_NOTE = ("Google's own figures from Search Console, web results, days in Pacific Time; "
           "a click is not a visit, so they are never added to Skald's figures.")


def search_console_lines(sc: dict | None) -> list[str]:
    """The Search Console section's words: the headline (or why there is
    none), then the days left out. Shared by the mail, its text and the PDF."""
    if not sc or not sc.get("connected"):
        return ["Search Console is not connected for this site "
                "(Settings > Integrations > Search)."]
    short = lambda days: ", ".join(f"{date.fromisoformat(d).day} {date.fromisoformat(d):%b}"
                                   for d in days)
    t = sc.get("totals")
    if not t:
        out = ["No final Search Console day in this period yet: Google gives a day's "
               "figures two to three days later."]
    else:
        pos = t.get("position")
        out = [f"{num(t['clicks'])} clicks · {num(t['impressions'])} impressions · "
               f"CTR {pct(t.get('ctr')) or '—'} · average position "
               f"{'—' if pos is None else f'{pos:.1f}'}, over {len(sc['final'])} final days "
               f"({sc['connected']})."]
    if sc.get("provisional"):
        out.append(f"Provisional, not counted (Google may still change them): "
                   f"{short(sc['provisional'])}.")
    if sc.get("missing"):
        out.append(f"Not in Search Console yet: {short(sc['missing'])}.")
    return out


def pct(share) -> str:
    return "" if share is None else f"{share * 100:.0f}%" if share >= 0.01 else "<1%"


def num(v) -> str:
    return "—" if v is None else f"{int(v):,}"
