# Send leads from your backend in 5 minutes

Your site's server tells Skald each time a lead is made. The quick way: download one file and call one function after your form is saved. WordPress needs no code at all: a plugin does it. The rest of this guide has the details the file does for you (the body, the signature, retries), for anyone who wants to write it themselves.

## The quick way: one file, one function

1. In the dashboard, open **Settings > This site > Leads & tools > Incoming hooks > Your site's server (lead)** and press **Make secret**. The secret is shown once.
2. In the same box, download the file for your site's language. Downloaded right after you made the secret, the file holds it and works as it is. Downloaded later, it holds no secret: set the environment variable `SKALD_LEAD_SECRET` on your server (every file reads it first, so it is the better place anyway).
3. Put the file next to your code and add one line where your form is saved:

| Your site | File | The line |
| --- | --- | --- |
| PHP | `skald-lead.php` | `require_once __DIR__ . '/skald-lead.php';` then `skald_lead($id, 'contact', $email, $name);` |
| Node 18 or later | `skald-lead.cjs` | `const { skaldLead } = require("./skald-lead.cjs");` then `await skaldLead(id, "contact", { email, name });` |
| Python 3.8 or later | `skald_lead.py` | `from skald_lead import skald_lead` then `skald_lead(id, "contact", email=email, name=name)` |
| WordPress | `skald-leads.zip` | No code: **Plugins > Add New > Upload Plugin**, choose the zip, then **Activate** |

- `id` is your own id for the lead, such as the form entry's id. The same lead always sends the same id: a repeat is never counted twice.
- The second word is what was done: `contact`, `demo`, `signup`, `trial`.
- Email and name are optional. Other fields from section 2 go in the last argument: `label`, `stage`, `test`, `vid`. PHP: `skald_lead($id, 'demo', $email, $name, ['label' => 'sales']);`.
- A sale with its value (2.32.0): PHP `skald_lead($order_id, 'paid', $email, $name, ['stage' => 'paid', 'value' => 49.00, 'currency' => 'USD', 'customer_ref' => $customer_id, 'tags' => ['plan' => 'pro']]);`, Node `await skaldLead(orderId, "paid", { stage: "paid", value: 49.00, currency: "USD", customer_ref: customerId })`, Python `skald_lead(order_id, "paid", stage="paid", value=49.00, currency="USD", customer_ref=customer_id)`. A refund: the same order ID with `stage` `refunded` and the total refunded on it so far as `value`. See [Revenue](revenue.md).
- Each function waits at most 3 seconds, never throws, and returns true when Skald kept the lead. Your form never breaks because of Skald.
- Node in an ES module: `import { skaldLead } from "./skald-lead.cjs";` works too.
- The files sign each lead (section 3), so they work with every version of Skald.

**WordPress.** The plugin works with Contact Form 7, WPForms, Gravity Forms, Elementor Pro forms and Ninja Forms. Each form sent becomes a lead with the action `contact`, the email and name fields it finds, and an id like `wpforms-123`. It sends in the background, so a form is never slower. To keep the secret out of the plugin file, add `define('SKALD_LEAD_SECRET', 'your-secret');` to `wp-config.php`, and download the plugin without the secret.

**Join the lead to the visit.** With Skald's script tag on your pages and visitor IDs on, the page knows the visitor's ID as `skald('id')`. Bring it to your server in a hidden form field named `skald_vid`, or read the `skald_vid` cookie (it exists when "Share across subdomains" is on). The PHP file and the WordPress plugin read both by themselves (the plugin also fills the hidden field for you). In Node and Python, pass it as `vid`. See [The tracking script](tracking-script.md).

**No code at all.** Zapier's **Webhooks by Zapier** and form plugins that can add a header send the secret as a plain key instead of signing: `Authorization: Bearer <your secret>`. See [Webhooks](webhooks.md#zapier-and-make).

Keep the secret on your server: in the environment variable, in `wp-config.php`, or in the downloaded file. Never in a web page, never in a public code repository.

