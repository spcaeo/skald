"""The second count of visits by the page they started on (day kind
`landings`, landings.py).

Registered in audit_more.RECOUNTS. Every people visit audit.recount splits
from the raw lines is counted here on its landing page, the audit's own label
of its first page view (audit_labels.py, handed over in `labels`), with:

  visits    one per visit
  one_page  the visit's page views, by the audit's own page rule, are one
  views     its page views
  search    its source, by the audit's own labels, is "Search engine"
  ai        its source is "AI assistant"

Nothing from landings.py, visits.py or dimensions.py is called; only the
source names are shared (the labels' own words). Compared with the stored
blob: every kept page field by field, the "(all others)" row against every
page it does not keep, and `folded` against how many those are.
"""
from __future__ import annotations

NAMES = ("visits", "one_page", "views", "search", "ai")
OTHER = "(all others)"


class Recount:
    def __init__(self, config, day, tz, own) -> None:
        self.rows: dict[str, list] = {}

    def visit(self, lines, is_page, labels) -> None:
        if labels is None:
            return
        seen = sum(1 for line in lines if is_page(line))
        row = self.rows.setdefault(labels["landing"], [0, 0, 0, 0, 0])
        row[0] += 1
        row[1] += seen == 1
        row[2] += seen
        row[3] += labels.get("source") == "Search engine"
        row[4] += labels.get("source") == "AI assistant"

    def compare(self, stored, same, problems) -> None:
        blob = stored.get("landings")
        if blob is None:
            return                      # not counted that day
        kept = {path: [int(x) for x in r] for path, r in (blob.get("pages") or {}).items()}
        for path in sorted(p for p in kept if p != OTHER):
            want, got = kept[path], self.rows.get(path) or [0] * 5
            for i, name in enumerate(NAMES):
                same(f"landings on {path}: {name}", want[i], got[i])
        rest = [r for path, r in self.rows.items() if path not in kept or path == OTHER]
        tail = kept.get(OTHER) or [0] * 5
        for i, name in enumerate(NAMES):
            same(f"landings on {OTHER}: {name}", tail[i], sum(r[i] for r in rest))
        same("landings: pages folded", int(blob.get("folded") or 0), len(rest))
