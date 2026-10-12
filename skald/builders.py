"""One failing data file must not stop the redraw.

The dashboard's data files fall in two kinds. The core ones - overview,
live, visits, hourly, breakdowns, health, ours, quality - carry the
verified figures every page starts from; an error there stops the run, as
it always did, so a broken figure is never drawn as if it were whole.
Every other file (bots, robots, speed, funnels, leads, events, the cubes,
page lifecycle, ...) is optional: when its builder raises, that one file is
written as

    {"state": "error", "error": "<short message>", "generated_at": ...}

with the usual envelope, everything else is written as normal, and the
failure is kept in `builder-errors.json` beside the history: which file,
the message, since when. quality.json lists them (`builders_failing`) so the
data-quality panel can show it. The traceback goes to the run's log once,
when a file starts failing or its error changes - not every 2 minutes.
"""
from __future__ import annotations

import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

from .files import write_atomic

CORE = frozenset({"overview", "live", "visits", "hourly", "breakdowns", "health", "ours",
                  "quality"})
STATE = "builder-errors.json"


def short(why: BaseException) -> str:
    text = " ".join(f"{type(why).__name__}: {why}".split())
    return text[:200]


class Failures:
    """This run's failures, merged into the state file beside the history."""

    def __init__(self, directory: Path | None) -> None:
        self.directory = Path(directory) if directory is not None else None
        self.now: dict[str, str] = {}           # name -> message, this run
        self.ok: set[str] = set()                # names built fine in this run
        self.stored = self._load()

    def _load(self) -> dict:
        if self.directory is None:
            return {}
        try:
            got = json.loads((self.directory / STATE).read_text())
        except (OSError, ValueError):
            return {}
        return got if isinstance(got, dict) else {}

    def failed(self, name: str, why: BaseException) -> str:
        message = short(why)
        self.now[name] = message
        old = self.stored.get(name) or {}
        if old.get("error") != message:          # new, or a different error: say it once
            sys.stderr.write(f"data file {name}.json failed, written as an error:\n")
            traceback.print_exception(why, file=sys.stderr)
        return message

    def built(self, name: str) -> None:
        self.ok.add(name)

    def listing(self, now: datetime | None = None) -> list[dict]:
        """What quality.json shows: [{"file","error","since"}], this run's view."""
        at = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
        out = []
        for name, message in sorted(self.now.items()):
            old = self.stored.get(name) or {}
            since = old.get("since") if old.get("error") == message else at
            out.append({"file": f"{name}.json", "error": message, "since": since})
        return out

    def save(self) -> None:
        """Keep failing files (with since); forget the ones built fine."""
        if self.directory is None:
            return
        state = {k: v for k, v in self.stored.items() if k not in self.ok}
        for row in self.listing():
            state[row["file"][:-5]] = {"error": row["error"], "since": row["since"]}
        if state == self.stored:
            return
        try:
            write_atomic(self.directory / STATE, json.dumps(state, indent=1, sort_keys=True) + "\n")
        except OSError:
            pass
        self.stored = state


def build_one(name: str, builder, page, failures: Failures | None) -> dict:
    """The body for one data file: strict for a core file, guarded otherwise."""
    if name in CORE or failures is None:
        body = builder(page)
        if failures is not None:
            failures.built(name)
        return body
    try:
        body = builder(page)
    except Exception as why:            # noqa: BLE001 - one optional file, never the redraw
        return {"state": "error", "error": failures.failed(name, why)}
    failures.built(name)
    return body
