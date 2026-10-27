"""The adapter interface: what one tool (tool_<id>.py) gives the framework.

An adapter is a plain object, one per tool, `ADAPTER = Adapter(...)` or a subclass
with these parts (docs/TOOLS.md, "Adding a tool"):

  id, name        "ga4", "Google Analytics": the name every figure is labelled with
  key_words       what the key is, in plain words ("a Google service-account key file")
  permission      the permission the key needs, read-only first ("Viewer on the property")
  make_key        where a person makes one, in plain words (with the page's address)
  env_names       names an AI agent may find in the site's project (.env files): only
                  ever named, never printed (kit/agent/jobs/connect-tools.md)
  find_more       one more line for the agent's search (where else the key may be)
  send_steps(...) the agent's commands for this tool: the key from a file or the
                  project's .env straight into POST <code>/toolkey on stdin
  grant(who)      the one click left for the person (a robot given read access), or ""
  options         {name: Option}: what a connection needs beside the key (GA4's
                  property id); never secret, kept in conn.py's file
  key_most        the longest key it takes, in bytes
  check_key(text) -> {"who": ...}
                  reads a key, never echoes it; "who" is what may be shown again (a
                  service account's address, an account's name): BadKey in plain words
  fetch(key, options, now, opener, sleep) -> [Answer]
                  the tool's answers, each kept exactly as it came (store.py)
  figures(answer) -> [Figure]
                  what is shown, each figure read from one place in the answer
                  (`src`, a JSON pointer, RFC 6901); a figure the tool did not give
                  is value None with src None, never 0
  headline(figs) -> [Figure]
                  the few figures Overview's card shows on its one line
  suggest(found) -> dict
                  what Skald can tell from what it already read about the site (the
                  site check's `found`): e.g. a GA4 tag's G- id. Never fetches.
  notes           plain lines the tool's drawer shows under its state (where its
                  figures come from beside Skald's own, what its key can do)
  latest_only     True: only the newest answer of each report is kept (a tool
                  whose answer names people, or whose window moves every day)
  scrub(answer, policy) -> Answer
                  before an answer is stored: the names and emails in it removed
                  as the site's People settings say (policy: {"identity": bool,
                  "keep_days": int, "now": datetime}); the default keeps it whole
  more(ctx) -> {"lines": [...], "people": [...]}
                  admins' drawer only: lines worked out with Skald's own data (the
                  Calendly bookings the webhook also has) and the people the tool's
                  answer names, as far as the People settings keep them

The framework (sync.py) calls fetch, stores each Answer and its figures, and the
audit (recount.py) reads every figure again from the stored answer by `src`,
its name by `name_src` and its row by `dim_src`, by its own code.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# `tr -d` of the quotes and line ends around a .env value (the shell text, quoted).
STRIP = "\"\\\"'\\r\\n\""


class BadKey(ValueError):
    """A key that is not one this tool takes, in plain words (never the key)."""


class Unreachable(RuntimeError):
    """The tool did not answer. `code` is the HTTP status (0: no answer at all)."""

    def __init__(self, words: str, code: int = 0) -> None:
        super().__init__(words)
        self.code = code


@dataclass
class Option:
    """One setting a connection needs beside its key (never a secret)."""
    label: str
    pattern: str                         # the whole value must match
    words: str                           # what it is and where to find it
    required: bool = True
    example: str = ""
    env: tuple = ()                      # names an AI agent may find it under (.env)

    def clean(self, value) -> str:
        got = str(value if value is not None else "").strip()
        if not got:
            if self.required:
                raise ValueError(f"{self.label} is needed. {self.words}")
            return ""
        if len(got) > 200 or not re.fullmatch(self.pattern, got):
            raise ValueError(f"That is not a {self.label.lower()}. {self.words}")
        return got


@dataclass
class Answer:
    """One answer a tool gave, exactly as it came.

    report  which of the tool's questions ("totals", "landing", "sources")
    period  the window's key, e.g. "2026-09-29..2026-10-26" (one answer per tool,
            report and period is kept; a newer one replaces it)
    start, end  the window's first and last day as the tool counts them, or None
    request what was asked (never a key)
    body    the tool's JSON answer
    flags   what the tool said about its own answer (sampled, thresholded...)
    note    one plain line about the window ("the property's time zone, ...")
    """
    report: str
    period: str
    start: str | None
    end: str | None
    request: dict
    body: dict
    flags: dict = field(default_factory=dict)
    note: str = ""


@dataclass
class Figure:
    """One figure shown, and where in its answer it was read.

    name     the tool's own name for it ("sessions"), from the tool's answer
    value    the number, or None when the tool did not give it (never 0)
    dim      the row it belongs to ("/pricing", "google / organic"), or None for a total
    src      JSON pointer to the value in the answer body, or None (value None)
    name_src JSON pointer to where the answer names it, or None
    dim_src  JSON pointer to the row's name, or None
    label    the figure in plain words ("Sessions")
    rank     the row's place in the tool's own order (0 first), None for a total
    """
    name: str
    value: float | int | None
    label: str = ""
    dim: str | None = None
    src: str | None = None
    name_src: str | None = None
    dim_src: str | None = None
    rank: int | None = None


class Adapter:
    """The defaults every tool shares; a tool overrides what it needs."""
    id = ""
    name = ""
    key_words = "an API key"
    permission = "read-only access"
    make_key = ""
    env_names: tuple = ()
    options: dict = {}
    key_most = 8192
    find_more = ""
    # A tool may answer without a key of its own (GA4 may use the Search Console key).
    shares_key: str | None = None
    notes: tuple = ()
    latest_only = False

    def grant(self, who: str | None) -> str:
        return ""

    def send_steps(self, curl: str, url: str, site: str, env_dir: str, robot=None) -> str:
        """The agent's command for a token kept in the project's .env: read straight
        from the file into curl's stdin, never shown."""
        var = self.env_names[0] if self.env_names else "<NAME>"
        return (f"With the user's yes, in the project folder (put the variable's real name in "
                f"place of `{var}` when it is another; fill in the options):\n\n"
                f"    grep -h '^{var}=' .env* 2>/dev/null | head -1 | cut -d= -f2- | "
                f"tr -d {STRIP} | {curl} '{url}'\n\n"
                f"Without it in a file, ask the user to make one ({self.make_key}) and to put "
                f"it in `{env_dir}/{site}.{self.id}.key` (0600) themselves; then send that "
                f"file with `< {env_dir}/{site}.{self.id}.key` and remove it.")

    def check_key(self, text: str) -> dict:
        raise NotImplementedError

    def fetch(self, key: str, options: dict, now, opener=None, sleep=None) -> list[Answer]:
        raise NotImplementedError

    def figures(self, answer: Answer) -> list[Figure]:
        raise NotImplementedError

    def headline(self, figures: list[Figure]) -> list[Figure]:
        return [f for f in figures if f.dim is None][:3]

    def suggest(self, found: dict | None) -> dict:
        return {}

    def scrub(self, answer: Answer, policy: dict) -> Answer:
        return answer

    def more(self, ctx: dict) -> dict:
        """ctx: {"config", "folder", "site", "answers": [{report, body, ...}]}."""
        return {}

    def clean_options(self, given: dict | None, keep: dict | None = None) -> dict:
        """The options, each checked; a value not given keeps `keep`'s."""
        given, keep = dict(given or {}), dict(keep or {})
        out = {}
        for name, option in self.options.items():
            value = given.get(name, keep.get(name))
            got = option.clean(value)
            if got:
                out[name] = got
        # "key": a tool that may answer with another connection's key (keys.SHARED).
        if self.shares_key and given.get("key", keep.get("key")) == self.shares_key:
            out["key"] = self.shares_key
        return out


