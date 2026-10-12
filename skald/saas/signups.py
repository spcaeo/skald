"""Sign-up links: an email address proves itself before anything is made.

`request` is called for every sign-up form, off the answer's clock (the
helper answers the same words at once, whatever happens here). It does the
same work whether or not the address has an account and answers:

    ("new", token)      a link to mail: valid SIGNUP_HOURS, used once
    ("exists", None)    the address has an account: mail "sign in instead"
    ("limited", None)   PER_EMAIL links this hour already: no mail
    ("refused", None)   not an address, or not in saas.allowed_domains

Only the SHA-256 of a link's token is kept, and the address it was asked
from only as a keyed hash. The per-address limit (PER_IP an hour) is the
helper's, checked before the answer (`ip_limited`, `note_ip`).

`finish` makes, in one transaction: the user (never an install admin), the
organisation (created_via signup) with the user as its owner, its first
site, and the default plan's trial (plans.start_trial). The site may not
be one of the install's config-file sites (`taken`) nor a name purged in
the last 30 days, and it starts "pending": nothing is collected for it until
its domain is verified (site_verify.py, Settings > Sites). When the plan caps
retention, the organisation's retention settings start at the cap, so no
data is ever kept longer than the plan allows (nothing exists yet to cut).
"""
from __future__ import annotations

import re
import secrets
from urllib.parse import urlsplit

from . import allowed_domains, plans
from ..accounts import auditlog, limits, orgs, passwords, users
from ..accounts import db as base

SIGNUP_HOURS = 24
PER_EMAIL = 3               # links an hour for one address
PER_IP = 10                 # sign-up forms an hour from one client address
NOT_VALID = "This sign-up link is not valid. Ask for a new one."
SITE_TAKEN = ("That site is already on Skald here. Ask its owner to invite you, or sign "
              "in if it is yours.")
HOST = re.compile(r"^(?=.{4,253}$)[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?"
                  r"(?:\.[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?)+$")
NOT_SITES = ("sites.json", "index.html")      # names the dashboard's own files use
BAD_HOST = "The site is a host name, like www.example.com."


def domain_allowed(config, email: str) -> bool:
    allowed = allowed_domains(config)
    if not allowed:
        return True
    domain = email.rsplit("@", 1)[-1]
    return any(domain == d or domain.endswith("." + d) for d in allowed)


def ip_limited(db, ip: str) -> bool:
    return limits.too_many(db, f"signup:ip:{ip}", limit=PER_IP, minutes=60)


def note_ip(db, ip: str) -> None:
    limits.note_failure(db, f"signup:ip:{ip}")


def request(db, email, ip: str, config) -> tuple[str, str | None]:
    try:
        email = users.clean_email(email)
    except ValueError:
        return "refused", None
    key = f"signup:email:{email}"
    with base.tx(db):
        limited = limits.too_many(db, key, limit=PER_EMAIL, minutes=60)
        limits.note_failure(db, key)
    token = secrets.token_urlsafe(32)
    digest = base.sha256(token)
    if not domain_allowed(config, email):
        return "refused", None
    if limited:
        return "limited", None
    if users.find_user(db, email=email) is not None:
        return "exists", None
    with base.tx(db):
        db.execute("DELETE FROM signups WHERE expires_at < ?", (base.shift(-30 * 86400),))
        db.execute("INSERT INTO signups (token_hash, email, created_at, expires_at, ip_hash) "
                   "VALUES (?, ?, ?, ?, ?)",
                   (digest, email, base.now(), base.shift(SIGNUP_HOURS * 3600),
                    base.keyed_hash(db, ip)))
        auditlog.record(db, None, "-", "signup.request", email)
    return "new", token


def _find(db, token) -> dict | None:
    if not isinstance(token, str) or not token or len(token) > 200:
        return None
    return base.one(db, "SELECT * FROM signups WHERE token_hash = ?", (base.sha256(token),))


