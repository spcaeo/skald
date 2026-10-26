# Data contract: Compare, any two date ranges (helper API)

Moved out of [DATA-CONTRACT.md](../DATA-CONTRACT.md) on 2026-10-26 to keep that file under
1000 lines; the rest of the data files are there.


`GET <page>/api/compare?a=YYYY-MM-DD..YYYY-MM-DD&b=YYYY-MM-DD..YYYY-MM-DD`
(same password; also `skald compare --a .. --b ..`). Optional filters, each
`name=value`: `page` (a path), or any of `country`, `continent`, `source`,
`assistant`, `device`, `browser`, `os`, `campaign`, `landing`. Ranges may be up
to 400 days long and go back as far as history keeps (`report.retention_days`,
400). Answer in well under a second at 365 days.

```json
{"ok":true,"site":"example.com","view":null,
 "a":{"from":"2026-10-01","to":"2026-10-31","days":31,"used":29,
      "excluded":[{"day":"2026-10-06","state":"partial"},{"day":"2026-10-12","state":"missing"}],
      "unmeasured":[]},
 "b":{"from":"2026-09-01","to":"2026-09-30","days":30,"used":30,"excluded":[],"unmeasured":[]},
 "presets":{"previous":{"from":"2026-08-31","to":"2026-09-30"},"last_year":{"from":"2025-10-01","to":"2025-10-31"}},
 "filters":{"country":"CA"},"filtered":true,
 "metrics":[{"key":"visitors","label":"Visitors","a":412,"b":300,"delta":112,"delta_pct":37.3}],
 "series":{"a":[{"day":"2026-10-01","state":"ok","visitors":14,"pages_read":20,"visitors_from_ai":0,
   "ai_asked":2,"ai_training":180,"search":160,"leads":0}],"b":[]},
 "dimensions":{"pages":[{"name":"/pricing/","a":40,"b":25,"delta":15,"delta_pct":60.0,"new":false,"gone":false}],
               "sources":[],"assistants":[],"countries":[],"continents":[],"devices":[],
               "browsers":[],"os":[],"campaigns":[]},
 "dimension_counts":{"pages":"page views","sources":"visitors"},
 "reconciled":true,"problems":[]}
```

- Only whole, verified days (`ok`) count; every other day in a range is in
  `excluded` with its state (`partial`, `withheld`, `missing`, `before`).
  `used` is the number of days counted. `unmeasured`: used days collected
  before the drill-down data existed (their dimension rows are missing; the
  metrics still count).
- `metrics[].key`: `visitors` (readers), `pages_read`, `visitors_from_ai`
  (readers who came from an assistant), `ai_asked`, `ai_training` (assistant
  fetches), `search` (search-engine fetches), `leads` (sign-up, contact,
  early access, demo booked; from the CMS), `returning`, `pages_per_visitor`
  (float), `not_found_people` (404s people met). A metric the filters cannot
  apply to is `null` on both sides (the CMS and crawler figures are not
  filtered by country, say), never a whole-site number under a filter.
- `delta = a - b` and `delta_pct = (a - b) / b * 100` (null when b is 0):
  **A is the range being looked at, B what it is compared with.** `new`: in A, not in B; `gone`: in B, not in A.
- Dimensions count visitors (readers, once each, by the first page they
  read), except `pages`, which counts page views. Rows are every value seen,
  biggest first (no top-N cut; at most 1,000 rows, then `"(all others)"`).
  `continents` are derived from the country (Africa, Antarctica, Asia,
  Europe, North America, Oceania, South America, Unknown). There are no
  sub-national regions: the address database is country-level.
- With `page=/path`: visitors = readers of that page, pages_read = its views,
  ai_asked / ai_training / search = fetches of that page; `sources`,
  `assistants`, `countries` and `continents` are that page's readers'; the
  other dimensions and metrics are null.
- `series.a` / `series.b`: one entry per calendar day of each range, with its
  state and the figures `visitors`, `pages_read`, `visitors_from_ai`,
  `ai_asked`, `ai_training`, `search`, `leads` - null on a day not counted,
  and null for a figure the filters cannot split. The days add up to the
  metrics (checked: `reconciled`).
- `reconciled`: the dimension rows add up to the visitors metric over the
  measured days (and the page rows to the page views); `problems` says
  where not.

The data under it, both kept `report.retention_days` (400) days:
`day_extras` kind `visit_cube` (every reader's visit as
[country, landing, source, assistant, device, browser, os, campaign] → n, all
pages, no cap; verified against the readers breakdowns and recounted by the
audit), kind `pages` (every page: views, readers, AI and search fetches,
sources, assistants, countries; read for a `page=` filter) and kind
`page_counts` (the same pages, compact: `{path: [views, readers, ai_asked,
ai_training, search]}`; read for the page views of an unfiltered compare).
