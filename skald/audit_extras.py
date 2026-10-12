"""The audit's own recount of the day extras and the visitor hashes.

Part of audit.py's second road, written apart from extras.py, campaigns.py
and visitors.py: it reads the raw lines audit.recount already parsed and
classified, and counts again - requests per group per hour, AI fetches per
tier per hour, 5xx per hour; every 404 and 410 by path, status, who asked
and whether it was a scanner probe; page views, landings and AI and
search fetches per page; visits per UTM tag, ad network and ref= value;
the heartbeat; and, when the visitor key is set, each visitor's keyed
hash for the day. Nothing from the package's code is called; only the
documented rules (DATA-CONTRACT.md, visitors.py) are written again.
"""
from __future__ import annotations

import hashlib
import hmac
import os
from collections import Counter
from urllib.parse import parse_qsl

OTHER = "(all others)"
NONE = "(none)"
NETWORKS = (("gclid", "Google Ads"), ("gbraid", "Google Ads"), ("wbraid", "Google Ads"),
            ("msclkid", "Microsoft Ads"), ("fbclid", "Meta"), ("li_fat_id", "LinkedIn"),
            ("ttclid", "TikTok"), ("twclid", "X"))
UTM = ("source", "medium", "campaign", "term", "content")


def secret(config: dict) -> bytes | None:
    """SKALD_VISITOR_KEY from the environment or report.env_file."""
    name = "SKALD_VISITOR_KEY"
    value = os.environ.get(name, "").strip()
    path = ((config or {}).get("report") or {}).get("env_file")
    if not value and path:
        try:
            with open(str(path), encoding="utf-8") as handle:
                for raw in handle:
                    raw = raw.strip()
                    raw = raw[7:].strip() if raw.startswith("export ") else raw
                    if raw.startswith(name + "="):
                        value = raw.split("=", 1)[1].strip().strip("'\"")
        except OSError:
            pass
    return value.encode() if value else None


def keyed(key: bytes, address: str, family: str) -> str:
    inner = hmac.new(key, address.encode("utf-8", "replace"), hashlib.sha256).hexdigest()
    return hashlib.sha256(f"{inner}|{family}".encode()).hexdigest()[:32]


def _tags(url: str) -> dict:
    if "?" not in url:
        return {}
    try:
        return {k.lower(): v for k, v in parse_qsl(url.split("?", 1)[1])[:60]}
    except ValueError:
        return {}


def _utc_key(when) -> str:
    """The UTC hour a line falls in, "YYYY-MM-DDTHH"."""
    from datetime import timezone
    return when.astimezone(timezone.utc).isoformat()[:13]


def _norm(v: str, n: int = 60) -> str:
    return " ".join(str(v).split()).strip().lower()[:n]


class ExtrasRecount:
    def __init__(self, tz, heartbeat: str, key: bytes | None) -> None:
        self.tz, self.heartbeat, self.key = tz, heartbeat, key
        self.hours: dict[str, Counter] = {}
        self.hours_utc: dict[str, Counter] = {}
        self.nf: Counter = Counter()
        self.pages: dict[str, Counter] = {}
        self.campaigns: dict[str, Counter] = {}
        self.beats = Counter()
        self.visitors: Counter = Counter()

    def hit(self, line, group: str, tier: str, name: str, ours_label: str,
            page: bool, probe: bool) -> None:
        hour = f"{line.when.astimezone(self.tz).hour:02d}"
        row = self.hours.setdefault(hour, Counter())
        utc = self.hours_utc.setdefault(_utc_key(line.when), Counter())
        for r in (row, utc):
            r[group] += 1
            if tier:
                r["ai_" + tier] += 1
            if line.status.startswith("5"):
                r["server_errors"] += 1
        if line.status in ("404", "410"):
            who = ("ai_" + tier) if group == "answer_engines" else group
            self.nf[(line.path[:100], int(line.status), who, probe)] += 1
        if page:
            key = {"people": "views", "search_engines": "search"}.get(group)
            key = ("ai_" + tier) if group == "answer_engines" else key
            if key:
                self.pages.setdefault(line.path[:70], Counter())[key] += 1
        if group == "ours" and ours_label == self.heartbeat:
            self.beats["ok" if line.status[:1] in ("2", "3") else "failed"] += 1
        if group == "answer_engines" and self.key is not None:
            self.visitors[(keyed(self.key, line.address, name), tier)] += 1

    def visit(self, landing, family: str) -> None:
        """One reader's visit, by its first page line."""
        self.hours_utc.setdefault(_utc_key(landing.when), Counter())["readers"] += 1
        self.pages.setdefault(landing.path[:70], Counter())["entries"] += 1
        tags = _tags(landing.url)
        names = {f"utm_{k}": (_norm(tags[f"utm_{k}"]) if tags.get(f"utm_{k}", "").strip()
                              else NONE) for k in UTM}
        names["paid"] = next((net for k, net in NETWORKS if tags.get(k)), NONE)
        names["ref_param"] = next((_norm(tags[k]) for k in ("ref", "source", "via")
                                   if tags.get(k, "").strip()), NONE)
        for d, name in names.items():
            self.campaigns.setdefault(d, Counter())[name] += 1
        if self.key is not None:
            self.visitors[(keyed(self.key, landing.address, family), "reader")] += 1

    def figures(self) -> dict:
        return {"hours": self.hours, "hours_utc": self.hours_utc, "not_found": self.nf,
                "pages": self.pages,
                "campaigns": self.campaigns, "beats": self.beats,
                "visitors": self.visitors if self.key is not None else None}


