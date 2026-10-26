#!/usr/bin/env python3
"""skald-log-anonymizer.py: turn a web-server access log into an anonymized table you can
analyse or share. It runs entirely on your own machine and needs only Python 3.8+.
Part of the Skald AI-visibility pilot study. Source-available, free to self-host:
https://github.com/spcaeo/skald    Site: https://skaldanalytics.com/
Write-up of the study: https://x.com/rakeshpatelco/status/2114851090453680324

USAGE
    # nginx or Apache "combined" format; .gz files are read directly
    python3 skald-log-anonymizer.py /var/log/nginx/access.log* > my-site.tsv

    # optional: check IPs against the bot ranges AI companies publish (needs internet once)
    python3 skald-log-anonymizer.py --fetch-ranges ranges.json
    python3 skald-log-anonymizer.py --ranges ranges.json access.log > my-site.tsv

    # prove to yourself that no IP survives (runs on built-in sample lines, no files needed)
    python3 skald-log-anonymizer.py --selftest

WHAT COMES OUT, one line per request, tab-separated:
    ts        time in UTC (ISO 8601)
    ip_key    first 12 hex characters of HMAC-SHA256(IP) using a random salt made when the
              script starts and never written anywhere. The same IP gives the same key inside
              one run, so you can count visits, but the key cannot be reversed and cannot be
              matched with the output of another run.
    ip_range  name of the published bot range the IP sits in (for example
              "openai-chatgpt-user"), or "-". Worked out BEFORE the IP is discarded.
    method, path, status
    ref_host  only the host name of the referrer (no path, no query)
    utm_source  the utm_source value if present, else "-"
    ua        bot user agents are kept (cut at 80 characters); browsers are reduced to a family
              such as "Chrome-d" (desktop) or "Safari-m" (mobile)
WHAT NEVER COMES OUT: IP addresses, query strings (except utm_source), cookies, response sizes,
full referrer URLs, login names. As an extra guard, anything that looks like an IP address or an
email address inside the path, host or user agent is replaced by [ip] or [email].
Use --hash-paths if your page names are private: paths become salted hashes (equal pages stay
equal), except "/", static assets and 4xx answers.

Lines that do not match a known format are counted and reported on stderr, never printed.
"""
import argparse, gzip, hashlib, hmac, io, ipaddress, json, os, re, sys, tempfile
from datetime import datetime, timezone
from urllib.parse import urlsplit, parse_qs

# nginx/Apache "combined": ip - user [time] "req" status size "ref" "ua"
COMBINED = re.compile(r'^(?P<ip>\S+) \S+ \S+ \[(?P<t>[^\]]+)\] "(?P<req>[^"]*)" (?P<st>\d{3}) \S+ "(?P<ref>[^"]*)" "(?P<ua>[^"]*)"')
# Skald "extended": ISO-time ip host "req" status size "ref" "ua" ...
EXTENDED = re.compile(r'^(?P<t>\d{4}-\d\d-\d\dT\S+) (?P<ip>\S+) (?P<host>\S+) "(?P<req>[^"]*)" (?P<st>\d{3}) \S+ "(?P<ref>[^"]*)" "(?P<ua>[^"]*)"')
BOT_HINT = re.compile(r'bot|crawl|spider|slurp|fetch|-user/|curl|wget|python|go-http|java/|okhttp|httpclient|scrapy|headless|libwww|axios|node-fetch|^-$|^node$|undici|zgrab|masscan|nmap|nuclei|scanner|probe|monitor|uptime|pingdom|lighthouse|preview|reqwest|apache-http|wordpress/|http-client|postman|insomnia|perl|ruby|php/|rss|feed|check|validator|analy[sz]|archive|\+http', re.I)
STATIC = re.compile(r'\.(js|css|png|jpe?g|gif|svg|webp|ico|woff2?|ttf|map|xml|txt|json)$', re.I)
IPV4 = re.compile(r'\b\d{1,3}(?:\.\d{1,3}){3}\b')
IPV6 = re.compile(r'(?<![0-9A-Za-z])(?:[0-9A-Fa-f]{1,4}:){2,7}[0-9A-Fa-f]{0,4}(?![0-9A-Za-z])')
EMAIL = re.compile(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+')

RANGE_SOURCES = {
    "openai-chatgpt-user": "https://openai.com/chatgpt-user.json",
    "openai-gptbot": "https://openai.com/gptbot.json",
    "openai-searchbot": "https://openai.com/searchbot.json",
    "perplexity-user": "https://www.perplexity.ai/perplexity-user.json",
    "perplexitybot": "https://www.perplexity.ai/perplexitybot.json",
    "anthropic": "https://claude.com/crawling/bots.json",
    "googlebot": "https://developers.google.com/static/search/apis/ipranges/googlebot.json",
    "google-user-triggered": "https://developers.google.com/static/search/apis/ipranges/user-triggered-fetchers.json",
    "bingbot": "https://www.bing.com/toolbox/bingbot.json",
}

def fetch_ranges(dest):
    """Download the vendors' published IP range lists into one JSON file. A source that
    fails is skipped with a warning (vendors move these URLs; check the vendor's docs)."""
    import urllib.request
    out = {}
    for name, url in RANGE_SOURCES.items():
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "skald-log-anonymizer/1.0"})
            d = json.load(urllib.request.urlopen(req, timeout=20))
            out[name] = [p.get("ipv4Prefix") or p.get("ipv6Prefix") for p in d.get("prefixes", [])]
            print(f"{name}: {len(out[name])} prefixes", file=sys.stderr)
        except Exception as e:
            print(f"{name}: FAILED ({e})", file=sys.stderr)
    with open(dest, "w") as f:
        json.dump(out, f, indent=1)

