"""AI crawler controls: allow, block, or block only the training crawlers.

The owner sets a policy per assistant (its owner, e.g. OpenAI) and, if they
want, per crawler. The refresh helper (refresh_server.py, as the
skald user) stores it in `bot_policy.file`; a root-owned systemd
path unit runs this file's `apply` when that file changes, which writes an
nginx map and reloads nginx. The helper never needs root, and nothing in the
policy file reaches the nginx config except as a choice between fixed
entries of CATALOG below.

Modes:
  per assistant   allow (the default), block, block_training (block the
                  "training" crawlers, keep the ones that index for AI
                  search and the ones fetching for a person's question)
  per crawler     allow or block; overrides its assistant's mode

The nginx side (`nginx_conf`):

  map $http_user_agent $skald_block_agent { default 0; "~*GPTBot" 1; ... }
  map $uri $skald_block { default $skald_block_agent; /robots.txt 0; }

and in the site's `location /`: `if ($skald_block) { return 403; }`, so a
blocked crawler is refused everything but robots.txt (it can still read the
rules), and short links, relay paths and the dashboard - other locations -
are never touched. A user agent is self-reported: blocking by it stops the
crawlers that say who they are, which the big ones do.

`apply` always runs `nginx -t` before a reload and puts the previous file
back when the test fails. `robots_lines` suggests robots.txt lines for the
same choices; nothing writes the website's robots.txt.

Standard library only and no package imports: root runs this file directly
(`python3 -I .../bot_policy.py apply ...`).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

VERSION = 1
OWNER_MODES = ("allow", "block", "block_training")
CRAWLER_MODES = ("allow", "block")
TIERS = ("training", "index", "asked")
MAX_BYTES = 16_384
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 -]{1,40}$")


@dataclass(frozen=True)
class Crawler:
    name: str            # the token its user agent carries
    owner: str           # the assistant or company it belongs to
    tier: str            # training, index (AI search) or asked (a person's question)
    robots_only: bool = False   # a robots.txt token no request carries: nginx cannot see it


# Every name in classify.AI_TRAINING and AI_ASKED (a test keeps them in
# step), plus the robots-only tokens. "training" and "index" are both
# "to train or index" on the dashboard; here they are split, so blocking
# training keeps the site in AI search answers.
CATALOG = (
    Crawler("GPTBot", "OpenAI", "training"),
    Crawler("OAI-SearchBot", "OpenAI", "index"),
    Crawler("ChatGPT-User", "OpenAI", "asked"),
    Crawler("ClaudeBot", "Anthropic", "training"),
    Crawler("anthropic-ai", "Anthropic", "training"),
    Crawler("Claude-SearchBot", "Anthropic", "index"),
    Crawler("Claude-User", "Anthropic", "asked"),
    Crawler("PerplexityBot", "Perplexity", "index"),
    Crawler("Perplexity-User", "Perplexity", "asked"),
    Crawler("Google-Extended", "Google", "training", robots_only=True),
    Crawler("Gemini-User", "Google", "asked"),
    Crawler("meta-externalagent", "Meta", "training"),
    Crawler("FacebookBot", "Meta", "training"),
    Crawler("meta-externalfetcher", "Meta", "asked"),
    Crawler("Applebot-Extended", "Apple", "training", robots_only=True),
    Crawler("Amazonbot", "Amazon", "training"),
    Crawler("Bytespider", "ByteDance", "training"),
    Crawler("CCBot", "Common Crawl", "training"),
    Crawler("cohere-ai", "Cohere", "training"),
    Crawler("Diffbot", "Diffbot", "training"),
    Crawler("omgili", "Webz.io", "training"),
    Crawler("AI2Bot", "Allen Institute for AI", "training"),
    Crawler("Timpibot", "Timpi", "training"),
    Crawler("ImagesiftBot", "ImageSift", "training"),
    Crawler("YouBot", "You.com", "index"),
    Crawler("PanguBot", "Huawei", "training"),
    Crawler("Kangaroo Bot", "Kangaroo LLM", "training"),
    Crawler("DuckAssistBot", "DuckDuckGo", "index"),
    Crawler("BingPreview", "Microsoft", "asked"),
    Crawler("MistralAI-User", "Mistral", "asked"),
    # Added 2026-10-18 with classify.py's lists.
    Crawler("Claude-Web", "Anthropic", "asked"),
    Crawler("Google-Agent", "Google", "asked"),
    Crawler("GoogleAgent-Mariner", "Google", "asked"),
    Crawler("Google-GeminiNotebook", "Google", "asked"),
    Crawler("Google-NotebookLM", "Google", "asked"),
    Crawler("Google-CloudVertexBot", "Google", "index"),
    Crawler("Amzn-SearchBot", "Amazon", "index"),
    Crawler("Amzn-User", "Amazon", "asked"),
    Crawler("cohere-training-data-crawler", "Cohere", "training"),
    # Added 2026-10-25: OpenAI's check of ad landing pages. Not training and
    # nobody waits on it, so it sits with the index crawlers: "block
    # training" leaves it alone.
    Crawler("OAI-AdsBot", "OpenAI", "index"),
)
BY_NAME = {c.name: c for c in CATALOG}
OWNERS = tuple(dict.fromkeys(c.owner for c in CATALOG))
_MATCHERS = tuple((re.compile(re.escape(c.name), re.I), c) for c in CATALOG
                  if not c.robots_only)


class Invalid(ValueError):
    """A policy that names an unknown assistant, crawler or mode."""


def match(agent: str) -> Crawler | None:
    """The catalog crawler a user agent names, or None."""
    for pattern, crawler in _MATCHERS:
        if pattern.search(agent or ""):
            return crawler
    return None


# ------------------------------------------------------------ the policy

def empty() -> dict:
    return {"version": VERSION, "owners": {}, "crawlers": {}, "updated_at": None,
            "updated_by": None}


def validate(data) -> dict:
    """A clean policy from untrusted JSON, or Invalid. Only names from the
    catalog and modes from the fixed lists survive; "allow" entries are
    dropped, since allow is the default."""
    if not isinstance(data, dict):
        raise Invalid("the policy must be a JSON object")
    owners = data["owners"] if data.get("owners") is not None else {}
    crawlers = data["crawlers"] if data.get("crawlers") is not None else {}
    if not isinstance(owners, dict) or not isinstance(crawlers, dict):
        raise Invalid("owners and crawlers must be objects")
    out = empty()
    for owner, mode in owners.items():
        if owner not in OWNERS:
            raise Invalid(f"unknown assistant: {str(owner)[:40]}")
        if mode not in OWNER_MODES:
            raise Invalid(f"{owner}: mode must be one of {', '.join(OWNER_MODES)}")
        if mode != "allow":
            out["owners"][owner] = mode
    for name, mode in crawlers.items():
        if name not in BY_NAME:
            raise Invalid(f"unknown crawler: {str(name)[:40]}")
        if mode not in CRAWLER_MODES:
            raise Invalid(f"{name}: mode must be allow or block")
        out["crawlers"][name] = mode
    for key in ("updated_at", "updated_by"):
        value = data.get(key)
        out[key] = str(value)[:64] if value else None
    return out


def decide(policy: dict, crawler: Crawler) -> str:
    """"allow" or "block" for one crawler under a policy."""
    own = (policy.get("crawlers") or {}).get(crawler.name)
    if own in CRAWLER_MODES:
        return own
    mode = (policy.get("owners") or {}).get(crawler.owner, "allow")
    if mode == "block" or (mode == "block_training" and crawler.tier == "training"):
        return "block"
    return "allow"


def blocked(policy: dict) -> list[Crawler]:
    return [c for c in CATALOG if decide(policy, c) == "block"]


def nginx_conf(policy: dict) -> str:
    """The http-level nginx file: $skald_block is 1 for a blocked crawler's
    request, except robots.txt. Robots-only tokens never reach it."""
    rows = []
    for c in blocked(policy):
        if c.robots_only:
            continue
        if not SAFE_NAME.match(c.name):          # never true for the catalog
            raise Invalid(f"unsafe crawler name {c.name!r}")
        rows.append(f'    "~*{c.name}" 1;')
    return "\n".join([
        "# Generated by Skald (skald/bot_policy.py) from the AI crawler",
        "# settings. Do not edit: the next change of the settings rewrites it.",
        "map $http_user_agent $skald_block_agent {",
        "    default 0;",
        *rows,
        "}",
        "# robots.txt is always answered, so a blocked crawler can read the rules.",
        "map $uri $skald_block {",
        "    default $skald_block_agent;",
        "    /robots.txt 0;",
        "}",
        "",
    ])


def robots_lines(policy: dict) -> str:
    """robots.txt lines matching the policy: a suggestion to copy by hand."""
    out = []
    for c in blocked(policy):
        out += [f"User-agent: {c.name}", "Disallow: /", ""]
    return "\n".join(out)


def view(policy: dict) -> dict:
    """The settings screen's data: every assistant with its crawlers."""
    return {
        "modes": {"owner": list(OWNER_MODES), "crawler": list(CRAWLER_MODES)},
        "assistants": [
            {"owner": owner, "mode": (policy.get("owners") or {}).get(owner, "allow"),
             "crawlers": [{"name": c.name, "tier": c.tier, "robots_only": c.robots_only,
                           "override": (policy.get("crawlers") or {}).get(c.name),
                           "effective": decide(policy, c)}
                          for c in CATALOG if c.owner == owner]}
            for owner in OWNERS],
        "blocked": [c.name for c in blocked(policy)],
        "robots_suggestion": robots_lines(policy),
    }


