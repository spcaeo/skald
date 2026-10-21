"""The name lists and rules of Security (security.py), shared with its second count.

Data only, like classify.py's lists: what a scanner probe looked for, the kinds of
injection in a query string, the paths a login or form posts to, and the
documented thresholds. security.py (the main road) and audit_security.py (the
second count) both read these and nothing else of each other.

Which requests are scanner probes is classify.PROBE / PROBE_QUERY's business;
these lists only say what a probe was after. Each probe gets exactly one
category: the first in CATEGORIES whose pattern matches (injection in the query
first, then the path's shape), else "other". So the categories add up to the
probes.
"""
from __future__ import annotations

import ipaddress
import re

# What a probe looked for, in the order a probe is filed. Patterns read the
# lower-cased path (no query string), except "injection", which reads the URL.
CATEGORIES = (
    ("injection", "Path tricks and injection", re.compile(
        r"\.\./|%2e%2e|/etc/passwd|\$\{jndi:|<script|%3cscript|union(?:\s|%20|\+)+select"
        r"|xdebug_session|allow_url_include|auto_prepend_file", re.I)),
    ("secrets", "Secret files (.env, keys)", re.compile(
        r"(?:^|/)\.(?:env|git|svn|hg|bzr|aws|ssh|npmrc|htpasswd|htaccess|bash_history"
        r"|ds_store|config|vscode|idea)(?:[._/-]|$)"
        r"|(?:^|/)id_(?:rsa|dsa|ecdsa|ed25519)|\.(?:pem|key|p12|pfx)$"
        r"|(?:^|/)(?:credentials?|secrets?|service-account[^/]*|firebase[^/]*|key)\."
        r"(?:json|ya?ml|xml|ini|env|txt)$|(?:^|/)env\.js$")),
    ("cloud", "Cloud and deploy configs", re.compile(
        r"\.tf$|\.tfvars|tfstate|terraform|(?:^|/)cdk(?:\.context)?\.json$|cdk\.out"
        r"|appspec\.ya?ml$|serverless\.ya?ml$|docker-compose|dockerfile|(?:^|/)\.docker"
        r"|kubeconfig|(?:^|/)\.kube|(?:^|/)k8s|helm|\.github/|buildspec\.ya?ml$"
        r"|cloudformation|samconfig|\.circleci|gitlab-ci|travis\.ya?ml$|vercel\.json$"
        r"|netlify\.toml$|(?:^|/)(?:config|settings|appsettings|parameters)\."
        r"(?:json|ya?ml|xml|ini)$|containers/json")),
    ("wordpress", "WordPress", re.compile(
        r"(?:^|/)(?:wp-[a-z]+|xmlrpc|wordpress|wp)(?:[/.]|$)")),
    ("dumps", "Database dumps and backups", re.compile(
        r"\.(?:sql|sqlite3?|db|bak|swp|old|orig|save|zip|tar|tgz|gz|rar|7z)$"
        r"|(?:^|/)backups?(?:/|$)|(?:^|/)dump")),
    ("admin", "Admin panels and consoles", re.compile(
        r"(?:^|/)(?:admin|administrator|phpmyadmin|pma|myadmin|adminer|cpanel|cgi-bin"
        r"|boaform|hudson|jenkins|solr|struts|actuator|_profiler|druid|geoserver|hnap1"
        r"|owa|autodiscover|manager|console|api/config|sdk)(?:[/.]|$)"
        r"|\.(?:asp|aspx|jsp|jspa|cgi|pl|cfm)(?:/|$)")),
    ("php", "PHP scripts", re.compile(
        r"\.(?:php\d?|phtml)(?:/|$)|phpinfo|eval-stdin|invokefunction|phpunit|laravel"
        r"|_ignition|telescope|_debugbar")),
)
OTHER = ("other", "Other probes")
CATEGORY_NAMES = {key: words for key, words, _ in CATEGORIES} | {OTHER[0]: OTHER[1]}

# The kinds of injection a query string carries (Attack attempts), first match
# wins, else "other".
INJECTION = (
    ("traversal", "Path traversal (../, /etc/passwd)", re.compile(
        r"\.\./|%2e%2e|/etc/passwd", re.I)),
    ("log4shell", "Log4Shell (${jndi:)", re.compile(r"\$\{jndi:", re.I)),
    ("xss", "Script injection (<script)", re.compile(r"<script|%3cscript", re.I)),
    ("sql", "SQL injection (union select)", re.compile(r"union(?:\s|%20|\+)+select", re.I)),
    ("php", "PHP settings and debugger", re.compile(
        r"xdebug_session|allow_url_include|auto_prepend_file", re.I)),
)
INJECTION_NAMES = {key: words for key, words, _ in INJECTION} | {"other": "Other injection"}

