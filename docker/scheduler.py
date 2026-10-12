#!/usr/bin/env python3
"""The container's clock: cron's three lines (DEPLOY.md section 5), no cron daemon.

    live        every SKALD_LIVE_MINUTES minutes (2), and once at start
    run-daily   at SKALD_DAILY_AT (07:15) in the site's time zone; on failure,
                one `notify-failure` mail (at most one per 12 hours)
    backup      at SKALD_BACKUP_AT (03:30) in the same zone; on failure, the same
    rotate      at 00:05: the in-image nginx's beacon log, Debian style
                (.1, then .2.gz ... .14.gz), then nginx reopens it

Like cron with `flock -n`: a job still running when it is next due is not
started twice; a time missed while the container was down is not caught up.
Each job's output goes to /var/log/skald/<job>.log; one line per run
goes to the container's log. Standard library only.
"""
from __future__ import annotations

import argparse
import gzip
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

APP = Path(os.environ.get("SKALD_APP", "/opt/skald"))
LOGS = Path(os.environ.get("SKALD_JOB_LOGS", "/var/log/skald"))
BEAT = Path("/tmp/skald-scheduler.beat")
NGINX_PID = Path("/tmp/skald-nginx/nginx.pid")
BEACON_LOG = Path("/var/log/nginx/skald-beacon.log")
LOG_CAP = 5 * 1024 * 1024
UTC = timezone.utc


# ------------------------------------------------------------ the timing

def parse_hhmm(text: str) -> tuple[int, int]:
    m = re.fullmatch(r"\s*([01]?\d|2[0-3]):([0-5]\d)\s*", text or "")
    if not m:
        raise ValueError(f"{text!r} is not a time of day (HH:MM, 24-hour)")
    return int(m.group(1)), int(m.group(2))


def next_daily(after: datetime, hhmm: str, tz: str) -> datetime:
    """The first HH:MM in `tz` strictly after `after` (an aware time), in UTC.

    A day the clocks change keeps working: a time that does not exist that
    day (02:30 when the clocks go forward) runs at the same moment cron's
    zone arithmetic gives, an hour on; a time that happens twice runs once.
    """
    h, m = parse_hhmm(hhmm)
    zone = ZoneInfo(tz)
    local = after.astimezone(zone)
    for add in range(0, 3):
        day = local.date() + timedelta(days=add)
        at = datetime(day.year, day.month, day.day, h, m, tzinfo=zone).astimezone(UTC)
        if at > after:
            return at
    raise AssertionError("unreachable")


def next_every(after: datetime, minutes: int) -> datetime:
    """The next multiple of `minutes` since the epoch strictly after `after`,
    as cron's */N does within an hour (N divides 60: 2, 5, 10...)."""
    if minutes < 1:
        raise ValueError("minutes must be at least 1")
    step = minutes * 60
    t = int(after.timestamp()) // step * step + step
    return datetime.fromtimestamp(t, UTC)


# -------------------------------------------------------------- rotation

def rotate(path: Path, keep: int = 14) -> bool:
    """logrotate's daily/rotate N/delaycompress: <log>.1 plain, older gzipped.
    False when there is nothing to rotate (no file, or an empty one)."""
    if not path.exists() or path.stat().st_size == 0:
        return False
    oldest = path.with_name(f"{path.name}.{keep}.gz")
    if oldest.exists():
        oldest.unlink()
    for n in range(keep - 1, 1, -1):
        src = path.with_name(f"{path.name}.{n}.gz")
        if src.exists():
            os.replace(src, path.with_name(f"{path.name}.{n + 1}.gz"))
    one = path.with_name(f"{path.name}.1")
    if one.exists():
        with open(one, "rb") as f, gzip.open(path.with_name(f"{path.name}.2.gz"), "wb") as g:
            shutil.copyfileobj(f, g)
        one.unlink()
    os.replace(path, one)
    return True


def reopen_nginx() -> None:
    try:
        os.kill(int(NGINX_PID.read_text().strip()), signal.SIGUSR1)
    except (OSError, ValueError):
        pass


def rotate_job() -> int:
    if rotate(BEACON_LOG):
        reopen_nginx()
    return 0


# ------------------------------------------------------------------ jobs

class Job:
    def __init__(self, name: str, args: list[str] | None, due, notify: bool = False, fn=None):
        self.name, self.args, self.due_after, self.notify, self.fn = name, args, due, notify, fn
        self.proc: subprocess.Popen | None = None
        self.out = None
        self.started = 0.0
        self.next: datetime | None = None


