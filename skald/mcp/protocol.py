"""JSON-RPC 2.0 and the MCP lifecycle, with no transport in it.

`handle(message, ctx)` takes one parsed message (an object) or a batch (a
list) and returns the response, a list of responses, or None when nothing
is to be sent back (notifications, a client's own responses).

Methods: initialize, ping, tools/list, tools/call, resources/list,
resources/templates/list, resources/read, prompts/list, prompts/get.
Notifications (notifications/initialized, notifications/cancelled, ...)
get no answer.

The server is stateless: each HTTP request stands alone, so a method is
answered whether or not `initialize` came first on this connection.

Version negotiation: we speak 2025-06-18. A client asking for it gets it;
a client asking for an older version (2025-03-26, 2024-11-05) or one we do
not know gets 2025-06-18, the version we support, and decides itself
whether to go on (MCP spec, Lifecycle).

Errors: -32700 parse error (the transports send it), -32600 invalid
request, -32601 unknown method, -32602 invalid params (also an unknown tool
or prompt), -32002 resource not found, -32603 internal error. A tool that
cannot answer (a site you may not read, a bad date) is not a protocol
error: it is a tools/call result with isError true and plain words.
"""
from __future__ import annotations

import sys
from pathlib import Path

PROTOCOL_VERSION = "2025-06-18"
SUPPORTED = ("2025-06-18", "2025-03-26", "2024-11-05")

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
RESOURCE_NOT_FOUND = -32002

INSTRUCTIONS = (
    "Skald is web analytics read from the server's own access log. Every figure comes from "
    "whole, verified days; withheld, partial and missing days are named and never counted. "
    "Call visits 'visits (an upper bound on people)', never users. Requests are not people. "
    "Start with list_sites; dates are YYYY-MM-DD in the site's time zone and default to the "
    "last 7 whole days. Read skald://docs/counting for what the figures cannot know. "
    "When the user asks to set Skald up for a site (\"Set up Skald for this site\"), call "
    "setup_left, then setup_line with its jobs (a token with the setup scope), then follow "
    "the line it answers. When the user asks to fix Skald's to-dos (\"Fix my Skald to-dos\"), "
    "call fix_todo for the list, then fix_todo with each id for every row and the steps, do "
    "the work in the site's own code or server (ask before any server change), then "
    "mark_todo_done (a token with the setup scope).")


class RpcError(Exception):
    def __init__(self, code: int, message: str, data=None):
        super().__init__(message)
        self.code, self.message, self.data = code, message, data


def version() -> str:
    try:
        return (Path(__file__).resolve().parent.parent.parent / "VERSION").read_text().strip()
    except OSError:
        return "0"


def error(mid, code: int, message: str, data=None) -> dict:
    err = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": mid, "error": err}


def handle(message, ctx):
    """The answer to one message or a batch; None when nothing is sent."""
    if isinstance(message, list):
        if not message:
            return error(None, INVALID_REQUEST, "Invalid Request: an empty batch")
        out = [r for r in (_one(m, ctx) for m in message) if r is not None]
        return out or None
    return _one(message, ctx)


def _good_id(mid) -> bool:
    return isinstance(mid, str) or (isinstance(mid, (int, float)) and not isinstance(mid, bool))


def _one(msg, ctx):
    if not isinstance(msg, dict):
        return error(None, INVALID_REQUEST, "Invalid Request: a message is a JSON object")
    has_id = "id" in msg
    mid = msg.get("id") if has_id and _good_id(msg.get("id")) else None
    if msg.get("jsonrpc") != "2.0":
        return error(mid, INVALID_REQUEST, 'Invalid Request: jsonrpc must be "2.0"')
    method = msg.get("method")
    if method is None and ("result" in msg or "error" in msg):
        return None                                 # a response to us: nothing to say
    if not isinstance(method, str) or not method:
        return error(mid, INVALID_REQUEST, "Invalid Request: method must be a string")
    if has_id and not _good_id(msg.get("id")):
        return error(None, INVALID_REQUEST, "Invalid Request: id must be a string or a number")
    params = msg.get("params")
    if not has_id:
        return None                                 # a notification: never answered
    if params is None:
        params = {}
    if not isinstance(params, dict):
        return error(mid, INVALID_PARAMS, "Invalid params: params must be an object")
    run = METHODS.get(method)
    if run is None:
        return error(mid, METHOD_NOT_FOUND, f"Method not found: {method}")
    try:
        result = run(params, ctx)
    except RpcError as why:
        return error(mid, why.code, why.message, why.data)
    except Exception as why:                       # noqa: BLE001 - never a traceback out
        sys.stderr.write(f"mcp: {method} failed: {type(why).__name__}: {why}\n")
        return error(mid, INTERNAL_ERROR, "Internal error")
    return {"jsonrpc": "2.0", "id": mid, "result": result}


# ---------------------------------------------------------------- methods

def _initialize(params, ctx):
    asked = params.get("protocolVersion")
    if not isinstance(asked, str) or not asked:
        raise RpcError(INVALID_PARAMS, "Invalid params: protocolVersion is needed",
                       {"supported": list(SUPPORTED)})
    return {"protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False},
                             "resources": {"listChanged": False, "subscribe": False},
                             "prompts": {"listChanged": False}},
            "serverInfo": {"name": "skald", "title": "Skald", "version": version()},
            "instructions": INSTRUCTIONS}


def _ping(params, ctx):
    return {}


def _tools_list(params, ctx):
    from . import tools
    return {"tools": tools.listing()}


def _tools_call(params, ctx):
    from . import tools
    name = params.get("name")
    if not isinstance(name, str) or name not in tools.TOOLS:
        raise RpcError(INVALID_PARAMS, f"Unknown tool: {name}")
    args = params.get("arguments")
    if args is not None and not isinstance(args, dict):
        raise RpcError(INVALID_PARAMS, "Invalid params: arguments must be an object")
    return tools.call(ctx, name, args or {})


def _resources_list(params, ctx):
    from . import resources
    return {"resources": resources.listing(ctx)}


def _resource_templates(params, ctx):
    from . import resources
    return {"resourceTemplates": resources.templates()}


def _resources_read(params, ctx):
    from . import resources
    uri = params.get("uri")
    if not isinstance(uri, str) or not uri:
        raise RpcError(INVALID_PARAMS, "Invalid params: uri is needed")
    try:
        return {"contents": resources.read(ctx, uri)}
    except resources.Missing:
        raise RpcError(RESOURCE_NOT_FOUND, "Resource not found", {"uri": uri})


def _prompts_list(params, ctx):
    from . import resources
    return {"prompts": list(resources.PROMPTS.values())}


def _prompts_get(params, ctx):
    from . import resources
    name = params.get("name")
    if not isinstance(name, str) or name not in resources.PROMPTS:
        raise RpcError(INVALID_PARAMS, f"Unknown prompt: {name}")
    args = params.get("arguments") or {}
    if not isinstance(args, dict) or not all(isinstance(v, str) for v in args.values()):
        raise RpcError(INVALID_PARAMS, "Invalid params: arguments are names and strings")
    return resources.prompt(ctx, name, args)


METHODS = {"initialize": _initialize, "ping": _ping,
           "tools/list": _tools_list, "tools/call": _tools_call,
           "resources/list": _resources_list,
           "resources/templates/list": _resource_templates,
           "resources/read": _resources_read,
           "prompts/list": _prompts_list, "prompts/get": _prompts_get}
