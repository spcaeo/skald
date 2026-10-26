"""The shipper's install kit: a zip a site's admin runs on their own web server.

Built from the templates in this folder with the standard library's zipfile,
by the helper (Settings > Collect data > Send logs, POST <page>/sites/kit, connections_api.py)
and by `python3 -m skald.kit` (a deployment's own make-kit script):

    skald-ship-<site>/install.sh     install-docker.sh or install-systemd.sh
                      uninstall.sh   removes only what install.sh made
                      check.sh       read-only checks, one line each, and a block to send
                      README.txt     README-docker.txt or README-systemd.txt
                      skald-ship.py  the shipper itself (systemd kit only; tools/skald-ship.py)
                      ship-token     only when the admin asked for it, mode 0600 (the
                                     page's "Include the access token in the zip", ticked
                                     by default); without it, no file holds the token and
                                     install.sh takes it from a ship-token file the admin
                                     makes, SKALD_SHIP_TOKEN, or asks

Placeholders, filled with plain str.replace: __SITE__, __URL__ (the send
address, <base>/traffic-ingest/<site>), __HOST__, __IMAGE__ and
__SHIP_PATH__ (the Docker kit: the image and the shipper's path inside it),
__METHOD__, __DASHBOARD__ and __HELP__. Nothing secret is in a template; the
token is in the zip only when `token` is given, and is never logged.

The image is not named in this package: `ingest.kit_image` in the config,
else the SKALD_KIT_IMAGE environment variable (the Docker image's entrypoint
sets both it and SKALD_KIT_SHIP_PATH). Without one, the Docker kit is not
offered and the page says why.

`one_file` builds the universal installer instead: install-server.sh filled,
one bash file (`POST <page>/sites/kit` with method "server", the one-command
install link of link.py, and the set-up pack of pack.py). It uses Docker when
the server has it and the image is known, else systemd with the shipper
inside the file (base64). check.sh and uninstall.sh are inside too, and are
left on the server as /usr/local/bin/skald-ship-check and skald-ship-uninstall.
"""
from __future__ import annotations

import argparse
import base64
import io
import os
import re
import sys
import time
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
SHIPPER = HERE.parent.parent / "tools" / "skald-ship.py"
METHODS = ("docker", "systemd")
TEMPLATES = {
    "docker": {"install.sh": "install-docker.sh", "uninstall.sh": "uninstall.sh",
               "check.sh": "check.sh", "README.txt": "README-docker.txt"},
    "systemd": {"install.sh": "install-systemd.sh", "uninstall.sh": "uninstall.sh",
                "check.sh": "check.sh", "README.txt": "README-systemd.txt"},
}
LEFT = re.compile(r"__[A-Z][A-Z_]*__")
SITE = re.compile(r"^[a-z0-9](?:[a-z0-9.-]{0,98}[a-z0-9])?$")
TOKEN = re.compile(r"^skald_[0-9a-f]{4,16}_[A-Za-z0-9_-]{16,120}$")
IMAGE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/:@-]{0,200}$")
NO_IMAGE = ("The Docker kit needs the image name: set ingest.kit_image in the server's "
            "config (the Docker image sets it by itself).")
NO_SHIPPER = "The kit without Docker needs tools/skald-ship.py, which this server does not have."
NO_SERVER = ("The one-file installer needs the image name (ingest.kit_image) or "
             "tools/skald-ship.py, and this server has neither.")
SERVER_TEMPLATE = "install-server.sh"
# The heredocs' end marks inside install-server.sh: no embedded file may hold one as a line.
ENDS = ("SKALD_SHIPPER_EOF", "SKALD_CHECK_EOF", "SKALD_UNINSTALL_EOF")


def _setting(config, key: str, env: str) -> str | None:
    got = ((config or {}).get("ingest") or {}).get(key) or os.environ.get(env) or ""
    got = str(got).strip()
    return got or None


def image(config) -> str | None:
    got = _setting(config, "kit_image", "SKALD_KIT_IMAGE")
    return got if got and IMAGE.match(got) else None


