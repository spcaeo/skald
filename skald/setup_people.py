"""Add a site's two first questions (2.43): which organisation, and who will use it.

The owner (2026-10-27): the organisation and the people are chosen when the
site is added, so the one agent line does everything on its own. In the
wizard's first step (site-wizard.js, site-wizard-org.js):

  Organisation   same (this one, the default), another of mine (an organisation
                 the person is an owner or admin of, by its id), or new (a name,
                 and "Internal, keep everything" or "A client: their own privacy
                 settings apply"). A new organisation is made when the site is
                 (sites/add): its maker becomes its owner, so the keys the
                 wizard makes stay valid (apitokens.creator_ok), and the site is
                 there from the start. Nothing moves later.
  Who will use it  members of this organisation (by user id), and new
                 addresses, each viewer or admin (owner only for a new
                 organisation). Kept in the site's set-up row (site_setup
                 `people`), never in an address.
  Sees           each person's site access (accounts' members.sites): "site",
                 this site only (the default in an existing organisation), or
                 "all", every site of it (the default in a new one). An owner
                 always sees every site.

The invites go out by themselves once the set-up is done and the first data
arrived (`tick`, from the live run and from sites/live while the wizard is
open): each new address gets the normal invite (accounts/invites.py) with
"<site> is live, 1,283 requests so far", a member of another organisation is
added to this one and told the same; the maker gets one mail, "<site> is
live. Invites sent to 1 person." When the set-up has not finished after
LATE_HOURS, the maker gets one mail with what is missing (setup_live.check's
words) and can send the invites anyway (sites/sendinvites).

Only rows made by 2.43's wizard (`made_by` set) are ticked: a site set up
before gets no mail on the first run after an upgrade. Every change writes
the audit log (accounts' own rows: org.create, member.add, invite.send,
site.setup; and setup.invites here). Nothing here counts a figure.
"""
from __future__ import annotations

import sys

from .accounts import auditlog, invites, orgs, site_setup, users
from .accounts import db as base

PER_SITE = 20                   # people one site's set-up may name
LATE_HOURS = 24
ROLES = ("viewer", "admin")     # and owner, for a new organisation only
ADMIN = ("owner", "admin")
SEES = ("site", "all")


# ------------------------------------------------------------ the answers

def clean(db, raw, members_of, new_org: bool = False) -> list[dict]:
    """[{"user": id, "role", "sees"} | {"email", "role", "sees"}]: `raw` checked.
    A user is a member of `members_of` (the asker's organisation); an address
    is cleaned; each once. "sees" is "site" (this site only) or "all"; absent,
    "all" in a new organisation and "site" otherwise; an owner's is "all".
    ValueError in plain words."""
    if raw in (None, ""):
        return []
    if not isinstance(raw, list):
        raise ValueError("people is a list of {user or email, role}.")
    if len(raw) > PER_SITE:
        raise ValueError(f"At most {PER_SITE} people for one site.")
    roles = ROLES + (("owner",) if new_org else ())
    out, seen = [], set()
    for one in raw:
        if not isinstance(one, dict):
            raise ValueError("Each person is {user or email, role}.")
        role = one.get("role") or "viewer"
        if role not in roles:
            raise ValueError("A role is viewer or admin" +
                             (", or owner for a new organisation." if new_org else
                              ". An owner can only be named for a new organisation."))
        sees = one.get("sees") or ("all" if new_org else "site")
        if sees not in SEES:
            raise ValueError("Sees is this site only (site) or every site (all).")
        if role == "owner":
            sees = "all"
        if one.get("user") is not None:
            try:
                uid = int(one["user"])
            except (TypeError, ValueError):
                raise ValueError("That person is not one of your organisation's.") from None
            if users.role_in(db, uid, members_of) is None:
                raise ValueError("That person is not one of your organisation's.")
            key, item = f"u{uid}", {"user": uid, "role": role, "sees": sees}
        else:
            email = users.clean_email(one.get("email") if isinstance(one.get("email"), str) else "")
            key, item = email, {"email": email, "role": role, "sees": sees}
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def target_org(db, uid, choice, name: str = "", privacy: str = "internal",
               install_admin: bool = False, hosted: bool = False) -> tuple[dict | None, bool]:
    """(the organisation the new site goes to, made now). `choice`: "same"
    (None: the page's), an organisation id the person is an owner or admin
    of, or "new" (made here, the person its owner, its data rule set).
    ValueError in plain words. On a hosted install only an install admin
    makes an organisation here (a plan belongs to each one)."""
    if choice in (None, "", "same"):
        return None, False
    if choice == "new":
        if hosted and not install_admin:
            raise ValueError("A new organisation is made by signing up. Choose one of yours.")
        if privacy not in orgs.PRIVACY_CLASSES:
            raise ValueError("Their data is Internal or A client.")
        org = orgs.create_org(db, name, uid)
        users.add_member(db, org["id"], uid, "owner", uid)
        orgs.set_privacy_class(db, org["id"], privacy, uid)
        return org, True
    try:
        oid = int(choice)
    except (TypeError, ValueError):
        raise ValueError("Choose this organisation, another of yours, or a new one.") from None
    if users.role_in(db, uid, oid) not in ADMIN:
        raise ValueError("You are not an owner or admin of that organisation.")
    return orgs.get_org(db, oid), False


