"""nginx route coverage: every path either helper answers reaches it.

The sample paths are generated from the helpers' own route patterns (the
compiled regexes and path constants of refresh_server.py and the modules its
dispatch calls, and of beacon_server.py and conversions/hooks.py), so a new
route in the code without its nginx location fails here. Checked against:

DEPLOY.md, the sessions-mode blocks between the skald-nginx-sessions
    markers (http level, the two snippets, the server level).

For each sample, nginx's own location choice (exact, longest prefix, ^~,
then regexes in order, nested locations first) must land on a location
that proxies to the right helper (8765 refresh, 8766 beacon) and clears
X-Skald-User / X-Skald-Role. A per-site route must match as a route, not by
accident with its first word taken as a view (settings/audit as view
"settings" + "audit"). With nginx installed, `nginx -t` runs on both in a
scratch prefix.
"""
from __future__ import annotations

import itertools
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

try:                                    # the regex parser of the standard library
    from re import _parser as sre_parse
    from re import _constants as C
except ImportError:                     # Python before 3.11
    import sre_constants as C           # type: ignore
    import sre_parse                    # type: ignore

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from skald import auth_api, beacon_server, refresh_server  # noqa: E402
from skald.conversions import hooks  # noqa: E402
from skald.saas import signup_api  # noqa: E402

DEPLOY = ROOT / "DEPLOY.md"
REFRESH, BEACON = "127.0.0.1:8765", "127.0.0.1:8766"
VIEW = "(?:[a-z0-9-]+/)?"               # the optional view segment, in the code and nginx
VIEW_IN_CODE = re.compile(re.escape("(?:(?P<view>[a-z0-9-]+)/)?") + "|" + re.escape(VIEW))
# Constants that are not routes (helpers that read a site name out of a path).
NOT_ROUTES = {("helper_sessions", "SITE_OF_PATH")}
# Values for named groups, so samples look like real addresses.
NAMED = {"site": "shop.example.com", "view": "blog", "name": "overview",
         "act": None, "shipper": "ship-1", "seq": "1"}
# Paths served from the dashboard's files, never by a helper.
STATIC = ("/traffic/shop.example.com/", "/traffic/shop.example.com/index.html",
          "/traffic/shop.example.com/data/overview.json", "/traffic/_app/app.js",
          "/traffic/shop.example.com/blog/data/overview.json")


# ------------------------------------------------------------- the samples

def _in_class(items, ch: str) -> bool:
    ok, negate = False, False
    for op, arg in items:
        if op is C.NEGATE:
            negate = True
        elif op is C.LITERAL:
            ok = ok or ord(ch) == arg
        elif op is C.RANGE:
            ok = ok or arg[0] <= ord(ch) <= arg[1]
        elif op is C.CATEGORY:
            ok = ok or bool(re.match({C.CATEGORY_DIGIT: r"\d", C.CATEGORY_WORD: r"\w",
                                      C.CATEGORY_SPACE: r"\s"}.get(arg, r"(?!)"), ch))
    return ok != negate


def _char(op, arg) -> str:
    if op is C.LITERAL:
        return chr(arg)
    for ch in "abcdefghijklmnopqrstuvwxyz0123456789-._":
        if op is C.ANY or _in_class(arg, ch):
            return ch
    raise AssertionError(f"no sample character for {op} {arg}")


