"""MCP over stdio: `skald mcp [--site NAME] [--private]`.

Newline-delimited JSON-RPC: one message per line on stdin, one answer per
line on stdout, nothing else on stdout; logs go to stderr. Local trust: no
token - whoever runs this on the server can already read the data files.
`--site` limits the server to one site. The two files that hold visitors'
addresses (requests, ai_activity) are read only with `--private`. No token
means no setup scope: setup_line answers that it needs one (HTTP only).
"""
from __future__ import annotations

import json
import sys

from . import protocol
from .data import Context


def serve(ctx: Context, stdin=None, stdout=None, stderr=None) -> int:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    stderr.write(f"skald mcp: stdio, protocol {protocol.PROTOCOL_VERSION}, sites: "
                 f"{', '.join(ctx.sites()) or 'none'}\n")
    stderr.flush()
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except ValueError:
            answer = protocol.error(None, protocol.PARSE_ERROR, "Parse error")
        else:
            answer = protocol.handle(message, ctx)
        if answer is not None:
            stdout.write(json.dumps(answer, separators=(",", ":")) + "\n")
            stdout.flush()
    return 0


def cmd_mcp(ctx) -> int:
    """The `mcp` command (cli.Context in, the stdio server out)."""
    from ..cli import _path
    from ..config import site_name
    only = getattr(ctx.args, "only_site", None)
    private = bool(getattr(ctx.args, "private", False))
    out = _path(ctx.config, ctx.config_path, "dashboard", "out", None)
    if out is None:
        ctx.err("mcp: no dashboard folder (dashboard.out) in the config")
        return 2
    configs = {site_name(c): c for c in getattr(ctx, "all_configs", None) or [ctx.config]}
    server = Context(out, config=ctx.config, live_dir=ctx.live_dir,
                     history_path=ctx.db_path, checker=lambda site: (True, "", private),
                     only_sites=[only] if only else None, configs=configs,
                     default_site=only or ctx.site, config_path=ctx.config_path)
    return serve(server)