class Scheduler:
    def __init__(self, config: str, tz: str, live_minutes: int, daily_at: str, backup_at: str):
        self.config = config
        ti = [sys.executable, str(APP / "bin/skald"), "--config", config]
        self.ti = ti
        self.jobs = []
        if live_minutes > 0:
            self.jobs.append(Job("live", ti + ["live"], lambda t: next_every(t, live_minutes)))
        self.jobs.append(Job("run-daily", ti + ["run-daily"],
                             lambda t: next_daily(t, daily_at, tz), notify=True))
        self.jobs.append(Job("backup", ti + ["backup"],
                             lambda t: next_daily(t, backup_at, tz), notify=True))
        self.jobs.append(Job("rotate", None, lambda t: next_daily(t, "00:05", tz), fn=rotate_job))
        self.stopping = False

    def log_path(self, job: Job) -> Path:
        return LOGS / f"{'run' if job.name == 'run-daily' else job.name}.log"

    def start(self, job: Job) -> None:
        if job.fn is not None:
            try:
                job.fn()
            except Exception as why:          # noqa: BLE001 - never stops the clock
                say(f"{job.name}: {type(why).__name__}: {why}")
            return
        path = self.log_path(job)
        try:
            if path.exists() and path.stat().st_size > LOG_CAP:
                os.replace(path, path.with_name(path.name + ".1"))
            job.out = open(path, "a")
            job.out.write(f"---- {datetime.now(UTC):%Y-%m-%dT%H:%M:%SZ} {job.name}\n")
            job.out.flush()
        except OSError:
            job.out = subprocess.DEVNULL
        job.proc = subprocess.Popen(job.args, cwd=str(APP), stdout=job.out,
                                    stderr=subprocess.STDOUT)
        job.started = time.monotonic()

    def finish(self, job: Job, code: int) -> None:
        took = time.monotonic() - job.started
        if job.out not in (None, subprocess.DEVNULL):
            job.out.close()
        job.proc, job.out = None, None
        if job.name == "live" and code in (0, 1):
            # 1 is "today does not reconcile": the panel says withheld. Quiet.
            if code == 1:
                say(f"live: withheld (exit 1, {took:.0f} s)")
            return
        say(f"{job.name}: exit {code} after {took:.0f} s")
        if code != 0 and job.notify:
            got = subprocess.run(self.ti + ["notify-failure", "--job", job.name, "--exit", str(code),
                                            "--log", str(self.log_path(job))],
                                 cwd=str(APP), capture_output=True, text=True, timeout=120)
            say(f"{job.name}: failure mail: {(got.stdout or got.stderr).strip()[:200] or got.returncode}")

    def tick(self, now: datetime) -> None:
        for job in self.jobs:
            if job.proc is not None:
                code = job.proc.poll()
                if code is not None:
                    self.finish(job, code)
            if job.next is None:
                job.next = job.due_after(now)
            if now >= job.next:
                job.next = job.due_after(now)
                if job.proc is None:
                    self.start(job)
                else:
                    say(f"{job.name}: still running; this turn is skipped")
        try:
            BEAT.touch()
        except OSError:
            pass

    def run(self) -> int:
        signal.signal(signal.SIGTERM, lambda *_: setattr(self, "stopping", True))
        signal.signal(signal.SIGINT, lambda *_: setattr(self, "stopping", True))
        LOGS.mkdir(parents=True, exist_ok=True)
        now = datetime.now(UTC)
        for job in self.jobs:
            job.next = job.due_after(now)
        live = [j for j in self.jobs if j.name == "live"]
        if live:
            self.start(live[0])               # the dashboard exists from the first minute
        for job in self.jobs:
            say(f"{job.name}: next {job.next:%Y-%m-%d %H:%M} UTC")
        while not self.stopping:
            self.tick(datetime.now(UTC))
            time.sleep(5)
        end = time.monotonic() + 45
        for job in self.jobs:
            while job.proc is not None and job.proc.poll() is None and time.monotonic() < end:
                time.sleep(0.5)
            if job.proc is not None and job.proc.poll() is None:
                job.proc.terminate()
        return 0


def say(msg: str) -> None:
    print(f"scheduler: {msg}", flush=True)


def site_timezone(config: str) -> str:
    sys.path.insert(0, str(APP))
    from skald.config import load_config, setting
    return str(setting(load_config(Path(config)), "report", "timezone", "UTC"))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--config", required=True)
    p.add_argument("--tz", help="the zone the daily times are in (default report.timezone)")
    a = p.parse_args(argv)
    tz = a.tz or os.environ.get("SKALD_SCHEDULE_TZ") or site_timezone(a.config)
    ZoneInfo(tz)                              # an unknown zone fails here, loudly
    daily = os.environ.get("SKALD_DAILY_AT") or "07:15"
    backup = os.environ.get("SKALD_BACKUP_AT") or "03:30"
    parse_hhmm(daily), parse_hhmm(backup)
    minutes = int(os.environ.get("SKALD_LIVE_MINUTES") or 2)
    say(f"times in {tz}: run-daily {daily}, backup {backup}, live every {minutes} min")
    return Scheduler(a.config, tz, minutes, daily, backup).run()


if __name__ == "__main__":
    raise SystemExit(main())