def _expand(parsed, names: dict) -> list[str]:
    """Every variant of a parsed pattern: each branch and each optional part
    both ways, character classes as one sample character."""
    variants = [""]
    for op, arg in parsed:
        if op is C.LITERAL:
            got = [chr(arg)]
        elif op is C.AT:
            got = [""]
        elif op in (C.IN, C.ANY):
            got = [_char(op, arg)]
        elif op is C.SUBPATTERN:
            group, sub = arg[0], arg[-1]
            name = names.get(group)
            got = [NAMED[name]] if NAMED.get(name) else _expand(sub, names)
        elif op is C.BRANCH:
            got = [v for alt in arg[1] for v in _expand(alt, names)]
        elif op in (C.MAX_REPEAT, C.MIN_REPEAT):
            low, high, sub = arg
            simple = len(sub) == 1 and sub[0][0] in (C.IN, C.LITERAL, C.ANY)
            if simple:
                n = max(low, min(high, 3))
                once = [_char(*sub[0]) * n]
            else:
                once = ["".join(p) for p in itertools.product(
                    *[_expand(sub, names)] * max(low, 1))]
            got = ([""] if low == 0 else []) + (once if high else [])
        else:
            raise AssertionError(f"pattern piece not handled: {op}")
        variants = [a + b for a, b in itertools.product(variants, got)]
    return variants


def samples(pattern: re.Pattern) -> list[str]:
    parsed = sre_parse.parse(pattern.pattern, pattern.flags)
    state = getattr(parsed, "state", None) or getattr(parsed, "pattern", None)
    names = {i: n for n, i in state.groupdict.items()}
    out = sorted(set(_expand(parsed, names)))
    for path in out:
        assert pattern.match(path), (pattern.pattern, path)
    return out


def _constants(module) -> list:
    out = []
    for attr, value in vars(module).items():
        if (module.__name__.rsplit(".", 1)[-1], attr) in NOT_ROUTES:
            continue
        if isinstance(value, re.Pattern) and value.pattern.startswith("^/traffic"):
            out.append(value)
        elif isinstance(value, str) and value.startswith("/traffic"):
            # A PREFIX is a start of paths (/traffic-auth/...), anything else a path.
            out.append(Prefix(value) if attr.endswith("PREFIX") else value)
        elif isinstance(value, tuple) and value and \
                all(isinstance(v, str) and v.startswith("/traffic") for v in value):
            out.extend(value)
    return out


class Prefix(str):
    """A path constant the code matches with startswith."""


def _paths_of(items: list) -> list[str]:
    out = []
    for item in items:
        if isinstance(item, re.Pattern):
            out += samples(item)
        else:
            out.append(item + "x" if isinstance(item, Prefix) else str(item))
    return out


def refresh_modules() -> list:
    """refresh_server and every module its dispatch asks, `<module>.is_...(`."""
    import types
    source = Path(refresh_server.__file__).read_text()
    names = sorted(set(re.findall(r"\b(\w+)\.is_\w+\(", source)))
    found = [getattr(refresh_server, n, None) for n in names]
    modules = [m for m in found if isinstance(m, types.ModuleType)]
    assert len(modules) >= 10, names
    return [refresh_server] + modules


def refresh_routes() -> list[str]:
    """Every path the refresh helper answers: its own patterns and those of
    every module its dispatch asks (`<module>.is_...(self.path)`)."""
    modules = refresh_modules()
    out = _paths_of([c for m in modules for c in _constants(m)])
    auth = list(auth_api.STATIC) + ["check", "invite-info", "login", "logout", "forgot",
                                     "reset", "invite"] + list(signup_api.NAMES)
    out += [auth_api.PREFIX + n for n in auth]
    return sorted(set(out))


def beacon_routes() -> list[str]:
    source = Path(beacon_server.__file__).read_text()
    # The startswith("/traffic-.../") tests of its dispatch are prefixes.
    literals = [Prefix(v) if v.endswith("/") else v
                for v in re.findall(r'"(/traffic[^"]*)"', source)]
    out = _paths_of(_constants(beacon_server) + _constants(hooks) + literals)
    return sorted(p for p in set(out) if p != "/traffic-hooks/_billing/stripe")


def view_free(pattern: re.Pattern) -> list[str]:
    """Samples of a per-site route with no view segment."""
    bare, n = VIEW_IN_CODE.subn("", pattern.pattern, count=1)
    return samples(re.compile(bare)) if n else []


# ---------------------------------------------------------- reading nginx

