"""Skald's MCP server: agents (Claude, ChatGPT, any MCP client) read the
same data files the dashboard reads (docs/MCP.md). Read-only, except one
tool: setup_line makes a set-up line, with a token's setup scope.

  protocol.py    JSON-RPC 2.0 and the MCP lifecycle, no transport
  tools.py       list_sites, overview, breakdown, top_pages, ai_activity, leads
  tools_more.py  funnel, compare, page_story, live_today, data_quality, site_health,
                 conversions
  tools_people.py   find_person (read_private only)
  tools_insights.py what_changed, todos, lost_pages (2.35)
  tools_pages.py    page_changes, ai_readiness, changed_pages (2.35)
  tools_setup.py    setup_left, setup_line (2.39.0: the set-up lines' open
                    lines; a set-up line for an AI agent, with the setup scope)
  resources.py   skald://docs/api, skald://docs/counting, skald://sites/<site>/overview,
                 and the weekly_report prompt
  data.py        reading the data files: sites, ranges, day states
  http.py        POST /traffic-mcp on the refresh helper (bearer token, mcp scope)
  stdio.py       `skald mcp`: newline-delimited JSON-RPC on stdin and stdout

This module only registers the command (cli_more.MODULES names "mcp");
nothing else is imported until it runs.
"""
from __future__ import annotations

import argparse


def _run(ctx) -> int:
    from .stdio import cmd_mcp
    return cmd_mcp(ctx)


def add_command(sub) -> None:
    p = sub.add_parser("mcp", help="MCP server on stdin/stdout for a local agent "
                                   "(docs/MCP.md); read-only")
    p.add_argument("--site", dest="only_site", metavar="NAME", default=argparse.SUPPRESS,
                   help="answer for this site only")
    p.add_argument("--private", action="store_true",
                   help="also read the files that hold visitors' addresses "
                        "(requests, ai_activity)")
    p.set_defaults(run=_run)
