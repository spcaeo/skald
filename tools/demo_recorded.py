"""Recorded journeys in the demo (tools/demo.py): a few sessions the demo site "sent
itself" after its visitors agreed to analytics, so Traffic › Visitors shows the
Recorded by your site card and a session's drawer (rj=<ref>).

They go in through the real road: a made-up journey secret in the install's
secrets file, each event signed and posted to the journey receiver
(recorded/receive.py) with its clock set to the event's time, kept by the real
store (recorded/store.py). Then the helper's own answers (journeys_api.listing and
one_session, as a member who is not an admin sees them: no address, no email) are
written beside the page as data/demo/recorded-*.json, for the periods the page
offers (today, yesterday, 7, 30 and 90 days, all time). Each listing's figures are
recounted from the raw events by audit_journeys, as on a live install; a period that
does not match stops the build.

Sample data only: example.com pages, example.org referrers, consent given on every
event, no address and no email sent."""
from __future__ import annotations

import json
import uuid as uuidlib
from datetime import date, datetime, timedelta
from pathlib import Path

SITE = "example.com"
NOTICE = "2026-09"
# (minutes before the demo's clock, visitor, touch, [(seconds in, event, path, label)])
SESSIONS = [
    (4 * 1440 + 200, 1, {"landing_path": "/", "referrer": {"host": "news.example.org", "path": "/weekly"}},
     [(0, "page_view", "/", None), (40, "page_view", "/features/", None),
      (150, "page_view", "/pricing/", None), (190, "cta_click", "/pricing/", "Compare plans")]),
    (2 * 1440 + 310, 2, {"landing_path": "/blog/server-logs-vs-tags", "utm_source": "newsletter",
                         "utm_medium": "email", "utm_campaign": "fall-launch"},
     [(0, "page_view", "/blog/server-logs-vs-tags", None), (95, "page_view", "/guides/getting-started", None),
      (260, "download", "/guides/getting-started", "Setup checklist (PDF)")]),
    (1440 + 125, 1, {"landing_path": "/pricing/", "utm_source": "google", "utm_medium": "cpc",
                     "utm_campaign": "spring"},
     [(0, "page_view", "/pricing/", None), (55, "page_view", "/signup/", None),
      (140, "form_sent", "/signup/", "Trial form"), (150, "signup", "/signup/", "Free trial")]),
    (1440 + 40, 3, {"landing_path": "/customers/"},
     [(0, "page_view", "/customers/", None)]),
    (95, 4, {"landing_path": "/", "referrer": {"host": "www.example.net", "path": "/tools"}},
     [(0, "page_view", "/", None), (35, "page_view", "/book-a-demo/", None),
      (70, "booking_opened", "/book-a-demo/", "Demo call"), (230, "booking_made", "/book-a-demo/", "Demo call")]),
]


def _id(*parts) -> str:
    """A made-up, repeatable UUID (version 4 shape, as a browser would make)."""
    raw = uuidlib.uuid5(uuidlib.NAMESPACE_URL, "skald-demo-journeys/" + "/".join(map(str, parts))).hex
    return f"{raw[:8]}-{raw[8:12]}-4{raw[13:16]}-8{raw[17:20]}-{raw[20:32]}"


def events(now: datetime) -> list[dict]:
    """Every event of SESSIONS, in time order, as the site's relay would send it."""
    out = []
    stamp = lambda t: t.strftime("%Y-%m-%dT%H:%M:%SZ")
    for n, (ago, who, touch, steps) in enumerate(SESSIONS):
        start = (now - timedelta(minutes=ago)).replace(microsecond=0)
        base = {"schema_version": 1, "visitor_id": _id("visitor", who), "session_id": _id("session", n),
                "consent": {"analytics": "granted", "notice_version": NOTICE}}
        out.append({**base, "event_id": _id("event", n, "start"), "event_name": "session_started",
                    "occurred_at": stamp(start), "path": touch["landing_path"], "touch": touch})
        for k, (sec, name, path, label) in enumerate(steps):
            ev = {**base, "event_id": _id("event", n, k), "event_name": name,
                  "occurred_at": stamp(start + timedelta(seconds=sec)), "path": path}
            if label:
                ev["label"] = label
            out.append(ev)
    return sorted(out, key=lambda e: e["occurred_at"])