def tokens(text: str):
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            i += 1
        elif ch == "#":
            i = text.find("\n", i)
            i = n if i < 0 else i
        elif ch in "{};":
            yield ch
            i += 1
        elif ch in "\"'":
            end = text.index(ch, i + 1)
            yield text[i + 1:end]
            i = end + 1
        else:
            j = i
            while j < n and not text[j].isspace() and text[j] not in "{};":
                j += 1
            yield text[i:j]
            i = j


def parse(text: str) -> list:
    """[(name, args, children or None)], nested."""
    stack, current, words = [], [], []
    for tok in tokens(text):
        if tok == ";":
            current.append((words[0], words[1:], None))
            words = []
        elif tok == "{":
            block = (words[0], words[1:], [])
            current.append(block)
            stack.append(current)
            current, words = block[2], []
        elif tok == "}":
            current = stack.pop()
        else:
            words.append(tok)
    assert not stack and not words, "unbalanced nginx text"
    return current


class Loc:
    def __init__(self, args, body, snippets):
        self.mod, self.arg = (args[0], args[1]) if len(args) == 2 else ("", args[0])
        self.body = []
        for name, a, children in body:      # includes, inlined
            if name == "include":
                key = Path(a[0]).name
                assert key in snippets, f"include of an unknown snippet {a[0]}"
                self.body += snippets[key]
            else:
                self.body.append((name, a, children))
        self.children = [Loc(a, c, snippets) for name, a, c in self.body
                         if name == "location"]

    def directives(self, name: str) -> list[list[str]]:
        return [a for n, a, c in self.body if n == name]

    def matches_prefix(self, path: str) -> bool:
        return self.mod in ("", "^~") and path.startswith(self.arg)

    def regex(self) -> re.Pattern | None:
        return re.compile(self.arg) if self.mod in ("~", "~*") else None

    def __repr__(self):
        return f"location {self.mod} {self.arg}".replace("  ", " ")


def find(locations: list[Loc], path: str) -> Loc | None:
    """nginx's choice (ngx_http_core_find_location)."""
    for loc in locations:
        if loc.mod == "=" and loc.arg == path:
            return loc
    prefixes = [loc for loc in locations if loc.matches_prefix(path)]
    best = max(prefixes, key=lambda loc: len(loc.arg)) if prefixes else None
    if best is not None:
        inner = find(best.children, path)
        if inner is not None:
            return inner
        if best.mod == "^~":
            return best
    for loc in locations:
        rx = loc.regex()
        if rx is not None and rx.search(path):
            return find(loc.children, path) or loc
    return best


class Config:
    def __init__(self, http: str, server: str, snippets: dict[str, str]):
        self.http_text, self.server_text, self.snippet_text = http, server, snippets
        parsed = {k: parse(v) for k, v in snippets.items()}
        self.upstreams = {a[0]: [s for n, s, _ in c if n == "server"][0][0]
                          for n, a, c in parse(http) if n == "upstream"}
        self.locations = [Loc(a, c, parsed) for n, a, c in parse(server) if n == "location"]

    def target(self, loc: Loc) -> str | None:
        got = loc.directives("proxy_pass")
        if not got:
            return None
        host = re.match(r"https?://([^/]+)", got[-1][0]).group(1)
        return self.upstreams.get(host, host)

    def all_locations(self, locs=None):
        for loc in self.locations if locs is None else locs:
            yield loc
            yield from self.all_locations(loc.children)


def from_deploy() -> Config:
    text = DEPLOY.read_text()
    begin, end = "<!-- skald-nginx-sessions:begin -->", "<!-- skald-nginx-sessions:end -->"
    part = text[text.index(begin):text.index(end)]
    http = server = None
    snippets = {}
    for block in re.findall(r"```nginx\n(.*?)```", part, re.S):
        head = block.splitlines()[0]
        if head.startswith("# ---- http level"):
            http = block
        elif head.startswith("# ---- server level"):
            server = block
        else:
            name = re.match(r"# ---- /etc/nginx/snippets/(\S+) ----", head)
            assert name, f"an nginx block with no known heading: {head}"
            snippets[name.group(1)] = block
    assert http and server, "DEPLOY.md: the http or server block is missing"
    return Config(http, server, snippets)


