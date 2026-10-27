"""The second road for the figures from your tools (yourtools/): every figure a
screen shows is read again from the tool's stored answer, by this file's own
code. It shares only the name lists in names.py with the code it checks; it
never imports an adapter, store.py or the sync.

A tool's figure is not Skald's count: it comes from the tool, like a booking
from a hook. So the audit cannot recount it from the log. What it checks, for
every answer kept in `yourtools.sqlite` (by its own SQL):

  1. the answer is the one stored: its text parses as JSON and its sha256 is
     the one written when it came (nothing changed it since);
  2. every figure, by the places it says it was read from (JSON pointers,
     RFC 6901, resolved here): the value at `src` is the figure's number (a
     figure with no `src` must be NULL: unknown, never 0), the text at
     `name_src` is the figure's name, the text at `dim_src` its row;
  3. Google Analytics answers (tool "ga4"), recounted whole: from the answer's
     own headers and rows, every metric of names.GA4_REPORTS the answer holds
     gives exactly one figure per row (and per total), and no figure is shown
     that the answer does not hold. A total GA4 did not give is NULL.
     Vercel (visits/count's two figures, each aggregate row's two), Calendly
     (names.py's CALENDLY_* counting rules over the meetings and invitees the
     answer holds) and Resend (contacts, each segment's, the emails' states) are
     recounted whole the same way. Calendly's and Resend's figures are counts of
     records, which no one place in the answer holds: for those two tools a
     figure without `src` is checked by this recount alone (COUNTED);
  4. webhook_match: the Calendly meetings the webhook also sent, by SQL over
     conversions.sqlite opened read-only (tool_calendly.webhook_line counts the
     same in Python; a difference withholds the line).

`check(history_folder, site, tool=None)` returns {tool: {"ok", "problems",
"answers", "figures", "checked"}}; the sync runs it after each sync and keeps
the result (conn.py `audit`), and a tool whose recheck fails has its figures
withheld on every screen. `skald tools audit` runs it by hand (exit 1 on a
mismatch).
"""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from pathlib import Path

from collections import Counter

from .names import CALENDLY_ACTIVE, CALENDLY_CANCELED, CALENDLY_COUNTS, GA4_REPORTS, NONE_DIM, \
    VERCEL_METRICS, VERCEL_REPORTS

FILE = "yourtools.sqlite"           # the store's file, named here on its own
MOST_SHOWN = 20                     # problems listed per tool


def _open(history_folder):
    path = Path(history_folder) / FILE
    if not path.is_file():
        return None
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=30)
    return db


def _resolve(doc, ref):
    """RFC 6901: the value at `ref` in `doc`, or KeyError."""
    if ref == "":
        return doc
    if not isinstance(ref, str) or not ref.startswith("/"):
        raise KeyError(ref)
    here = doc
    for raw in ref[1:].split("/"):
        part = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(here, list):
            if not part.isdigit() or int(part) >= len(here):
                raise KeyError(ref)
            here = here[int(part)]
        elif isinstance(here, dict):
            if part not in here:
                raise KeyError(ref)
            here = here[part]
        else:
            raise KeyError(ref)
    return here


def _number(raw):
    """A tool's number (a JSON number or a numeric string), or ValueError."""
    if isinstance(raw, bool):
        raise ValueError("a true/false is not a number")
    if isinstance(raw, (int, float)):
        got = raw
    elif isinstance(raw, str) and raw.strip():
        text = raw.strip()
        got = int(text) if text.lstrip("-").isdigit() else float(text)
    else:
        raise ValueError("not a number")
    if isinstance(got, float) and not math.isfinite(got):
        raise ValueError("not a finite number")
    return got


def _same(a, b) -> bool:
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, int) and isinstance(b, int):
        return a == b
    return abs(float(a) - float(b)) <= 1e-9 * max(1.0, abs(float(a)))


