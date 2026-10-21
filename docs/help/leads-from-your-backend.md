# Send leads from your backend in 5 minutes

Your site's server tells Skald each time a lead is made, in one signed message. This guide has the steps and copy-paste examples in curl, Node, Python and PHP, with retries, and what to do when the backend sits on the same server as Skald.

## 1. Make the secret

On the server:

```
sudo skald hooks secret example.com lead
```

Or in the dashboard: **Settings > Integrations > Your site's server (lead) > Make secret**. Docker: `docker exec skald skald hooks secret example.com lead` (in Docker, run every `skald` command in this guide the same way, without `sudo`).

It prints the secret once, and the address to post to. With `access.base_url` set, the address is the real one, such as `https://stats.example.com/traffic-hooks/example.com/lead`.

Keep the secret in an environment variable on your backend, such as `SKALD_HOOK_SECRET`. Never in the code, never in the browser.

## 2. The body

One JSON object per lead:

```
{
  "external_ref": "L-1001",
  "action": "demo",
  "stage": "completed",
  "at": "2026-09-25T14:30:00-04:00",
  "vid": "skv_Q2xhc3NpY0V4YW1wbGVJRA",
  "first_touch": {"referrer": "https://www.google.com/", "landing": "/", "at": "2026-09-20T09:12:00Z"},
  "last_touch": {"landing": "/pricing/", "utm_source": "newsletter", "utm_medium": "email"}
}
```

| Field | | |
| --- | --- | --- |
| `external_ref` | required | The lead's own id in your system. Keep it stable: the same lead always sends the same id |
| `action` | required | What was done, a short lowercase word: `demo`, `contact`, `signup`, `trial` |
| `stage` | default `completed` | `started`, `completed`, `cancelled`, `rescheduled`, `no_show`, `paid`, `won`, `lost` |
| `at` | default: when it arrived | When it happened. A full ISO time with its offset: `2026-09-25T14:30:00-04:00` or `2026-09-25T18:30:00Z` |
| `vid` | | The visitor ID the page had. Kept only when the site has visitor IDs on |
| `first_touch`, `last_touch` | | Where the visitor came from: `referrer`, `landing`, `utm_source`, `utm_medium`, `utm_campaign`, `at` |
| `ip`, `user_agent` | | Skald looks up the country and the device, then drops both |
| `name`, `email` | | Kept only when the site's **Leads' names and emails** is **full**; otherwise dropped |
| `label` | optional | A short word that sorts leads of one action, such as a contact form's topic: `sales`, `support`, `partnership`. Lowercase letters, digits, `-` and `_`, at most 40, starting with a letter or digit (`Sales` is read as `sales`). Anything else is dropped: the lead is still kept, without a label, and the answer and the delivery log say so |

Each stage keeps its own label: send it again with a later stage if that stage should carry it too. Pipeline (Count from: Tools) filters by label, and the lists of conversions show it as a small tag.

Always send the offset. A time without one ("2026-09-25" or "2026-09-25T14:30:00") is read in the site's own time zone, and the delivery log says so. That guess is right only when your server writes local times in the same zone.

## 3. Sign it and send it

The header:

```
X-Skald-Signature: t=<unix seconds>,v1=<hex HMAC-SHA256 of "<t>.<raw body>">
```

The key is the secret. Sign the exact bytes you send. Skald refuses a `t` more than 5 minutes from its own clock, so keep the server's clock right.

Each example below signs, posts, and tries again when the post fails.

curl:

```
URL='https://stats.example.com/traffic-hooks/example.com/lead'
BODY='{"external_ref":"L-1001","action":"demo","at":"2026-09-25T14:30:00-04:00"}'
for wait in 0 5 30 120; do
  sleep "$wait"
  T=$(date +%s)
  SIG=$(printf '%s.%s' "$T" "$BODY" | openssl dgst -sha256 -hmac "$SKALD_HOOK_SECRET" -hex | sed 's/^.* //')
  CODE=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$URL" \
    -H 'Content-Type: application/json' -H "X-Skald-Signature: t=$T,v1=$SIG" --data-raw "$BODY")
  case "$CODE" in 2*) break ;; 400|401|404|413) echo "refused: $CODE"; break ;; esac
done
```

Node (18 or later):