## 1. Make the secret

On the server:

```
sudo skald hooks secret example.com lead
```

Or in the dashboard: **Settings > This site > Leads & tools > Incoming hooks > Your site's server (lead) > Make secret**. Docker: `docker exec skald skald hooks secret example.com lead` (in Docker, run every `skald` command in this guide the same way, without `sudo`).

It prints the secret once, and the address to post to. With `access.base_url` set, the address is the real one, such as `https://stats.example.com/traffic-hooks/example.com/lead`.

Keep the secret in an environment variable on your backend, such as `SKALD_LEAD_SECRET`. Never in the code, never in the browser.

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
| `stage` | default `completed` | `started`, `completed`, `cancelled`, `rescheduled`, `no_show`, `paid`, `won`, `lost`, and `refunded` (2.32.0: a refund on the sale's own `external_ref`, never a lead) |
| `at` | default: when it arrived | When it happened. A full ISO time with its offset: `2026-09-25T14:30:00-04:00` or `2026-09-25T18:30:00Z` |
| `vid` | | The visitor ID the page had. Kept only when the site has visitor IDs on |
| `first_touch`, `last_touch` | | Where the visitor came from: `referrer`, `landing`, `utm_source`, `utm_medium`, `utm_campaign`, `at` |
| `ip`, `user_agent` | | Skald looks up the country and the device, then drops both |
| `name`, `email` | | Kept only when the site's **Leads' names and emails** is **full**; otherwise dropped |
| `label` | optional | A short word that sorts leads of one action, such as a contact form's topic: `sales`, `support`, `partnership`. Lowercase letters, digits, `-` and `_`, at most 40, starting with a letter or digit (`Sales` is read as `sales`). Anything else is dropped: the lead is still kept, without a label, and the answer and the delivery log say so |
| `value`, `currency` | optional | 2.32.0: a sale's amount in the currency's normal units (`49.00`, not cents) and its three-letter code (`USD`). Shown on Leads & sales > Revenue, summed per currency, never converted. See [Revenue](revenue.md) |
| `customer_ref` | optional | Your customer's own ID (`u-119797`, never an email): it joins a renewal to the first sale |
| `tags` | optional | Up to 5 labels of your own, such as `{"plan": "pro"}`: lowercase names and values |
| `test` | optional | `true` for a lead your own team made (a team account, a QA run): Skald keeps it and lists it, and never counts it. `false` or left out: a real lead. Only `true` or `false` (not `"true"`, not `1`); anything else is ignored, the lead counts, and the answer and the delivery log say so |

Each stage keeps its own label: send it again with a later stage if that stage should carry it too. Leads and Summary (Count from: Tools) filter by label, and the lists of leads and conversions show it as a small tag.

Always send the offset. A time without one ("2026-09-25" or "2026-09-25T14:30:00") is read in the site's own time zone, and the delivery log says so. That guess is right only when your server writes local times in the same zone.

## 3. Sign it and send it

The header:

```
X-Skald-Signature: t=<unix seconds>,v1=<hex HMAC-SHA256 of "<t>.<raw body>">
```

The key is the secret. Sign the exact bytes you send. Skald refuses a `t` more than 5 minutes from its own clock, so keep the server's clock right.

A sender that cannot sign may send the secret itself instead, with no `X-Skald-Signature` header:

```
Authorization: Bearer <the secret>
```

It works on the `lead` and `json` hooks only, over `https://` only in practice (the key travels with each message), and a wrong key is refused like a bad signature. Signing is better when you can: a stolen signed message is useless after 5 minutes, a stolen key is not until you rotate it.

Each example below signs, posts, and tries again when the post fails.

curl:

```
URL='https://stats.example.com/traffic-hooks/example.com/lead'
BODY='{"external_ref":"L-1001","action":"demo","at":"2026-09-25T14:30:00-04:00"}'
for wait in 0 5 30 120; do
  sleep "$wait"
  T=$(date +%s)
  SIG=$(printf '%s.%s' "$T" "$BODY" | openssl dgst -sha256 -hmac "$SKALD_LEAD_SECRET" -hex | sed 's/^.* //')
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
    const sig = crypto.createHmac("sha256", process.env.SKALD_LEAD_SECRET).update(`${t}.${body}`).digest("hex");
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
    secret = os.environ["SKALD_LEAD_SECRET"].encode()
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
        $sig = hash_hmac('sha256', $t . '.' . $body, getenv('SKALD_LEAD_SECRET'));
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

Send each lead through one road only. If the same lead also goes through Zapier (the `json` hook), or Skald also reads it from the lead database, it counts once per road. **Settings > This site > Leads & tools > Incoming hooks > Status** flags such leads as "One lead, two tools".

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

It posts a signed sample, marked as a test: read, never kept. It says what a real one would keep: the action, the stage, the source, and whether the visitor ID is kept. **Send a test event** on the Incoming hooks tab does the same.

Then send a real lead. The Incoming hooks tab shows "last received 2 min ago (kept)", and `sudo skald doctor` shows the hook as OK.

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
SIG=$(printf '%s.GET %s?%s' "$T" "$P" "$Q" | openssl dgst -sha256 -hmac "$SKALD_LEAD_SECRET" -hex | sed 's/^.* //')
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
    const sig = crypto.createHmac("sha256", process.env.SKALD_LEAD_SECRET).update(`${t}.GET ${PATH}?${q}`).digest("hex");
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
    secret = os.environ["SKALD_LEAD_SECRET"].encode()
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
        $sig = hash_hmac('sha256', "$t.GET $path?$query", getenv('SKALD_LEAD_SECRET'));
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

## 10. Mark leads as test

Leads your own team makes, from a team account or a QA run, should not count. **Send your team's own accounts with `test: true`; to fix ones already sent, call `leads/test`.** Either way Skald keeps the lead, lists it (Leads > Left out, the person drawer, and the check above with `"test": true`), and never counts it.

An owner or admin can also do it by hand: open the lead in the dashboard and press **Mark as test** under its reference (or **Not a test** to count it again). It is the same mark as the call below. See [Marking a conversion as a test](leads-and-conversions.md#marking-a-conversion-as-a-test).

**When you send it.** Add `"test": true` to the body (section 2). It marks that message only: send it on every stage of a test lead (`started`, `completed`, `won`...). Sending a lead again with only `test` changed does nothing, like any repeat. Use the call below to change one Skald already has.

**After you sent it.** Post the refs to mark, signed with the **same secret** and the same way as a lead (section 3):

```
POST /traffic-hooks/example.com/leads/test
X-Skald-Signature: t=<unix seconds>,v1=<hex HMAC-SHA256 of "<t>.<raw body>">

{"refs": ["L-1001", "L-1002"], "test": true}
```

| Field | | |
| --- | --- | --- |
| `refs` | required | 1 to 100 of your `external_ref`s |
| `test` | default `true` | `false` takes the mark off, and the lead counts again |

It marks every stage of each ref that came through this site's lead hook (not Zapier's `json` hook, a booking tool or the lead database). And a stage you send later for a marked ref is marked too, so a team account's next steps stay out. The answer:

```
{"ok": true, "test": true, "marked": 3, "already": 0, "not_found": ["L-1002"]}
```

`marked` is how many rows changed (one per stage), `already` how many were so already, `not_found` the refs Skald has no lead for. Calling it twice is safe.

curl:

```
URL='https://stats.example.com/traffic-hooks/example.com/leads/test'
BODY='{"refs":["L-1001","L-1002"],"test":true}'
T=$(date +%s)
SIG=$(printf '%s.%s' "$T" "$BODY" | openssl dgst -sha256 -hmac "$SKALD_LEAD_SECRET" -hex | sed 's/^.* //')
curl -s -X POST "$URL" -H 'Content-Type: application/json' -H "X-Skald-Signature: t=$T,v1=$SIG" --data-raw "$BODY"
```

Node (18 or later):

```
import crypto from "node:crypto";

const URL = "https://stats.example.com/traffic-hooks/example.com/leads/test";

// Mark (test = true) or unmark (test = false) up to 100 leads by your own ids.
export async function markTest(refs, test = true) {
  const body = JSON.stringify({ refs, test });
  const t = Math.floor(Date.now() / 1000);
  const sig = crypto.createHmac("sha256", process.env.SKALD_LEAD_SECRET).update(`${t}.${body}`).digest("hex");
  const res = await fetch(URL, { method: "POST", body,
    headers: { "Content-Type": "application/json", "X-Skald-Signature": `t=${t},v1=${sig}` } });
  if (!res.ok) throw new Error(`Skald answered ${res.status}`);
  return res.json();
}
```

Python (standard library only):

```
import hashlib, hmac, json, os, time, urllib.request

URL = "https://stats.example.com/traffic-hooks/example.com/leads/test"

def mark_test(refs: list, test: bool = True) -> dict:
    """Mark (or unmark) up to 100 leads by your own ids."""
    body = json.dumps({"refs": refs, "test": test}).encode()
    t = str(int(time.time()))
    sig = hmac.new(os.environ["SKALD_LEAD_SECRET"].encode(), t.encode() + b"." + body,
                   hashlib.sha256).hexdigest()
    req = urllib.request.Request(URL, data=body, method="POST", headers={
        "Content-Type": "application/json", "X-Skald-Signature": f"t={t},v1={sig}"})
    with urllib.request.urlopen(req, timeout=10) as res:
        return json.load(res)
```

PHP:

```
function skald_mark_test(array $refs, bool $test = true): array {
    $url = 'https://stats.example.com/traffic-hooks/example.com/leads/test';
    $body = json_encode(['refs' => array_values($refs), 'test' => $test]);
    $t = time();
    $sig = hash_hmac('sha256', $t . '.' . $body, getenv('SKALD_LEAD_SECRET'));
    $ch = curl_init($url);
    curl_setopt_array($ch, [CURLOPT_POST => true, CURLOPT_POSTFIELDS => $body,
        CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 10,
        CURLOPT_HTTPHEADER => ['Content-Type: application/json', "X-Skald-Signature: t=$t,v1=$sig"]]);
    $answer = curl_exec($ch);
    $code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    if ($code !== 200) throw new RuntimeException("Skald answered $code");
    return json_decode($answer, true);
}
```

The figures follow at the next update of the dashboard: a lead marked today leaves the day it happened, even weeks ago, and comes back when unmarked. The check above (section 9) shows the change at once. Each call is in the delivery log and the audit log, with the refs it named.

The answers: 200 as above; 400 the body is wrong (not JSON, no `refs`, more than 100, an empty ref, `test` not `true` or `false`, or another field), the answer says which; 401 the signature does not match, or `t` is more than 5 minutes off; 404 the site is not set up or its lead hook has no secret; 429 more than 60 calls a minute for the site, wait and try again.

Not the same as section 8's test: a message with the header `X-Skald-Test: 1` is only read and checked, never kept. A lead with `"test": true` is kept, as a test lead.

## What Skald answers

| Answer | Means | Do |
| --- | --- | --- |
| 200 | Taken: `{"ok":true,"recorded":1,"duplicates":0}`. A repeat shows as a duplicate | Nothing |
| 400 | The body is not JSON, or a field is wrong (no `external_ref`, a time that is not a time) | Fix the body; do not retry |
| 401 | The signature (or the `Bearer` key) does not match, or `t` is more than 5 minutes off | Check the secret and the clock |
| 404 | No such site or tool, or the hook has no secret | Make the secret; check the address |
| 413 | The body is over 64 KiB | Send fewer records at once |
| 429 | Too many at once | Wait and try again |
| 500 | Not kept (disk or database) | Send it again |
