"""The one-file lead helpers: a site's backend tells Skald a lead was made by
calling one function (docs/help/leads-from-your-backend.md).

Built from the templates in leads/, by the helper (Settings > Leads & integrations,
POST <page>/integrations/leadfile, integrations_api.py) and by the set-up pack:

    files(site, url, secret) -> {path under a leads/ folder: bytes}
        skald-lead.php                         skald_lead($ref, $action, $email, $name, $extra)
        skald-lead.cjs                         skaldLead(ref, action, {email, name, ...})
        skald_lead.py                          skald_lead(ref, action, email, name, **extra)
        wordpress/skald-leads/skald-leads.php  a plugin: form plugins' entries, no code
        README.md                              the one line per language, the secret,
                                               the visitor ID, the no-code road
    one(lang, site, url, secret) -> (file name, bytes, media type)
        lang php, node, python or wordpress (a zip of the plugin's folder,
        skald-leads.zip, for Plugins > Add New > Upload Plugin)

`url` is the lead hook's address, <base>/traffic-hooks/<site>/lead, or the
base alone (the path is added). Node's file ends in .cjs, never .js or .mjs:
Gmail refuses a zip holding those.

Each file signs with X-Skald-Signature (every Skald version takes it) and
reads the secret from the environment variable SKALD_LEAD_SECRET first. With
`secret` None nothing secret is in any file, and its header says where the
secret goes; with a secret, the code files hold it as the fallback and say
to move it to the environment. The README never holds it. Placeholders are
filled with plain str.replace, as the shipper's kit does (kit/__init__.py).
"""
from __future__ import annotations

import io
import re
import time
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent / "leads"
PLUGIN = "wordpress/skald-leads/skald-leads.php"
FILES = ("skald-lead.php", "skald-lead.cjs", "skald_lead.py", PLUGIN, "README.md")
LANGS = {"php": ("skald-lead.php", "application/x-php"),
         "node": ("skald-lead.cjs", "application/javascript"),
         "python": ("skald_lead.py", "text/x-python"),
         "wordpress": ("skald-leads.zip", "application/zip")}
PLACEHOLDERS = ("SECRET_NOTE", "SECRET", "SITE", "URL", "ORIGIN")
SITE = re.compile(r"^[a-z0-9](?:[a-z0-9.-]{0,98}[a-z0-9])?$")
SECRET = re.compile(r"^[A-Za-z0-9_.~+/=-]{12,200}$")
HOST = re.compile(r"^[A-Za-z0-9.-]{1,253}(?::[0-9]{1,5})?$")
ENV_ONLY = ["The secret is read from the environment variable SKALD_LEAD_SECRET:",
            "set it on your server. Nothing secret is in this file."]
WP_ENV_ONLY = ["The secret is read from wp-config.php: add",
               "  define('SKALD_LEAD_SECRET', 'your-secret');",
               "(or the environment variable SKALD_LEAD_SECRET). Nothing secret is in this file."]
EMBEDDED = ["The secret is written in this file, so it works as it is. Better: move it",
            "to the environment variable SKALD_LEAD_SECRET (read first) and delete it",
            "here. Never put this file in a public place or a public code repository."]
WP_EMBEDDED = ["The secret is written in this file, so it works as it is. Better: move it",
               "to wp-config.php, define('SKALD_LEAD_SECRET', '...'); (read first),",
               "and delete it here."]


def address(site: str, url: str) -> str:
    """The lead hook's address from `url` (the address, or the base alone);
    ValueError in plain words."""
    if not SITE.match(site or ""):
        raise ValueError("A site is a lower-case host name, like example.com.")
    parts = urlsplit(str(url or "").strip())
    path = parts.path.rstrip("/")
    if parts.scheme not in ("https", "http") or not HOST.match(parts.netloc or "") \
            or parts.query or parts.fragment or path not in ("", f"/traffic-hooks/{site}/lead"):
        raise ValueError(f"The address is https://<server>/traffic-hooks/{site}/lead.")
    return f"{parts.scheme}://{parts.netloc}/traffic-hooks/{site}/lead"


def _note(text: str, lines: list[str]) -> str:
    """Each __SECRET_NOTE__ as lines, each with the comment start it sat behind."""
    out = []
    for line in text.split("\n"):
        at = line.find("__SECRET_NOTE__")
        if at < 0:
            out.append(line)
            continue
        out += [(line[:at] + got).rstrip() for got in lines]
    return "\n".join(out)


def files(site: str, url: str, secret: str | None) -> dict[str, bytes]:
    """{path under leads/: bytes}; ValueError in plain words."""
    hook = address(site, url)
    if secret is not None:
        secret = str(secret).strip()
        if not SECRET.match(secret):
            raise ValueError("That is not a hook secret.")
    parts = urlsplit(hook)
    values = {"SITE": site, "URL": hook, "ORIGIN": f"{parts.scheme}://{parts.netloc}"}
    out = {}
    for name in FILES:
        text = (HERE / name).read_text(encoding="utf-8")
        wp = name == PLUGIN
        text = _note(text, (WP_EMBEDDED if wp else EMBEDDED) if secret else
                     (WP_ENV_ONLY if wp else ENV_ONLY))
        text = text.replace("__SECRET__", "" if name == "README.md" else secret or "")
        for key, value in values.items():
            text = text.replace(f"__{key}__", value)
        left = [p for p in PLACEHOLDERS if f"__{p}__" in text]
        if left:
            raise ValueError(f"{name} has a placeholder left: __{left[0]}__")
        out[name] = text.encode("utf-8")
    return out


def plugin_zip(data: bytes) -> bytes:
    """The WordPress plugin as skald-leads.zip: one folder, skald-leads/."""
    stamp = time.gmtime()[:6]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        top = zipfile.ZipInfo("skald-leads/", stamp)
        top.create_system = 3
        top.external_attr = (0o40755 << 16) | 0x10
        z.writestr(top, b"")
        info = zipfile.ZipInfo("skald-leads/skald-leads.php", stamp)
        info.create_system = 3
        info.external_attr = (0o100644 << 16)
        info.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(info, data)
    return buf.getvalue()


def one(lang: str, site: str, url: str, secret: str | None) -> tuple[str, bytes, str]:
    """(file name, bytes, media type) of one language's file; ValueError."""
    if lang not in LANGS:
        raise ValueError(f"Choose one of: {', '.join(LANGS)}.")
    got = files(site, url, secret)
    name, mime = LANGS[lang]
    if lang == "wordpress":
        return name, plugin_zip(got[PLUGIN]), mime
    return name, got[name], mime