def ship_path(config) -> str:
    return _setting(config, "kit_ship_path", "SKALD_KIT_SHIP_PATH") or \
        "/opt/skald/tools/skald-ship.py"


def available(config) -> dict:
    """{"docker", "systemd": bool, "why": {method: words}, "image", "ship_path"}
    for the page (the manual Docker command names the image too)."""
    why = {}
    if not image(config):
        why["docker"] = NO_IMAGE
    if not SHIPPER.is_file():
        why["systemd"] = NO_SHIPPER
    if "docker" in why and "systemd" in why:
        why["server"] = NO_SERVER
    return {"docker": "docker" not in why, "systemd": "systemd" not in why,
            "server": "server" not in why, "why": why,
            "image": image(config), "ship_path": ship_path(config)}


def fill(text: str, values: dict) -> str:
    for key, value in values.items():
        text = text.replace(f"__{key}__", value)
    return text


def _values(site: str, url: str, method: str, dashboard: str, help_url: str,
            image_name: str | None, shipper_path: str | None) -> dict:
    """The placeholders' values, checked; ValueError in plain words."""
    if not SITE.match(site or ""):
        raise ValueError("A site is a lower-case host name, like example.com.")
    parts = urlsplit(url or "")
    if parts.scheme not in ("https", "http") or not parts.hostname or \
            not parts.path.endswith(f"/traffic-ingest/{site}"):
        raise ValueError("The send address is https://<server>/traffic-ingest/<site>.")
    if image_name and not IMAGE.match(image_name):
        raise ValueError(NO_IMAGE)
    for name, value in (("send address", url), ("dashboard", dashboard), ("help", help_url),
                        ("image", image_name or ""), ("shipper path", shipper_path or "")):
        if any(c in value for c in "\"'`$\\\n\r ;|&<>"):
            raise ValueError(f"The {name} has a character a shell script cannot hold.")
    return {"SITE": site, "URL": url, "HOST": parts.netloc, "METHOD": method,
            "IMAGE": image_name or "", "SHIP_PATH": shipper_path or "",
            "DASHBOARD": dashboard, "HELP": help_url}


def _token(token) -> str:
    token = str(token).strip()
    if not TOKEN.match(token):
        raise ValueError("That is not a Skald token.")
    return token


def files(site: str, url: str, method: str, dashboard: str, help_url: str,
          image_name: str | None = None, shipper_path: str | None = None) -> dict:
    """{name in the zip: (bytes, mode)}; ValueError in plain words."""
    if method not in METHODS:
        raise ValueError("The kit is for docker or systemd.")
    if method == "docker" and not image_name:
        raise ValueError(NO_IMAGE)
    values = _values(site, url, method, dashboard, help_url, image_name, shipper_path)
    out = {}
    for name, template in TEMPLATES[method].items():
        text = fill((HERE / template).read_text(encoding="utf-8"), values)
        left = LEFT.findall(text)
        if left:
            raise ValueError(f"{template} has a placeholder left: {left[0]}")
        out[name] = (text.encode("utf-8"), 0o755 if name.endswith(".sh") else 0o644)
    if method == "systemd":
        if not SHIPPER.is_file():
            raise ValueError(NO_SHIPPER)
        out["skald-ship.py"] = (SHIPPER.read_bytes(), 0o755)
    return out


def build(site: str, url: str, method: str, dashboard: str, help_url: str,
          image_name: str | None = None, shipper_path: str | None = None,
          token: str | None = None) -> bytes:
    """The zip's bytes. `token`, when given, goes in as ship-token (0600)."""
    got = files(site, url, method, dashboard, help_url, image_name, shipper_path)
    if token is not None:
        got["ship-token"] = ((_token(token) + "\n").encode(), 0o600)
    folder = f"skald-ship-{site}"
    stamp = time.gmtime()[:6]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        top = zipfile.ZipInfo(f"{folder}/", stamp)
        top.create_system = 3
        top.external_attr = (0o40755 << 16) | 0x10
        z.writestr(top, b"")
        for name in sorted(got):
            data, mode = got[name]
            info = zipfile.ZipInfo(f"{folder}/{name}", stamp)
            info.create_system = 3                     # Unix: unzip keeps the modes
            info.external_attr = (0o100000 | mode) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)
    return buf.getvalue()


