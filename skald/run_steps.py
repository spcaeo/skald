"""run-daily's step runner: each step while the one before returned 0, and the
steps of their own (AFTER_A_STOP) even after a stop (#3)."""
from __future__ import annotations

from typing import Callable


# Steps that do not rest on the day's log figures and never stop the run: they still run
# after a step stopped it (#3: a withheld log day skipped "events", so one site's 4 Nov
# in-page events were never stored). The mails, the dashboard (a failed day draws nothing;
# the live run draws it every few minutes) and anything counting the log day do not.
AFTER_A_STOP = ("events", "favicons", "logo", "updates", "stack", "kit tokens", "pagespeed")


def run_steps(steps: list[tuple[str, Callable[[], int]]], err=print,
              stopped: list | None = None) -> int:
    """Run each step while the previous one returned 0. The first failure
    stops the rest, but for AFTER_A_STOP's steps; its name goes into `stopped`
    when one is given, and its code is the run's."""
    code = 0
    for name, step in steps:
        if code:
            if name in AFTER_A_STOP:
                step()
            continue
        code = step()
        if code:
            err(f"run-daily stopped at '{name}' (exit {code}); later steps skipped "
                f"but {', '.join(n for n, _ in steps if n in AFTER_A_STOP) or 'none'}")
            if stopped is not None:
                stopped.append(name)
    return code