```
import crypto from "node:crypto";

const URL = "https://stats.example.com/traffic-hooks/example.com/lead";

export async function sendLead(lead) {
  const body = JSON.stringify(lead);
  for (const wait of [0, 5, 30, 120]) {
    await new Promise((r) => setTimeout(r, wait * 1000));
    const t = Math.floor(Date.now() / 1000);
    const sig = crypto.createHmac("sha256", process.env.SKALD_HOOK_SECRET).update(`${t}.${body}`).digest("hex");
    try {
      const res = await fetch(URL, { method: "POST", body,
        headers: { "Content-Type": "application/json", "X-Skald-Signature": `t=${t},v1=${sig}` } });
      if (res.ok) return true;
      if ([400, 401, 404, 413].includes(res.status)) return false;
    } catch { /* the network: try again */ }
  }
  return false;
}
```

Python (standard library only):

```
import hashlib, hmac, json, os, time, urllib.error, urllib.request

URL = "https://stats.example.com/traffic-hooks/example.com/lead"

def send_lead(lead: dict) -> bool:
    body = json.dumps(lead).encode()
    secret = os.environ["SKALD_HOOK_SECRET"].encode()
    for wait in (0, 5, 30, 120):
        time.sleep(wait)
        t = str(int(time.time()))
        sig = hmac.new(secret, t.encode() + b"." + body, hashlib.sha256).hexdigest()
        req = urllib.request.Request(URL, data=body, method="POST", headers={
            "Content-Type": "application/json", "X-Skald-Signature": f"t={t},v1={sig}"})
        try:
            with urllib.request.urlopen(req, timeout=10):
                return True
        except urllib.error.HTTPError as why:
            if why.code in (400, 401, 404, 413):
                return False
        except OSError:
            pass
    return False
```

PHP:

```
function skald_send_lead(array $lead): bool {
    $url = 'https://stats.example.com/traffic-hooks/example.com/lead';
    $body = json_encode($lead);
    foreach ([0, 5, 30, 120] as $wait) {
        sleep($wait);
        $t = time();
        $sig = hash_hmac('sha256', $t . '.' . $body, getenv('SKALD_HOOK_SECRET'));
        $ch = curl_init($url);
        curl_setopt_array($ch, [CURLOPT_POST => true, CURLOPT_POSTFIELDS => $body,
            CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 10,
            CURLOPT_HTTPHEADER => ['Content-Type: application/json', "X-Skald-Signature: t=$t,v1=$sig"]]);
        curl_exec($ch);
        $code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);
        if ($code >= 200 && $code < 300) return true;
        if (in_array($code, [400, 401, 404, 413])) return false;
    }
    return false;
}
```

In a web request, send the lead after the page has answered, or from a queue, so a slow answer never holds up your visitor.

## 4. Retries are safe

Try again on anything but a 2xx answer, and on a network error, with a growing wait. A repeat changes nothing: Skald keeps a conversion once per site, tool, `external_ref` and stage.

Do not retry a 400. The body is wrong: the answer says what, and so does the delivery log. Fix the body first.

## 5. One tool per lead

Send each lead through one road only. If the same lead also goes through Zapier (the `json` hook), or Skald also reads it from the lead database, it counts once per road. **Settings > Integrations > Status** flags such leads as "One lead, two tools".

## 6. Backfill old leads

Send each old lead with its original `at`, with the offset. Then it lands on the day it happened.

- Each hook takes at most 60 messages a minute by default (`hooks.per_minute`). Space them out, or retry on 429.
- Or send up to 100 at once through the `json` hook: `{"records": [ {...}, {...} ]}`. Make its secret first, the same way.
- An `at` more than a day in the future is refused.

## 7. Same server as Skald, behind Cloudflare

When your backend runs on the same server as Skald, and the public address goes through Cloudflare (or another CDN proxy), post to Skald's local address instead. Cloudflare can block a server that posts to its own public address: 403, error 1010, a bot check.

| Skald runs | Post to |
| --- | --- |
| In Docker | `http://127.0.0.1:8080/traffic-hooks/example.com/lead` (the port you published) |
| Installed with the install script | `http://127.0.0.1:8766/traffic-hooks/example.com/lead` (the hook receiver itself) |

Or allow the path `/traffic-hooks/` in Cloudflare's security rules for your server. The signature is the same either way.

## 8. Test it

```
sudo skald hooks test example.com lead
```

