"""Keep everything: a site on which Skald deletes and clears nothing by itself.

The owner's rule (2026-10-26): "all our projects that we have on live are
internal and enterprise, nothing gets deleted on that, it's a rule".

A site keeps everything when

    the install says so   `retention.keep_everything: true` in config.yml
                          (Docker: SKALD_KEEP_EVERYTHING=1): every site of it,
                          except the sites of an organisation an install admin
                          made a client (below)
    hosted (saas on)      the site's organisation has no plan (the install's
                          own: internal), or its plan says `keep_everything:
                          true` in saas.plans (Enterprise). A site no
                          organisation holds is the install's own.

The organisation rule (accounts schema 6, accounts/orgs.py `privacy_class`):
each organisation is "internal" (the default: the rules above, unchanged) or
"client" (set by an install admin): a client's sites follow their own
retention settings even on an install that keeps everything; only a plan that
keeps everything (hosted) still keeps them. Every Keeper decision asks it; a
doubt (no accounts file, one that cannot be read) is internal.

On such a site no automatic deletion or clearing runs, whatever a retention
setting or a plan's cap says. Every path that deletes or clears by itself
asks `Keeper(config, live_dir)(site)` (or `of(ctx)`) first (the list:
docs/SETTINGS.md, "Keep everything"):

    history       journeys, returning-visitor hashes, the per-day detail and
                  the AI fetches (prune.prune_kept, store_visits.prune_sites)
    people        visits with addresses past privacy.keep_days, every visit
                  when keep_ips turns off, the shortening when it turns short,
                  and the scanner rows kept the same days (people/visits.py,
                  security_kept.py)
    conversions   leads, removed rows, journeys, identities, deliveries, replay
                  hashes and payment links (conversions/store.prune); the hook
                  spool (conversions/spool.prune); names and emails past the
                  People days (conversions/people_days.py); the outgoing
                  webhooks' outbox (conversions/outgoing.prune)
    your tools    names and emails in the tools' stored answers past the People
                  days (yourtools/people_days.py); the figures stay
    in-page       event counts past beacon.keep_days (events.collect) and the
                  beacon spool files (beacon.prune)
    AI answers    runs past their profile's days (answers/run.py)
    alerts        closed alerts after 30 days (alerts.py)
    backups       the conversions file's daily and weekly copies (backup.make)
    raw logs      shipped days past ingest.keep move to <site>/archive/ (ingest_log)

Kept as before (not stored data about a person or a figure): the history's
own backups, the live files,
caches, sessions and sign-in records, and an upgrade's temporary files.

A person's own deletion (`skald forget`, `skald conversions forget`), run by
an admin by hand, still deletes: it is not automatic.
"""
from __future__ import annotations

from .config import setting

WORDS = "Kept: nothing is deleted (internal or enterprise)."
TRUE = ("1", "true", "yes", "on")


def install_on(config: dict) -> bool:
    """`retention.keep_everything` (config.yml or SKALD_KEEP_EVERYTHING)."""
    raw = setting(config or {}, "retention", "keep_everything", False)
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in TRUE


