"""Second count of the visit records' combinations (SKALD-62): every reader's visit by all
its labels at once, as Traffic's shared filter and Compare read them (day_extras kind
`visit_cube`, compare.py).

audit_release2.compare_visit_cube already holds each field's totals (visitors by country,
by device, ...). Those can all be right while the combinations are wrong: swap the devices
of a US and an Indian visit and every total still matches, but "visitors from the USA on
mobile" does not. This recount labels each visit with the audit's own labels (audit.py
_reader, audit_labels.py; never dimensions.py) and holds every combination of country,
landing page, source, device, browser, system and campaign to the stored rows exactly.

The AI assistant field is left out: the audit labels a visit "AI assistant" by its source
but keeps no assistant name per visit; the stored rows are summed over it. A folded blob
(over cube.VISIT_CAP rows: its rest cannot be sliced) is not checked, as compare_visit_cube.
"""
from __future__ import annotations

from collections import Counter

# The stored row's fields, in order: country, landing, source, assistant, device, browser,
# os, campaign, then the visits (cube.VISIT_DIMS; DATA-CONTRACT-COMPARE.md).
FIELDS = ("country", "landing", "source", "device", "browser", "os", "campaign")
SHOWN = 20          # combinations that differ, named one by one; the rest as a count
AT = {"country": 0, "landing": 1, "source": 2, "device": 4, "browser": 5, "os": 6, "campaign": 7}


class Recount:
    def __init__(self, config: dict, day, tz, own: set) -> None:
        self.combos: Counter = Counter()

    def visit(self, lines: list, is_page, labels: dict | None) -> None:
        if labels is not None:
            self.combos[tuple(labels[f] for f in FIELDS)] += 1

    def compare(self, stored: dict, same, problems: list) -> None:
        blob = stored.get("visit_cube")
        if blob is None or blob.get("folded"):
            return
        kept: Counter = Counter()
        for row in blob.get("rows") or []:
            kept[tuple(row[AT[f]] for f in FIELDS)] += row[-1]
        keys = sorted(set(kept) | set(self.combos))
        differ = [k for k in keys if kept.get(k, 0) != self.combos.get(k, 0)]
        # One figure for the whole set (the audit's count does not grow by thousands a day), then
        # the first combinations that differ by name; one wrong field would fail many at once.
        same("visit records: combinations that match", len(keys), len(keys) - len(differ))
        for key in differ[:SHOWN]:
            same(f"visit records {' · '.join(key)}", kept.get(key, 0), self.combos.get(key, 0))
        if len(differ) > SHOWN:
            problems.append(f"visit records: {len(differ) - SHOWN} more combinations differ")
