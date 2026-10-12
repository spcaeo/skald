"""The checks `skald upgrade` makes before it changes anything (upgrade.py):
which release, whether this is a good time, and whether the files are the
ones the release published.

    target()      the version to go to, and the refusals: a downgrade, a
                  major jump without --allow-major, and for --auto anything
                  `updates.auto` does not allow (never a major)
    in_window()   the daily run's window: `report.run_window` ("HH:MM-HH:MM"
                  in report.timezone), else the cron line's run-daily time
                  ±10 minutes in the server's clock
    fetch_release()  the tarball and SHA256SUMS from the release; the tarball's
                  SHA-256 must be the one SHA256SUMS lists for it
    unpack()      the tarball into a folder, refusing any path that would land
                  outside it, any link, any device; it must hold this layout
                  (skald/cli.py, skald) and say the version asked for

Standard library only.
"""
from __future__ import annotations

import hashlib
import io
import re
import shutil
import tarfile
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from zoneinfo import ZoneInfo

from . import updates

DOWNLOAD = "https://github.com/{repo}/releases/download/{tag}"
TARBALL = "skald-{version}.tar.gz"
SUMS = "SHA256SUMS"
MAX_BYTES = 100 * 1024 * 1024
TIMEOUT = 60
CRON = Path("/etc/cron.d/skald")
SLACK = timedelta(minutes=10)
PACKAGE = "skald"
ENTRY = "bin/skald"
HHMM = re.compile(r"^\s*([01]?\d|2[0-3]):([0-5]\d)\s*-\s*([01]?\d|2[0-3]):([0-5]\d)\s*$")


class Refused(Exception):
    """Stopped before anything was changed."""


class Skipped(Refused):
    """Nothing to do, or not allowed for an automatic run: not an error."""


# ------------------------------------------------------------ which version

def target(current: str, latest: str | None, to: str | None = None,
           allow_major: bool = False, auto: str | None = None) -> tuple[str, str]:
    """(version, level). Refused when there is nothing to do or it is not allowed.
    `auto` is updates.auto for an --auto run (off, patch, minor), else None."""
    wanted = updates.plain(to) if to else updates.plain(latest)
    if not wanted:
        raise Refused("no release is known: GitHub could not be asked "
                      "(`skald updates --check-now` says why), and no --to was given")
    if updates.parse_version(wanted) is None:
        raise Refused(f"{wanted!r} is not a version (vX.Y.Z)")
    if updates.parse_version(current) is None:
        raise Refused(f"this install's version {current!r} is not known (VERSION, build.json)")
    how = updates.level(current, wanted)
    if how == "same":
        raise Skipped(f"already on {wanted}: nothing to do")
    if how == "older":
        raise Refused(f"{wanted} is older than {current}: a downgrade is refused "
                      "(roll back instead: docs/UPGRADING.md)")
    if auto is not None:
        if auto not in ("patch", "minor"):
            raise Skipped("automatic upgrades are off (updates.auto: off)")
        if how == "major":
            raise Skipped(f"{wanted} is a major release: never applied automatically; "
                          "read its notes, then run `skald upgrade --allow-major`")
        if how == "minor" and auto == "patch":
            raise Skipped(f"{wanted} is a minor release and updates.auto allows patch "
                          "releases only")
    elif how == "major" and not allow_major:
        raise Refused(f"{wanted} is a major release (from {current}): it may need steps "
                      "by hand. Read its notes, then add --allow-major")
    return wanted, how


# ------------------------------------------------------------ the run window

def _minutes(h, m) -> int:
    return int(h) * 60 + int(m)


def _inside(now_min: int, start: int, end: int) -> bool:
    start, end = start % 1440, end % 1440
    return start <= now_min <= end if start <= end else (now_min >= start or now_min <= end)


def cron_time(text: str) -> tuple[int, int] | None:
    """(hour, minute) of the run-daily line in a cron file, server clock."""
    for line in (text or "").splitlines():
        if line.lstrip().startswith("#") or "run-daily" not in line:
            continue
        parts = line.split()
        if len(parts) > 2 and parts[0].isdigit() and parts[1].isdigit():
            return int(parts[1]), int(parts[0])
    return None