# ------------------------------------------------------------------- tests

class Coverage:
    config: Config

    def check(self, path: str, helper: str) -> Loc:
        loc = find(self.config.locations, path)
        self.assertIsNotNone(loc, f"{path}: no location")
        self.assertEqual(self.config.target(loc), helper, f"{path}: {loc} goes elsewhere")
        sets = {a[0]: a[1] if len(a) > 1 else None
                for a in loc.directives("proxy_set_header")}
        self.assertEqual((sets.get("X-Skald-User"), sets.get("X-Skald-Role")), ("", ""),
                         f"{path}: {loc} does not clear X-Skald-User / X-Skald-Role")
        return loc

    def test_every_refresh_helper_route(self):
        routes = refresh_routes()
        for must in ("/traffic/shop.example.com/settings", "/traffic/shop.example.com/sites",
                     "/traffic/shop.example.com/integrations/webhooks/rotate",
                     "/traffic-ingest/shop.example.com", "/traffic-mcp",
                     "/traffic/sites.json", "/traffic-hooks/_billing/stripe"):
            self.assertIn(must, routes, "the sample generator missed a route")
        self.assertGreater(len(routes), 80)
        for path in routes:
            with self.subTest(path=path):
                self.check(path, REFRESH)

    def test_every_beacon_helper_route(self):
        routes = beacon_routes()
        for must in ("/traffic-beacon", "/traffic-js/skald.js"):
            self.assertIn(must, routes)
        self.assertTrue(any(p.startswith("/traffic-hooks/") for p in routes))
        for path in routes:
            with self.subTest(path=path):
                self.check(path, BEACON)

    def test_a_route_is_a_route_not_a_view(self):
        """settings/audit must match as the route `settings/audit`, never only
        because `settings/` passes for a view segment."""
        modules = refresh_modules()
        patterns = [c for m in modules for c in _constants(m) if isinstance(c, re.Pattern)]
        checked = 0
        for pattern in patterns:
            for path in view_free(pattern):
                loc = self.check(path, REFRESH)
                rx = loc.regex()
                if rx is None or VIEW not in rx.pattern:
                    continue
                bare = re.compile(rx.pattern.replace(VIEW, "", 1))
                checked += 1
                with self.subTest(path=path):
                    self.assertTrue(bare.search(path),
                                    f"{path} reaches {loc} only as a view + another route")
        self.assertGreater(checked, 30)

    def test_static_files_stay_static(self):
        for path in STATIC:
            loc = find(self.config.locations, path)
            with self.subTest(path=path):
                self.assertEqual((loc.mod, loc.arg), ("^~", "/traffic/"))
                self.assertIsNone(self.config.target(loc))
                self.assertTrue(loc.directives("auth_request"))

    def test_the_session_check_is_internal(self):
        loc = find(self.config.locations, "/traffic-auth/check")
        self.assertEqual(loc.mod, "=")
        self.assertTrue(loc.directives("internal"))
        dash = [loc for loc in self.config.locations if loc.arg == "/traffic/"][0]
        self.assertEqual(dash.directives("auth_request"), [["/traffic-auth/check"]])

    def test_every_helper_location_clears_the_user_headers(self):
        for loc in self.config.all_locations():
            if self.config.target(loc) is None:
                continue
            sets = {a[0]: a[1] if len(a) > 1 else None
                    for a in loc.directives("proxy_set_header")}
            with self.subTest(loc=repr(loc)):
                self.assertEqual(sets.get("X-Skald-User"), "")
                self.assertEqual(sets.get("X-Skald-Role"), "")

    @unittest.skipUnless(shutil.which("nginx"), "nginx is not installed here")
    def test_nginx_accepts_it(self):
        version = subprocess.run(["nginx", "-V"], capture_output=True, text=True, timeout=10)
        if "http_auth_request_module" not in version.stderr + version.stdout:
            self.skipTest("this nginx has no auth_request module")
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "snippets").mkdir()
            for name, body in self.config.snippet_text.items():
                (base / "snippets" / name).write_text(body)
            temp = " ".join(f"{k}_temp_path {base};" for k in
                            ("client_body", "proxy", "fastcgi", "uwsgi", "scgi"))
            server = self.config.server_text.replace("/var/log/nginx/", f"{base}/")
            (base / "nginx.conf").write_text(
                f"worker_processes 1;\npid {base}/nginx.pid;\nerror_log {base}/error.log;\n"
                "events { worker_connections 16; }\n"
                f"http {{\n access_log off;\n {temp}\n{self.config.http_text}\n"
                f" server {{\n  listen 127.0.0.1:18089;\n  server_name localhost;\n"
                f"{server}\n }}\n}}\n")
            done = subprocess.run(["nginx", "-t", "-p", str(base), "-c", str(base / "nginx.conf"),
                                   "-e", str(base / "error.log")],
                                  capture_output=True, text=True, timeout=30)
            self.assertEqual(done.returncode, 0, done.stderr)