def compare(stored: dict | None, visitors: dict | None, got: dict, same, problems) -> None:
    """Stored extras blobs ({kind: blob}) against the recount. `visitors`
    is {(hash, kind): n} as history holds it, or None to skip."""
    if not stored:
        problems.append("no day extras stored to compare")
        return
    hourly = stored.get("hourly") or {}
    for hour in sorted(set(hourly) | set(got["hours"])):
        mine = got["hours"].get(hour, Counter())
        for k in ("people", "answer_engines", "search_engines", "bots", "ours", "ai_asked",
                  "ai_training", "server_errors"):
            same(f"hour {hour}: {k}", int((hourly.get(hour) or {}).get(k, 0)), mine.get(k, 0))
    if "hourly_utc" in stored:
        utc = stored.get("hourly_utc") or {}
        for hour in sorted(set(utc) | set(got["hours_utc"])):
            mine = got["hours_utc"].get(hour, Counter())
            for k in ("people", "answer_engines", "search_engines", "bots", "ours", "readers",
                      "ai_asked", "ai_training", "server_errors"):
                same(f"UTC hour {hour}: {k}", int((utc.get(hour) or {}).get(k, 0)), mine.get(k, 0))
    nf = Counter()
    for r in stored.get("not_found") or []:
        nf[(r["path"], int(r["status"]), r["group"], bool(r["probe"]))] += r["n"]
    for key in sorted(set(nf) | set(got["not_found"]), key=str):
        same(f"404/410 {key[0]} ({key[2]}, {key[1]})", nf.get(key, 0), got["not_found"].get(key, 0))
    pages = stored.get("pages") or {}
    for path in sorted(set(pages) | set(got["pages"])):
        mine = got["pages"].get(path, Counter())
        for k in ("views", "entries", "ai_asked", "ai_training", "search"):
            same(f"page {path}: {k}", int((pages.get(path) or {}).get(k, 0)), mine.get(k, 0))
    rows = ((stored.get("campaigns") or {}).get("rows")) or {}
    for d, counted in got["campaigns"].items():
        kept = {r["name"]: r["visits"] for r in rows.get(d, [])}
        for name in sorted(k for k in kept if k != OTHER):
            same(f"visits by {d}: {name}", kept[name], counted.get(name, 0))
        same(f"visits by {d}: {OTHER}", kept.get(OTHER, 0),
             sum(counted.values()) - sum(counted.get(k, 0) for k in kept if k != OTHER))
    beat = ((stored.get("ours") or {}).get("heartbeat")) or {}
    same("heartbeats answered", int(beat.get("ok", 0)), got["beats"].get("ok", 0))
    same("heartbeats failed", int(beat.get("failed", 0)), got["beats"].get("failed", 0))
    if visitors is not None and got["visitors"] is not None:
        for key in sorted(set(visitors) | set(got["visitors"])):
            if visitors.get(key, 0) != got["visitors"].get(key, 0):
                problems.append(f"visitor hash {key[0][:8]}... ({key[1]}): history has "
                                f"{visitors.get(key, 0)}, the recount finds "
                                f"{got['visitors'].get(key, 0)}")
        same("visitor hashes", len(visitors), len(got["visitors"]))