class Keeper:
    """site -> True when it keeps everything. Reads the accounts file once,
    on the first question: the organisation rule when there is a file, and
    the plans only on a hosted install.

    The organisation rule (accounts/orgs.py, privacy_class): a site whose
    organisation is "client" follows its own retention settings even when
    the install keeps everything; only its plan (hosted, keep_everything:
    true) still keeps it. "internal" (the default, and any site no
    organisation holds) follows the install's rule as before."""

    def __init__(self, config: dict, live_dir=None):
        self.config = config or {}
        self.live_dir = live_dir
        self.install = install_on(self.config)
        self._hosted = None
        self._why: dict = {}
        self._org: dict | None = None     # site -> (its organisation's name, privacy class)

    @property
    def all(self) -> bool:
        """Every site keeps everything: the install says so and no organisation
        is a client. The prunes that skip all their work on it (store_visits,
        the spool, the People-days sweep) then open nothing, as before."""
        if not self.install:
            return False
        if self._org is None:
            self._org = self._orgs()
        return not any(cls == "client" for _, cls in self._org.values())

    def hosted(self) -> bool:
        if self._hosted is None:
            from . import saas
            self._hosted = bool(saas.enabled(self.config))
        return self._hosted

    def __call__(self, site) -> bool:
        return self.why(site) is not None

    def why(self, site) -> str | None:
        """"install", "no plan" or "plan <name>"; None: the site's data
        follows its retention settings."""
        name = site.split("::", 1)[0] if isinstance(site, str) else None
        if name is not None and self.privacy(name) == "client":
            if not self.hosted():
                return None
            kept = self._plan_why(name)
            return kept if kept and kept.startswith("plan ") else None
        if self.install:
            return "install"
        if not self.hosted() or name is None:
            return None
        return self._plan_why(name)

    def _plan_why(self, name: str) -> str | None:
        if not self._why:
            self._load()
        return self._why.get(name, "no plan")

    def privacy(self, site: str) -> str:
        """The organisation rule for `site`: "client" or "internal"."""
        return self.org_of(site)[1]

    def org_of(self, site: str) -> tuple[str | None, str]:
        """(the site's organisation's name or None, its privacy class)."""
        if self._org is None:
            self._org = self._orgs()
        return self._org.get(str(site).split("::", 1)[0], (None, "internal"))

    def _orgs(self) -> dict:
        """{site: (organisation, class)} from the accounts file; {} without one,
        or when it cannot be read (a doubt keeps everything)."""
        import sqlite3
        from .settings_store import accounts_file
        path = accounts_file(self.config, self.live_dir)
        if path is None:
            return {}
        from .accounts import connect
        try:
            db = connect(path)
        except (sqlite3.Error, OSError, RuntimeError):
            return {}
        try:
            return {name: (org, cls if cls in ("internal", "client") else "internal")
                    for name, org, cls in db.execute(
                        "SELECT s.name, o.name, o.privacy_class FROM sites s "
                        "JOIN orgs o ON o.id = s.org_id")}
        except sqlite3.Error:
            return {}
        finally:
            db.close()

    def rule(self, site: str) -> dict:
        """{"class", "org", "words"}: which rule decides `site`, in plain words,
        for the Privacy page and the doctor."""
        org, cls = self.org_of(site)
        who = f"{org} is" if org else "This site's organisation is"
        if cls == "client":
            words = (f"{who} a client organisation: this site follows its own retention "
                     "settings" + (", even though the install keeps everything." if self.install
                                   else "."))
        elif self.install:
            words = (f"{who} an internal organisation: the install keeps everything "
                     "(retention.keep_everything), so nothing is deleted by itself.")
        else:
            words = (f"{who} an internal organisation: the install does not keep "
                     "everything, so the retention settings apply.")
        return {"class": cls, "org": org, "words": words}

    def _load(self) -> None:
        """Each site an organisation holds: None (its plan clears) or why it
        keeps; a site not in the file is the install's own ("no plan")."""
        self._why = {"": None}            # loaded, even when there is no file
        from .settings_store import accounts_file
        path = accounts_file(self.config, self.live_dir)
        if path is None:
            return
        from .accounts import connect
        from .saas import plans as plan_table
        try:
            table = plan_table.plans(self.config)
        except ValueError:
            table = {}
        default = table.get(plan_table.default_plan(self.config) or "") or {}
        db = connect(path)
        try:
            for name, org in db.execute("SELECT name, org_id FROM sites").fetchall():
                state = plan_table.org_state(db, org) if org is not None else None
                plan = (state or {}).get("plan")
                if not plan:
                    self._why[name] = "no plan"
                    continue
                entry = table.get(plan) or default
                self._why[name] = f"plan {plan}" if entry.get("keep_everything") else None
        finally:
            db.close()

    def any(self, sites=()) -> bool:
        """Whether any of `sites` (or any site an organisation holds) keeps
        everything: for what one file holds for every site. With the install
        keeping everything, only when every one of them is a client's is the
        answer no."""
        if self.install:
            if self._org is None:
                self._org = self._orgs()
            names = set(sites) | set(self._org)
            return not names or any(self(s) for s in names)
        if not self.hosted():
            return False
        if not self._why:
            self._load()
        return any(self(s) for s in sites) or any(
            self(k) for k, v in self._why.items() if k and v is not None)


def of(ctx) -> Keeper:
    """The keeper of a run's context (its config and live folder)."""
    return Keeper(ctx.config, getattr(ctx, "live_dir", None))


def describe(config: dict, site: str, live_dir=None) -> dict:
    """{"on", "why", "words", "rule"} for the settings page, the notice and the
    doctor; rule: which organisation rule decides it (Keeper.rule)."""
    keeper = Keeper(config, live_dir)
    why = keeper.why(site)
    return {"on": why is not None, "why": why, "words": WORDS if why else None,
            "rule": keeper.rule(site)}