def _usable(found: dict | None) -> dict:
    if found is None:
        raise ValueError(NOT_VALID)
    if found["used_at"]:
        raise ValueError("This sign-up link was already used. Sign in instead.")
    if found["expires_at"] <= base.now():
        raise ValueError("This sign-up link has expired. Ask for a new one.")
    return found


def info(db, token) -> dict | None:
    """{"email"} for a usable link, else None."""
    try:
        return {"email": _usable(_find(db, token))["email"]}
    except ValueError:
        return None


def clean_host(raw) -> str:
    """"https://WWW.Example.com/pricing" -> "www.example.com"; ValueError when
    it is not a host name with a dot (no port, no address)."""
    text = str(raw or "").strip().lower()
    if "//" not in text:
        text = "//" + text
    try:
        host = urlsplit(text).hostname or ""
    except ValueError:
        raise ValueError(BAD_HOST) from None
    host = host.rstrip(".")
    if (not HOST.match(host) or host in NOT_SITES or host.replace(".", "").isdigit()
            or " " in str(raw or "").strip()):
        raise ValueError(BAD_HOST)
    return host


def finish(db, token, name, password, org_name, host, config, taken=(), log_root=None) -> dict:
    """{"user", "org", "site"}; ValueError in plain words (the link stays
    usable when the form was wrong). The site is a dashboard site, like one
    added in Settings > Add or remove sites, so the runs process it and its
    shipped log lands in <log_root>/<site> (ingest_log.root)."""
    from .. import ingest_log, settings_store, site_verify
    from ..accounts import site_configs
    from . import limits as plan_limits
    found = _usable(_find(db, token))
    email = found["email"]
    name = " ".join(str(name or "").split())[:100]
    if not name:
        raise ValueError("Type your name, as your team should see it.")
    org_name = orgs._name(org_name)
    host = clean_host(host)
    if orgs.org_of_site(db, host) is not None or host in set(taken):
        raise ValueError(SITE_TAKEN)
    site_verify.refuse_reserved(db, host)
    if users.find_user(db, email=email) is not None:
        raise ValueError("This address already has an account. Sign in instead.")
    problem = passwords.password_problem(password, email)
    if problem:
        raise ValueError(problem)
    pw_hash = passwords.hash_password(password)
    with base.tx(db):
        used = db.execute("UPDATE signups SET used_at = ? WHERE token_hash = ? "
                          "AND used_at IS NULL AND expires_at > ?",
                          (base.now(), found["token_hash"], base.now()))
        if not used.rowcount:
            raise ValueError(NOT_VALID)
        if orgs.org_of_site(db, host) is not None:
            raise ValueError(SITE_TAKEN)
        user = users.create_user(db, email, name, actor="signup")
        db.execute("UPDATE users SET pw_hash = ? WHERE id = ?", (pw_hash, user["id"]))
        org = orgs.create_org(db, org_name, user["id"])
        users.add_member(db, org["id"], user["id"], "owner", user["id"])
        plans.start_trial(db, org["id"], config, user["id"])
        ok, why = plan_limits.can_add_site(db, org["id"], config)
        if not ok:
            raise ValueError(why)
        log_dir = ingest_log.site_folder(log_root, host) if log_root is not None else None
        site_configs.create(db, org["id"], host, user["id"], log_dir=log_dir, taken=taken)
        site_verify.start(db, host)
        cap = plan_limits.retention_cap(db, org["id"], config)
        if cap is not None:
            current = settings_store.explain(config, host, db)
            for key in settings_store.SHRINKING:
                most = settings_store.capped(key, cap)
                # The value before the cap: explain shows it capped already.
                value = current[key].get("set_value", current[key]["value"])
                if isinstance(value, int) and most is not None and value > most:
                    settings_store.put(db, f"org:{org['id']}", key, most, user["id"])
        auditlog.record(db, org["id"], user["id"], "signup.finish", email, host)
    if log_dir is not None:
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass                        # the ingest makes it with the first batch
    return {"user": users.find_user(db, user_id=user["id"]), "org": orgs.get_org(db, org["id"]),
            "site": host}
