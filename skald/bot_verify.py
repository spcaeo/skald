"""Is "Googlebot" really Googlebot? Checking crawler claims, and fake browsers.

A user agent is a claim anyone can make. The crawlers that matter publish
how to check them:

  ranges    the owner publishes the addresses it crawls from (Google, Bing,
            Apple, OpenAI, Perplexity, Anthropic, DuckDuckGo)
  dns       the address's reverse DNS name ends in the owner's domain, and
            that name resolves back to the same address (Google, Bing,
            Apple, Yandex)
  network   the owner's own network (Meta: AS32934's announced prefixes)

Each named assistant or search crawler hit is then

  verified    the address is the owner's
  spoofed     the owner's list or DNS says it is not: filed under bots, as
              "claims to be <name>"
  unverified  nothing to check against (no list published, the list could
              not be fetched, DNS not looked up yet or it timed out). The
              claim is kept: an unreachable list never moves a fetch.

**Nothing here touches the network while counting.** Lists are fetched once
a day by `skald verify-bots` (run-daily runs it first) into `bots.ranges_dir`,
each with its fetch date, and the last good copy is kept when a fetch fails.
Reverse DNS is looked up by the same command for the crawler addresses in
the logs it has not seen, a few seconds at most, and kept in `dns.json`
beside the lists. Classification only reads those files, so the daily
collect and the audit that follows it read the same answers.

The same files carry the hosting networks (the big clouds and hosters, by
their announced prefixes): a browser user agent from one of them is flagged
"hosting_network" - a flag, not a verdict, because VPNs exit there too.
"""
from __future__ import annotations

import bisect
import ipaddress
import json
import re
import socket
import threading
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .files import write_atomic

RIPE = "https://stat.ripe.net/data/announced-prefixes/data.json?resource=AS{asn}"
GOOGLE = "https://developers.google.com/static/crawling/ipranges/"

# list name -> URL. Every one is a JSON file of {"prefixes": [{"ipv4Prefix"
# or "ipv6Prefix": cidr}]}, except the network ones (RIPEstat).
LISTS = {
    "google-common": GOOGLE + "common-crawlers.json",
    "google-special": GOOGLE + "special-crawlers.json",
    "google-user": GOOGLE + "user-triggered-fetchers.json",
    "google-user-google": GOOGLE + "user-triggered-fetchers-google.json",
    "bing": "https://www.bing.com/toolbox/bingbot.json",
    "apple": "https://search.developer.apple.com/applebot.json",
    "openai-gptbot": "https://openai.com/gptbot.json",
    "openai-searchbot": "https://openai.com/searchbot.json",
    "openai-chatgpt-user": "https://openai.com/chatgpt-user.json",
    "openai-adsbot": "https://openai.com/adsbot.json",
    "perplexity-bot": "https://www.perplexity.ai/perplexitybot.json",
    "perplexity-user": "https://www.perplexity.ai/perplexity-user.json",
    "anthropic": "https://claude.com/crawling/bots.json",
    "duckduckgo": "https://duckduckgo.com/duckduckbot.json",
    "meta": RIPE.format(asn=32934),
}

# Hosting and cloud networks, by AS number: a browser agent from one of these
# is flagged, never moved.
HOSTING_ASNS = {
    16509: "Amazon AWS", 14618: "Amazon AWS", 15169: "Google", 396982: "Google Cloud",
    8075: "Microsoft Azure", 14061: "DigitalOcean", 24940: "Hetzner", 213230: "Hetzner",
    16276: "OVH", 63949: "Akamai Linode", 20473: "Vultr", 51167: "Contabo",
    47583: "Hostinger", 31898: "Oracle Cloud", 45102: "Alibaba Cloud",
    132203: "Tencent Cloud", 12876: "Scaleway", 9009: "M247", 60068: "Datacamp",
    212238: "Datacamp", 46606: "Unified Layer", 36352: "ColoCrossing",
}