# A POST to a login or form path (Attack attempts, "login and form hammering"):
# a path segment that names signing in, a password, a sign-up or a contact form.
LOGIN_PATH = re.compile(
    r"(?:^|/)[\w.-]*(?:login|log-in|logon|signin|sign-in|sign_in|auth|session|password"
    r"|passwd|register|signup|sign-up|subscribe|contact|otp|verify|xmlrpc)[\w.-]*(?:/|$)",
    re.I)

# Log signs "worth a look" (2.21): a PHP script's path, and the gateway errors a crashing
# PHP worker or upstream answers with.
PHP_PATH = re.compile(r"\.php\d?(?:/|$)", re.I)
GATEWAY = ("502", "503", "504")
SIGN_PATHS = 5

# The documented thresholds (config `security:` or settings rows; DEFAULTS).
DEFAULTS = {
    # "Is anything exposed?": a 2xx answer to a probe is the host's "unknown
    # path" shell when its size is within TOLERANCE bytes of a size the host
    # gave at least SHELL_PATHS distinct probe paths that day.
    "shell_paths": 3, "tolerance": 16,
    # Login and form hammering: at least LOGIN_POSTS POSTs to a login or form
    # path from one address within LOGIN_SECONDS.
    "login_posts": 20, "login_seconds": 300,
    # A burst: at least BURST_REQUESTS requests from one address within
    # BURST_SECONDS (people and bots only; crawlers and our own are left out).
    "burst_requests": 300, "burst_seconds": 60,
    # Log signs: a POST whose request_length= is at least this many bytes is large.
    "large_post_bytes": 1_000_000,
}
LIMITS = {"shell_paths": (2, 50), "tolerance": (0, 4096), "login_posts": (3, 10_000),
          "login_seconds": (10, 86_400), "burst_requests": (20, 1_000_000),
          "burst_seconds": (5, 3_600), "large_post_bytes": (10_000, 1_000_000_000)}

# The exposure rule a day was counted with (the day's `rules.exposure_rule`). 2 (2.21.1): a
# host may have several fallback sizes, and a probe whose path is an ordinary page (only its
# query string is an attack) is no exposure candidate. A day counted with an older rule is
# never alerted on (alerts_security, security_notify) until it is recounted.
EXPOSURE_RULE = 2

# How much a day keeps (the day kind `security`).
WHO = 300            # suspect (address, agent) rows kept per day, worst first
TOP_PATHS = 20       # probed paths per day, then "(all others)"
TOP_COUNTRIES = 10
ROW_PATHS = 5        # per suspect row: its top probed paths and pages
EXPOSURE_ROWS = 200  # "possible" and "can't tell" answers kept per day
EPISODES = 100       # login and burst episodes kept per day
FAKE_PAGES = 10
FOLD = "(all others)"
UNKNOWN = "Unknown"


def settings(config: dict | None) -> dict:
    """The thresholds: config `security:` over DEFAULTS, each within LIMITS."""
    raw = (config or {}).get("security") or {}
    out = {}
    for key, default in DEFAULTS.items():
        try:
            value = int(raw.get(key, default))
        except (TypeError, ValueError):
            value = default
        lo, hi = LIMITS[key]
        out[key] = min(max(value, lo), hi)
    return out


def bare_ip(host: str) -> bool:
    """A Host header that is an IP literal (203.0.113.5, [2001:db8::1], with or
    without a port): the request went to the server's address, not the site."""
    text = (host or "").strip().lower()
    if text.startswith("["):
        text = text[1:].split("]", 1)[0]
    elif text.count(":") == 1:
        text = text.split(":", 1)[0]
    try:
        ipaddress.ip_address(text)
    except ValueError:
        return False
    return True


def own_like(host: str, own: set) -> bool:
    """A referrer host that is the site's: one of its hosts, or a subdomain of
    one (with "www." taken off): the wp. subdomain of the site's own name."""
    host = (host or "").lower()
    if not host:
        return False
    for h in own:
        base = h[4:] if h.startswith("www.") else h
        if host == h or host == base or host.endswith("." + base):
            return True
    return False