class DeployMd(Coverage, unittest.TestCase):
    config = from_deploy()


class TheMatcherItself(unittest.TestCase):
    """The location choice follows nginx's rules on a small config."""

    def test_rules(self):
        cfg = Config("", """
            location = /a { proxy_pass http://127.0.0.1:1; }
            location /a { proxy_pass http://127.0.0.1:2; }
            location ^~ /b/ { proxy_pass http://127.0.0.1:3;
                location ~ ^/b/x$ { proxy_pass http://127.0.0.1:4; } }
            location ~ ^/b/y$ { proxy_pass http://127.0.0.1:5; }
            location /c/ { proxy_pass http://127.0.0.1:6; }
            location ~ ^/c/z$ { proxy_pass http://127.0.0.1:7; }
        """, {})
        got = {p: cfg.target(find(cfg.locations, p))
               for p in ("/a", "/ab", "/b/x", "/b/y", "/c/q", "/c/z")}
        self.assertEqual(got, {"/a": "127.0.0.1:1", "/ab": "127.0.0.1:2",
                               "/b/x": "127.0.0.1:4", "/b/y": "127.0.0.1:3",
                               "/c/q": "127.0.0.1:6", "/c/z": "127.0.0.1:7"})

    def test_the_old_regex_would_have_failed(self):
        """The sessions block before 2026-10-11 had no `settings`: caught."""
        old = (r"^/traffic/[a-z0-9.-]+/(?:[a-z0-9-]+/)?(?:me|refresh|ours(?:/(?:add|remove|"
               r"add-mine))?|funnels(?:/(?:save|delete))?|bot-policy|team(?:/[a-z-]+)?|account"
               r"(?:/[a-z-]+(?:/[a-z]+)?)?|tokens(?:/[a-z]+)?|audit|sites(?:/[a-z]+)?|billing"
               r"(?:/(?:checkout|portal))?|integrations(?:/[a-z]+(?:/[a-z]+)?)?|api/(?:v1/"
               r"(?:[a-z_]+)?|compare|page))$")
        rx = re.compile(old)
        missed = [p for p in refresh_routes() if p.startswith("/traffic/shop") and
                  "/data/" not in p and not rx.search(p)]
        self.assertIn("/traffic/shop.example.com/settings", missed)
        bare = re.compile(old.replace(VIEW, "", 1))
        self.assertTrue(rx.search("/traffic/shop.example.com/settings/audit"))
        self.assertFalse(bare.search("/traffic/shop.example.com/settings/audit"))


if __name__ == "__main__":
    unittest.main()