It posts a signed sample, marked as a test: read, never kept. It says what a real one would keep: the action, the stage, the source, and whether the visitor ID is kept. **Send a test event** on the Integrations page does the same.

Then send a real lead. The Integrations page shows "last received 2 min ago (kept)", and `sudo skald doctor` shows the hook as OK.

## 9. Check that Skald has every lead

Your server can ask Skald for the leads it holds from this hook, compare them with its own, and send again any that are missing. It is read only, and signed with the **same secret** as the lead hook.

```
GET /traffic-hooks/example.com/leads?since=2026-10-19T00:00:00Z&limit=500
X-Skald-Signature: t=<unix seconds>,v1=<hex HMAC-SHA256 of "<t>.GET <path>?<query>">
```

Sign the method, the path and the query exactly as you send them, such as `1792540800.GET /traffic-hooks/example.com/leads?since=2026-10-19T00%3A00%3A00Z&limit=500`. So nobody can change a parameter on the way. Without a query, sign `<t>.GET <path>` with no `?`. The same 5-minute clock rule as the POST.

| Parameter | | |
| --- | --- | --- |
| `since` | optional | Leads Skald **received** at or after this time. ISO with its offset (`Z` is simplest; a `+` must be sent as `%2B`) or Unix seconds |
| `at_since`, `at_until` | optional | Leads whose `at` (when they happened) is from `at_since`, and before `at_until` |
| `limit` | default 200 | Rows a page, 1 to 500 |
| `cursor` | | The `next_cursor` of the page before |

`since` is when Skald got the lead, not its `at`. A lead you backfill today about a day last month has an old `at`, and it is found by today's `since`. Use `at_since` and `at_until` to ask about the days the leads happened.

The answer:

```
{
  "ok": true,
  "site": "example.com",
  "since": "2026-10-19T00:00:00Z",
  "at_since": null,
  "at_until": null,
  "limit": 500,
  "rows": [
    {"external_ref": "L-1001", "action": "contact", "stage": "completed", "at": "2026-10-19T14:30:00Z",
     "label": "sales", "test": false, "received_at": "2026-10-19T14:30:02Z"}
  ],
  "next_cursor": null
}
```

- Only the leads that came through this site's `lead` hook. Never a name, an email, an address, a browser, a visitor ID or a source.
- Rows are in the order Skald received them. While `next_cursor` is not `null`, ask again with `cursor=<next_cursor>` (and the same other parameters) for the next page. New leads arriving meanwhile come after it: no page skips or repeats one.
- Leads marked test are in it, with `"test": true`: you can see that your tests landed. (A delivery sent with `X-Skald-Test: 1` is never kept, so it is not in it.)
- A lead older than the site's keeping time is not in it: Skald deletes conversions whose `at` is more than 400 days old (`conversions.retention_days`). Nor is a lead deleted on request (`skald conversions forget`).

curl (GNU `date`; on a Mac, `date -u -v-2d +%Y-%m-%dT%H:%M:%SZ`):

```
BASE='https://stats.example.com'
P='/traffic-hooks/example.com/leads'
Q="since=$(date -u -d '2 days ago' +%Y-%m-%dT%H:%M:%SZ)&limit=500"
T=$(date +%s)
SIG=$(printf '%s.GET %s?%s' "$T" "$P" "$Q" | openssl dgst -sha256 -hmac "$SKALD_HOOK_SECRET" -hex | sed 's/^.* //')
curl -s "$BASE$P?$Q" -H "X-Skald-Signature: t=$T,v1=$SIG"
```

Node (18 or later):

```
import crypto from "node:crypto";

const BASE = "https://stats.example.com";
const PATH = "/traffic-hooks/example.com/leads";

// Every lead Skald received since `since` (a Date), as "ref/stage" -> row.
export async function leadsInSkald(since) {
  const found = new Map();
  let cursor = null;
  do {
    const q = new URLSearchParams({ since: since.toISOString(), limit: "500", ...(cursor ? { cursor } : {}) }).toString();
    const t = Math.floor(Date.now() / 1000);
    const sig = crypto.createHmac("sha256", process.env.SKALD_HOOK_SECRET).update(`${t}.GET ${PATH}?${q}`).digest("hex");
    const res = await fetch(`${BASE}${PATH}?${q}`, { headers: { "X-Skald-Signature": `t=${t},v1=${sig}` } });
    if (!res.ok) throw new Error(`Skald answered ${res.status}`);
    const page = await res.json();
    for (const row of page.rows) found.set(`${row.external_ref}/${row.stage}`, row);
    cursor = page.next_cursor;
  } while (cursor);
  return found;
}
```

