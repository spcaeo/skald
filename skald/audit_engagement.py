"""The audit's own count of engagement by source and device, and of
returning visitors by this visit's source (phase 4, lane B).

Part of the audit's second road (audit_more.py), written apart from
engagement.py, visits.py and visitors.py: each people visit audit.recount
splits from the raw lines is labelled by the audit's own labels of its
first page (audit_labels.py, handed over in `labels`), its pages are the
audit's page rule, its length is the span of its lines bucketed by
audit_visits._bucket, and its visitor hash is the audit's own
(audit_extras.keyed, over the first page's address and browser/system).
Nothing from dimensions.py, visits.py or visitors.py is called.

Compared with the stored day (or the live snapshot):
  engagement            every row of by_source and by_device, every field
  returning.by_source   readers and returning readers per source, against
                        the earlier days' hashes in visitor_days
                        (Recount.returning, called by audit._compare_extras,
                        which reads them)
"""
from __future__ import annotations

from collections import Counter

from .audit_extras import keyed, secret
from .audit_visits import _bucket

DIMS = (("by_source", "source"), ("by_device", "device"))
FIELDS = (("visits", "visits"), ("views", "pages loaded"), ("one_page", "one-page visits"))


class Recount:
    """One day's (or today's) engagement rows and visits by hash and source."""

    def __init__(self, config: dict, day, tz, own: set) -> None:
        self.rows: dict[str, dict] = {name: {} for name, _ in DIMS}
        self.key = secret(config)
        self.readers: Counter = Counter()        # (keyed hash, source) -> visits

    def visit(self, lines: list, is_page, labels: dict | None) -> None:
        if labels is None:
            return
        pages = [l for l in lines if is_page(l)]
        span = max(0, int((lines[-1].when - lines[0].when).total_seconds()))
        bucket = str(_bucket(span))
        for name, label in DIMS:
            row = self.rows[name].setdefault(labels[label], {"visits": 0, "views": 0,
                                                             "one_page": 0,
                                                             "seconds": Counter()})
            row["visits"] += 1
            row["views"] += len(pages)
            row["one_page"] += len(pages) == 1
            row["seconds"][bucket] += 1
        if self.key is not None:
            family = f"{labels['browser']}/{labels['os']}"
            self.readers[(keyed(self.key, pages[0].address, family), labels["source"])] += 1

    def compare(self, stored: dict, same, problems: list) -> None:
        blob = stored.get("engagement")
        if blob is None:
            return                               # not counted that day
        for name, label in DIMS:
            want, got = blob.get(name) or {}, self.rows[name]
            for key in sorted(set(want) | set(got)):
                w, g = want.get(key) or {}, got.get(key) or {}
                what = f"engagement by {label}: {key}"
                for field, words in FIELDS:
                    same(f"{what}: {words}", int(w.get(field, 0)), int(g.get(field, 0)))
                ws, gs = w.get("seconds") or {}, g.get("seconds") or Counter()
                for b in sorted(set(ws) | set(gs), key=int):
                    same(f"{what}: visits of {b} s", int(ws.get(b, 0)), int(gs.get(b, 0)))

    def returning(self, blob, earlier: set | None, same, problems: list) -> None:
        """The stored returning blob's by_source against the hashes: a visit
        is returning when its hash is on an earlier day within 30 days.
        `earlier` None: those hashes are pruned (audit.EXPIRED), so only the
        readers per source are compared."""
        if self.key is None or not isinstance(blob, dict) or blob.get("by_source") is None:
            return                               # no key, or not recorded that day
        counted: dict[str, Counter] = {}
        for (visitor, source), n in self.readers.items():
            row = counted.setdefault(source, Counter())
            row["readers"] += n
            row["returning"] += n if earlier is not None and visitor in earlier else 0
        want = blob["by_source"]
        fields = ("readers", "returning") if earlier is not None else ("readers",)
        for source in sorted(set(want) | set(counted)):
            w, g = want.get(source) or {}, counted.get(source) or Counter()
            for field in fields:
                same(f"returning by source: {source}: {field}", int(w.get(field, 0)),
                     int(g.get(field, 0)))