def parse_time(raw):
    try:
        if raw[:4].isdigit():
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
        return datetime.strptime(raw, "%d/%b/%Y:%H:%M:%S %z").astimezone(timezone.utc)
    except ValueError:
        return None

def browser_family(ua):
    mobile = "m" if re.search(r'Mobile|Android|iPhone', ua) else "d"
    for name in ("Edg/", "Firefox/", "Chrome/", "Safari/"):
        if name in ua:
            return f"{name.rstrip('/')}-{mobile}"
    return f"other-{mobile}"

def scrub(s):
    """Last line of defence: no IP-looking or email-looking text in free-text fields."""
    return EMAIL.sub("[email]", IPV6.sub("[ip]", IPV4.sub("[ip]", s)))

class Anonymizer:
    def __init__(self, ranges=None, hash_paths=False, hosts=None):
        self.nets = []
        for name, prefixes in (ranges or {}).items():
            for p in prefixes:
                if p:
                    self.nets.append((name, ipaddress.ip_network(p, strict=False)))
        self.salt = os.urandom(32)          # held in memory only
        self.hash_paths = hash_paths
        self.hosts = set(hosts) if hosts else None
        self._cache = {}
        self.stats = {"unparsed": 0, "other_host": 0, "rsc_prefetch": 0, "written": 0}

    def _h(self, s):
        return hmac.new(self.salt, s.encode(), hashlib.sha256).hexdigest()[:12]

    def _range(self, ip):
        if ip not in self._cache:
            try:
                a = ipaddress.ip_address(ip)
                self._cache[ip] = next((n for n, net in self.nets if a.version == net.version and a in net), "-")
            except ValueError:
                self._cache[ip] = "-"
        return self._cache[ip]

    def row(self, line):
        """Return the anonymized fields for one log line, or None to skip it."""
        m = EXTENDED.match(line) or COMBINED.match(line)
        if not m:
            self.stats["unparsed"] += 1; return None
        if self.hosts is not None and "host" in m.groupdict() and m["host"] not in self.hosts:
            self.stats["other_host"] += 1; return None
        # Next.js router prefetches are not page views
        if "_rsc=" in m["req"] or line.rstrip().endswith("rsc_prefetch=1"):
            self.stats["rsc_prefetch"] += 1; return None
        t = parse_time(m["t"])
        parts = m["req"].split(" ")
        if t is None or len(parts) < 2:
            self.stats["unparsed"] += 1; return None
        method, target = parts[0], parts[1]
        u = urlsplit(target)
        path = u.path or "/"
        utm = (parse_qs(u.query).get("utm_source") or ["-"])[0][:40]
        if self.hash_paths and path != "/" and not STATIC.search(path) and not m["st"].startswith("4"):
            path = "/h/" + self._h("p" + path)
        ref = m["ref"]
        ref_host = (urlsplit(ref).hostname or "-") if ref not in ("", "-") else "-"
        ua = m["ua"]
        is_browser = ua.startswith(("Mozilla/", "Opera/")) and not BOT_HINT.search(ua)
        ua_out = browser_family(ua) if is_browser else ua[:80]
        fields = [t.strftime("%Y-%m-%dT%H:%M:%SZ"), self._h("i" + m["ip"]), self._range(m["ip"]), method,
                  scrub(path), m["st"], scrub(ref_host), scrub(utm), scrub(ua_out)]
        self.stats["written"] += 1
        return [f.replace("\t", " ") for f in fields]

def open_text(path):
    if path == "-":
        return sys.stdin
    if path.endswith(".gz"):
        return io.TextIOWrapper(gzip.open(path, "rb"), encoding="utf-8", errors="replace")
    return open(path, encoding="utf-8", errors="replace")