# Who owns each crawler, by the name the classifier matched (lower case),
# and how to check it: (vendor, lists, dns suffixes, network list).
VENDORS = {
    "google": (("google-common", "google-special", "google-user", "google-user-google"),
               ("googlebot.com", "google.com", "googleusercontent.com")),
    "bing": (("bing",), ("search.msn.com",)),
    "apple": (("apple",), ("applebot.apple.com",)),
    "yandex": ((), ("yandex.ru", "yandex.net", "yandex.com")),
    "openai": (("openai-gptbot", "openai-searchbot", "openai-chatgpt-user", "openai-adsbot"),
               ()),
    "perplexity": (("perplexity-bot", "perplexity-user"), ()),
    "anthropic": (("anthropic",), ()),
    "duckduckgo": (("duckduckgo",), ()),
    "meta": (("meta",), ()),
}
CLAIMS = (
    (re.compile(r"^(?:googlebot|google-inspectiontool|googleother|apis-google"
                r"|adsbot-google|google-adwords-instant)$"), "google"),
    (re.compile(r"^(?:bingbot|bingpreview)$"), "bing"),
    (re.compile(r"^applebot(?:-extended)?$"), "apple"),
    (re.compile(r"^yandexbot$"), "yandex"),
    (re.compile(r"^(?:gptbot|oai-searchbot|chatgpt-user|oai-adsbot)$"), "openai"),
    (re.compile(r"^(?:perplexitybot|perplexity-user)$"), "perplexity"),
    (re.compile(r"^(?:claudebot|claude-user|claude-searchbot|anthropic-ai)$"), "anthropic"),
    (re.compile(r"^(?:duckduckbot|duckassistbot)$"), "duckduckgo"),
    (re.compile(r"^(?:meta-externalagent|meta-externalfetcher|facebookbot)$"), "meta"),
)
# Agents that run on the asker's own machine, so no owner list can hold
# them: Claude Code fetching a page for a developer says Claude-User.
LOCAL_TOOL = re.compile(r"claude-code/", re.I)

# A list older than this is not trusted to say "spoofed" any more.
MAX_LIST_AGE = timedelta(days=7)
# Lists all fetched this recently are not fetched again: run-daily runs
# verify-bots once per site, and every site shares the one folder.
REFETCH_AFTER = timedelta(hours=12)
DNS_FILE = "dns.json"
DNS_TTL = timedelta(days=7)
FETCH_TIMEOUT = 10


def vendor_of(name: str) -> str | None:
    low = (name or "").lower()
    for pattern, vendor in CLAIMS:
        if pattern.match(low):
            return vendor
    return None


def method_of(vendor: str | None) -> str:
    if vendor is None:
        return "none"
    lists, suffixes = VENDORS[vendor]
    if vendor == "meta":
        return "network"
    return "ranges" if lists else ("dns" if suffixes else "none")


class NetSet:
    """Address ranges, merged and searchable in log time."""

    def __init__(self, cidrs) -> None:
        spans = {4: [], 6: []}
        for cidr in cidrs:
            try:
                net = ipaddress.ip_network(str(cidr).strip(), strict=False)
            except ValueError:
                continue
            spans[net.version].append((int(net.network_address), int(net.broadcast_address)))
        self.starts, self.ends, self.size = {}, {}, 0
        for version, got in spans.items():
            got.sort()
            merged: list[list[int]] = []
            for a, b in got:
                if merged and a <= merged[-1][1] + 1:
                    merged[-1][1] = max(merged[-1][1], b)
                else:
                    merged.append([a, b])
            self.starts[version] = [a for a, _ in merged]
            self.ends[version] = [b for _, b in merged]
            self.size += len(got)

    def __contains__(self, address: str) -> bool:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            return False
        starts = self.starts.get(ip.version) or []
        i = bisect.bisect_right(starts, int(ip)) - 1
        return i >= 0 and int(ip) <= self.ends[ip.version][i]


# ------------------------------------------------------------------ files

def ranges_dir(config: dict) -> Path | None:
    raw = ((config or {}).get("bots") or {}).get("ranges_dir")
    return Path(str(raw)) if raw else None


