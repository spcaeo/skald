#!/usr/bin/env python3
"""Write docs/CLI.md: every `skald` command and flag, from the real parser.

    python3 tools/cli-reference.py            # rewrite docs/CLI.md
    python3 tools/cli-reference.py --check    # exit 1 when docs/CLI.md is not what it writes

The words are the parser's own help texts (skald/cli.py and every module
cli_more.MODULES registers). A command or argument the parser gives no help for
takes its words from WORDS below, each checked against the code that reads it;
one with neither is written "(no help text)", so the gap shows.
tests/test_cli_reference.py fails when a command or a flag is missing from the
file. Run this after adding or changing a command, and commit its output.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from skald import cli  # noqa: E402

OUT = ROOT / "docs" / "CLI.md"
HEAD = """# Command reference

Every command and every argument of `skald` (`skald` in the Docker image), written from
the parser itself by `tools/cli-reference.py`: do not edit by hand.
In Docker, put `docker exec skald` in front: `docker exec skald skald doctor`. What each part
does and when to run it: [README.md](../README.md) ("System"), [DEPLOY.md](../DEPLOY.md),
[INSTALL.md](INSTALL.md) and each part's own guide. Exit codes, unless a command says
otherwise: 0 done, 1 refused or failed, 2 a usage mistake.
"""

# Words for what the parser leaves without help: "command::argument" or "command".
WORDS = {
    "::--config": "the config file",
    "check::--day": "the local day: YYYY-MM-DD, yesterday or today",
    "collect::--day": "the local day: YYYY-MM-DD, yesterday or today",
    "audit::--day": "the local day: YYYY-MM-DD, yesterday or today",
    "events::--day": "the local day: YYYY-MM-DD, yesterday or today",
    "backfill::--days": "how many local days, ending yesterday",
    "mail::--daily": "yesterday's mail (the default)",
    "mail::--weekly": "the last 7 complete days against the 7 before",
    "export::--table": "what to export",
    "export::--path-prefix": "only paths that start with this",
    "export::--country": "only this country (two letters)",
    "export::--format": "csv or json",
    "compare::--json": "print the answer as JSON",
    "page::path": "the page's path, e.g. /pricing/",
    "page::--json": "print the answer as JSON",
    "version::--json": "print it as JSON",
    "user::action": "list, add, remove or role",
    "user::name": "the dashboard user's name (basic mode's password file)",
    "user::--role": "the user's role",
    "token::action": "create, list or revoke",
    "report::--format": "an HTML file, or a zip of CSV files",
    "report::--out": "where to write it",
    "markers::--json": "print them as JSON",
    "alerts::--json": "print them as JSON",
    "updates::--json": "print the answer as JSON",
    "org list": "every organisation",
    "org create": "make an organisation",
    "org create::name": "its name",
    "org rename": "rename an organisation",
    "org rename::slug": "the organisation's slug (`skald org list`)",
    "org rename::name": "its new name",
    "member list": "the members of one organisation",
    "member invite": "invite someone by email; prints the invite link",
    "member invite::email": "their email",
    "member role": "change a member's role",
    "member role::email": "the member's email",
    "member role::role": "the new role",
    "member remove": "take someone out of the organisation",
    "member remove::email": "the member's email",
    "account reset-link": "print a link to set a new password",
    "account reset-link::email": "the account's email",
    "account disable": "stop an account signing in",
    "account disable::email": "the account's email",
    "account enable": "let a disabled account sign in again",
    "account enable::email": "the account's email",
    "account totp-off": "turn off an account's two-step sign-in",
    "account totp-off::email": "the account's email",
    "account install-admin": "make an account an install admin, or stop it being one",
    "account install-admin::email": "the account's email",
    "account install-admin::flag": "on or off",
    "site assign": "give a site to an organisation",
    "site assign::site": "the site's name",
    "site assign::--org": "the organisation's slug",
    "site add::host": "the site's host name, e.g. example.com",
    "site add::--org": "the organisation's slug",
    "site add::--format": "the log format (auto: told from the lines)",
    "site add::--timezone": "the site's IANA time zone, e.g. America/New_York",
    "site hosts::name": "the site's name",
    "site hosts::hosts": "every host name it answers to",
    "site remove::name": "the site's name",
    "site purge::name": "the site's name",
    "site verify::name": "the site's name",
    "hooks secret::site": "the site's name",
    "hooks secret::tool": "the hook",
    "hooks test::site": "the site's name",
    "hooks test::tool": "the hook",
    "conversions forget::--email": "everything kept for this email",
    "conversions mark-test::site": "the site's name",
    "conversions remove::site": "the site's name",
    "conversions list::site": "the site's name",
    "conversions list::--limit": "how many",
    "plan list": "the plans in the config, then each organisation's plan and status",
    "plan set": "give an organisation a plan (none takes it away)",
    "plan set::--status": "the billing status",
    "usage::--org": "one organisation (its slug)",
    "usage::--month": "another month",
    "billing secret": "the Stripe secret key or the webhook's signing secret, read from stdin "
                      "into secrets.json (0600); never printed",
    "billing secret::which": "which secret",
    "settings get::site": "the site's name",
    "settings get::key": "the setting's key (`settings list-keys`)",
    "settings set::site": "the site's name",
    "settings set::key": "the setting's key (`settings list-keys`)",
    "ours pause::entry": "the entry's label or address",
    "ours resume::entry": "the entry's label or address",
    "ours edit::entry": "the entry's label or address",
    "ours edit::--label": "its new label",
    "ours edit::--address": "its new address",
    "ours delete::entry": "the entry's label or address",
    "ours delete::--yes": "really delete it",
}


def _subparsers(p: argparse.ArgumentParser):
    for a in p._actions:
        if isinstance(a, argparse._SubParsersAction):
            helps = {c.dest: c.help for c in a._choices_actions}
            for name, sub in a.choices.items():
                yield name, sub, helps.get(name)


def _clean(text) -> str:
    return " ".join(str(text or "").replace("|", "\\|").split())


def _args(p: argparse.ArgumentParser, where: str) -> list[tuple[str, str]]:
    """[(the argument as typed, what it does)] for one parser."""
    out = []
    for a in p._actions:
        if isinstance(a, (argparse._SubParsersAction, argparse._HelpAction)):
            continue
        if a.help == argparse.SUPPRESS:
            continue
        flag = a.option_strings[-1] if a.option_strings else a.dest
        name = ", ".join(f"`{o}`" for o in a.option_strings) if a.option_strings else f"`{a.dest}`"
        if a.metavar and a.option_strings and a.nargs != 0:
            name += f" {a.metavar}"
        extra = []
        if a.choices and not isinstance(a.choices, dict):
            extra.append("one of " + ", ".join(f"`{c}`" for c in a.choices))
        if a.option_strings and a.default not in (None, False, argparse.SUPPRESS, [], ""):
            extra.append(f"default `{a.default}`")
        if a.required and a.option_strings:
            extra.append("required")
        what = _clean(a.help) or WORDS.get(f"{where}::{flag}") or "(no help text)"
        out.append((name, what + (f" ({'; '.join(extra)})" if extra else "")))
    return out


def _about(about, where: str) -> str:
    text = _clean(about) or WORDS.get(where, "")
    return text[:1].upper() + text[1:] + ("." if text and not text.endswith(".") else "")


def render() -> str:
    ap = cli.parser()
    out = [HEAD.rstrip(), "", "## Global options", "",
           "They go before the command: `skald --config /etc/skald/config.yml --site "
           "example.com live`.", "", "| Argument | What it does |", "| --- | --- |"]
    out += [f"| {n} | {w} |" for n, w in _args(ap, "") if n != "`command`"]
    names = [n for n, _, _ in _subparsers(ap)]
    out += ["", "## Commands", "", " · ".join(f"`{n}`" for n in names)]
    for name, sub, about in _subparsers(ap):
        out += ["", f"### skald {name}", ""]
        if about or WORDS.get(name):
            out += [_about(about, name), ""]
        subs = list(_subparsers(sub))
        rows = _args(sub, name)
        if not subs:
            if rows:
                out += ["| Argument | What it does |", "| --- | --- |"]
                out += [f"| {n} | {w} |" for n, w in rows]
            else:
                out += ["No arguments."]
            continue
        out += ["| Command | Argument | What it does |", "| --- | --- | --- |"]
        out += [f"| | {n} | {w} |" for n, w in rows if n != "`action`"]
        for sub_name, leaf, leaf_help in subs:
            where = f"{name} {sub_name}"
            out.append(f"| `{where}` | | {_about(leaf_help, where) or '(no help text)'} |")
            out += [f"| | {n} | {w} |" for n, w in _args(leaf, where)]
    return "\n".join(out).rstrip() + "\n"


def main(argv=None) -> int:
    text = render()
    if "--check" in (argv if argv is not None else sys.argv[1:]):
        if not OUT.is_file() or OUT.read_text() != text:
            print(f"{OUT.relative_to(ROOT)} is not what tools/cli-reference.py writes; run it")
            return 1
        return 0
    OUT.write_text(text)
    print(f"wrote {OUT.relative_to(ROOT)} ({len(text.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