def _figures(db, answer_id: int) -> list[dict]:
    rows = db.execute("SELECT name, dim, value, src, name_src, dim_src, rank FROM figures "
                      "WHERE answer_id = ?", (answer_id,)).fetchall()
    return [dict(zip(("name", "dim", "value", "src", "name_src", "dim_src", "rank"), r))
            for r in rows]


def _by_pointer(body, fig: dict, where: str, problems: list, counted: bool = False) -> None:
    """Check 2: the figure as its pointers say. `counted`: the tool's figures are
    counts of its answer's records (no one place holds them), so a value with no
    `src` is the whole recount's to check (check 3), not a mismatch here."""
    label = f"{where} {fig['name']}{' / ' + str(fig['dim']) if fig['dim'] is not None else ''}"
    if fig["src"] is None:
        if fig["value"] is not None and not counted:
            problems.append(f"{label}: shown as {fig['value']} with no place in the answer")
    else:
        try:
            got = _number(_resolve(body, fig["src"]))
        except (KeyError, ValueError, OverflowError) as why:
            problems.append(f"{label}: its value cannot be read again ({type(why).__name__})")
        else:
            if not _same(got, fig["value"]):
                problems.append(f"{label}: shown {fig['value']}, the answer says {got}")
    for key, want in (("name_src", fig["name"]), ("dim_src", fig["dim"])):
        if fig[key] is None:
            continue
        try:
            got = _resolve(body, fig[key])
        except KeyError:
            problems.append(f"{label}: {key} points nowhere in the answer")
            continue
        if str(got) != str(want):
            problems.append(f"{label}: shown as {want!r}, the answer says {got!r}")


def _ga4(body: dict, report: str, figs: list[dict], where: str, problems: list) -> None:
    """Check 3: GA4's answer recounted whole, by its own reading of runReport."""
    if report not in GA4_REPORTS:
        problems.append(f"{where}: Skald never asks GA4 for a {report!r} report")
        return
    dims, metrics = GA4_REPORTS[report]
    heads = [str((m or {}).get("name") or "") for m in body.get("metricHeaders") or []]
    names = [str((d or {}).get("name") or "") for d in body.get("dimensionHeaders") or []]
    if names and tuple(names) != tuple(dims):
        problems.append(f"{where}: GA4 answered for {names}, Skald asked for {list(dims)}")
    want: dict = {}
    for i, metric in enumerate(heads):
        if metric not in metrics:
            continue
        if not dims:
            rows = body.get("rows") or []
            want[(metric, None)] = _number((rows[0].get("metricValues") or [])[i]
                                           .get("value")) if rows else None
            continue
        for row in body.get("rows") or []:
            dim = str(((row.get("dimensionValues") or [{}])[0] or {}).get("value"))
            want[(metric, dim)] = _number(((row.get("metricValues") or [])[i] or {}).get("value"))
        totals = body.get("totals") or []
        tot = (totals[0].get("metricValues") or []) if totals else []
        want[(metric, None)] = _number((tot[i] or {}).get("value")) if i < len(tot) else None
    for metric in metrics:                    # asked, but not in GA4's headers: unknown
        if metric not in heads:
            want[(metric, None)] = None
    have = {(f["name"], f["dim"]): f["value"] for f in figs}
    for key in sorted(set(want) | set(have), key=lambda k: (k[0], str(k[1]))):
        label = f"{where} {key[0]}{' / ' + key[1] if key[1] is not None else ''}"
        if key not in have:
            problems.append(f"{label}: GA4 gave {want[key]}, not shown")
        elif key not in want:
            problems.append(f"{label}: shown {have[key]}, not in GA4's answer")
        elif not _same(want[key], have[key]):
            problems.append(f"{label}: shown {have[key]}, GA4's answer says {want[key]}")


