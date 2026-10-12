#!/bin/sh
# The build file the dashboard footer, the reports and the mails read:
# what is deployed, and when. Run from the repository, at deploy time:
#
#   tools/build-info.sh > build.json
#
# name     NAME (the tool's display name: the one place to rename it)
# tagline  TAGLINE (optional)
# version  VERSION (semver, bumped by hand for each release worth naming)
# release  the number of commits on HEAD: goes up by one with every commit
# commit   HEAD, short
set -eu
cd "$(dirname "$0")/.."
name=$(tr -d '\n' < NAME)
version=$(tr -d '\n' < VERSION)
tagline=$( [ -f TAGLINE ] && tr -d '\n' < TAGLINE || true )
release=$(git rev-list --count HEAD)
commit=$(git rev-parse --short HEAD)
now=$(date -u +%Y-%m-%dT%H:%M:%SZ)
printf '{"schema_version":1,"name":"%s","version":"%s","tagline":"%s","release":%s,"commit":"%s","deployed_at":"%s"}\n' \
  "$name" "$version" "$tagline" "$release" "$commit" "$now"
