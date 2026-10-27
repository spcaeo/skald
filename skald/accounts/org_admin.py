"""Organisation management: what Settings > Organisations and `skald org ...`
do beyond orgs.py's create, rename and assign (docs/ACCOUNTS.md, "Organisations").

    card(db, org, ...)            one organisation as the page's card shows it
    move_site(db, site, org, ...) move a site in; its one-site tokens keep working
    transfer_owner(...)           hand the ownership on: the other becomes an
                                  owner, the one handing it on an admin
    leave(db, org_id, user_id)    a member leaves (never the last owner)

No HTTP here; orgs_api.py and cli_orgs.py call these. Every change is one
audit row; nothing here deletes data.
"""
from __future__ import annotations

from . import auditlog, orgs, users
from . import db as base


def _need_org(db, org_id) -> dict:
    org = orgs.get_org(db, org_id)
    if org is None:
        raise ValueError("There is no such organisation.")
    return org


def plan_of(db, org_id) -> str | None:
    """The organisation's plan (saas), or None: "none" on a hosted page, hidden elsewhere."""
    row = db.execute("SELECT plan FROM orgs WHERE id = ?", (org_id,)).fetchone()
    return row[0] if row is not None and row[0] else None


def card(db, org: dict, role: str | None = None) -> dict:
    """{id, name, slug, sites, members, plan, privacy_class, state, created_at,
    archived_at, role}: what the Organisations page lists. `role` is the
    reader's own (None: an install admin who is not a member)."""
    sites = orgs.sites_of_org(db, org["id"])
    count = db.execute("SELECT COUNT(*) FROM members WHERE org_id = ?", (org["id"],)).fetchone()
    return {"id": org["id"], "name": org["name"], "slug": org["slug"], "sites": sites,
            "members": int(count[0]), "plan": plan_of(db, org["id"]),
            "privacy_class": org.get("privacy_class") or "internal",
            "state": "archived" if org.get("archived_at") else "active",
            "created_at": org["created_at"], "archived_at": org.get("archived_at"),
            "role": role}


def cards(db, user_id, install_admin: bool) -> list[dict]:
    """Every organisation for an install admin, else the reader's own."""
    mine = {o["id"]: o["role"] for o in orgs.list_orgs(db, user_id)}
    every = orgs.list_orgs(db) if install_admin else [o for o in orgs.list_orgs(db)
                                                        if o["id"] in mine]
    return [card(db, o, mine.get(o["id"])) for o in every]


# ---------------------------------------------------------------- move a site

def _keeper_of_tokens(db, org_id, actor) -> str | None:
    """Who a moved token is credited to in its new organisation: the mover
    when they are an owner or admin there, else its first enabled owner."""
    who = str(actor)
    if who.isdigit() and users.role_in(db, int(who), org_id) in ("owner", "admin"):
        user = users.find_user(db, user_id=int(who))
        if user is not None and not user["disabled_at"]:
            return who
    owners = users.owners(db, org_id)
    return str(owners[0]["id"]) if owners else None


def move_site(db, site, org_id, actor) -> dict:
    """Move `site` into the organisation (orgs.assign_site: its settings, its
    set-up progress and its one-site tokens move with it). A token made by a
    person keeps working only while they are an owner or admin of its
    organisation (apitokens.creator_ok); a moved token whose maker is not one
    in the new organisation is credited to the mover (an owner or admin there)
    or to its first owner, so a log shipper does not stop. One audit row each.
    {"site", "from", "tokens": [moved token ids], "recredited": [ids]}."""
    site = str(site or "").strip().lower()
    with base.tx(db):
        dest = _need_org(db, org_id)
        before = orgs.org_of_site(db, site)
        if before is None:
            raise ValueError("There is no such site here.")
        if before["id"] == dest["id"]:
            raise ValueError(f"{site} is already in {dest['name']}.")
        before_tokens = {r[0] for r in db.execute("SELECT id FROM tokens WHERE org_id = ?",
                                                  (before["id"],))}
        orgs.assign_site(db, site, org_id, actor)
        moved = [r[0] for r in db.execute("SELECT id FROM tokens WHERE org_id = ? ORDER BY id",
                                          (org_id,)) if r[0] in before_tokens]
        recredited = []
        for tid in moved:
            made_by = db.execute("SELECT created_by FROM tokens WHERE id = ?",
                                 (tid,)).fetchone()[0]
            from .apitokens import creator_ok
            if creator_ok(db, org_id, made_by):
                continue
            keeper = _keeper_of_tokens(db, org_id, actor)
            if keeper is None:
                continue                  # no owner to credit: the token waits, as before
            db.execute("UPDATE tokens SET created_by = ? WHERE id = ?", (keeper, tid))
            auditlog.record(db, org_id, actor, "token.recredit", tid,
                            f"moved with {site}: its maker is not an owner or admin of "
                            f"{dest['name']}, so it is credited to user {keeper}")
            recredited.append(tid)
    return {"site": site, "from": before["name"], "tokens": moved, "recredited": recredited}


# ---------------------------------------------------------- owners, leaving

def transfer_owner(db, org_id, from_user, to_user, actor) -> None:
    """`to_user` (a member) becomes an owner and `from_user` (an owner) an
    admin, in one step, so the organisation is never without an owner."""
    _need_org(db, org_id)
    if int(from_user) == int(to_user):
        raise ValueError("Choose someone else to hand the ownership to.")
    with base.tx(db):
        if users.role_in(db, from_user, org_id) != "owner":
            raise ValueError("Only an owner can hand on the ownership.")
        target = users.find_user(db, user_id=to_user)
        if target is None or users.role_in(db, to_user, org_id) is None:
            raise ValueError("Hand the ownership to a member of the organisation.")
        if target["disabled_at"]:
            raise ValueError(f"{target['email']} is disabled: enable them first.")
        if users.role_in(db, to_user, org_id) != "owner":
            users.set_role(db, org_id, to_user, "owner", actor)
        users.set_role(db, org_id, from_user, "admin", actor)
        auditlog.record(db, org_id, actor, "org.transfer", target["email"],
                        "ownership handed on; the former owner is an admin")


def leave(db, org_id, user_id) -> None:
    """The member leaves the organisation. The last owner cannot (ValueError)."""
    _need_org(db, org_id)
    users.remove_member(db, org_id, user_id, user_id)


# --------------------------------------------------------------- overview

def overview(db, org_id, history_path=None) -> dict:
    """The drawer's figures: sites, members, the requests of the 7 days before
    today and the last day with data. A figure the history does not hold, or
    whose second count (audit_orgs.py) disagrees, is None, never 0."""
    from .. import org_figures
    sites = orgs.sites_of_org(db, org_id)
    count = db.execute("SELECT COUNT(*) FROM members WHERE org_id = ?", (org_id,)).fetchone()
    got = org_figures.recent(history_path, sites)
    return {"sites": len(sites), "members": int(count[0]), **got}
