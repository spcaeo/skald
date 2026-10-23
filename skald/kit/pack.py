"""The set-up pack: one zip with every way to connect a site, for a person or
an AI coding agent (POST <page>/sites/pack and sites/packmail, kit_api.py).

    skald-setup-<site>/
      START-HERE.md            for a person: pick your case, then leads, then the checks
      CLAUDE.md, AGENTS.md     the same steps for an AI coding agent, numbered, no guessing
      secrets.env              the send and lead addresses; the token and the lead secret
                               only when the admin asked for them
      logs/install-server.sh   the one-file installer (kit.one_file; the token inside when asked)
      logs/cloudflare.md       the Skald Worker's steps
      logs/vercel-netlify.md   the log drains' steps
      tag/script-tag.html      the script tag
      tag/README.md            where to put it
      leads/...                skald.kit.leadfiles.files(site, url, secret) when that
                               module is there, else a README that points to Settings >
                               Integrations

The words come from the templates in setup-pack/, filled with str.replace.
Mail filters refuse an attachment that holds scripts they block (Gmail: .js,
.mjs and others), so such a name gets ".txt" added and the leads README says
to take it off. No secret is ever logged.
"""
from __future__ import annotations

import io
import re
import time
import zipfile
from datetime import datetime, timezone
from email.message import EmailMessage
from html import escape as esc
from pathlib import Path

from . import LEFT, fill

HERE = Path(__file__).resolve().parent / "setup-pack"
MAIL_MOST = 3
NOTE_MOST = 1000
EMAIL = re.compile(r"^[^@\s<>,;\"]{1,64}@[A-Za-z0-9.-]{1,253}\.[A-Za-z]{2,63}$")
# Names mail filters refuse inside an attachment (Gmail's list, the script kinds).
BLOCKED = (".js", ".mjs", ".jse", ".vbs", ".vbe", ".bat", ".cmd", ".com", ".exe", ".ps1",
           ".jar", ".scr", ".msi", ".dll", ".lnk", ".wsf", ".wsh", ".hta", ".cpl")

LEAD_NOTES = {
    "included": "The lead secret is `SKALD_LEAD_SECRET` in `secrets.env`.",
    "exists": ("This site already has a lead secret, so it is not in this folder. Use the one "
               "the site's backend already has, or make a new one in Skald: Settings > "
               "Integrations > Lead > Make secret. Making a new one stops the old one at once."),
    "env": ("The lead secret is kept in the Skald server's environment. Ask whoever runs your "
            "Skald for it."),
    "none": ("The lead secret is not in this folder. Make it in Skald: Settings > Integrations "
             "> Lead > Make secret (making a new one stops the old one at once)."),
}


def _secrets_words(token: str | None, lead_secret: str | None) -> str:
    if token or lead_secret:
        held = [w for w, v in (("the sending token (in `secrets.env`, and inside "
                                "`logs/install-server.sh`)", token),
                               ("the lead secret (in `secrets.env`)", lead_secret)) if v]
        return (f"**This folder holds keys:** {' and '.join(held)}. Treat it like a password: "
                "do not commit it to git or paste it in a chat, and delete it (and the mail it "
                "came in) after the set-up.")
    return ("**This folder holds no keys.** The sending token comes separately (or the "
            "installer asks for it); make one in Skald under Settings > Connections. "
            "`secrets.env` lists the keys and where each comes from.")


def secrets_env(site: str, ingest_url: str, lead_url: str, token: str | None,
                lead_secret: str | None) -> str:
    head = [f"# Skald keys for {site}.",
            "# Treat this file like a password: keep it out of git and out of chats,",
            "# put each value in an environment variable or the host's secret settings,",
            "# and delete this file after the set-up."]
    if not token:
        head.append("# SKALD_INGEST_TOKEN: make a sending token in Skald, Settings > Connections.")
    if not lead_secret:
        head.append("# SKALD_LEAD_SECRET: make it in Skald, Settings > Integrations > Lead "
                    "(a new one stops the old one).")
    return "\n".join(head + [f"SKALD_INGEST_URL={ingest_url}",
                             f"SKALD_INGEST_TOKEN={token or ''}",
                             f"SKALD_LEAD_URL={lead_url}",
                             f"SKALD_LEAD_SECRET={lead_secret or ''}"]) + "\n"


def safe_name(name: str) -> str:
    """A file name mail filters take: a blocked kind gets ".txt" added."""
    return name + ".txt" if name.lower().endswith(BLOCKED) else name


def lead_files(site: str, url: str, secret: str | None) -> dict | None:
    """{name: bytes} from leadfiles.files, or None when that module is not here."""
    try:
        from .leadfiles import files as made
    except ImportError:
        return None
    return made(site, url, secret)


LEADS_README = """# Leads for {site}

When the site's backend makes a lead (a contact form, a sign-up), it can post it to Skald,
signed with the lead secret. Skald then shows which pages and sources bring leads.

The address: {url}

{note}

Skald's page has the code for each backend language: Settings > Integrations > Lead, and its
help guide "Send leads from your backend". Keep the secret in an environment variable, never
in code or in git.
"""


