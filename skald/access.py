"""Named users and roles: who may look, and who may change things.

nginx asks for the password (basic auth) and tells the helper who answered
it, in the X-Skald-User header; the helper believes that header only on
connections from 127.0.0.1, which is nginx itself. Two roles:

  admin    may change internal addresses and funnels (and, on the server,
           tokens and users with skald)
  viewer   reads everything the dashboard shows, changes nothing

Roles live in `access.roles` (default users.json beside the history):
{"users": {"name": {"role", "added_at", "added_by"}}}. Before that file
exists there is one shared login, and whoever has it is admin - so
installing this changes nothing until a role is written. Once it exists,
a user it does not name is a viewer.

With `access: {mode: sessions}` people sign in with accounts instead
(skald/accounts/, auth_api.py). Then the helper never believes
X-Skald-User or X-Skald-Role, from anyone: user_from and role_of read the
session cookie itself (accounts.sqlite) and the role on the site's
organisation, on every request (session_caller). Any local process could
reach the helper's port and send those headers; it cannot make a cookie.

X-Real-IP (the browser's address, for the sign-in limits and "add my
address") is believed only on a connection from the proxy (127.0.0.1, or
the helper's Unix socket) and only while `access.trust_proxy_ip` is true
(the default). Every local process can reach 127.0.0.1:8765 and claim any
address there; on a server with other local users set it false, or give
the helper a Unix socket only nginx can open (refresh.socket, DEPLOY.md).

`skald user add NAME --role viewer|admin` asks for the password (or reads it
from stdin with --password-stdin) and appends one line to the password file
(`access.htpasswd`), hashed by the `htpasswd` binary (bcrypt) when the server
has it, else by `openssl passwd -6` (SHA-512 crypt, which nginx reads through
the system's crypt). It never changes an existing user's password: a user
already in the file is refused. `user remove`, `user role`, `user list`.
Each change is appended to access.log beside the history.
"""
from __future__ import annotations

import getpass
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from .files import own_like_folder, write_atomic

ROLES = ("admin", "viewer")
NAME = re.compile(r"^[a-z0-9][a-z0-9._-]{0,31}$")


def roles_path(config: dict, live_dir: Path | None) -> Path | None:
    raw = ((config or {}).get("access") or {}).get("roles")
    if raw:
        return Path(str(raw))
    return Path(live_dir) / "users.json" if live_dir is not None else None


def htpasswd_path(config: dict) -> Path | None:
    raw = ((config or {}).get("access") or {}).get("htpasswd")
    return Path(str(raw)) if raw else None


def load_roles(path: Path | None) -> dict | None:
    """{name: {...}}, or None when there is no roles file yet."""
    if path is None:
        return None
    try:
        got = json.loads(Path(path).read_text())
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        return {}                       # unreadable: nobody is admin
    users = got.get("users") if isinstance(got, dict) else None
    return users if isinstance(users, dict) else {}


def mode(config: dict | None) -> str:
    """`access.mode`: "basic" (default: nginx basic auth, users.json) or
    "sessions" (accounts.sqlite, signed-in sessions; docs/plans/
    2026-10-11-phase1-accounts-plan.md). Anything else is read as basic."""
    got = str(((config or {}).get("access") or {}).get("mode") or "basic").strip().lower()
    return "sessions" if got == "sessions" else "basic"


PROXY = "127.0.0.1"      # nginx's connection (a Unix socket peer is reported as this too)


def trust_proxy_ip(config: dict | None) -> bool:
    """`access.trust_proxy_ip` (default true): believe nginx's X-Real-IP."""
    got = ((config or {}).get("access") or {}).get("trust_proxy_ip", True)
    return got is not False and str(got).strip().lower() not in ("false", "no", "off", "0")


def proxy_ip(headers, peer: str, config: dict | None = None) -> str | None:
    """X-Real-IP, when the connection is the proxy's and the config trusts it."""
    if peer != PROXY or not trust_proxy_ip(config):
        return None
    got = ((headers.get("X-Real-IP") if headers is not None else "") or "").strip()
    return got if got and len(got) <= 64 else None