def _match(want: dict, figs: list[dict], where: str, problems: list, word: str) -> None:
    """Every figure (keyed name, row, place) against the recount: changed, missing
    or extra."""
    have = {(f["name"], f["dim"], f["rank"]): f["value"] for f in figs}
    for key in sorted(set(want) | set(have), key=lambda k: (k[0], str(k[1]), k[2] or -1)):
        label = f"{where} {key[0]}{' / ' + str(key[1]) if key[1] is not None else ''}"
        if key not in have:
            problems.append(f"{label}: {word} gave {want[key]}, not shown")
        elif key not in want:
            problems.append(f"{label}: shown {have[key]}, not in {word}'s answer")
        elif not _same(want[key], have[key]):
            problems.append(f"{label}: shown {have[key]}, {word}'s answer says {want[key]}")


def _vercel(body: dict, report: str, figs: list[dict], where: str, problems: list) -> None:
    """Vercel recounted whole: visits/count's two figures, or one figure per metric
    per row of visits/aggregate, the row named by the report's own dimension."""
    if report not in VERCEL_REPORTS:
        problems.append(f"{where}: Skald never asks Vercel for a {report!r} report")
        return
    dim, data, want = VERCEL_REPORTS[report], body.get("data"), {}
    if dim is None:
        for m in VERCEL_METRICS:
            raw = data.get(m)
            want[(m, None, None)] = None if raw is None else _number(raw)
    else:
        for i, row in enumerate(data):
            name = row.get(dim)
            name = NONE_DIM if name in (None, "") else str(name)
            for m in VERCEL_METRICS:
                want[(m, name, i)] = None if row.get(m) is None else _number(row[m])
    _match(want, figs, where, problems, "Vercel")


def _utc(text):
    from datetime import datetime, timezone
    raw = str(text or "").replace("Z", "+00:00")
    try:
        got = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return got if got.tzinfo else got.replace(tzinfo=timezone.utc)


def _calendly(body: dict, report: str, figs: list[dict], where: str, problems: list) -> None:
    """Calendly recounted whole by names.py's rules, from the meetings and invitees
    the answer holds."""
    from datetime import timedelta
    if report != "totals":
        problems.append(f"{where}: Skald never asks Calendly for a {report!r} report")
        return
    meetings = list(body.get("events") or [])
    asked = _utc(body.get("asked_at"))
    want: dict = {}
    if not body.get("complete") or asked is None:
        for n in CALENDLY_COUNTS:
            want[(n, None, None)] = None
        _match(want, figs, where, problems, "Calendly")
        return
    midnight = asked.replace(hour=0, minute=0, second=0, microsecond=0)
    status = Counter(m.get("status") for m in meetings)
    before = [m for m in meetings if m.get("status") == CALENDLY_ACTIVE
              and _utc(m.get("start_time")) is not None and _utc(m.get("start_time")) < asked]
    later = [m for m in meetings if m.get("status") == CALENDLY_ACTIVE and m not in before]
    made = Counter()
    for m in meetings:
        t = _utc(m.get("created_at"))
        if t is None:
            continue
        age = (midnight - t) / timedelta(days=1)
        if 0 < age <= 7:
            made["booked_7d"] += 1
        elif 7 < age <= 14:
            made["booked_prev_7d"] += 1
    gone = {m.get("uri") for m in before}
    shows = None
    if body.get("no_shows_complete") and gone.issubset(set(body.get("invitees_read") or ())):
        shows = len([p for p in body.get("invitees") or ()
                     if p.get("event") in gone and p.get("no_show")])
    want.update({("bookings", None, None): len(meetings), ("upcoming", None, None): len(later),
                 ("past", None, None): len(before),
                 ("canceled", None, None): status.get(CALENDLY_CANCELED, 0),
                 ("no_shows", None, None): shows,
                 ("booked_7d", None, None): made["booked_7d"],
                 ("booked_prev_7d", None, None): made["booked_prev_7d"]})
    kinds = Counter(m.get("name") or NONE_DIM for m in meetings)
    for rank, (name, n) in enumerate(sorted(kinds.items(), key=lambda x: (-x[1], x[0]))):
        want[("bookings", name, rank)] = n
    _match(want, figs, where, problems, "Calendly")


