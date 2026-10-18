# Client reports: the settings and send-log tables (2.13)

Part of [DATA-CONTRACT.md](../DATA-CONTRACT.md) (kept apart to hold that file
under 1000 lines); the rules there apply.

## Client reports (2.13)

Settings > Reports keeps two tables in `accounts.sqlite` (made on first use, like
`mail_confirms`; never in the history file). They hold settings and a send log, not
figures: every figure a report shows is read at send time from verified history and
checked twice (`client_report_data.py`, `audit_client_reports.py`).

| table | column | meaning |
|---|---|---|
| `client_reports` | `id`, `org_id`, `site` | the report, its organisation and site; every query names both |
| | `spec` | JSON: `name`, `recipients` (addresses as typed), `schedule` `{kind, weekday \| day \| every + start, at}`, `period`, `sections`, `notes`, `footer`, `agency_logo`, `paused` |
| | `created_by`, `created_at`, `updated_at` | who made it (an email or `cli`), UTC stamps |
| `client_report_sends` | `report_id`, `org_id`, `site`, `at` | one row per try, UTC |
| | `occurrence` | the scheduled local day it was for; NULL for a hand send |
| | `first`, `last` | the period's local days; NULL when it was refused before a period was read |
| | `by` | `schedule`, the person's email, or `skald reports` |
| | `recipients` | JSON list of the confirmed addresses it went to (`[]` when refused) |
| | `ok`, `detail` | 1 sent, 0 not; the words (the refusal or the mail server's error class) |

A deleted report takes its sends with it. The agency logo is a file, not a row
(`<history folder>/logos/org-<id>/agency.png|jpg`).
