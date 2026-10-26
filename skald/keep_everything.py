"""Keep everything: a site on which Skald deletes and clears nothing by itself.

The owner's rule (2026-10-26): "all our projects that we have on live are
internal and enterprise, nothing gets deleted on that, it's a rule".

A site keeps everything when

    the install says so   `retention.keep_everything: true` in config.yml
                          (Docker: SKALD_KEEP_EVERYTHING=1): every site of it
    hosted (saas on)      the site's organisation has no plan (the install's
                          own: internal), or its plan says `keep_everything:
                          true` in saas.plans (Enterprise). A site no
                          organisation holds is the install's own.

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
    on the first question, and only on a hosted install."""

    def __init__(self, config: dict, live_dir=None):
        self.config = config or {}
        self.live_dir = live_dir
        self.all = install_on(self.config)
        self._hosted = None
        self._why: dict = {}

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
        if self.all:
            return "install"
        if not self.hosted() or not isinstance(site, str):
            return None
        if not self._why:
            self._load()
        return self._why.get(site.split("::", 1)[0], "no plan")

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
        """Whether any of `sites` (or, hosted, any site an organisation
        holds) keeps everything: for what one file holds for every site."""
        if self.all:
            return True
        if not self.hosted():
            return False
        if not self._why:
            self._load()
        return any(self(s) for s in sites) or any(
            v is not None for k, v in self._why.items() if k)


def of(ctx) -> Keeper:
    """The keeper of a run's context (its config and live folder)."""
    return Keeper(ctx.config, getattr(ctx, "live_dir", None))


def describe(config: dict, site: str, live_dir=None) -> dict:
    """{"on", "why", "words"} for the settings page, the notice and the doctor."""
    why = Keeper(config, live_dir).why(site)
    return {"on": why is not None, "why": why, "words": WORDS if why else None}