def files(site: str, *, ingest_url: str, lead_url: str, dashboard: str, help_url: str,
          tag: str, installer: bytes, token: str | None = None,
          lead_secret: str | None = None, lead_note: str = "none") -> dict:
    """{path in the folder: bytes}; ValueError in plain words."""
    values = {"SITE": site, "INGEST_URL": ingest_url, "LEAD_URL": lead_url,
              "DASHBOARD": dashboard, "HELP": help_url, "TAG": tag,
              "TOKEN": token or "<the sending token: SKALD_INGEST_TOKEN in secrets.env>",
              "SECRETS": _secrets_words(token, lead_secret),
              "LEAD_SECRET_NOTE": LEAD_NOTES.get(lead_note, LEAD_NOTES["none"])}
    out = {}
    for name, template in (("START-HERE.md", "START-HERE.md"), ("CLAUDE.md", "CLAUDE.md"),
                           ("logs/cloudflare.md", "cloudflare.md"),
                           ("logs/vercel-netlify.md", "vercel-netlify.md"),
                           ("tag/README.md", "tag-README.md")):
        text = fill((HERE / template).read_text(encoding="utf-8"), values)
        left = LEFT.findall(text)
        if left:
            raise ValueError(f"{template} has a placeholder left: {left[0]}")
        out[name] = text.encode("utf-8")
    out["AGENTS.md"] = out["CLAUDE.md"]
    out["secrets.env"] = secrets_env(site, ingest_url, lead_url, token, lead_secret).encode()
    out["logs/install-server.sh"] = installer
    out["tag/script-tag.html"] = (tag + "\n").encode()
    leads = lead_files(site, lead_url, lead_secret)
    if leads is None:
        out["leads/README.md"] = LEADS_README.format(
            site=site, url=lead_url, note=values["LEAD_SECRET_NOTE"]).encode()
    else:
        renamed = []
        for name, data in sorted(leads.items()):
            clean = "/".join(p for p in str(name).replace("\\", "/").split("/")
                             if p not in ("", ".", ".."))
            if not clean:
                continue
            got = safe_name(clean)
            if got != clean:
                renamed.append(clean)
            out[f"leads/{got}"] = data if isinstance(data, bytes) else str(data).encode()
        if renamed:
            words = "\n".join(f"- {n}.txt: rename it to {n}" for n in renamed)
            out["leads/RENAME-ME.md"] = (
                "# Files renamed for mail\n\nMail filters refuse these kinds of file inside an "
                f"attachment, so each got .txt added. Take it off before use:\n\n{words}\n").encode()
    return out


def build(site: str, got: dict) -> bytes:
    """The zip of `files`' answer, in the folder skald-setup-<site>/. The
    installer keeps mode 0755, secrets.env is 0600, the rest 0644."""
    folder = f"skald-setup-{site}"
    stamp = time.gmtime()[:6]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(got):
            mode = 0o755 if name.endswith(".sh") else 0o600 if name == "secrets.env" else 0o644
            info = zipfile.ZipInfo(f"{folder}/{name}", stamp)
            info.create_system = 3                     # Unix: unzip keeps the modes
            info.external_attr = (0o100000 | mode) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, got[name])
    return buf.getvalue()


def clean_recipients(raw) -> list[str]:
    """Up to MAIL_MOST addresses, checked; ValueError in plain words."""
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list) or not raw:
        raise ValueError("Give at least one address to send the pack to.")
    got = []
    for one in raw:
        email = str(one or "").strip().lower()
        if not EMAIL.match(email):
            raise ValueError(f"That is not an email address: {email[:80] or '(empty)'}.")
        if email not in got:
            got.append(email)
    if len(got) > MAIL_MOST:
        raise ValueError(f"Send it to {MAIL_MOST} addresses at most.")
    return got


def message(config, site: str, to: list[str], data: bytes, secrets: bool,
            note: str = "", now: datetime | None = None) -> tuple[EmailMessage, dict]:
    """(the mail with the zip attached, the mail settings); mailer.Refused when
    mail is not set up here."""
    from .. import mailer
    from ..accounts.mails import FONT, mail_settings
    cfg = dict(mail_settings(config, to[0]))
    cfg["to"] = list(to)
    name = f"skald-setup-{site}.zip"
    paras = [f"Attached: {name}, everything to connect {site} to Skald.",
             "Open START-HERE.md in it and pick your case. Or give the folder to Claude Code "
             "(or another AI coding agent) and say: Set up Skald from CLAUDE.md."]
    note = " ".join(str(note or "").split())[:NOTE_MOST]
    if note:
        paras.append(f"Note: {note}")
    if secrets:
        paras.append("This mail holds keys (the sending token and the lead secret): delete it "
                     "after the set-up.")
    text = f"Set up Skald for {site}\n\n" + "\n\n".join(paras) + "\n"
    body = "".join(f'<p style="margin:0 0 14px;font:400 15px/1.55 {FONT};color:#17212b">'
                   f"{esc(p)}</p>" for p in paras)
    html = ('<!doctype html><html><head><meta charset="utf-8"></head>'
            f'<body style="margin:0;padding:24px;background:#f4f6f8"><div style="max-width:560px;'
            'margin:0 auto;background:#ffffff;border:1px solid #dde3e8;border-radius:10px;'
            f'padding:24px 26px"><div style="font:600 18px/1.3 {FONT};color:#17212b;'
            f'padding-bottom:14px">Set up Skald for {esc(site)}</div>{body}</div></body></html>')
    msg = mailer._message(cfg, f"Set up Skald for {site}", text, html,
                          now or datetime.now(timezone.utc))
    msg.add_attachment(data, maintype="application", subtype="zip", filename=name)
    return msg, cfg
