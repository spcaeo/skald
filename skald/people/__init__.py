"""People (2.4.0, "nothing hidden"): each visit kept with its address, and
one place to look a person up.

    policy.py   what a site keeps: `privacy.keep_ips` (full, short, off), `privacy.keep_days`,
                `conversions.identity` - and the upgrade rule that keeps an
                older install as it was until someone turns them on
    visits.py   each reader's visit with its address and user agent, in
                conversions.sqlite (`visits`, `visit_days`), written by the
                daily run and every live run; pruned; forgotten
    lookup.py   a person by address, email, lead or visitor ID: every visit,
                lead and conversion found, linked; the leads and conversions
                left out of the figures (spam, duplicates, test, cancelled,
                removed), listed
    api.py      the helper's routes for the page, and the token route
    notice.py   wording for the site's privacy notice, made from what the
                policy functions say it keeps (Settings > Privacy & retention)

Every visit kept is checked: audit_people.py recounts the day's readers per
address from the raw log by its own road, and a day that disagrees is
withheld like any other.
"""