def in_window(config: dict, now: datetime, cron_text: str | None = None,
              local_tz=None) -> str | None:
    """Why now is the daily run's window, or None when it is not."""
    raw = ((config or {}).get("report") or {}).get("run_window")
    if raw:
        m = HHMM.match(str(raw))
        if m:
            zone = ZoneInfo(str(((config or {}).get("report") or {}).get("timezone") or "UTC"))
            here = now.astimezone(zone)
            if _inside(_minutes(here.hour, here.minute), _minutes(*m.group(1, 2)),
                       _minutes(*m.group(3, 4))):
                return f"the daily run's window ({raw} {zone.key}, report.run_window)"
            return None
    if cron_text is None:
        try:
            cron_text = CRON.read_text()
        except OSError:
            return None
    got = cron_time(cron_text)
    if got is None:
        return None
    here = now.astimezone(local_tz) if local_tz is not None else now.astimezone()
    at = _minutes(*got)
    slack = int(SLACK.total_seconds() // 60)
    if _inside(_minutes(here.hour, here.minute), at - slack, at + slack):
        return (f"the daily run's window ({got[0]:02d}:{got[1]:02d} server time "
                f"±{slack} minutes, from the cron file)")
    return None


# ------------------------------------------------------------ the files

def _get(url: str, agent: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": agent})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        data = resp.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise Refused(f"{url}: larger than {MAX_BYTES // (1024 * 1024)} MB")
    return data


def sums_of(text: str) -> dict[str, str]:
    """{file name: sha256} from a SHA256SUMS file (`sha256sum` output)."""
    out = {}
    for line in (text or "").splitlines():
        m = re.match(r"^([0-9a-fA-F]{64})\s+\*?(\S.*?)\s*$", line)
        if m:
            out[m.group(2)] = m.group(1).lower()
    return out


def check_hash(data: bytes, name: str, sums_text: str) -> str:
    """The SHA-256 of `data`; Refused unless SHA256SUMS lists that for `name`."""
    listed = sums_of(sums_text).get(name)
    if listed is None:
        raise Refused(f"{SUMS} does not list {name}: not upgrading")
    got = hashlib.sha256(data).hexdigest()
    if got != listed:
        raise Refused(f"{name}: SHA-256 {got[:16]}... is not the {listed[:16]}... "
                      f"{SUMS} lists: the download is damaged or not the release; "
                      "nothing was changed")
    return got


def fetch_release(version: str, repo: str, fetch=None, base: str | None = None,
                  agent: str = "") -> tuple[bytes, str, str]:
    """(tarball bytes, its file name, its sha256), checked against SHA256SUMS."""
    tag = f"v{version}"
    base = (base or DOWNLOAD.format(repo=repo, tag=tag)).rstrip("/")
    name = TARBALL.format(version=version)
    get = fetch or _get
    try:
        sums = get(f"{base}/{SUMS}", agent).decode("utf-8", "replace")
        data = get(f"{base}/{name}", agent)
    except Refused:
        raise
    except Exception as why:            # noqa: BLE001 - said, nothing changed
        raise Refused(f"could not download the release {tag} from {base}: "
                      f"{type(why).__name__}: {why}") from None
    if len(data) > MAX_BYTES:
        raise Refused(f"{name}: larger than {MAX_BYTES // (1024 * 1024)} MB")
    return data, name, check_hash(data, name, sums)


def _safe_members(tar: tarfile.TarFile) -> tuple[str, list[tarfile.TarInfo]]:
    """The one top folder and the members under it; Refused for anything else."""
    members, top = [], None
    for m in tar.getmembers():
        if m.name in ("pax_global_header",) or m.type in (tarfile.XGLTYPE, tarfile.XHDTYPE):
            continue
        p = PurePosixPath(m.name)
        if p.is_absolute() or ".." in p.parts or not p.parts:
            raise Refused(f"the tarball has an unsafe path {m.name[:80]!r}")
        if not (m.isfile() or m.isdir()):
            raise Refused(f"the tarball has a link or device {m.name[:80]!r}")
        if top is None:
            top = p.parts[0]
        if p.parts[0] != top:
            raise Refused("the tarball has more than one top folder")
        members.append(m)
    if top is None:
        raise Refused("the tarball is empty")
    return top, members


def unpack(data: bytes, dest: Path, version: str) -> Path:
    """Unpack the release into `dest` (made here; must not exist). The code's
    folder is returned; Refused when it is not this layout or version."""
    dest = Path(dest)
    scratch = dest.with_name(dest.name + ".unpack")
    shutil.rmtree(scratch, ignore_errors=True)
    scratch.mkdir(parents=True)
    try:
        try:
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
                top, members = _safe_members(tar)
                for m in members:
                    m.mode = (m.mode | 0o644) & 0o755 if m.isfile() else 0o755
                    m.uid = m.gid = 0
                    m.uname = m.gname = ""
                if hasattr(tarfile, "data_filter"):
                    tar.extractall(scratch, members=members, filter="data")
                else:                   # Python before 3.11.4: checked above
                    tar.extractall(scratch, members=members)
        except (tarfile.TarError, OSError, EOFError) as why:
            raise Refused(f"the tarball cannot be unpacked: {why}") from None
        code = scratch / top
        if not (code / PACKAGE / "cli.py").is_file() or not (code / ENTRY).is_file():
            raise Refused(f"the release does not have this install's layout "
                          f"({PACKAGE}/cli.py, {ENTRY}): not upgrading")
        said = (code / "VERSION").read_text().strip() if (code / "VERSION").exists() else ""
        if updates.plain(said) != version:
            raise Refused(f"the release says VERSION {said or 'nothing'}, not {version}")
        code.rename(dest)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    return dest


def build_json(code: Path, now: datetime) -> str:
    """build.json for the unpacked code (tools/build-info.sh's fields; the
    release number and commit are not in a tarball)."""
    import json

    def text(name: str) -> str:
        try:
            return " ".join((code / name).read_text().split())
        except OSError:
            return ""
    return json.dumps({"schema_version": 1, "name": text("NAME") or "Skald",
                       "version": text("VERSION"), "tagline": text("TAGLINE"),
                       "release": 0, "commit": "unknown",
                       "deployed_at": now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
                      separators=(",", ":")) + "\n"