def options(db, uid, org_id) -> dict:
    """GET sites/whoopts: the organisations this person may add a site to
    (owner or admin), and this organisation's members to pick from."""
    mine = [{"id": o["id"], "name": o["name"], "role": o["role"],
             "sites": len(orgs.sites_of_org(db, o["id"]))}
            for o in orgs.list_orgs(db, uid) if o["role"] in ADMIN and o["id"] != org_id]
    people = [{"id": m["id"], "name": m["name"] or "", "email": m["email"], "role": m["role"],
               "limited": m["sites"] is not None}
              for m in users.members(db, org_id) if not m["disabled_at"]]
    return {"orgs": mine, "members": people}


# ---------------------------------------------------------------- mails

def _mail(config, to: str, subject: str, paras: list[str], link: str | None, button: str):
    from .accounts import mails
    paras = [p for p in paras if p]
    text = "\n\n".join([subject, *paras, *([f"{button}: {link}"] if link else [])]) + "\n"
    return mails._build(config, to, subject, text,
                        mails._html(subject, paras, link, button, "Skald, server-log analytics."))


def _send(config, to: str, msg) -> bool:
    from .accounts import mails
    try:
        mails.deliver(msg, config, to)
        return True
    except Exception as why:             # noqa: BLE001 - a mail never stops the set-up
        sys.stderr.write(f"setup mail not sent: {type(why).__name__}\n")
        return False


def _people(n: int) -> str:
    return f"{n} {'person' if n == 1 else 'people'}"


def live_words(site: str, requests: int | None) -> str:
    got = f", {requests:,} requests so far" if requests else ""
    return f"{site} is live{got}."


# ------------------------------------------------------------- sending