def _read_json(path: Path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def load_list(folder: Path, name: str) -> dict | None:
    """A stored list: {"fetched", "source", "networks": [cidr], "error"}."""
    got = _read_json(Path(folder) / f"{name}.json")
    return got if isinstance(got, dict) and isinstance(got.get("networks"), list) else None


def _fresh(entry: dict | None, now: datetime) -> bool:
    if not entry or not entry.get("networks"):
        return False
    try:
        fetched = datetime.fromisoformat(entry["fetched"])
    except (KeyError, TypeError, ValueError):
        return False
    return now - fetched <= MAX_LIST_AGE


class Verifier:
    """Reads the stored lists and DNS answers; answers per (name, address).

    `status(name, address, agent)` is "verified", "unverified", "spoofed",
    or None for a name nobody can check (method "none")."""

    def __init__(self, folder: Path | None, now: datetime | None = None) -> None:
        self.folder = Path(folder) if folder else None
        self.now = now or datetime.now(timezone.utc)
        self.sets: dict[str, NetSet] = {}
        self.fresh: set[str] = set()
        self.dns: dict = {}
        self.hosting_set: NetSet | None = None
        self._memo: dict[tuple, str | None] = {}
        self._hosting_memo: dict[str, bool] = {}
        if self.folder is None:
            return
        for name in LISTS:
            entry = load_list(self.folder, name)
            if entry and entry.get("networks"):
                self.sets[name] = NetSet(entry["networks"])
                if _fresh(entry, self.now):
                    self.fresh.add(name)
        hosting = load_list(self.folder, "hosting")
        if hosting and hosting.get("networks"):
            self.hosting_set = NetSet(hosting["networks"])
        dns = _read_json(self.folder / DNS_FILE)
        self.dns = dns.get("answers", {}) if isinstance(dns, dict) else {}

    def status(self, name: str, address: str, agent: str = "") -> str | None:
        vendor = vendor_of(name)
        if vendor is None:
            return None
        if agent and LOCAL_TOOL.search(agent):
            return "unverified"
        key = (vendor, address)
        if key in self._memo:
            return self._memo[key]
        lists, suffixes = VENDORS[vendor]
        loaded = [n for n in lists if n in self.sets]
        result = "unverified"
        if any(address in self.sets[n] for n in loaded):
            result = "verified"
        elif suffixes:
            answer = (self.dns.get(f"{vendor}|{address}") or {}).get("result")
            if answer in ("verified", "spoofed"):
                result = answer
        elif lists and all(n in self.fresh for n in lists):
            result = "spoofed"
        self._memo[key] = result
        return result

    def hosting(self, address: str) -> bool:
        if self.hosting_set is None:
            return False
        got = self._hosting_memo.get(address)
        if got is None:
            got = self._hosting_memo[address] = address in self.hosting_set
        return got

    def lists_summary(self) -> dict:
        """{list: {"fetched","networks","ok","error"}} for bots.json."""
        out = {}
        for name in [*LISTS, "hosting"]:
            entry = load_list(self.folder, name) if self.folder else None
            out[name] = {"fetched": (entry or {}).get("fetched"),
                         "networks": len((entry or {}).get("networks") or []),
                         "ok": bool(entry and entry.get("networks") and not entry.get("error")),
                         "error": (entry or {}).get("error")}
        return out

    def dns_summary(self) -> dict:
        got = _read_json(self.folder / DNS_FILE) if self.folder else None
        return {"addresses": len(self.dns),
                "checked_at": got.get("checked_at") if isinstance(got, dict) else None}


def from_config(config: dict, now: datetime | None = None) -> Verifier | None:
    folder = ranges_dir(config)
    return Verifier(folder, now) if folder is not None else None


# --------------------------------------------------------------- fetching

def _get(url: str, timeout: int = FETCH_TIMEOUT) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "skald-ranges/1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read(20_000_000)


def parse_list(raw: bytes) -> list[str]:
    """CIDRs from a vendor list or a RIPEstat answer. Raises ValueError."""
    data = json.loads(raw)
    if isinstance(data, dict) and isinstance(data.get("prefixes"), list):
        out = [p.get("ipv4Prefix") or p.get("ipv6Prefix") for p in data["prefixes"]
               if isinstance(p, dict)]
    elif isinstance(data, dict) and isinstance((data.get("data") or {}).get("prefixes"), list):
        out = [p.get("prefix") for p in data["data"]["prefixes"] if isinstance(p, dict)]
    else:
        raise ValueError("not a list of prefixes")
    out = [c for c in out if c]
    for cidr in out:
        ipaddress.ip_network(cidr, strict=False)
    if not out:
        raise ValueError("an empty list")
    return out


def _store(folder: Path, name: str, url: str, networks: list[str] | None,
           error: str | None, now: datetime) -> None:
    """Write a list; on failure keep the last good networks and note why."""
    old = load_list(folder, name) or {}
    entry = {"source": url,
             "fetched": now.isoformat(timespec="seconds") if networks else old.get("fetched"),
             "networks": networks if networks else old.get("networks", []),
             "error": error, "tried": now.isoformat(timespec="seconds")}
    write_atomic(Path(folder) / f"{name}.json", json.dumps(entry) + "\n")


def refresh_lists(folder: Path, now: datetime | None = None, fetch=_get,
                  hosting: bool = True) -> dict[str, str]:
    """Fetch every list (and the hosting networks). {name: "ok" or error}.
    Never raises for a network failure: the last good copy stays."""
    now = now or datetime.now(timezone.utc)
    Path(folder).mkdir(parents=True, exist_ok=True)
    done: dict[str, str] = {}
    for name, url in LISTS.items():
        try:
            nets = parse_list(fetch(url))
            _store(folder, name, url, nets, None, now)
            done[name] = "ok"
        except Exception as why:          # noqa: BLE001 - any failure keeps the old copy
            _store(folder, name, url, None, f"{type(why).__name__}: {why}"[:200], now)
            done[name] = f"failed: {why}"[:200]
    if hosting:
        nets, errors = [], []
        for asn in HOSTING_ASNS:
            try:
                nets += parse_list(fetch(RIPE.format(asn=asn)))
            except Exception as why:      # noqa: BLE001
                errors.append(f"AS{asn}: {why}"[:80])
        _store(folder, "hosting", "RIPEstat announced prefixes of "
               + ", ".join(f"AS{a}" for a in HOSTING_ASNS), nets or None,
               "; ".join(errors)[:400] or None, now)
        done["hosting"] = "ok" if nets and not errors else ("partial" if nets else "failed")
    return done


def lists_current(folder: Path, now: datetime) -> bool:
    """Every list (and the hosting networks) fetched without error within
    REFETCH_AFTER: another site's run this morning already fetched them."""
    for name in [*LISTS, "hosting"]:
        entry = load_list(folder, name)
        if not entry or entry.get("error") or not entry.get("networks"):
            return False
        try:
            if now - datetime.fromisoformat(entry["fetched"]) > REFETCH_AFTER:
                return False
        except (KeyError, TypeError, ValueError):
            return False
    return True


# ------------------------------------------------------------------- DNS

def _reverse_forward(address: str, suffixes: tuple[str, ...]) -> tuple[str, str]:
    """(result, name): verified / spoofed / failed (could not tell)."""
    try:
        name = socket.gethostbyaddr(address)[0].lower().rstrip(".")
    except socket.herror as why:
        # HOST_NOT_FOUND: no reverse name, so not the crawler's. Anything
        # else (TRY_AGAIN) is a lookup that did not finish.
        return ("spoofed" if why.args and why.args[0] == 1 else "failed"), ""
    except (socket.gaierror, OSError):
        return "failed", ""
    if not any(name == s or name.endswith("." + s) for s in suffixes):
        return "spoofed", name
    try:
        forward = {i[4][0] for i in socket.getaddrinfo(name, None)}
    except (socket.gaierror, OSError):
        return "failed", name
    return ("verified" if address in forward else "spoofed"), name


def resolve(folder: Path, wanted: set[tuple[str, str]], now: datetime | None = None,
            budget_s: float = 20.0, lookup=_reverse_forward) -> dict[str, int]:
    """Look up (vendor, address) pairs not in dns.json (or older than
    DNS_TTL) in parallel threads, for at most `budget_s` seconds; pairs
    still running are left for next time. {result: n} of what was added."""
    now = now or datetime.now(timezone.utc)
    path = Path(folder) / DNS_FILE
    got = _read_json(path)
    answers = got.get("answers", {}) if isinstance(got, dict) else {}
    todo = []
    for vendor, address in sorted(wanted):
        old = answers.get(f"{vendor}|{address}")
        try:
            stale = now - datetime.fromisoformat(old["checked"]) > DNS_TTL if old else True
        except (KeyError, ValueError):
            stale = True
        if stale and VENDORS[vendor][1]:
            todo.append((vendor, address))
    results: dict[tuple, tuple] = {}

    def work(vendor, address):
        results[(vendor, address)] = lookup(address, VENDORS[vendor][1])

    threads = [threading.Thread(target=work, args=p, daemon=True) for p in todo[:200]]
    for t in threads:
        t.start()
    deadline = time.monotonic() + budget_s
    for t in threads:
        t.join(max(0.0, deadline - time.monotonic()))
    added: dict[str, int] = {}
    for (vendor, address), (result, name) in list(results.items()):
        answers[f"{vendor}|{address}"] = {"result": result, "name": name,
                                          "checked": now.isoformat(timespec="seconds")}
        added[result] = added.get(result, 0) + 1
    cutoff = now - timedelta(days=30)
    answers = {k: v for k, v in answers.items()
               if v.get("checked", "") >= cutoff.isoformat(timespec="seconds")}
    Path(folder).mkdir(parents=True, exist_ok=True)
    write_atomic(path, json.dumps({"checked_at": now.isoformat(timespec="seconds"),
                                   "answers": answers}, sort_keys=True) + "\n")
    return added


def claimed(config: dict, start: datetime, end: datetime) -> set[tuple[str, str]]:
    """(vendor, address) for every DNS-checkable crawler claim in a window."""
    from .classify import AI_ASKED, AI_TRAINING, SEARCH_ENGINE
    from .parse import read
    from .window import within, window_paths
    fmt = (config.get("logs") or {}).get("format") or "auto"
    out = set()
    for hit in within(read(window_paths(config, start, end), fmt), start, end):
        m = AI_ASKED.search(hit.user_agent) or AI_TRAINING.search(hit.user_agent) \
            or SEARCH_ENGINE.search(hit.user_agent)
        vendor = vendor_of(m.group(0)) if m else None
        if vendor and VENDORS[vendor][1]:
            out.add((vendor, hit.address))
    return out


# --------------------------------------------------------------- command

def run(ctx, lists: bool = True, budget_s: float = 30.0) -> int:
    """Refresh the lists (unless `lists` is False) and resolve the crawler
    addresses of yesterday and today. Exit 0, or 2 when not configured."""
    from . import runs
    from .window import day_window, yesterday
    folder = ranges_dir(ctx.config)
    if folder is None:
        ctx.err("verify-bots: set bots.ranges_dir in the config first")
        return 2
    now = ctx.now.astimezone(timezone.utc)
    if lists and lists_current(folder, now):
        ctx.out(f"lists: all fetched within {REFETCH_AFTER.seconds // 3600} hours; kept")
    elif lists:
        for name, said in refresh_lists(folder, now).items():
            ctx.out(f"list {name}: {said}")
    start = day_window(yesterday(ctx.tz, ctx.now), ctx.tz)[0]
    listed = Verifier(folder, now)
    wanted = {(vendor, address) for vendor, address
              in claimed(ctx.config, start, now + timedelta(seconds=1))
              if not any(address in listed.sets[n] for n in VENDORS[vendor][0]
                         if n in listed.sets)}
    added = resolve(folder, wanted, now, budget_s)
    ctx.out(f"dns: {len(wanted)} crawler addresses claimed; looked up "
            + (", ".join(f"{n} {k}" for k, n in sorted(added.items())) or "none new"))
    runs.record(ctx.live_dir, "verify-bots", 0)
    return 0


def cmd_verify_bots(ctx) -> int:
    return run(ctx, lists=not ctx.args.dns_only)


def add_command(sub) -> None:
    p = sub.add_parser("verify-bots", help="fetch the crawler owners' address lists and "
                       "look up reverse DNS of claimed crawlers (run-daily runs it first)")
    p.add_argument("--dns-only", action="store_true",
                   help="only look up addresses not seen yet; do not fetch the lists")
    p.set_defaults(run=cmd_verify_bots)
