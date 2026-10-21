#!/usr/bin/env python3
"""skald-ship: send a web server's access log to a Skald install.

One file, Python 3.9+ standard library only. It tails one access log, follows
its rotation, and posts the new lines in gzip batches to the install's
ingest address with a token that may only add lines to one site:

    skald-ship --url https://stats.example.com/traffic-ingest/www.example.com \\
               --token-file /etc/skald-ship/token \\
               --log /var/log/nginx/access.log \\
               [--state /var/lib/skald-ship/state.json] \\
               [--batch-lines 2000] [--interval 10] [--from-end] [--once]

What it does:

  * Reads whole lines only. A last line still being written waits for its
    end. A line longer than 64 KiB is cut to 64 KiB (counted as "cut").
  * Sends at most --batch-lines lines (and at most 4 MiB) a batch, gzip'd,
    as soon as lines are there, and then at most every --interval seconds
    unless a batch is full. It looks at the file about once a second.
  * Every batch is numbered: X-Skald-Batch: <shipper id>:<seq>. The shipper
    id is random, made on the first run and kept in the state file. A batch
    whose answer was lost is sent again with the same number and the same
    lines; the server keeps it once.
  * The state file (offset, inode, last batch number) is written only after
    the server answered 2xx, atomically (temp file, fsync, rename). A lost
    state file starts again from the beginning of the current file, with a
    new shipper id.
  * The first run, with no state, starts at the beginning of the current
    file. --from-end starts at its end instead.
  * Rotation: when the log's path names a new file (logrotate's rename), the
    old file is read to its end first, a final unfinished line included,
    then the new one from its start. If the shipper was stopped across a
    rotation, it finds the old file again as <log>.1 by its inode and reads
    it from where it stopped. If that file is already compressed or gone,
    it says so on stderr and starts the new file from its start.
    Truncation in place (copytruncate) starts again at offset 0.
  * Failures: never drops a line. 413 (too large) splits the batch in two.
    429, 503 and 507 (the server short of disk) wait for Retry-After (at most
    600 s). Anything else - no network, 5xx, 401, 403, 404 - waits with exponential backoff and
    full jitter (1 s doubling up to 300 s) and tries again, for ever. Each
    failure is one line on stderr, with the server's reason, never the token.
  * --once gives up instead: after ONCE_TRIES failed tries of one batch, or
    when the next wait would pass ONCE_SECONDS in all (a 507's Retry-After of
    600 gives up at once). The state is kept, so no line is lost: the batch
    is sent again at the next run. It exits 1 with one plain line on stderr.
  * Lines the server could not read in the site's log format are counted by
    the server and reported here ("2 rejected"); the server does not keep them.
  * SIGTERM / SIGINT: stops reading, gives the batch in flight one last try,
    keeps only what the server acknowledged, exits 0.

The URL must be https://. Plain http:// is accepted only for 127.0.0.1,
::1 and localhost (tests, or a tunnel on the same machine).

Install (Ubuntu/Debian):

    sudo install -m 0755 skald-ship.py /usr/local/bin/skald-ship
    sudo useradd --system --no-create-home --shell /usr/sbin/nologin \\
         --groups adm skald-ship
    sudo install -d -m 0750 -o root -g skald-ship /etc/skald-ship
    sudo sh -c 'umask 027; cat > /etc/skald-ship/token'   # paste, Ctrl-D
    sudo chgrp skald-ship /etc/skald-ship/token

/etc/systemd/system/skald-ship.service:

    [Unit]
    Description=Ship the access log to Skald
    After=network-online.target
    Wants=network-online.target

    [Service]
    # The user's own group reads the token; its membership of adm (useradd
    # --groups adm) reads /var/log/nginx. No Group= line: that would drop it.
    User=skald-ship
    ExecStart=/usr/local/bin/skald-ship \\
        --url https://stats.example.com/traffic-ingest/www.example.com \\
        --token-file /etc/skald-ship/token \\
        --log /var/log/nginx/access.log \\
        --state /var/lib/skald-ship/state.json
    Restart=always
    RestartSec=5
    StateDirectory=skald-ship
    StateDirectoryMode=0700
    NoNewPrivileges=true
    ProtectSystem=strict
    ProtectHome=true
    PrivateTmp=true
    PrivateDevices=true
    ReadOnlyPaths=/var/log /etc/skald-ship
    CapabilityBoundingSet=
    RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
    SystemCallFilter=@system-service

    [Install]
    WantedBy=multi-user.target

    sudo systemctl daemon-reload && sudo systemctl enable --now skald-ship
    journalctl -u skald-ship -f
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import random
import secrets
import signal
import sys
import time
import urllib.error
import urllib.request
from http.client import HTTPException
from urllib.parse import urlsplit

VERSION = "1"
MAX_LINE = 64 * 1024              # a longer line is cut to this
MAX_BATCH = 4 * 1024 * 1024       # bytes before gzip; the server takes 5 MiB
BACKOFF_BASE = 1.0
BACKOFF_CAP = 300.0
RETRY_AFTER_CAP = 600
POLL = 1.0                        # seconds between looks at the file
TIMEOUT = 60                      # one request
LAST_TRY_TIMEOUT = 5              # the last try after SIGTERM
ONCE_TRIES = 5                    # --once: failed tries of one batch before giving up
ONCE_SECONDS = 60                 # --once: the most time spent retrying one batch
LOOPBACK = ("127.0.0.1", "::1", "localhost")


def url_problem(url: str) -> str | None:
    """None when the URL may be used, else why not."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return "not a URL"
    if parts.scheme == "https" and parts.hostname:
        return None
    if parts.scheme == "http" and parts.hostname in LOOPBACK:
        return None
    if parts.scheme == "http":
        return "use https:// (plain http only for 127.0.0.1 or localhost)"
    return "the URL must start with https://"


