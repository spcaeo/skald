"""Read config.yml, with or without PyYAML.

The package runs on the standard library alone, so the config file has to be
readable by a small parser too. It handles exactly what config.example.yml
uses: top-level sections, one level of keys under them, flow lists ("[a, b]")
and block lists ("- a"). Values come back as strings; callers wrap numbers in
int().

Secrets never live here. The mail section names the environment variables
that hold the SMTP login, and mailer.py reads them at send time.
"""
from __future__ import annotations

import json
import re
from pathlib import Path


def load_config(path: Path) -> dict:
    """Read config.yml. Falls back to a plain parser so PyYAML is optional."""
    path = Path(path)
    if not path.exists():
        return {}
    text = path.read_text()
    try:
        import yaml
        return yaml.safe_load(text) or {}
    except ImportError:
        # JSON is YAML too: PyYAML reads it, so the plain parser must as well.
        if text.lstrip().startswith("{"):
            return json.loads(text) or {}
        return tiny_yaml(text)


# A comment starts at "#" at the start of a line or after whitespace. A "#"
# inside a value - a URL fragment - is kept.
_COMMENT = re.compile(r"(^|\s)#.*$")


def tiny_yaml(text: str) -> dict:
    """Enough YAML for this one config: two levels and simple lists.

    A list item may be a flow mapping on one line - `- {name: A, path_prefix:
    /a/}` - which is how dashboard.views is written. Values in it cannot
    contain a comma; none of the config's do.
    """
    root: dict = {}
    section: dict | None = None
    key = None
    for raw in text.splitlines():
        line = _COMMENT.sub("", raw).rstrip()
        if not line.strip():
            continue
        if not line.startswith(" "):
            name = line.rstrip(":").strip()
            section = root.setdefault(name, {})
            key = None
        elif line.strip().startswith("- ") and section is not None and not key:
            # A top-level list (`sites:` then "  - file.yml"): the section
            # itself is the list.
            if not isinstance(root.get(name), list):
                root[name] = []
            root[name].append(line.strip()[2:].strip().strip("'\""))
        elif line.strip().startswith("- ") and section is not None and key:
            # "key:" on its own line is how YAML opens a block list, so the
            # placeholder left by the branch below becomes a list here.
            if not isinstance(section.get(key), list):
                section[key] = []
            item = line.strip()[2:].strip()
            if item.startswith("{") and item.endswith("}"):
                section[key].append(_flow_mapping(item[1:-1]))
            else:
                section[key].append(item.strip("'\""))
        elif ":" in line and section is not None:
            k, _, v = line.strip().partition(":")
            key = k.strip()
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                inner = v[1:-1].strip()
                if inner.startswith("{"):
                    # A flow list of flow mappings: [{ip: a, label: b}, {...}]
                    section[key] = [_flow_mapping(m) for m in re.findall(r"\{([^}]*)\}", inner)]
                else:
                    section[key] = [i.strip().strip("'\"") for i in inner.split(",")] if inner else []
            elif v == "":
                # Either a block list or a nested mapping; the next line says
                # which. Empty until then.
                section[key] = []
            elif v.lower() in ("true", "false"):
                # As PyYAML reads them: bool("false") is True, which turned
                # a switched-off option on.
                section[key] = v.lower() == "true"
            else:
                section[key] = v.strip("'\"")
    return root


def _flow_mapping(inner: str) -> dict:
    out = {}
    for part in inner.split(","):
        if ":" in part:
            k, _, v = part.partition(":")
            out[k.strip()] = v.strip().strip("'\"")
    return out


def setting(config: dict, section: str, key: str, default=None):
    """One value, with an empty list or empty string treated as unset.

    The tiny parser cannot tell "url:" (nothing) from "url:" opening a list,
    so both come back as []. Either way the caller meant "not set".
    """
    got = (config.get(section) or {}).get(key)
    if got in (None, "", []):
        return default
    return got


def site_name(config: dict) -> str:
    """The name history rows and the dashboard are filed under.

    `site.name` if given, else the first of `site.hosts`, else "site". It is
    a label taken from the config, never something the package knows.
    """
    name = setting(config, "site", "name")
    if name:
        return str(name)
    hosts = setting(config, "site", "hosts") or []
    return str(hosts[0]) if hosts else "site"


def country_credit(config: dict) -> tuple[str, str | None] | None:
    """(text, url) crediting where countries come from, or None.

    `report.country_credit` and `report.country_credit_url`. A GeoIP
    database's free licence usually requires attribution wherever its data
    is shown. Unset, a GeoIP file Skald itself reads (`logs.country_db`,
    or the city file `logs.city_db`) that is one of DB-IP's gets DB-IP's
    credit. Only an http(s) URL becomes a link.
    """
    text = setting(config, "report", "country_credit")
    if not text:
        from .conversions.geo import city_database, credit, database
        return credit(database(config), city_database(config))
    url = setting(config, "report", "country_credit_url")
    url = str(url) if url and str(url).startswith(("https://", "http://")) else None
    return str(text), url