def pointer(*parts) -> str:
    """A JSON pointer (RFC 6901) from its parts: pointer("rows", 0, "value")."""
    return "".join("/" + str(p).replace("~", "~0").replace("/", "~1") for p in parts)


def when(text):
    """A tool's time (ISO 8601, "Z", or Resend's "2026-10-06 23:47:56.678+00") as an
    aware UTC datetime, or None."""
    from datetime import datetime, timezone
    raw = str(text or "").strip().replace("Z", "+00:00").replace(" ", "T", 1)
    if raw.endswith(("+00", "-00")) or (len(raw) > 3 and raw[-3] in "+-" and raw[-2:].isdigit()):
        raw += ":00"
    try:
        got = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return (got if got.tzinfo else got.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)


def kept_person(at, policy: dict) -> bool:
    """Whether a name or an email seen at `at` may be kept: the site keeps names
    and emails (conversions.identity: full) and `at` is within its People days
    (privacy.keep_days). An unknown time keeps nothing."""
    from datetime import datetime, timedelta, timezone
    seen = when(at)
    if not (policy or {}).get("identity") or seen is None:
        return False
    now = policy.get("now") or datetime.now(timezone.utc)
    return now - seen <= timedelta(days=int(policy.get("keep_days") or 0))


def plain_key_words(text: str, most: int) -> str:
    """A pasted key as one line of text, or BadKey (never echoing it)."""
    if isinstance(text, bytes):
        text = text.decode("utf-8", "replace")
    got = str(text or "").strip()
    if not got:
        raise BadKey("The key is empty.")
    if len(got) > most:
        raise BadKey("That is too long to be this tool's key.")
    return got