Python (standard library only):

```
import hashlib, hmac, json, os, time, urllib.parse, urllib.request

BASE = "https://stats.example.com"
PATH = "/traffic-hooks/example.com/leads"

def leads_in_skald(since: str) -> dict:
    """{(external_ref, stage): row} for every lead Skald received since `since`."""
    secret = os.environ["SKALD_HOOK_SECRET"].encode()
    found, cursor = {}, None
    while True:
        params = {"since": since, "limit": 500, **({"cursor": cursor} if cursor else {})}
        query = urllib.parse.urlencode(params)
        t = str(int(time.time()))
        sig = hmac.new(secret, f"{t}.GET {PATH}?{query}".encode(), hashlib.sha256).hexdigest()
        req = urllib.request.Request(f"{BASE}{PATH}?{query}",
                                     headers={"X-Skald-Signature": f"t={t},v1={sig}"})
        with urllib.request.urlopen(req, timeout=20) as res:
            page = json.load(res)
        for row in page["rows"]:
            found[(row["external_ref"], row["stage"])] = row
        cursor = page["next_cursor"]
        if not cursor:
            return found
```

PHP:

```
function skald_leads_since(string $since): array {
    $base = 'https://stats.example.com';
    $path = '/traffic-hooks/example.com/leads';
    $found = [];
    $cursor = null;
    do {
        $params = ['since' => $since, 'limit' => 500];
        if ($cursor) $params['cursor'] = $cursor;
        $query = http_build_query($params);
        $t = time();
        $sig = hash_hmac('sha256', "$t.GET $path?$query", getenv('SKALD_HOOK_SECRET'));
        $ch = curl_init("$base$path?$query");
        curl_setopt_array($ch, [CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 20,
            CURLOPT_HTTPHEADER => ["X-Skald-Signature: t=$t,v1=$sig"]]);
        $body = curl_exec($ch);
        $code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);
        if ($code !== 200) throw new RuntimeException("Skald answered $code");
        $page = json_decode($body, true);
        foreach ($page['rows'] as $row) $found[$row['external_ref'] . '/' . $row['stage']] = $row;
        $cursor = $page['next_cursor'];
    } while ($cursor);
    return $found;
}
```

**A daily check.** Once a day:

1. List the leads your server made in the last 2 days, each with its stage.
2. Ask Skald with `since` a little before that window, such as 3 days ago. Skald receives a lead after you make it, so a lead of your window is never missed; the overlap with yesterday's check does no harm.
3. Send every lead (with its stage) that is not in the answer again, through the lead hook, with its original `at`. A lead Skald has already is answered `"duplicates": 1` and changes nothing: Skald keeps one row per lead and stage. So when in doubt, send it.

Two cautions: never send again a lead that was deleted on request, or it comes back. And a lead older than the keeping time (400 days) is gone from the answer on purpose. A lead sent again keeps the label of its first delivery.

The answers: 200 as above; 400 a parameter is wrong (the answer says which; any other parameter name is refused); 401 no signature, a wrong one, or `t` more than 5 minutes off; 404 the site is not set up or its lead hook has no secret (the same answer for both); 429 more than 60 a minute for the site (`hooks.leads_per_minute`), wait and ask again. A 403 from an install set up before 2.18 means its nginx lets only POST through to `/traffic-hooks/`: the line `limit_except POST { deny all; }` must read `limit_except GET POST { deny all; }` (INSTALL.md, DEPLOY.md).

## What Skald answers

| Answer | Means | Do |
| --- | --- | --- |
| 200 | Taken: `{"ok":true,"recorded":1,"duplicates":0}`. A repeat shows as a duplicate | Nothing |
| 400 | The body is not JSON, or a field is wrong (no `external_ref`, a time that is not a time) | Fix the body; do not retry |
| 401 | The signature does not match, or `t` is more than 5 minutes off | Check the secret and the clock |
| 404 | No such site or tool, or the hook has no secret | Make the secret; check the address |
| 413 | The body is over 64 KiB | Send fewer records at once |
| 429 | Too many at once | Wait and try again |
| 500 | Not kept (disk or database) | Send it again |