def session_caller(config: dict | None, live_dir, headers, site: str | None = None):
    """Sessions mode: who holds the session cookie in `headers`, as a dict
    {user_id, email, name, install_admin, csrf, session_id, role, org,
    member_sites, admin_sites, orgs}; `role` and `org` are for `site` (None when
    not a member, or no site); `orgs`: [{name, sites}] the caller belongs to. None without a valid session. Headers such
    as X-Skald-User are never read."""
    from . import accounts
    from .auth_api import cookie_of
    path = accounts.path_for(config or {}, live_dir)
    if path is None or headers is None or not Path(path).is_file():
        return None
    db = accounts.connect(path)
    try:
        who = accounts.sessions.resolve(db, cookie_of(headers))
        if who is None:
            return None
        role, org = (accounts.site_role(db, who["user_id"], site) if site else (None, None))
        member, admin, orgs = [], [], []
        for o in accounts.list_orgs(db, who["user_id"]):
            names = accounts.sites_of_org(db, o["id"])
            member += names
            orgs.append({"name": o["name"], "sites": names})
            if o["role"] in ("owner", "admin"):
                admin += names
        return {**who, "role": role, "org": org if role else None,
                "member_sites": sorted(set(member)), "admin_sites": sorted(set(admin)),
                "orgs": orgs}
    finally:
        db.close()


def role_of(config: dict, live_dir, user: str | None, headers=None, peer: str = "",
            site: str | None = None) -> str:
    """The role of the person asking. Basic mode: users.json for `user`.
    Sessions mode: from the session cookie and `site`'s organisation, never
    from a header; "" when there is no session or no membership."""
    if mode(config) == "sessions":
        who = session_caller(config, live_dir, headers, site)
        return (who or {}).get("role") or ""
    users = load_roles(roles_path(config, live_dir))
    if users is None:
        return "admin"                  # one shared login, before roles existed
    entry = users.get((user or "").strip())
    role = (entry or {}).get("role")
    return role if role in ROLES else "viewer"


def user_from(headers, peer: str, config: dict | None = None, live_dir=None) -> str:
    """Who is asking. Basic mode: who nginx says logged in (X-Skald-User),
    "" unless the connection is nginx's own. Sessions mode: the email of the
    session cookie's account (needs `live_dir`), whatever the headers say."""
    if mode(config) == "sessions":
        return (session_caller(config, live_dir, headers) or {}).get("email") or ""
    if peer != PROXY:
        return ""
    got = (headers.get("X-Skald-User") or "").strip()
    return got if NAME.match(got) else ""


# ------------------------------------------------------------ password file

def _read_lines(path: Path) -> list[str]:
    try:
        return [l for l in Path(path).read_text().splitlines() if l.strip()]
    except FileNotFoundError:
        return []


def users_in(path: Path) -> list[str]:
    return [l.split(":", 1)[0] for l in _read_lines(path) if ":" in l]


def hash_password(name: str, password: str, run=subprocess.run) -> str:
    """The password file line for `name`, the password passed on stdin only."""
    if shutil.which("htpasswd"):
        done = run(["htpasswd", "-n", "-i", "-B", name], input=password, text=True,
                   capture_output=True, check=True)
        return done.stdout.strip()
    if shutil.which("openssl"):
        done = run(["openssl", "passwd", "-6", "-stdin"], input=password, text=True,
                   capture_output=True, check=True)
        return f"{name}:{done.stdout.strip()}"
    raise RuntimeError("neither htpasswd nor openssl is installed")


def _write_lines(path: Path, lines: list[str]) -> None:
    try:
        st = os.stat(path)
        mode, owner = st.st_mode & 0o777, (st.st_uid, st.st_gid)
    except FileNotFoundError:
        mode, owner = 0o640, None
    write_atomic(Path(path), "\n".join(lines) + "\n")
    os.chmod(path, mode)
    if owner is not None:
        try:
            os.chown(path, *owner)
        except PermissionError:
            pass


def _save_roles(path: Path, users: dict) -> None:
    write_atomic(Path(path), json.dumps({"users": users}, indent=1, sort_keys=True) + "\n")
    os.chmod(path, 0o640)
    own_like_folder(path)


