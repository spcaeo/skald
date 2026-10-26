# skald-log-anonymizer.py

A single-file script (Python 3, standard library only) that turns a web server access log into a tab-separated table you can analyze or share. Written for the AI-visibility study by [Skald](https://skaldanalytics.com/). Free to use, source-available, free to self-host. Study write-up: https://x.com/rakeshpatelco/status/2114851090453680324

## What it does

- Reads nginx or Apache "combined" format logs. Takes files (plain or .gz) or stdin.
- Replaces each IP address with a 12-character key made with HMAC-SHA256 and a random salt that exists only in memory. The same IP gets the same key within one run, and the key cannot be reversed. A new run uses a new salt, so keys do not match across runs.
- Before the IP is discarded, it checks the IP against vendors' published bot ranges (if you give it a ranges file) and writes only the vendor label into `ip_range`.
- Drops query strings (the `utm_source` value is kept as its own column), converts times to UTC, and reduces browser user agents to a family token such as `Chrome-d` (desktop) or `Chrome-m` (mobile). Bot and tool user agents are kept so you can count them.
- Scrubs any IP-looking or email-looking text from paths, hosts, UTM and user agent fields.
- Skips Next.js prefetch requests and lines it cannot parse (it prints counts to stderr).

Output columns: `ts  ip_key  ip_range  method  path  status  ref_host  utm_source  ua`

## Use

    python3 skald-log-anonymizer.py --selftest
    python3 skald-log-anonymizer.py --fetch-ranges ranges.json        # optional, needs internet
    python3 skald-log-anonymizer.py --ranges ranges.json access.log access.log.*.gz --out mine.tsv

`--selftest` runs 14 built-in checks, including "no sample IP appears in the output". `--hash-paths` replaces page paths with salted hashes if paths are sensitive. `--hosts a.com,b.com` keeps only those hosts (for logs that record the host name).

Always look at the first lines of your output before sharing it.

## Count the study's four things (copy and paste)

Columns: 1 ts, 2 ip_key, 3 ip_range, 4 method, 5 path, 6 status, 7 ref_host, 8 utm_source, 9 ua. These count requests, not visits, so expect numbers a bit above a visit count.

    # 1. Requests that arrived from a ChatGPT referrer or tag
    awk -F'\t' 'NR>1 && ($7 ~ /chatgpt/ || $8 ~ /chatgpt/)' mine.tsv | wc -l
    # (repeat with gemini, claude, perplexity, copilot)

    # 2. ChatGPT-User live fetches that got an answer (200 or 304)
    awk -F'\t' 'NR>1 && $9 ~ /ChatGPT-User/ && ($6==200||$6==304)' mine.tsv | wc -l

    # 3. Tag but no referrer
    awk -F'\t' 'NR>1 && $8 ~ /chatgpt/ && $7 !~ /chatgpt/' mine.tsv | wc -l

    # 4. IPs claiming 5 or more different bot names (change th=5 to test)
    awk -F'\t' -v th=5 'NR>1 && match($9,/(ChatGPT-User|GPTBot|OAI-SearchBot|PerplexityBot|Perplexity-User|ClaudeBot|Claude-User|Claude-SearchBot|Googlebot|bingbot)/){k[$2 SUBSEP substr($9,RSTART,RLENGTH)]=1} END{for(x in k){split(x,b,SUBSEP);n[b[1]]++} for(i in n) if(n[i]>=th) c++; print c+0}' mine.tsv

Fetch bursts and visits need a little grouping by time (a gap over 10 minutes starts a new burst; a gap over 30 minutes starts a new visit). The study's own scripts do that, but the four commands above are enough for a first look.

## Limits

- Only the nginx/Apache combined format and Skald's extended format are handled. If the first run says most lines were "unparsed", your format differs.
- Published ranges are a snapshot from the day you fetch them. Claude-User and some other agents have no published ranges.
- Behind a CDN, the IP in the log may be the CDN's, not the visitor's.