SAMPLE = [
    '203.0.113.7 - - [12/Oct/2026:10:00:01 +0000] "GET /blog/post-1?utm_source=chatgpt.com&token=SECRET HTTP/1.1" 200 5123 "-" "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"',
    '198.51.100.23 - - [12/Oct/2026:10:00:05 +0000] "GET /blog/post-1 HTTP/1.1" 200 5123 "https://www.google.com/search?q=private+query" "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1"',
    '192.0.2.99 - - [12/Oct/2026:10:01:00 +0000] "GET /pricing HTTP/1.1" 200 900 "-" "Mozilla/5.0 AppleWebKit/537.36; compatible; ChatGPT-User/1.0; +https://openai.com/bot"',
    '2001:db8::1234 - - [12/Oct/2026:12:30:00 +0200] "GET /.env HTTP/1.1" 404 10 "-" "curl/8.0 contact admin@example.org from 192.0.2.99"',
    '2026-10-12T10:02:00Z 203.0.113.50 www.example.org "GET /about HTTP/1.1" 200 800 "https://chatgpt.com/" "Mozilla/5.0 (Macintosh) Firefox/121.0"',
    'this is not a log line 203.0.113.7',
]
SAMPLE_IPS = ["203.0.113.7", "198.51.100.23", "192.0.2.99", "2001:db8::1234", "203.0.113.50"]

def selftest():
    ranges = {"openai-chatgpt-user": ["192.0.2.0/24"]}
    a = Anonymizer(ranges)
    rows = [a.row(l) for l in SAMPLE]
    out = [r for r in rows if r]
    text = "\n".join("\t".join(r) for r in out)
    ok = True
    def check(cond, msg):
        nonlocal ok
        print(("PASS " if cond else "FAIL ") + msg); ok = ok and cond
    check(len(out) == 5, "5 of 6 lines kept; the junk line is counted, not printed")
    check(a.stats["unparsed"] == 1, "unparsed lines are counted")
    check(not any(ip in text for ip in SAMPLE_IPS), "no sample IP appears anywhere in the output")
    check("SECRET" not in text and "private" not in text, "query strings and search terms are gone")
    check("admin@example.org" not in text and "[email]" in text, "email in a user agent is replaced")
    check(out[0][8] == "Chrome-d" and out[1][8] == "Safari-m", "browsers reduced to a family token")
    check(out[0][7] == "chatgpt.com" and out[0][6] == "-", "utm_source kept, referrer host '-'")
    check(out[1][6] == "www.google.com", "referrer reduced to its host")
    check(out[2][2] == "openai-chatgpt-user" and out[0][2] == "-", "range check done before the IP is dropped")
    check(out[3][0] == "2026-10-12T10:30:00Z", "timestamps converted to UTC")
    check(out[0][1] != out[1][1] and len(out[0][1]) == 12, "different IPs give different 12-char keys")
    b = Anonymizer(ranges)
    check(b.row(SAMPLE[0])[1] != out[0][1], "a second run gives a different key for the same IP (random salt)")
    c = Anonymizer(ranges, hash_paths=True)
    r = c.row(SAMPLE[0]); r2 = c.row(SAMPLE[1])
    check(r[4].startswith("/h/") and r[4] == r2[4] and "blog" not in r[4], "--hash-paths hides names but keeps equality")
    d = Anonymizer(None, hosts=["www.example.org"])
    check(d.row(SAMPLE[4]) is not None and d.row(SAMPLE[0]) is not None, "--hosts only filters the extended format")
    print("\nALL CHECKS PASSED" if ok else "\nSOME CHECKS FAILED")
    return 0 if ok else 1

def main():
    ap = argparse.ArgumentParser(description="Anonymize a web server access log (see the docstring at the top of this file).")
    ap.add_argument("files", nargs="*", help="log files (.gz ok); default: read stdin")
    ap.add_argument("--ranges", help="ranges.json made by --fetch-ranges (optional)")
    ap.add_argument("--fetch-ranges", metavar="OUT.json", help="download vendors' published bot IP ranges and exit")
    ap.add_argument("--hash-paths", action="store_true", help="replace page paths by salted hashes")
    ap.add_argument("--hosts", help="comma list: for Skald extended logs, keep only these host names")
    ap.add_argument("--out", help="write to this file instead of stdout")
    ap.add_argument("--selftest", action="store_true", help="run built-in checks and exit")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    if a.fetch_ranges:
        fetch_ranges(a.fetch_ranges); return
    ranges = json.load(open(a.ranges)) if a.ranges else {}
    if not ranges:
        print("note: no --ranges given, so ip_range will be '-' for every row", file=sys.stderr)
    an = Anonymizer(ranges, a.hash_paths, a.hosts.split(",") if a.hosts else None)
    out = open(a.out, "w") if a.out else sys.stdout
    out.write("ts\tip_key\tip_range\tmethod\tpath\tstatus\tref_host\tutm_source\tua\n")
    for name in (a.files or ["-"]):
        with open_text(name) as f:
            for line in f:
                r = an.row(line)
                if r:
                    out.write("\t".join(r) + "\n")
    if a.out:
        out.close()
    s = an.stats
    print(f"written: {s['written']}; unparsed: {s['unparsed']}; other-host skipped: {s['other_host']}; "
          f"Next.js prefetch skipped: {s['rsc_prefetch']}", file=sys.stderr)

if __name__ == "__main__":
    main()