# ------------------------------------------------------------ files

def _read_json(path: Path):
    """JSON from a file the skald user can write: never through a
    symlink, never more than MAX_BYTES, and no file content in errors."""
    import stat
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    fd = os.open(str(path), flags)
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        os.close(fd)
        raise Invalid("the policy file is not a regular file")
    with os.fdopen(fd, "rb") as handle:
        raw = handle.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise Invalid("the policy file is too large")
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise Invalid("the policy file is not valid JSON") from None


def _write(path: Path, text: str, mode: int = 0o644) -> None:
    """Temp file beside `path`, renamed over it (a symlink at `path` is
    replaced, never followed)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def load(path: Path) -> dict:
    """The stored policy; the all-allow one when there is none yet."""
    try:
        return validate(_read_json(Path(path)))
    except FileNotFoundError:
        return empty()


def save(path: Path, data, by: str | None = None, now: datetime | None = None) -> dict:
    """Validate and store a policy (the helper's POST)."""
    policy = validate(data)
    policy["updated_at"] = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    policy["updated_by"] = (by or "page")[:64]
    _write(Path(path), json.dumps(policy, indent=2, sort_keys=True) + "\n")
    return policy


def paths(config: dict) -> tuple[Path, Path]:
    """(policy file, apply-status file): `bot_policy.file` and
    `bot_policy.status`, by default beside the history."""
    got = (config or {}).get("bot_policy") or {}
    db = ((config or {}).get("history") or {}).get("db") or "history.sqlite"
    base = Path(str(db)).parent
    return (Path(str(got.get("file") or base / "bot-policy.json")),
            Path(str(got.get("status") or base / "bot-policy-applied.json")))


def status(path: Path) -> dict | None:
    try:
        got = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return got if isinstance(got, dict) else None


# ------------------------------------------------------------ apply (root)

def apply(policy_path: Path, conf_path: Path, status_path: Path,
          test=("nginx", "-t"), reload=("systemctl", "reload", "nginx"),
          run=subprocess.run, now: datetime | None = None) -> int:
    """Turn the stored policy into the nginx file. 0 when nginx runs the
    policy (changed or not), 1 when it was refused; the previous file is
    then back in place. The outcome goes to `status_path`."""
    now = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    record = {"at": now, "ok": False, "changed": False, "error": None,
              "blocked": [], "policy_updated_at": None, "conf_sha256": None}

    def done(code: int) -> int:
        _write(Path(status_path), json.dumps(record, indent=2) + "\n")
        return code

    try:
        policy = validate(_read_json(Path(policy_path)))
    except FileNotFoundError:
        policy = empty()
    except (Invalid, OSError) as why:
        record["error"] = f"policy not applied: {why}"[:300]
        return done(1)
    record["blocked"] = [c.name for c in blocked(policy)]
    record["policy_updated_at"] = policy.get("updated_at")
    text = nginx_conf(policy)
    record["conf_sha256"] = hashlib.sha256(text.encode()).hexdigest()
    conf = Path(conf_path)
    try:
        old = conf.read_text(encoding="utf-8")
    except FileNotFoundError:
        old = None
    if old == text:
        record["ok"] = True
        return done(0)
    prev = conf.with_name(conf.name + ".prev")
    if old is not None:
        _write(prev, old)
    _write(conf, text)
    tested = run(list(test), capture_output=True, text=True)
    if tested.returncode != 0:
        if old is None:
            conf.unlink()
        else:
            _write(conf, old)
        tail = (tested.stderr or tested.stdout or "").strip().splitlines()[-2:]
        record["error"] = ("nginx -t refused it; previous file kept: " + " / ".join(tail))[:300]
        return done(1)
    reloaded = run(list(reload), capture_output=True, text=True)
    if reloaded.returncode != 0:
        record["error"] = "nginx reload failed: " + (reloaded.stderr or "").strip()[:200]
        return done(1)
    record["ok"] = record["changed"] = True
    return done(0)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Apply Skald's AI crawler policy to nginx.")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("apply")
    a.add_argument("--policy", required=True)
    a.add_argument("--conf", required=True)
    a.add_argument("--status", required=True)
    sub.add_parser("show").add_argument("--policy", required=True)
    args = p.parse_args(argv)
    if args.cmd == "show":
        policy = load(Path(args.policy))
        sys.stdout.write(nginx_conf(policy) + "\n# robots.txt suggestion\n"
                         + robots_lines(policy))
        return 0
    return apply(Path(args.policy), Path(args.conf), Path(args.status))


if __name__ == "__main__":
    raise SystemExit(main())
