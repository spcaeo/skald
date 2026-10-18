"""Release 2 commands, registered on skald's parser (cli.parser).

Each feature module defines `add_command(sub)`, which adds its subparser
and sets `run` to a function taking cli.Context, like the commands in
cli.py. Kept here so cli.py stays a readable size.
"""
from __future__ import annotations

import importlib

MODULES = ("compare", "lifecycle", "brand", "access", "tokens", "report_export", "bot_verify", "backup", "privacy", "markers", "leads", "alerts", "favicons", "pagespeed", "events", "failmail", "cli_accounts", "mcp", "cli_conversions", "saas.cli", "llms_txt", "updates", "migrations", "upgrade", "doctor", "site_logos", "settings_cli")


def register(sub) -> None:
    for name in MODULES:
        try:
            module = importlib.import_module(f".{name}", __package__)
        except ModuleNotFoundError as why:
            if why.name != f"{__package__}.{name}":
                raise
            continue
        add = getattr(module, "add_command", None)
        if add is not None:
            add(sub)
