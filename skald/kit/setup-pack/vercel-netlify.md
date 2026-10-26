# Vercel or Netlify: a log drain for __SITE__

Vercel (Pro or Enterprise) and Netlify (Enterprise) post their request logs to an address you
give them. Nothing to install.

## Vercel

1. Team Settings > Drains > Add Drain > Logs.
2. Projects: this site's project. Sources: static, edge and lambda. Environments:
   production. Sampling: 100%.
3. Destination, a custom endpoint:

       __INGEST_URL__?format=vercel

4. Format: JSON or NDJSON. Custom header:

       Authorization: Bearer __TOKEN__

5. Keep Team Settings > Security & Privacy > IP Address Visibility on: without the
   visitor's address Skald refuses the record.

## Netlify

1. The site's log drain settings, service General HTTP endpoint, log type traffic logs.
2. Endpoint:

       __INGEST_URL__?format=netlify

3. Authorization header:

       Bearer __TOKEN__

4. Format JSON or NDJSON. Leave "Exclude personally identifiable information" off.

## Then

Open a page of the site. Within a few minutes it shows on __DASHBOARD__ (Settings >
Collect data > Send logs says what arrived).

The token works like a password: it goes only in the drain's header setting, never in the
site's code or in git.