# The key that holds the value in a labelled `ours` entry, per list.
OURS_KEYS = {"user_agents": "agent", "referrers": "referrer", "addresses": "ip"}
OURS_KINDS = {"user_agents": "user agent", "referrers": "referrer", "addresses": "address"}


def ours_entries(raw, which: str) -> list[tuple[str, str]]:
    """(value, label) for one `ours` list.

    An entry is a plain string - the old form - or a mapping with the value
    under its key (agent, referrer or ip) and an optional `label`:
    `{ip: 192.0.2.10, label: "Office Mac"}`. Without a label, an agent or
    referrer is labelled by itself; an address is labelled "Listed address
    N" - an address is never used as a label, because labels are shown on
    the dashboard and the address must not be.
    """
    out: list[tuple[str, str]] = []
    key = OURS_KEYS[which]
    for i, item in enumerate(raw or [], 1):
        if isinstance(item, dict):
            value = item.get(key) or item.get("value") or ""
            label = item.get("label") or ""
        else:
            value, label = item, ""
        value = str(value).strip()
        if not value:
            continue
        if not str(label).strip():
            label = f"Listed address {i}" if which == "addresses" else value
        out.append((value, str(label).strip()))
    return out


def ours_rules(config: dict) -> list[dict]:
    """Everything that counts as our own traffic, by label and kind, in the
    order the classifier tries them. Never the values themselves: an
    address is shown only by its label."""
    from .ours_store import live, load, path_of, paused_since
    ours = (config or {}).get("ours") or {}
    rules = [{"label": label, "kind": OURS_KINDS[which], "source": "config"}
             for which in ("user_agents", "referrers", "addresses")
             for _, label in ours_entries(ours.get(which), which)]
    # A paused page-added address is still listed, marked paused (2026-10-18).
    return rules + [{"label": e["label"], "kind": "address", "source": "file",
                     "paused": paused_since(e) is not None}
                    for e in live(load(path_of(config)))]


# Directories the dashboard writes beside the view pages.
RESERVED_SLUGS = {"exports", "api", "data"}


class View:
    """A slice of the site by path: a pre-built dashboard view.

    `path_prefix` is what a path must start with (empty: any path);
    `exclude` lists prefixes it must not start with. A prefix ending in "/"
    also matches the same path without the slash, so "/ca/" covers the
    Canada home page whether it is requested as /ca or /ca/. Matching is
    case-sensitive and on the path only, never the query string.
    """

    def __init__(self, name: str, path_prefix: str = "",
                 exclude: tuple[str, ...] = ()) -> None:
        from .files import slug
        self.name = name
        self.slug = slug(name.lower())
        self.path_prefix = path_prefix
        self.exclude = tuple(exclude)

    @staticmethod
    def _under(path: str, prefix: str) -> bool:
        if not prefix:
            return True
        return path.startswith(prefix) or (
            prefix.endswith("/") and path == prefix[:-1])

    def matches(self, path: str) -> bool:
        return self._under(path, self.path_prefix) and not any(
            self._under(path, x) for x in self.exclude)

    def describe(self) -> str:
        """The rule in words, for the page and the history row."""
        what = (f"paths under {self.path_prefix}" if self.path_prefix
                else "all paths")
        if self.exclude:
            what += " except under " + " and ".join(self.exclude)
        return what


def views(config: dict) -> list[View]:
    """`dashboard.views`: [{name, path_prefix, exclude_prefix}, ...].

    `exclude_prefix` may hold several prefixes separated by spaces. A view
    without a name, or two views whose names slug the same, is a config
    error rather than something to guess around.
    """
    raw = setting(config, "dashboard", "views") or []
    found: list[View] = []
    for item in raw:
        if not isinstance(item, dict) or not item.get("name"):
            raise ValueError(f"dashboard.views: each view needs a name, got {item!r}")
        exclude = item.get("exclude_prefix") or ""
        if isinstance(exclude, str):
            exclude = exclude.split()
        view = View(str(item["name"]), str(item.get("path_prefix") or ""),
                    tuple(str(x) for x in exclude))
        if view.slug in RESERVED_SLUGS:
            raise ValueError(f"dashboard.views: {view.name!r} would overwrite the "
                             f"dashboard's own {view.slug}/ directory; rename it")
        if any(v.slug == view.slug for v in found):
            raise ValueError(f"dashboard.views: two views are both {view.slug!r}")
        found.append(view)
    return found
