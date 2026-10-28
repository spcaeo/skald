"""Adding a site: the one code path for POST sites/add and the MCP's add_site (2.44).

    refusal(db, config, org_id, role)   why this person may not add a site now, or None
    add(db, config, org, uid, form, ...) the site added -> sites/add's answer (no "ok")

The rules, in this order, the same for a person in the dashboard and an AI
agent with a token's add_sites scope (mcp/tools_addsite.py):

  * an owner or admin of the organisation (the token's maker, for a token)
  * the organisation is not read-only (saas.limits.read_only: cancelled, long
    unpaid): 402
  * the log endpoint is on (ingest.enabled)
  * the plan allows another site (saas.limits.can_add_site)
  * the host is a site name, not a site of this install already
    (site_configs.create), at most setup_people.PER_SITE people, each a viewer
    or admin (owner only for a new organisation)
  * the plan allows the people it names as new members, open invites
    included (saas.limits.can_add_people)
  * with saas on, the site starts "pending" (site_verify.py): nothing is
    collected until its domain is verified

A refusal is `Refused` (a ValueError with the HTTP status) in one plain
sentence. Nothing is made when one is refused: the organisation, the site, its
token and its set-up row are made in one transaction.
"""
from __future__ import annotations

from . import first_page, ingest, ingest_log, site_verify
from .auth_api import text

ADMIN = ("owner", "admin")


class Refused(ValueError):
    """A plain-words refusal with its HTTP status (400, 402, 403)."""

    def __init__(self, status: int, words: str):
        super().__init__(words)
        self.status = status


def refusal(db, config, org_id, role) -> str | None:
    """Why this person may not add a site to `org_id` now, or None."""
    from .sites_api import plan_allows
    if role not in ADMIN:
        return "Only an admin can add a site."
    if not ingest.enabled(config):
        return ("Adding sites here needs the log endpoint switched on "
                "(ingest.enabled in the server's config).")
    return plan_allows(db, config, org_id)


def people_allowed(db, config, org_id, people) -> str | None:
    """None, or the plan's reason not to take this many new people."""
    from .saas import limits
    ok, why = limits.can_add_people(db, org_id, config, people)
    return None if ok else why


def add(db, config, org, uid, form, *, live_dir, config_path, allowed, out, origin: str,
        role: str = "owner", install_admin: bool = False) -> dict:
    """Add the site `form` names ({host, timezone?, format?, token?, hosts?,
    asset_prefixes?, org?, org_name?, privacy_class?, people?}) for `uid`, an
    owner or admin (`role`) of `org`. `origin`: this install's address for the
    script tag. The answer of POST sites/add without "ok"; Refused otherwise."""
    from . import settings_store, setup_people
    from .accounts import apitokens, site_configs, site_setup
    from .accounts import db as base
    from .sites_api import (SHIP_TOKEN_FILE, _base, config_sites, plan_allows, read_only,
                            saas_on, ship_command, tag)
    frozen = read_only(db, config, org["id"])
    if frozen:
        raise Refused(402, frozen)
    refused = refusal(db, config, org["id"], role)
    if refused:
        raise Refused(403, refused)
    root = ingest_log.root(config, ingest.history_folder(config, live_dir))
    try:
        name = site_configs.clean_name(text(form, "host", 200))
        folder = ingest_log.site_folder(root, name)
        assets = form.get("asset_prefixes") or None
        if assets is not None:
            try:
                assets = settings_store.validate("site.asset_prefixes", assets)
            except settings_store.Invalid as why:
                raise ValueError(str(why)) from None
        choice = form.get("org")
        choice = str(choice) if isinstance(choice, (str, int)) and not isinstance(choice, bool) \
            else "same"
        privacy = text(form, "privacy_class", 20) or "internal"
        with base.tx(db):
            # 2.43: the wizard's organisation (a new one is made here, its maker its owner).
            got, made = setup_people.target_org(
                db, uid, choice, text(form, "org_name", 100), privacy,
                install_admin=install_admin, hosted=saas_on(config))
            target = got or org
            if got is not None and not made:
                again = read_only(db, config, target["id"]) or plan_allows(db, config,
                                                                           target["id"])
                if again:
                    raise ValueError(again)
            people = setup_people.clean(db, form.get("people"), org["id"], new_org=made)
            seats = people_allowed(db, config, target["id"], people)
            if seats:
                raise ValueError(seats)
            site_configs.create(
                db, target["id"], name, uid, hosts=form.get("hosts") or None,
                timezone=text(form, "timezone", 64) or None,
                fmt=text(form, "format", 40) or "auto", log_dir=str(folder),
                taken=config_sites(config, config_path))
            token = apitokens.create(db, target["id"], f"Log shipper for {name}"[:60],
                                     sites=[name], scopes=("ingest",), actor=uid) \
                if form.get("token") is not False else None
            if assets:
                settings_store.put(db, f"site:{name}", "site.asset_prefixes", assets, uid)
            if saas_on(config):
                site_verify.start(db, name)
            # Its set-up row from the start: who added it, who will use it, the data rule.
            site_setup.save(db, target["id"], name, uid, step=1)
            site_setup.note(db, name, made_by=str(uid), people=people,
                            privacy_class=privacy if made else None)
    except ValueError as why:
        raise Refused(400, str(why)) from None
    folder.mkdir(parents=True, exist_ok=True)
    # Its page is there at once, not a 404; its logo is asked for first (2.25).
    first_page.start(out, name, config_path,
                     before=first_page.logo_fetch(config, config_path, name, live_dir, out))
    return dict(site=name, token=token, log_dir=str(folder),
                ingest_url=f"{_base(config, allowed)}{ingest.PREFIX}{name}",
                ship_command=ship_command(config, allowed, name), tag=tag(name, origin),
                token_file=SHIP_TOKEN_FILE, verify=site_verify.shown(db, name),
                org={"id": target["id"], "name": target["name"], "new": made},
                people=len(people))