def _log(live_dir, action: str, name: str, detail: str = "") -> None:
    if live_dir is None:
        return
    who = os.environ.get("SUDO_USER") or os.environ.get("USER") or "?"
    line = (f"{datetime.now(timezone.utc).isoformat(timespec='seconds')}\t{action}\t{name}\t"
            f"{detail}\tby {who}\n")
    with open(Path(live_dir) / "access.log", "a", encoding="utf-8") as handle:
        handle.write(line)
    own_like_folder(Path(live_dir) / "access.log")


# ------------------------------------------------------------- commands

def cmd_user(ctx) -> int:
    a = ctx.args
    pw_file = htpasswd_path(ctx.config)
    roles_file = roles_path(ctx.config, ctx.live_dir)
    users = load_roles(roles_file)
    if a.action == "list":
        try:
            names = users_in(pw_file) if pw_file else []
        except PermissionError:
            ctx.err(f"cannot read {pw_file}: run skald user as root")
            return 1
        for name in sorted(set(names) | set(users or {})):
            role = role_of(ctx.config, ctx.live_dir, name)
            where = "" if name in names else "  (no password line: cannot log in)"
            ctx.out(f"{name:<20} {role}{where}")
        if users is None:
            ctx.out("no roles file yet: every login is admin until one is written")
        return 0
    name = (a.name or "").strip()
    if not NAME.match(name):
        ctx.err("user names: lower-case letters, digits, . _ - (at most 32)")
        return 2
    users = dict(users or {})
    if a.action == "role":
        if a.role not in ROLES:
            ctx.err("--role admin or viewer")
            return 2
        if users.get(name, {}).get("role") == "admin" and a.role != "admin" and \
                sum(1 for u in users.values() if u.get("role") == "admin") <= 1:
            ctx.err("refused: that would leave no admin")
            return 1
        users[name] = {**users.get(name, {}), "role": a.role}
        _save_roles(roles_file, users)
        _log(ctx.live_dir, "role", name, a.role)
        ctx.out(f"{name} is now {a.role}")
        return 0
    if pw_file is None:
        ctx.err("set access.htpasswd in the config (the nginx password file)")
        return 2
    if a.action == "add":
        if a.role not in ROLES:
            ctx.err("--role admin or viewer")
            return 2
        if name in users_in(pw_file):
            ctx.err(f"refused: {name} already has a password; it is never changed here")
            return 1
        if a.password_stdin:
            password = sys.stdin.readline().rstrip("\n")
        else:
            password = getpass.getpass(f"password for {name}: ")
            if password != getpass.getpass("again: "):
                ctx.err("the two passwords differ")
                return 1
        if len(password) < 12:
            ctx.err("refused: at least 12 characters")
            return 1
        line = hash_password(name, password)
        _write_lines(pw_file, _read_lines(pw_file) + [line])
        users[name] = {"role": a.role, "added_at": datetime.now(timezone.utc)
                       .isoformat(timespec="seconds"),
                       "added_by": os.environ.get("SUDO_USER") or os.environ.get("USER") or ""}
        _save_roles(roles_file, users)
        _log(ctx.live_dir, "add", name, a.role)
        ctx.out(f"added {name} ({a.role}); nginx reads the file on each request")
        return 0
    if a.action == "remove":
        if users.get(name, {}).get("role") == "admin" and \
                sum(1 for u in users.values() if u.get("role") == "admin") <= 1:
            ctx.err("refused: that would leave no admin")
            return 1
        lines = _read_lines(pw_file)
        kept = [l for l in lines if l.split(":", 1)[0] != name]
        if len(kept) == len(lines) and name not in users:
            ctx.err(f"no user {name}")
            return 1
        _write_lines(pw_file, kept)
        users.pop(name, None)
        _save_roles(roles_file, users)
        _log(ctx.live_dir, "remove", name)
        ctx.out(f"removed {name}")
        return 0
    return 2


def add_command(sub) -> None:
    p = sub.add_parser("user", help="named dashboard users and their roles (run as root)")
    p.add_argument("action", choices=("list", "add", "remove", "role"))
    p.add_argument("name", nargs="?")
    p.add_argument("--role", choices=ROLES, default="viewer")
    p.add_argument("--password-stdin", action="store_true",
                   help="read the new user's password from stdin")
    p.set_defaults(run=cmd_user)
