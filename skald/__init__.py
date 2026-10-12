"""skald: who actually visited a website, from its server logs.

Domain agnostic by construction - nothing here knows a product name. Point it
at an access log, say which hostnames are yours, and it reports five groups
that add up to the log exactly.

    from skald import analyse, as_text, as_html

Read SOP.md before changing the counting rules; COUNTING-TRAPS.md lists the
mistakes this package exists to prevent, each one taken from a real report
that went out wrong.
"""
from .aggregate import GroupStats, Totals, summarise
from .classify import Classifier, Group, Tier
from .parse import Hit, log_files, read
from .report import as_html, as_text
from .verify import Problem, check, report_or_die

__all__ = [
    "GroupStats", "Totals", "summarise", "Classifier", "Group", "Tier",
    "Hit", "log_files", "read", "as_html", "as_text",
    "Problem", "check", "report_or_die", "analyse",
]


def analyse(config: dict):
    """Config in, Totals out. The one call most callers need."""
    from pathlib import Path

    from .window import analyse_paths
    logs = config.get("logs", {})
    paths = log_files(Path(logs.get("dir", "/var/log/nginx")),
                      logs.get("base", "access.log"), int(logs.get("days", 2)))
    return analyse_paths(config, paths)