def _embedded(template: str, values: dict) -> str:
    """check.sh or uninstall.sh as the one file leaves them in /usr/local/bin:
    the way (docker or systemd) is written in at install time (@@METHOD@@),
    and the words name the commands the admin has there."""
    text = fill((HERE / template).read_text(encoding="utf-8"), {**values, "METHOD": "@@METHOD@@"})
    for old, new in (("sudo bash check.sh", "sudo skald-ship-check"),
                     ("sudo bash uninstall.sh", "sudo skald-ship-uninstall"),
                     ("sudo bash install.sh", "the Skald installer"),
                     ("run install.sh again", "run the Skald installer again"),
                     ("install.sh did not finish", "the installer did not finish"),
                     ("download the kit again", "run the Skald installer again")):
        text = text.replace(old, new)
    if template == "uninstall.sh":
        text = text.replace('echo "Done. Nothing else was changed."',
                            "rm -f /usr/local/bin/skald-ship-check /usr/local/bin/skald-ship-uninstall"
                            ' && echo "skald-ship-check and skald-ship-uninstall removed"\n'
                            'echo "Done. Nothing else was changed."')
    return text


def one_file(site: str, url: str, dashboard: str, help_url: str,
             image_name: str | None = None, shipper_path: str | None = None,
             token: str | None = None) -> bytes:
    """The universal installer (install-server.sh, filled): one bash file.
    Docker is offered in it only with both the image and the shipper's path in
    it; the token is inside only when given. ValueError in plain words."""
    docker = bool(image_name and shipper_path)
    has_shipper = SHIPPER.is_file()
    if not docker and not has_shipper:
        raise ValueError(NO_SERVER)
    values = _values(site, url, "server", dashboard, help_url,
                     image_name if docker else None, shipper_path if docker else None)
    values["TOKEN"] = _token(token) if token is not None else ""
    parts = {"CHECK_SCRIPT": _embedded("check.sh", values),
             "UNINSTALL_SCRIPT": _embedded("uninstall.sh", values)}
    for name, text in parts.items():
        left = LEFT.findall(text)
        if left:
            raise ValueError(f"{name.lower()} has a placeholder left: {left[0]}")
        if any(line.strip() in ENDS for line in text.splitlines()):
            raise ValueError(f"{name.lower()} holds a line the installer uses as an end mark.")
    text = fill((HERE / SERVER_TEMPLATE).read_text(encoding="utf-8"), values)
    left = [p for p in LEFT.findall(text)
            if p not in ("__CHECK_SCRIPT__", "__UNINSTALL_SCRIPT__", "__SHIPPER_B64__")]
    if left:
        raise ValueError(f"{SERVER_TEMPLATE} has a placeholder left: {left[0]}")
    packed = base64.encodebytes(SHIPPER.read_bytes()).decode("ascii") if has_shipper else ""
    for name, value in (*parts.items(), ("SHIPPER_B64", packed)):
        text = text.replace(f"__{name}__", value.rstrip("\n"))
    return text.encode("utf-8")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python3 -m skald.kit",
                                description="Build a site's shipper kit (a zip, no token).")
    p.add_argument("--site", required=True)
    p.add_argument("--url", required=True, help="the send address, <base>/traffic-ingest/<site>")
    p.add_argument("--method", choices=METHODS, default="docker")
    p.add_argument("--image", help="the Docker image (docker kit)")
    p.add_argument("--ship-path", default=None, help="skald-ship.py's path inside the image")
    p.add_argument("--dashboard", default="")
    p.add_argument("--help-url", default="")
    p.add_argument("--out", required=True, help="the zip to write")
    a = p.parse_args(argv)
    try:
        data = build(a.site, a.url, a.method, a.dashboard, a.help_url, a.image,
                     a.ship_path or ship_path({}))
    except ValueError as why:
        print(f"kit: {why}", file=sys.stderr)
        return 2
    out = Path(a.out)
    out.write_bytes(data)
    print(out)
    return 0
