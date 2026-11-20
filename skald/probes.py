"""The probe name lists (CLASSIFICATION.md rules 6, 6b and 6c): paths no real site serves to a
reader, and attack strings in a query. Moved out of classify.py (SKALD-24, its 1000-line limit);
classify.py re-exports PROBE, SECRET_PROBE and PROBE_QUERY, so the audit still imports them
from there, the only things it shares with the main road."""
from __future__ import annotations

import re

# Paths no real site serves. A request for one is somebody trying credentials,
# whatever its user agent claims - so it is never a page view, and the agent is
# not to be believed about anything else either.
#
# Every pattern is anchored to the SHAPE of the thing being hunted - a file
# name, an extension, a directory segment - never a bare word. The first
# version matched "backup" anywhere, and a real site's page with "backup" in
# its name became a scanner, with every person who read it.
# tests/fixtures/site_paths.txt is a made-up sitemap of the same shape (475
# pages, many named with scanners' words); none may match. Tested on the path only: a query string is a
# page's own business (an image URL inside one mentioned "backup" too).
_SEG = r"(?:^|/)"          # starts a path segment
_END = r"(?:[/.]|$)"       # ends one: a slash, an extension, or the end
# The families that mark the whole visitor (rule 6b, Scanners): secret,
# config and infrastructure files that no site serves to a reader.
_SECRETS = (
    # Dotfiles and version control: no site serves these on purpose.
    _SEG + r"\.(?:env|git|svn|hg|bzr|aws|ssh|docker|vscode|idea|npmrc|htpasswd"
    r"|htaccess|bash_history|ds_store|config|terraform|kube|circleci|travis|gitlab-ci"
    r"|github)(?:[._/-]|$)",
    # Dumps and backups, shaped like files.
    _SEG + r"(?:backups?|bak|db|database|dump|site|www|web|html|public_html"
    r"|wwwroot|data|old|test)\.(?:zip|tar|tar\.gz|tgz|gz|rar|7z|sql|bak)$"
    r"|\.(?:sql|sql\.gz|sqlite3?|bak|swp)$|" + _SEG + r"backups?/?$",
    # Keys and credentials, shaped like files.
    _SEG + r"id_(?:rsa|dsa|ecdsa|ed25519)(?:\.pub)?$|\.(?:pem|key|p12|pfx)$"
    r"|" + _SEG + r"(?:credentials?|secrets?|service-account[^/]*)"
    r"\.(?:json|ya?ml|xml|ini|env|txt)$"
    r"|" + _SEG + r"docker-compose[^/]*\.ya?ml$",
    # Infrastructure and deployment files (2.20.1). A scanner on a live site
    # asked for /main.tf, /outputs.tf, /cdk.out and /appspec.yml in the same
    # two seconds as six .env files, sending a Chrome agent: the .env rows
    # were probes, these were "people: client error". Terraform (any file
    # ending .tf, .tfvars, .tf.json or .tfstate), AWS CDK, CodeDeploy and
    # CodeBuild, Serverless, SAM, Kubernetes and Helm, CI files. Names a
    # real page could carry (template, values, Chart) only at the root.
    r"\.tf(?:vars)?(?:\.json)?$|\.tfstate(?:\.backup)?$"
    r"|" + _SEG + r"cdk\.out(?:/|$)|" + _SEG + r"cdk(?:\.context)?\.json$"
    r"|" + _SEG + r"(?:appspec|buildspec|serverless|cloudbuild|bitbucket-pipelines"
    r"|azure-pipelines|kustomization|skaffold)\.ya?ml$"
    r"|" + _SEG + r"(?:samconfig\.toml|kubeconfig(?:\.ya?ml)?|Jenkinsfile|Dockerfile)$"
    r"|^/(?:template|values|Chart)\.ya?ml$",
    # A project's package and lock files: lock files anywhere, manifests only
    # at the root (a sitemap may have a /package/ or /composer/ page).
    _SEG + r"(?:composer\.lock|package-lock\.json|yarn\.lock|pnpm-lock\.yaml"
    r"|Gemfile\.lock|Pipfile\.lock|poetry\.lock|Cargo\.lock)$"
    r"|^/(?:composer\.json|package\.json|Gemfile|Pipfile|requirements\.txt|go\.mod"
    r"|Cargo\.toml|pyproject\.toml)$",
)
# Probes too, but each moves only its own request: a real site may serve
# them to real readers - a WordPress site's /wp-content/ and /wp-json/, a PHP
# site's scripts, the owner's own /admin, an app that loads /config.json,
# /appsettings.json or /env.js as it starts.
_SERVED = (
    # Server-side scripts that a static or Node site never runs.
    r"\.(?:php\d?|phtml|asp|aspx|jsp|jspa|cgi|pl|cfm)(?:/|$)",
    # WordPress and its kin. The bare words only at the start of the path (a
    # scanner's /wordpress/ or //wp/...): a site may have its own page about
    # WordPress, such as /integrations/wordpress/ or /blog/category/wp/.
    _SEG + r"(?:wp-admin|wp-login|wp-content|wp-includes|wp-json|wp-config"
    r"|xmlrpc)" + _END + r"|^/+(?:wordpress|wp)" + _END,
    # An app's settings, shaped like files.
    _SEG + r"(?:firebase[^/]*|config|settings|appsettings|parameters|key)"
    r"\.(?:json|ya?ml|xml|ini|env|txt)$|" + _SEG + r"env\.js$",
    # Admin panels, app-server consoles and framework debug routes (several
    # are remote-code-execution endpoints that send a Chrome user agent).
    _SEG + r"(?:admin|administrator|phpmyadmin|pma|myadmin|adminer|cpanel"
    r"|cgi-bin|boaform|hudson|jenkins|solr|struts|actuator|telescope|_ignition"
    r"|_debugbar|_profiler|laravel|druid|geoserver|HNAP1|owa|autodiscover"
    r"|vendor/phpunit|containers/json|api/config|sdk)" + _END +
    r"|phpinfo|eval-stdin|invokefunction|" + _SEG + r"\.well-known/ALFA",
    # A recon of React and Next.js server actions (SKALD-24, 17 Nov 2026: a scanner with a
    # browser agent asked these twice each, answered 5xx, and was counted as people). No
    # browser asks for a bare /_next/ or for the build's server folder, and React's flight
    # and RSC streams are a query (?_rsc=) or a header, never a folder of their own.
    # /api/, /app/, /actions/ and /api/auth/ are left out: a site may have them.
    r"^/_next/?$|^/_next/server(?:-actions)?" + _END
    + r"|^/(?:__flight|_rsc|_react)" + _END,
)
PROBE = re.compile("|".join(_SECRETS + _SERVED), re.I)
# The probes that mark the whole visitor (Scanners, rule 6b): a name list
# the audit shares, as it shares PROBE.
SECRET_PROBE = re.compile("|".join(_SECRETS), re.I)

# Attack strings that arrive in the query string instead of the path.
# The dots of "../" and the slashes of "/etc/passwd" may come encoded once
# (%2e%2e) or again and again (%252e%252e: a live attack on 2026-10-23 sent
# templates%252f%252e%252e%252f... to reach a PHP tool and was counted as
# 1,260 people page views): %(?:25)* is "%", "%25", "%2525", ...
_DOT = r"(?:\.|%(?:25)*2e)"
_SLASH = r"(?:/|\\|%(?:25)*(?:2f|5c))"
PROBE_QUERY = re.compile(
    r"\.\./|%(?:25)*2e%(?:25)*2e|" + _DOT + _DOT + _SLASH
    + r"|" + _SLASH + r"etc" + _SLASH + r"passwd|\$\{jndi:|<script|union(?:\s|%20|\+)+select"
    r"|XDEBUG_SESSION|allow_url_include|auto_prepend_file",
    re.I,
)