def seed(root: Path, cfgp: Path, cfg: dict, now: datetime, say=print) -> int:
    """Sign and post every event to the journey receiver; returns how many were kept."""
    from conversions_support import FakeHandler
    from skald.conversions import secrets_store
    from skald.recorded import TOOL, receive
    secret = "demo-journey-" + _id("secret").replace("-", "")        # made up, local
    secrets_store.put(secrets_store.path_for(cfg, root), secrets_store.key(SITE, TOOL), secret)
    kept = 0
    for ev in events(now):
        at = datetime.fromisoformat(ev["occurred_at"].replace("Z", "+00:00")).timestamp() + 2
        body = json.dumps(ev).encode()
        stamp = str(int(at))
        headers = {"Content-Type": "application/json", "X-Skald-Timestamp": stamp,
                   "X-Skald-Signature": receive.sign(secret, stamp, body)}
        status, got, _ = receive.answer(FakeHandler(f"/traffic-hooks/{SITE}/journey", body, headers),
                                        cfg, cfgp, clock=lambda at=at: at)
        if status != 201:
            raise SystemExit(f"demo: a recorded journey event was refused ({status}): {got}")
        kept += 1
    say(f"demo: {len(SESSIONS)} recorded sessions, {kept} events")
    return kept


class _Ctx:
    """What journeys_api's readers ask of their context, for a member who is not an admin."""

    def __init__(self, cfg: dict, root: Path):
        from skald.journeys_api import Ctx
        self.config, self.folder, self.site, self.admin = cfg, root, SITE, False
        self._store = Ctx.store

    def store(self):
        return self._store(self)

    def conf(self) -> dict:
        return self.config

    def ok(self, **body) -> dict:
        return {"ok": True, **body}

    def no(self, code: int, error: str, **extra) -> dict:
        return {"ok": False, "error": error, **extra}

    def log(self, *_args, **_kw) -> None:
        pass


def periods(site_dir: Path) -> list[tuple[str, str]]:
    """The Visitors tab's presets (state.js RANGES, data.js rangeOf): today, yesterday, 7, 30
    and 90 days to the last whole day, and all time (allTime: from the later of the first
    day the site has data and the first day the page holds)."""
    app = json.loads((site_dir / "data" / "app.json").read_text())
    today, anchor = date.fromisoformat(app["today"]), date.fromisoformat(app["anchor"])
    out = [(today, today), (today - timedelta(days=1), today - timedelta(days=1))]
    out += [(anchor - timedelta(days=k - 1), anchor) for k in (7, 30, 90)]
    begins = [app.get("firstDay")]
    try:
        conv = json.loads((site_dir / "data" / "conversions.json").read_text())
        if conv.get("available") and conv.get("since"):
            begins.append(conv["since"])
    except (OSError, ValueError):
        pass
    begins = sorted(b for b in begins if b)
    held = sorted(d["day"] for d in app.get("days") or [] if d.get("day"))
    if begins:
        first = begins[0]
        if held and first < held[0]:
            first = held[0]
        out.append((min(date.fromisoformat(first), anchor), anchor))
    return [(a.isoformat(), b.isoformat()) for a, b in dict.fromkeys(out)]


def answers(root: Path, site_dir: Path, cfg: dict) -> dict:
    """Writes the helper's answers; returns {helper path: file} for app.json's demo.api.recorded."""
    from skald.journeys_api import listing, one_session
    c = _Ctx(cfg, root)
    folder = site_dir / "data" / "demo"
    folder.mkdir(parents=True, exist_ok=True)
    out, refs = {}, set()
    for first, last in periods(site_dir):
        got = listing(c, {"first": first, "last": last})
        if not got.get("ok") or got.get("state") != "ok":
            raise SystemExit(f"demo: recorded journeys {first} to {last}: {got.get('why') or got.get('error')}")
        name = f"recorded-{first}-{last}.json"
        (folder / name).write_text(json.dumps(got, separators=(",", ":")))
        out[f"recorded?first={first}&last={last}"] = f"data/demo/{name}"
        refs |= {s["ref"] for s in got.get("sessions") or []}
    for ref in sorted(refs):
        got = one_session(c, {"ref": ref})
        if got.get("ok"):
            (folder / f"recorded-{ref}.json").write_text(json.dumps(got, separators=(",", ":")))
            out[f"recorded/session?ref={ref}"] = f"data/demo/recorded-{ref}.json"
    return out