def send(db, config, site: str, base_url: str | None, actor, requests: int | None = None,
         by_hand: bool = False) -> dict:
    """Invite the set-up's people now, once: {sent, added, skipped, words,
    already}. A new address gets the normal invite with the live words; a
    member of another organisation is added to this one; one already in it is
    skipped. The maker gets one mail. invites_at is set whatever went, so it
    runs once (sites/sendinvites may run it before the data comes)."""
    from .accounts import mails
    row = site_setup.get(db, site)
    if row is None:
        raise ValueError("There is no set-up for this site.")
    if row.get("invites_at"):
        return {"sent": 0, "added": 0, "skipped": 0, "words": row.get("invites_words") or "",
                "already": True}
    org = orgs.get_org(db, row["org_id"])
    maker = users.find_user(db, user_id=int(row["made_by"])) if str(
        row.get("made_by") or "").isdigit() else None
    inviter = (maker or {}).get("name") or (maker or {}).get("email") or ""
    page = f"{base_url}/traffic/{site}/" if base_url else None
    words = live_words(site, requests) if not by_hand else f"{site} is being set up on Skald."
    mail_on = mails.configured(config)
    sent = added = skipped = handed = 0
    for one in row.get("people") or []:
        role = one.get("role") or "viewer"
        # A row from before "sees" (2.43's first cut) keeps the old rule: every site.
        only = [site] if one.get("sees") == "site" and role != "owner" else None
        what = f"{role} of {site} only" if only else role
        if one.get("user") is not None:
            user = users.find_user(db, user_id=int(one["user"]))
            if user is None or user.get("disabled_at"):
                skipped += 1
                continue
            if users.role_in(db, user["id"], org["id"]) is None:
                users.add_member(db, org["id"], user["id"], role, row.get("made_by") or actor,
                                 sites=only)
                added += 1
                if mail_on:
                    _send(config, user["email"], _mail(
                        config, user["email"], f"{site} is on Skald",
                        [words, f"You were added to {org['name']} as {what}."], page,
                        "Open the dashboard"))
            else:
                skipped += 1
            continue
        email = one.get("email") or ""
        existing = users.find_user(db, email=email)
        if existing and users.role_in(db, existing["id"], org["id"]):
            skipped += 1
            continue
        try:
            token = invites.invite(db, org["id"], email, role, row.get("made_by") or actor,
                                   sites=only)
        except ValueError:
            skipped += 1
            continue
        from .accounts import links
        link = links.link(base_url, "invite", token) if base_url else None
        if mail_on and link:
            msg = _mail(config, email, f"You are invited to {site} on Skald",
                        [words, f"{inviter or 'Someone'} invited you to {org['name']} as {what}. "
                                f"The link works once, for {invites.INVITE_DAYS} days."
                                + (f" After you join, the site's page is {page}" if page else "")],
                        link, "Open your dashboard")
            if _send(config, email, msg):
                sent += 1
                continue
        invites.mark_handed(db, token)
        handed += 1
    n = sent + added
    told = (f"Invites sent to {_people(n)}." if n else "No one else to invite.")
    if handed:
        told += (f" {_people(handed)} could not be mailed: copy their links in "
                 "Settings › Organisation › People.")
    stamp = base.now()
    site_setup.note(db, site, invites_at=stamp, invites_words=told)
    auditlog.record(db, org["id"], actor, "setup.invites", site,
                    f"{'by hand' if by_hand else 'data arrived'}: {sent} invited, {added} added, "
                    f"{skipped} skipped, {handed} not mailed")
    if maker and mail_on and not maker.get("disabled_at"):
        head = (f"{site} is live. {told}" if not by_hand else f"Invites for {site}: {told}")
        _send(config, maker["email"], _mail(config, maker["email"], head,
                                            [live_words(site, requests) if not by_hand else head,
                                             told], page, "Open the dashboard"))
    return {"sent": sent, "added": added, "skipped": skipped, "handed": handed, "words": told,
            "already": False}


def tick(db, config, site: str, base_url: str | None, heard, check=None,
         now: float | None = None) -> str | None:
    """The live run's and sites/live's look at one site: when its set-up
    (made by 2.43's wizard) heard data and is verified, mark it done and send
    the invites; when it is not done after LATE_HOURS, the maker's one late
    mail. `heard()` -> (lines kept so far, any data arrived). `check()` ->
    the plain words of what is missing (setup_live.check). What it did:
    "done", "late" or None."""
    now = base.parse(base.now()).timestamp() if now is None else now    # the accounts' clock
    row = site_setup.get(db, site)
    if row is None or not str(row.get("made_by") or "").isdigit() or row.get("invites_at"):
        return None
    from . import site_verify
    lines, arrived = heard()
    verified = not site_verify.pending(db, site)
    if arrived and verified:
        if not row["done"]:
            site_setup.save(db, row["org_id"], site, "skald", step=site_setup.STEPS, done=True)
        send(db, config, site, base_url, "skald", requests=lines or None)
        return "done"
    started = base.parse(row["started_at"]).timestamp()
    if row["done"] or row.get("late_at") or now - started < LATE_HOURS * 3600:
        return None
    from .accounts import mails
    maker = users.find_user(db, user_id=int(row["made_by"]))
    site_setup.note(db, site, late_at=base.now())
    if maker and mails.configured(config):
        what = check() if check else "No data has arrived yet."
        page = f"{base_url}/traffic/{site}/#settings/org/sites?setup={site}" if base_url else None
        n = len(row.get("people") or [])
        more = (f"{_people(n)} will get an invite once data arrives. To send them now, press "
                "Send the invites now on the set-up page." if n else "")
        _send(config, maker["email"], _mail(config, maker["email"],
                                            f"{site} is not set up yet",
                                            [f"{site} was added a day ago, but its set-up has not "
                                             "finished.", what, more], page, "Open the set-up"))
    auditlog.record(db, row["org_id"], "skald", "setup.late", site, "not finished after a day")
    return "late"