def read_token(path: str, err=None) -> str:
    """The token in `path`, stripped. Warns (never echoing it) when the file
    can be read by everyone or written by anyone but its owner. 640 is fine:
    the shipper often reads it through its group (the Docker kit: root:adm)."""
    err = err or sys.stderr
    mode = os.stat(path).st_mode
    if mode & 0o027:
        print(f"skald-ship: warning: {path} is open to others (mode "
              f"{mode & 0o777:o}); chmod 600 or 640 it", file=err, flush=True)
    with open(path, encoding="utf-8") as f:
        token = f.read().strip()
    if not token or any(c.isspace() for c in token):
        raise SystemExit(f"skald-ship: {path} does not hold one token")
    return token


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect is a failure: it would drop the body (and could carry the
    token elsewhere)."""

    def redirect_request(self, *args, **kwargs):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def http_post(url: str, data: bytes, headers: dict, timeout: float):
    """(status, body bytes, headers) of one POST; status 0 and the reason as
    the body when the network failed."""
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with _OPENER.open(req, timeout=timeout) as got:
            return got.status, got.read(65536), dict(got.headers)
    except urllib.error.HTTPError as got:
        try:
            body = got.read(65536)
        except (OSError, HTTPException):
            body = b""
        return got.code, body, dict(got.headers or {})
    except (urllib.error.URLError, OSError, HTTPException, ValueError) as why:
        reason = getattr(why, "reason", why)
        return 0, f"network error ({type(reason).__name__})".encode(), {}


class Line:
    __slots__ = ("data", "end")

    def __init__(self, data: bytes, end: tuple):
        self.data, self.end = data, end      # end: (dev, ino, offset after the line)


class Shipper:
    def __init__(self, url, token, log, state, batch_lines=2000, interval=10,
                 from_end=False, sleep=None, clock=None, post=None, err=None, rnd=None,
                 patience=None):
        self.url, self.token, self.path, self.state_path = url, token, str(log), str(state)
        self.batch_lines = max(1, int(batch_lines))
        self.interval = max(0.0, float(interval))
        self.from_end = from_end
        self.sleep = sleep or self._sleep
        self.clock = clock or time.monotonic
        self.post = post or http_post
        self.err = err or sys.stderr
        self.random = rnd or random.Random()
        # (failed tries, seconds) before one batch is given up for now; None:
        # for ever, the service's way. run(once=True) sets the --once limits.
        self.patience = patience
        self.stopping = False
        self.started = False
        self.pending: list[Line] = []
        self.counts = dict(read=0, sent=0, accepted=0, rejected=0, cut=0, duplicate=0)
        self.last_send = None
        self.f = None
        self.cur = None                 # (dev, ino) of the open file
        self.pos = 0
        self.rotation_seen = False
        self.empty_poll = False
        self.shipper = None
        self.seq = 0
        self.acked = None               # (dev, ino, offset) the server has
        self.inflight = None

    # ---------------------------------------------------------------- output

    def say(self, words: str) -> None:
        if self.token:
            words = words.replace(self.token, "[token]")
        print(f"skald-ship: {words}", file=self.err, flush=True)

    def on_signal(self, signum, frame) -> None:
        if not self.stopping:
            self.say("stopping: one last try for the batch in flight, then exit")
        self.stopping = True

    def _sleep(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while not self.stopping:
            left = end - time.monotonic()
            if left <= 0:
                return
            time.sleep(min(0.2, left))

    # ----------------------------------------------------------------- state

    def load(self) -> dict | None:
        try:
            with open(self.state_path, encoding="utf-8") as f:
                got = json.load(f)
        except FileNotFoundError:
            return None
        except (OSError, ValueError) as why:
            self.say(f"state file {self.state_path} unreadable ({type(why).__name__}); "
                     "starting afresh")
            return None
        return got if isinstance(got, dict) else None

    def save(self) -> None:
        dev, ino, offset = self.acked or (None, None, None)
        body = {"version": 1, "shipper": self.shipper, "seq": self.seq, "dev": dev,
                "ino": ino, "offset": offset, "log": self.path, "inflight": self.inflight}
        folder = os.path.dirname(os.path.abspath(self.state_path))
        os.makedirs(folder, exist_ok=True)
        tmp = os.path.join(folder, f".{os.path.basename(self.state_path)}.{os.getpid()}.tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(body, f)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.state_path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        try:
            dfd = os.open(folder, os.O_RDONLY)
            try:
                os.fsync(dfd)
            finally:
                os.close(dfd)
        except OSError:
            pass

    # ----------------------------------------------------------------- files

    @staticmethod
    def _id(path: str):
        try:
            st = os.stat(path)
        except OSError:
            return None
        return (st.st_dev, st.st_ino), st.st_size

    def _open(self, path: str, offset: int) -> bool:
        try:
            f = open(path, "rb")
        except OSError:
            return False
        st = os.fstat(f.fileno())
        if self.f is not None:
            self.f.close()
        self.f, self.cur = f, (st.st_dev, st.st_ino)
        self.pos = st.st_size if offset == "end" else int(offset)
        return True

    def start(self) -> None:
        if self.started:
            return
        self.started = True
        state = self.load() or {}
        self.shipper = state.get("shipper") or secrets.token_hex(8)
        self.seq = int(state.get("seq") or 0)
        self.inflight = state.get("inflight") or None
        if state.get("ino") is not None:
            self.acked = (state["dev"], state["ino"], int(state["offset"] or 0))
        if self.acked is None:
            if not self._open(self.path, "end" if self.from_end else 0):
                self.say(f"waiting for {self.path} to exist")
            return
        dev, ino, offset = self.acked
        here = self._id(self.path)
        if here is not None and here[0] == (dev, ino):
            if here[1] < offset:
                self.say(f"{self.path} was truncated while stopped; reading it from the start")
                offset = 0
            self._open(self.path, offset)
            return
        older = self._id(self.path + ".1")
        if older is not None and older[0] == (dev, ino):
            self.say(f"the log rotated while stopped; reading {self.path}.1 from where it "
                     "stopped first")
            self._open(self.path + ".1", min(offset, older[1]))
            return
        self.say(f"could not resume: the file it was reading is not {self.path}.1 any more "
                 "(compressed or removed); lines written to it after the last batch are "
                 "not sent. Starting the new file from its start")
        if not self._open(self.path, 0):
            self.say(f"waiting for {self.path} to exist")

    def poll(self, want: int) -> bool:
        """Read up to `want` more lines into `pending`. True when anything
        happened (lines read, a rotation noticed or followed)."""
        if self.f is None:
            if not self._open(self.path, 0):
                return False
        try:
            size = os.fstat(self.f.fileno()).st_size
        except OSError:
            size = self.pos
        if size < self.pos:
            self.say(f"{self.path} was truncated; reading it again from the start")
            self.pos = 0
        self.f.seek(self.pos)
        got = 0
        nbytes = sum(len(x.data) for x in self.pending)
        while got < want and nbytes < MAX_BATCH:
            start = self.pos
            raw = self.f.readline(MAX_LINE)
            if not raw:
                break
            if raw.endswith(b"\n"):
                self.pos += len(raw)
            elif len(raw) == MAX_LINE:          # a long line: skip to its end
                rest = 0
                done = False
                while True:
                    chunk = self.f.readline(1 << 20)
                    if not chunk:
                        break
                    rest += len(chunk)
                    if chunk.endswith(b"\n"):
                        done = True
                        break
                if not done:
                    self.f.seek(start)
                    break
                raw = raw + b"\n"
                self.pos += MAX_LINE + rest
                self.counts["cut"] += 1
                self.say(f"cut a line of {MAX_LINE + rest} bytes to {MAX_LINE}")
            else:                                # unfinished: wait for its end
                self.f.seek(start)
                break
            self.pending.append(Line(raw, (*self.cur, self.pos)))
            self.counts["read"] += 1
            nbytes += len(raw)
            got += 1
        if got:
            self.rotation_seen = False
            self.empty_poll = False
            return True
        self.empty_poll = True
        here = self._id(self.path)
        if here is None or here[0] == self.cur:
            self.rotation_seen = False
            return False
        if not self.rotation_seen:          # read the old file once more first
            self.rotation_seen = True
            return True
        tail = self.f.read()
        if tail:
            data = tail[:MAX_LINE]
            if len(tail) > MAX_LINE:
                self.counts["cut"] += 1
            self.pos += len(tail)
            self.pending.append(Line(data.rstrip(b"\n") + b"\n", (*self.cur, self.pos)))
            self.counts["read"] += 1
        self.rotation_seen = False
        if self._open(self.path, 0):
            self.say("rotated: reading the new file")
        return True

    # -------------------------------------------------------------- sending

    def backoff(self, attempt: int) -> float:
        ceiling = min(BACKOFF_CAP, BACKOFF_BASE * 2 ** min(attempt, 30))
        return self.random.uniform(0, ceiling)

    def _take(self, force: bool):
        """(lines, seq) of the next batch, None to wait for more lines."""
        if self.inflight:
            k = int(self.inflight.get("lines") or 0)
            end = tuple(self.inflight.get("end") or ())
            if k and len(self.pending) >= k and tuple(self.pending[k - 1].end) == end:
                return self.pending[:k], int(self.inflight["seq"])
            if len(self.pending) < k and not self.empty_poll:
                return None
            self.say(f"could not rebuild batch {self.inflight.get('seq')} exactly; its lines "
                     "go in the next batch (the server may hold some of them twice)")
            self.seq = max(self.seq, int(self.inflight.get("seq") or 0))
            self.inflight = None
        out, nbytes = [], 0
        for item in self.pending[:self.batch_lines]:
            if out and nbytes + len(item.data) > MAX_BATCH:
                break
            out.append(item)
            nbytes += len(item.data)
        return out, self.seq + 1

    def send_next(self, force: bool = False) -> str:
        """Send one batch from the front of `pending`: "sent", "stopped" or
        "wait" (more lines are needed to rebuild a batch)."""
        got = self._take(force)
        if got is None:
            return "wait"
        lines, seq = got
        chunks = [lines]
        while chunks:
            chunk = chunks[0]
            done = self._send(chunk, seq)
            if done == "split":
                half = len(chunk) // 2
                chunks[0:1] = [chunk[:half], chunk[half:]]
                continue
            if done in ("stopped", "gave up"):
                return done
            chunks.pop(0)
            del self.pending[:len(chunk)]
            seq = self.seq + 1
        return "sent"

    def _send(self, chunk: list, seq: int) -> str:
        self.inflight = {"seq": seq, "lines": len(chunk), "end": list(chunk[-1].end)}
        self.save()
        body = gzip.compress(b"".join(x.data for x in chunk), mtime=0)
        headers = {"Authorization": f"Bearer {self.token}",
                   "Content-Type": "text/plain; charset=utf-8", "Content-Encoding": "gzip",
                   "X-Skald-Batch": f"{self.shipper}:{seq}", "X-Skald-Lines": str(len(chunk)),
                   "User-Agent": f"skald-ship/{VERSION}"}
        attempt, first, waited = 0, self.clock(), 0.0
        while True:
            last = self.stopping
            status, raw, got_headers = self.post(self.url, body, headers,
                                                 LAST_TRY_TIMEOUT if last else TIMEOUT)
            self.last_send = self.clock()
            answer = {}
            if status:
                try:
                    answer = json.loads(raw.decode("utf-8", "replace") or "{}")
                except ValueError:
                    answer = {}
                if not isinstance(answer, dict):
                    answer = {}
            if 200 <= status < 300:
                self._acked(chunk, seq, answer)
                return "sent"
            if status == 413 and len(chunk) > 1:
                self.say(f"batch {seq} too large ({len(chunk)} lines); splitting it")
                return "split"
            why = (f"HTTP {status}" + (f" {str(answer.get('error'))[:200]}"
                                       if answer.get("error") else "")) if status \
                else raw.decode("utf-8", "replace")[:200]
            if last:
                self.say(f"batch {seq} not sent ({why}); stopping with it unsent, it is "
                         "sent again at the next start")
                return "stopped"
            wait = None
            if status in (429, 503, 507):
                wait = _retry_after(got_headers)
            if wait is None:
                wait = self.backoff(attempt)
            attempt += 1
            if self.patience is not None:
                tries, seconds = self.patience
                spent = max(self.clock() - first, waited)       # a test's sleep takes none
                if attempt >= tries or spent + wait > seconds:
                    self.say(f"giving up for now after {attempt} "
                             f"tr{'y' if attempt == 1 else 'ies'} ({why}). Nothing is lost: "
                             "the lines are sent again at the next run")
                    return "gave up"
            self.say(f"retry in {wait:.0f} s: {why}")
            self.sleep(wait)
            waited += wait

    def _acked(self, chunk: list, seq: int, answer: dict) -> None:
        self.seq = seq
        self.acked = tuple(chunk[-1].end)
        self.inflight = None
        self.save()
        n = len(chunk)
        self.counts["sent"] += n
        if answer.get("duplicate"):
            self.counts["duplicate"] += n
            self.say(f"batch {seq} was already received ({n} lines); moving on")
            return
        accepted = _int(answer.get("accepted"), n)
        rejected = _int(answer.get("rejected"), 0)
        self.counts["accepted"] += accepted
        self.counts["rejected"] += rejected
        self.say(f"sent batch {seq}: {n} lines, {accepted} accepted, {rejected} rejected")

    # ----------------------------------------------------------------- loop

    def _want(self) -> int:
        k = int((self.inflight or {}).get("lines") or 0)
        return max(0, max(self.batch_lines, k) - len(self.pending))

    def run(self, once: bool = False) -> int:
        self.start()
        if once:
            if self.patience is None:
                self.patience = (ONCE_TRIES, ONCE_SECONDS)
            while True:
                progressed = self.poll(self._want())
                if self.pending:
                    done = self.send_next(force=True)
                    if done == "gave up":
                        self.summary()
                        return 1
                    if done == "stopped":
                        break
                    if done == "sent" or progressed:
                        continue
                if not progressed:
                    break
            self.summary()
            return 0
        while not self.stopping:
            progressed = self.poll(self._want())
            full = len(self.pending) >= self.batch_lines or \
                sum(len(x.data) for x in self.pending) >= MAX_BATCH
            due = self.last_send is None or self.clock() - self.last_send >= self.interval
            if self.pending and (full or due):
                if self.send_next() == "sent":
                    continue
            if not progressed:
                self.sleep(POLL)
        self.summary()
        return 0

    def close(self) -> None:
        if self.f is not None:
            self.f.close()
            self.f = None

    def summary(self) -> None:
        c = self.counts
        self.say(f"read {c['read']} lines, sent {c['sent']}, accepted {c['accepted']}, "
                 f"rejected {c['rejected']}, already received {c['duplicate']}, cut {c['cut']}")


def _int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _retry_after(headers: dict):
    for k, v in (headers or {}).items():
        if k.lower() == "retry-after":
            try:
                return max(0, min(RETRY_AFTER_CAP, int(float(str(v).strip()))))
            except ValueError:
                return None
    return None


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="skald-ship", description="Send an access log to a Skald install.",
        epilog="The URL must be https:// (plain http only for 127.0.0.1 or localhost). "
               "Full notes: the top of this file, or docs/INGEST.md.")
    p.add_argument("--url", required=True, help="https://<skald host>/traffic-ingest/<site>")
    p.add_argument("--token-file", required=True, help="a file holding the ingest token")
    p.add_argument("--log", required=True, help="the access log, e.g. /var/log/nginx/access.log")
    p.add_argument("--state", default="/var/lib/skald-ship/state.json",
                   help="where the position is kept (default %(default)s)")
    p.add_argument("--batch-lines", type=int, default=2000,
                   help="lines per batch at most (default %(default)s)")
    p.add_argument("--interval", type=float, default=10,
                   help="seconds at most before a part batch is sent (default %(default)s)")
    p.add_argument("--from-end", action="store_true",
                   help="first run only: start at the end of the log, not its start")
    p.add_argument("--once", action="store_true",
                   help="send what the log holds now, then exit (1 when the server keeps "
                        f"refusing: {ONCE_TRIES} tries or {ONCE_SECONDS} s; nothing is lost)")
    a = p.parse_args(argv)
    problem = url_problem(a.url)
    if problem:
        print(f"skald-ship: --url: {problem}", file=sys.stderr)
        return 2
    if a.batch_lines < 1:
        print("skald-ship: --batch-lines must be at least 1", file=sys.stderr)
        return 2
    try:
        token = read_token(a.token_file)
    except OSError as why:
        print(f"skald-ship: --token-file: {why.strerror or why}", file=sys.stderr)
        return 2
    s = Shipper(a.url, token, a.log, a.state, a.batch_lines, a.interval, a.from_end)
    signal.signal(signal.SIGTERM, s.on_signal)
    signal.signal(signal.SIGINT, s.on_signal)
    try:
        return s.run(once=a.once)
    finally:
        s.close()


if __name__ == "__main__":
    raise SystemExit(main())