def _resend(body: dict, report: str, figs: list[dict], where: str, problems: list) -> None:
    """Resend recounted whole: its contacts, each segment's, and the emails' states."""
    want: dict = {}
    if report == "totals":
        whole = bool(body.get("complete"))
        people = body.get("contacts") or []
        flags = Counter(c.get("unsubscribed") for c in people)
        for n, v in (("contacts", len(people)), ("subscribed", flags.get(False, 0)),
                     ("unsubscribed", flags.get(True, 0))):
            want[(n, None, None)] = v if whole else None
    elif report == "segments":
        for i, s in enumerate(body.get("segments") or []):
            ids = s.get("contacts")
            want[("contacts", str(s.get("name") or NONE_DIM), i)] = \
                len(ids) if s.get("complete") and isinstance(ids, list) else None
    elif report == "emails":
        sent = body.get("emails") or []
        want[("emails", None, None)] = len(sent)
        states = Counter(str(e.get("last_event") or NONE_DIM) for e in sent)
        for rank, (state, n) in enumerate(sorted(states.items(), key=lambda x: (-x[1], x[0]))):
            want[("emails", state, rank)] = n
    else:
        problems.append(f"{where}: Skald never asks Resend for a {report!r} report")
        return
    _match(want, figs, where, problems, "Resend")


RECOUNTS = {"ga4": _ga4, "vercel": _vercel, "calendly": _calendly, "resend": _resend}
COUNTED = ("calendly", "resend")        # figures that are counts of the answer's records


def webhook_match(conv_path, site: str, uris) -> int | None:
    """How many of these Calendly meetings (their URIs) the Calendly webhook sent
    Skald: a conversions row of tool calendly whose reference is an invitee of the
    meeting ("<meeting URI>/invitees/..."), by SQL over the file opened read-only.
    None without the file."""
    path = Path(conv_path) if conv_path else None
    if path is None or not path.is_file():
        return None
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=30)
    try:
        found = 0
        for uri in dict.fromkeys(str(u) for u in uris):
            like = uri.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            found += db.execute("SELECT EXISTS (SELECT 1 FROM conversions WHERE site = ? AND "
                                "tool = 'calendly' AND external_ref LIKE ? ESCAPE '\\')",
                                (site, like + "/invitees/%")).fetchone()[0]
        return found
    finally:
        db.close()


def check(history_folder, site: str, tool: str | None = None) -> dict:
    """{tool: {"ok", "problems", "answers", "figures", "checked"}} for a site."""
    db = _open(history_folder)
    if db is None:
        return {}
    out: dict = {}
    try:
        sql = "SELECT id, tool, report, period, body, sha256 FROM answers WHERE site = ?"
        args: tuple = (site,)
        if tool:
            sql, args = sql + " AND tool = ?", (site, tool)
        for aid, name, report, period, text, sha in db.execute(sql + " ORDER BY id", args):
            part = out.setdefault(name, {"ok": True, "problems": [], "answers": 0,
                                         "figures": 0, "shas": []})
            part["answers"] += 1
            part["shas"].append(sha)
            where = f"{name} {report} {period}"
            problems = part["problems"]
            if hashlib.sha256(text.encode("utf-8")).hexdigest() != sha:
                problems.append(f"{where}: the stored answer changed since it came")
            try:
                body = json.loads(text)
            except ValueError:
                problems.append(f"{where}: the stored answer is not JSON")
                continue
            figs = _figures(db, aid)
            part["figures"] += len(figs)
            for fig in figs:
                _by_pointer(body, fig, where, problems, counted=name in COUNTED)
            if name in RECOUNTS and isinstance(body, dict):
                try:
                    RECOUNTS[name](body, report, figs, where, problems)
                except (ValueError, TypeError, AttributeError, IndexError) as why:
                    problems.append(f"{where}: the answer cannot be recounted "
                                    f"({type(why).__name__})")
    finally:
        db.close()
    for part in out.values():
        part["ok"] = not part["problems"]
        part["problems"] = part["problems"][:MOST_SHOWN]
        part["checked"] = hashlib.sha256("".join(part.pop("shas")).encode()).hexdigest()[:16]
    return out
