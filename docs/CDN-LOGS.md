# Reading a CDN's logs

A site behind a CDN is mostly served by the CDN. When a page is in the CDN's
cache, the request never reaches your server, so your server's access log
never sees it. The CDN's own log sees every request. Skald reads three:

| `logs.format` | CDN | What it reads |
| --- | --- | --- |
| `cloudflare_json` | Cloudflare | Logpush, dataset `http_requests`, one JSON object a line |
| `cloudfront_w3c` | AWS CloudFront | Standard logs (legacy): W3C, tab-separated |
| `fastly_json` | Fastly | The JSON log format below, written in the logging endpoint |
| `edge_json` | Cloudflare, any plan | Edge records the Skald Worker posts ([below](#cloudflare-on-any-plan-the-skald-worker)) |

`format: auto` picks each one from the first lines. It also reads a file
that mixes them with nginx lines, for the day you move a site behind a CDN.

## What changes when you read a CDN log

- **Read the CDN log, not the origin's.** The CDN log counts every request,
  cache hits included. The origin's log counts only the misses the CDN passed
  on. On a site behind a CDN, the origin's figures are too low.
- **Never read both.** A cache miss is in both logs. Read both and that
  request is counted twice. Point `logs.dir` at the CDN log only. The one
  exception is the Skald Worker below: Skald keeps only its cache hits, so
  it adds to the origin's log without counting anything twice.
- **The address is whoever connected to the CDN.** For CloudFront that is a
  proxy's address when the visitor came through one; Skald does not read
  `x-forwarded-for`.
- **Logs arrive late.** Logpush pushes batches as they fill, often more than
  once a minute. CloudFront usually delivers within an hour, but says some
  entries can be up to 24 hours late. Fastly writes a file each period (an
  hour by default). Run the daily report late enough for yesterday's files
  to be in.
- **Lines are not always in time order.** CloudFront says so outright. Skald
  places each request by its own timestamp, so the day's totals are right.
  Fetch files in name order (they carry the date and hour) to keep visits
  whole.
- **The independent audit (`skald audit`) does not read CDN logs.** It reads
  the nginx and Apache layouts only, as with Caddy, the Vercel and Netlify
  log drain lines (HOSTING.md), and the Skald Worker's edge records.

## Getting the files to the server

Skald reads one log and its rotations: `<base>`, `<base>.1`, `<base>.N.gz`.
A CDN delivers many small gzip files to a bucket instead. So: copy the
bucket to the server, append each new file to one log, and let logrotate
rotate it.

```sh
#!/bin/sh
# /usr/local/bin/cdn-logs - run from cron every 15 minutes.
set -eu
RAW=/var/lib/cdn-logs/raw            # a copy of the bucket
OUT=/var/log/cdn/access.log          # the log Skald reads
DONE=/var/lib/cdn-logs/done.txt      # files already appended
mkdir -p "$RAW" "$(dirname "$OUT")"
touch "$DONE"
aws s3 sync s3://my-log-bucket/my-prefix/ "$RAW" --only-show-errors
find "$RAW" -type f -name '*.gz' | sort | while read -r f; do
  grep -qxF "$f" "$DONE" && continue
  zcat "$f" >> "$OUT"
  echo "$f" >> "$DONE"
done
```

```text
# /etc/logrotate.d/cdn
/var/log/cdn/access.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
}
```

```yaml
# config.yml
logs:
  dir: /var/log/cdn
  base: access.log
  format: auto
```

`delaycompress` keeps `access.log.1` plain, as nginx's rotation does. For
Cloudflare R2, add `--endpoint-url https://<account id>.r2.cloudflarestorage.com`
to `aws s3 sync`; R2 speaks the S3 API. For Fastly over SFTP there is no
bucket: point the endpoint's path at `$RAW` and drop the `aws s3 sync` line.

Two safety nets are built in. CloudFront starts every file with
`#Version:` and `#Fields:` lines. Skald skips those lines and does not count
them as unreadable, so a day made of many small files is not withheld. And
a CloudFront line carries a request id (`x-edge-request-id`) that is unique
per request, so a file appended twice is counted once.

## Cloudflare: Logpush

Create a Logpush job for the zone with the dataset
**HTTP requests** (`http_requests`). Send it to R2 or to S3, then sync as
above. Output type: the default, one JSON object per line (`ndjson`).

Turn on these fields. Logpush has no "all fields" option; you list them.

| Logpush field | Skald reads it as |
| --- | --- |
| `EdgeStartTimestamp` | the time (required) |
| `ClientRequestURI` | the URL, path and query (required) |
| `ClientIP` | the address |
| `ClientRequestHost` | the host, for `site.hosts` |
| `ClientRequestMethod` | the method |
| `EdgeResponseStatus` | the status |
| `EdgeResponseBytes` | the size |
| `ClientRequestReferer` | the referrer - needed to see who came from an answer engine |
| `ClientRequestUserAgent` | the user agent - needed to tell people from crawlers |
| `ClientCountry` | the country (written lower-case, `us`; Skald upper-cases it) |
| `EdgeTimeToFirstByteMs` | the request time, in milliseconds |
| `OriginResponseDurationMs` | the request time, when the one above is absent |

Any timestamp format works: `rfc3339` (the dashboard's default),
`rfc3339ms`, `rfc3339ns`, `unix` and `unixnano` (the API's default).
`CacheCacheStatus` is worth adding for your own checks; Skald ignores it. A
line without `ClientRequestURI` or `EdgeStartTimestamp` is counted as
unreadable. `xx` (unknown) means no country.

## Cloudflare on any plan: the Skald Worker

Logpush's **HTTP requests** dataset is not on every Cloudflare plan
("Dataset availability depends on the Cloudflare products on your account",
<https://developers.cloudflare.com/logs/logpush/>). Without it, a page Cloudflare serves from its
cache reaches no log Skald reads. The Skald Worker closes that gap, on any
plan: a Cloudflare Worker that passes every request
on unchanged and, after the response has gone out (`ctx.waitUntil`), posts
one edge record of it to Skald. Code and setup:
`deploy/cloudflare-worker/` (`skald-edge.js`, `wrangler.toml` for the
Deploy to Cloudflare button, `wrangler.toml.example`, `README.md`).

[![Deploy to Cloudflare](https://deploy.workers.cloudflare.com/button)](https://deploy.workers.cloudflare.com/?url=https://github.com/spcaeo/skald/tree/main/deploy/cloudflare-worker)

**With the button.** Do step 1 below first. The button copies
`deploy/cloudflare-worker/` into a new repository in your GitHub or GitLab
account and deploys it. It asks for `SKALD_INGEST_URL` and `SKALD_TOKEN` as
secrets (`.dev.vars.example`), with no default. The Worker is deployed with
no route and no `workers.dev` address: add your site's route afterwards, or it
sees no request.

**Setup by hand, in short.**

1. In Skald: turn on ingest, make the site, make an ingest token for it
   (INGEST.md). Format `edge_json` when these records are the site's only
   log; `auto` when Skald reads the server's log too.
2. Copy `wrangler.toml.example` over `wrangler.toml`; set the routes
   (`example.com/*`) and `SKALD_INGEST_URL`
   (`https://stats.example.com/traffic-ingest/example.com`).
3. `npx wrangler secret put SKALD_TOKEN` (the ingest token), then
   `npx wrangler deploy`.

**The record.** One JSON object per request, posted to
`POST /traffic-ingest/<site>?format=edge` with `Authorization: Bearer
<ingest token>`. A JSON array or NDJSON of many works too, gzip or plain, so
another edge platform can send the same format.

| Field | Holds | Required |
| --- | --- | --- |
| `ts` | when the request came in: RFC 3339 (`2026-10-06T10:00:00.000Z`) or a JSON number of Unix milliseconds | yes |
| `ip` | the visitor's address (`CF-Connecting-IP`) | yes |
| `method` | `GET`, `POST`, ... | |
| `host` | the host asked for | |
| `path` | path and query, starting with `/` | yes |
| `status` | the status code sent | yes |
| `bytes` | `Content-Length` of the response, or `null` | |
| `referer` | the `Referer` header | |
| `ua` | the `User-Agent` header | |
| `cache` | `cf-cache-status` (`HIT`, `MISS`, ...) | for the rule below |
| `id` | the request's own id (`CF-Ray`): a record posted twice is read once | |

Skald writes only these fields; anything else a sender adds is dropped. A
record without `ip`, `path`, `status` or a readable `ts` is refused and
counted as rejected.

**The double-count rule.** A request Cloudflare passed on to the origin
(any cache status but `HIT`) is in the origin's log too. With
`logs.edge_only_cached: true`, Skald keeps only the edge records whose
`cache` is `HIT` and skips the others (the answer's `"skipped"` counts
them). Unset, it is true unless the site's format is `edge_json`, where the
edge is the only log and every record is kept. `STALE` and `UPDATING` are
skipped too: the origin may have logged a request for them. Set it in the
site's config to override:

```yaml
logs:
  format: auto
  edge_only_cached: true    # the server's log is read as well
```

For the two to be read together, both must land in the site's folder: ship
the server's log with `skald-ship` to the same `/traffic-ingest/<site>`, or,
on the server Skald runs on, point `logs.dir` at the site's ingest folder
(`<ingest root>/<site>`) and ship the local log there too. The Worker's
`SKALD_CACHE_HITS_ONLY = "true"` skips non-hits at the edge, which saves the
posts Skald would drop anyway.

**What it costs.** Every request through the Worker is a Worker request on
your Cloudflare plan's allowance or bill; the post to Skald is a subrequest,
which Cloudflare does not bill
(<https://developers.cloudflare.com/workers/platform/pricing/>). On Skald's
side each record is one post, with its own rate limit per site,
`ingest.edge_per_minute` (1200) and `ingest.edge_burst` (300). A post over
it is refused and the Worker drops it, so that request is not counted: set
the limit above the site's busiest minute.

**Privacy.** A record holds what an access log line holds (time, address,
method, host, path and query, status, bytes, referrer, user agent), plus the
cache status and Cloudflare's request id. No cookies, no other headers, no
body.

**Order.** Edge records arrive as requests happen; shipped server lines in
batches a little later. Skald places each request by its own time, as for
any CDN log.

## AWS CloudFront: standard logs

Turn on **Standard logging** for the distribution and choose **Amazon S3
(Legacy)** as the destination. The bucket must have ACLs enabled. Give it a
log prefix. CloudFront writes gzip files named
`<prefix>/<distribution id>.YYYY-MM-DD-HH.<unique id>.gz`. Sync them with
`aws s3 sync` as above.

Skald reads the standard 33 fields in their documented order, and follows a
`#Fields:` line if a file lists them in another order. It reads:

- `date` and `time` (UTC) for the time
- `c-ip` for the address
- `x-host-header` for the host. `cs(Host)` is the distribution's
  `dxxxxx.cloudfront.net` name, so it is used only when the Host header is
  missing.
- `cs-method`, `sc-status`, `sc-bytes` (bytes sent, headers included)
- `cs-uri-stem`, plus `?` and `cs-uri-query` when there is one, for the URL
- `cs(Referer)` and `cs(User-Agent)`, URL-decoded once. CloudFront encodes
  spaces and other characters, and some twice; one decode gives what the
  browser sent.
- `time-taken` for the request time, in seconds
- `x-edge-request-id` to drop a line seen twice

`-` means empty. CloudFront's standard logs carry no country, so the country
cards are left out, as with any log that has none.

## Fastly: a JSON logging endpoint

Fastly has no fixed log format. You write it in the logging endpoint. Create
an **Amazon S3** endpoint (then sync as above) or an **SFTP** endpoint that
writes straight to the server. Leave the endpoint's log line format at
**Blank**, so each line is the JSON object alone. Paste this into the
endpoint's **Log format** field, as one line:

```text
{"timestamp":"%{strftime(\{"%Y-%m-%dT%H:%M:%S%z"\}, time.start)}V","client_ip":"%{req.http.Fastly-Client-IP}V","geo_country":"%{client.geo.country_code}V","host":"%{if(req.http.Fastly-Orig-Host, req.http.Fastly-Orig-Host, req.http.Host)}V","url":"%{json.escape(req.url)}V","request_method":"%{json.escape(req.method)}V","request_referer":"%{json.escape(req.http.referer)}V","request_user_agent":"%{json.escape(req.http.User-Agent)}V","response_state":"%{json.escape(fastly_info.state)}V","response_status":%{resp.status}V,"response_body_size":%{resp.body_bytes_written}V,"time_elapsed":%{time.elapsed.usec}V}
```

This is Fastly's own example JSON format with two changes. `geo_country`
logs `client.geo.country_code` (a two-letter code) instead of
`client.geo.country_name`: Skald keeps only a code and never guesses one
from a name. And `time_elapsed` is added, in microseconds.

If you log from custom VCL instead, emit the same JSON object, one per
line, from a `log` statement (Fastly's VCL `log` reference is listed
below).

Skald also accepts the common alternatives, so a format you already have
may work as it is:

| Field | Also accepted |
| --- | --- |
| `timestamp` (ISO 8601, `%z` offset, Unix seconds, ms, µs or ns, or `[%t]`) | `time` |
| `url` | `request_url`, or `path` plus `query` |
| `request_method` | `method` |
| `response_status` | `status`, `resp_status` |
| `request_referer` | `referer` |
| `request_user_agent` | `user_agent` |
| `response_body_size` | `response_bytes`, `bytes` |
| `geo_country` (two-letter code) | `country_code` |
| `time_elapsed` (microseconds) | `elapsed_ms`, `time_elapsed_ms` (milliseconds) |

`timestamp` and a URL are required. Skald tells a Fastly line from a Caddy
one (a `request` object) and a Cloudflare one (`ClientRequestURI`) by its
keys.

## Sources

Checked on 2026-10-08 (the Worker's sources on 2026-10-12).

- Cloudflare Workers, `ctx.waitUntil` and `ctx.passThroughOnException`:
  <https://developers.cloudflare.com/workers/runtime-apis/context/>
- Cloudflare, `cf-cache-status` values:
  <https://developers.cloudflare.com/cache/concepts/cache-responses/>
- Cloudflare, Deploy to Cloudflare buttons:
  <https://developers.cloudflare.com/workers/platform/deploy-buttons/>
- Cloudflare Workers pricing:
  <https://developers.cloudflare.com/workers/platform/pricing/>

- Cloudflare, Logpush `http_requests` fields:
  <https://developers.cloudflare.com/logs/logpush/logpush-job/datasets/zone/http_requests/>
- Cloudflare, Logpush output options (timestamp formats, ndjson, field list):
  <https://developers.cloudflare.com/logs/logpush/logpush-job/log-output-options/>
- Cloudflare, Logpush to R2:
  <https://developers.cloudflare.com/logs/logpush/logpush-job/enable-destinations/r2/>
- Cloudflare, Logpush to Amazon S3:
  <https://developers.cloudflare.com/logs/logpush/logpush-job/enable-destinations/aws-s3/>
- AWS, CloudFront standard log fields:
  <https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/standard-logs-reference.html>
- AWS, CloudFront standard logging (legacy) to S3, file names and encoding:
  <https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/standard-logging-legacy-s3.html>
- Fastly, Amazon S3 endpoint and its example JSON format:
  <https://www.fastly.com/documentation/guides/integrations/logging-endpoints/log-streaming-amazon-s3/>
- Fastly, SFTP endpoint:
  <https://www.fastly.com/documentation/guides/integrations/logging-endpoints/log-streaming-sftp/>
- Fastly, custom log formats (`%D` and `time.elapsed.usec` are microseconds):
  <https://www.fastly.com/documentation/guides/integrations/streaming-logs/custom-log-formats/>
- Fastly, useful variables to log (`client.geo.country_code`):
  <https://www.fastly.com/documentation/guides/integrations/streaming-logs/useful-variables-to-log/>
- Fastly, the VCL `log` statement:
  <https://www.fastly.com/documentation/reference/vcl/statements/log/>
