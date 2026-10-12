"""Shared fixtures for the system tests. Not a test module itself.

Addresses are RFC 5737 documentation ranges and the host is example.com;
logs are written per test into a temporary directory, dated for the day
under test.
"""
from __future__ import annotations

import gzip
import io
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald import Classifier, read, summarise  # noqa: E402
from skald import cli  # noqa: E402


ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
UTC = timezone.utc
NY = ZoneInfo("America/New_York")

CHROME = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")
GPTBOT = "Mozilla/5.0 (compatible; GPTBot/1.2; +https://openai.com/gptbot)"
ASKED = ("Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; "
         "ChatGPT-User/1.0; +https://openai.com/bot")
GOOGLEBOT = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"


def line(when: datetime, address: str = "203.0.113.10", path: str = "/",
         agent: str = CHROME, referrer: str = "-", status: int = 200,
         host: str = "example.com", country: str = "US") -> str:
    """One nginx_extended line."""
    return (f'{when.isoformat()} {address} {host} "GET {path} HTTP/2.0" '
            f'{status} 512 "{referrer}" "{agent}" 0.004 cc={country} '
            f'ray=0000000000000000-LHR\n')


def day_lines(day: date, people: int, tz=UTC) -> list[str]:
    """A day with `people` readers (one cited), and one of each other group.

    Exactly: people hits = people, visits = people, views = people, one
    citation; GPTBot 1 (training), ChatGPT-User 1 (asked), Googlebot 1,
    one scanner probe, one api.example.com request excluded.
    """
    noon = datetime(day.year, day.month, day.day, 12, tzinfo=tz)
    out = []
    for i in range(people):
        ref = "https://chatgpt.com/" if i == 0 else "-"
        out.append(line(noon + timedelta(minutes=i), f"203.0.113.{10 + i}",
                        "/guides/alpha" if i % 2 else "/", referrer=ref,
                        country="GB" if i % 2 else "US"))
    out.append(line(noon + timedelta(hours=1), "198.51.100.40", "/guides/alpha", GPTBOT))
    out.append(line(noon + timedelta(hours=1, minutes=1), "198.51.100.41", "/guides/beta", ASKED))
    out.append(line(noon + timedelta(hours=1, minutes=2), "198.51.100.42", "/", GOOGLEBOT))
    out.append(line(noon + timedelta(hours=1, minutes=3), "198.51.100.52", "/.env",
                    "curl/8.7.1", status=404))
    out.append(line(noon + timedelta(hours=1, minutes=4), "198.51.100.54", "/v1/x",
                    CHROME, host="api.example.com"))
    return out


def totals_for(lines: list[str]):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "access.log"
        path.write_text("".join(lines))
        return summarise(read([path]), Classifier(["MyCompanyCrawler"]), 30,
                         top=50, hosts=["example.com"])


def config_text(tmp: Path, *, tz: str = "UTC", mail: bool = True,
                url: str = "https://stats.example.com/example.com/",
                views: list[str] = (), coverage_gap: int = 1440) -> str:
    text = (
        # The fixtures' readers fetch pages only, written before visitors had
        # to render them (rendering.py); test_rendering.py turns it on.
        "site:\n  name: example.com\n  hosts: [example.com]\n  require_rendering: false\n"
        f"logs:\n  dir: {tmp / 'logs'}\n  base: access.log\n  days: 2\n"
        "  format: auto\n"
        "ours:\n  user_agents: [MyCompanyCrawler]\n"
        f"report:\n  session_gap_minutes: 30\n  timezone: {tz}\n"
        # Test logs are sparse - a few lines at noon - so a day here tolerates
        # any hole; the partial-day tests set the real default, 60.
        f"  coverage_gap_minutes: {coverage_gap}\n"
        "history:\n  db: history.sqlite\n"
        # app: false: these tests read the plain page; test_webapp switches the app on.
        f"dashboard:\n  out: www\n  url: {url}\n  app: false\n"
    )
    if views:
        text += "  views:\n" + "".join(f"    - {v}\n" for v in views)
    if mail:
        text += ("mail:\n  host: smtp.example.com\n  port: 587\n"
                 "  from: traffic@example.com\n  to:\n    - owner@example.com\n"
                 "    - second@example.com\n  user_env: TI_TEST_SMTP_USER\n"
                 "  password_env: TI_TEST_SMTP_PASSWORD\n"
                 '  subject_prefix: "[traffic]"\n')
    return text


class Sandbox:
    """A temp directory with a config, a log directory and a history file."""

    def __init__(self, **config) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "logs").mkdir()
        self.config = self.root / "config.yml"
        self.config.write_text(config_text(self.root, **config))

    def close(self) -> None:
        self._tmp.cleanup()

    @property
    def db(self) -> Path:
        return self.root / "history.sqlite"

    def log(self, lines: list[str], name: str = "access.log") -> Path:
        path = self.root / "logs" / name
        if name.endswith(".gz"):
            with gzip.open(path, "wt") as handle:
                handle.write("".join(lines))
        else:
            path.write_text("".join(lines))
        return path

    def run(self, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(["--config", str(self.config), *argv])
        return code, out.getvalue(), err.getvalue()


SECRETS = {"TI_TEST_SMTP_USER": "relay-user", "TI_TEST_SMTP_PASSWORD": "relay-pass"}


