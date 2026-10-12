# Skald in one container: nginx on port 8080 in front of the two
# helpers (127.0.0.1:8765 refresh/sign-in/API, 127.0.0.1:8766 beacon) and a small
# scheduler (live every 2 minutes, run-daily, backup). docker/entrypoint.py
# supervises the four; docs/INSTALL.md says how to run it.
#
#   docker build -f docker/Dockerfile -t ghcr.io/spcaeo/skald:latest .
#
# Skald itself is standard library only; PyYAML is optional and included here.
FROM python:3.12.12-slim-bookworm

ARG UID=10001
ARG GID=10001
# Filled in by the release workflow (git rev-list --count HEAD / rev-parse --short HEAD).
ARG SKALD_RELEASE=0
ARG SKALD_COMMIT=unknown

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SKALD_PORT=8080

# nginx (Debian's, with auth_request and realip) is the one web server in front.
# The user is in group adm (gid 4), which can read a host's /var/log/nginx on
# Ubuntu and Debian when it is mounted at /logs.
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
# Debian's nginx is not pinned to a version: a pin breaks the build at its next security update.
# hadolint ignore=DL3008
RUN apt-get update \
 && apt-get install -y --no-install-recommends nginx-light \
 && rm -rf /var/lib/apt/lists/* /etc/nginx/sites-enabled/* /var/log/nginx \
 && pip install --no-cache-dir PyYAML==6.0.2 \
 && groupadd --system --gid "$GID" skald \
 && useradd --system --uid "$UID" --gid "$GID" --groups adm --no-create-home \
      --home-dir /var/lib/skald --shell /usr/sbin/nologin skald \
 && install -d -o root -g root -m 0755 /opt/skald \
 && install -d -o root -g skald -m 0750 /etc/skald \
 && install -d -o skald -g skald -m 0750 /var/lib/skald /var/log/skald \
 && install -d -o skald -g skald -m 0755 /var/www/skald /logs \
 && ln -s /var/lib/skald/nginx /var/log/nginx

COPY --chown=root:root . /opt/skald

# build.json: what the dashboard's footer says is running (tools/build-info.sh's fields).
RUN python3 -c 'import json, os, time; a = "/opt/skald"; \
r = lambda n: open(f"{a}/{n}").read().strip() if os.path.exists(f"{a}/{n}") else ""; \
json.dump({"schema_version": 1, "name": r("NAME"), "version": r("VERSION"), "tagline": r("TAGLINE"), \
"release": int(os.environ.get("SKALD_RELEASE") or 0), "commit": os.environ.get("SKALD_COMMIT") or "unknown", \
"deployed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, open(f"{a}/build.json", "w"))' \
 && printf '#!/bin/sh\nexec python3 /opt/skald/docker/entrypoint.py skald "$@"\n' \
      > /usr/local/bin/skald \
 && chmod 0755 /usr/local/bin/skald /opt/skald/docker/entrypoint.py \
 && python3 -m compileall -q /opt/skald/skald \
 && nginx -V 2>&1 | grep -q http_auth_request_module

WORKDIR /opt/skald
# No USER line on purpose: the entrypoint starts as root only to give a data disk
# that a platform mounted for root (Railway, Fly, Render) to uid 10001, then drops
# to uid 10001 before it runs anything (docker/entrypoint.py, drop_privileges).
# `--user 10001:10001` (or Kubernetes runAsUser) skips that step.
VOLUME ["/var/lib/skald"]
EXPOSE 8080

HEALTHCHECK --interval=60s --timeout=15s --start-period=60s --retries=3 \
  CMD ["python3", "/opt/skald/docker/entrypoint.py", "health"]

ENTRYPOINT ["python3", "/opt/skald/docker/entrypoint.py"]
CMD ["serve"]
