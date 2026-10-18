#!/bin/sh
# Download DB-IP's free "IP to City Lite" file (MaxMind .mmdb format, CC BY 4.0,
# a new one each month: https://db-ip.com/db/download/ip-to-city-lite) to
# /usr/share/GeoIP/dbip-city-lite.mmdb, the file Skald's `logs.city_db`
# (SKALD_CITY_DB=/geoip/dbip-city-lite.mmdb with -v /usr/share/GeoIP:/geoip:ro)
# reads. The country file's updater (update-dbip-country) does the same for
# dbip-country-lite.mmdb.
#
# On the server, as root (it is not run by Skald, and not from this repo):
#   install -m 0755 tools/update-dbip-city.sh /usr/local/sbin/update-dbip-city
#   echo '23 4 3 * * root /usr/local/sbin/update-dbip-city' > /etc/cron.d/dbip-city
#   /usr/local/sbin/update-dbip-city          # the first time, by hand
#
# This month's file, else last month's (early in a month the new one may not be
# out yet). The new file replaces the old one in a single rename, only when it
# unpacked whole and is a MaxMind file: a failed download keeps the old file.
# Skald reads the file again when its time changes; the credit "IP Geolocation
# by DB-IP" is shown wherever cities show. About 120 MB unpacked.
#
# GEOIP_DIR overrides the folder (a test, another layout). Needs curl, gzip and
# GNU date.
set -eu

DIR=${GEOIP_DIR:-/usr/share/GeoIP}
NAME=dbip-city-lite.mmdb
BASE=https://download.db-ip.com/free

this=$(date -u +%Y-%m)
last=$(date -u -d "$(date -u +%Y-%m-01) -1 month" +%Y-%m)

mkdir -p "$DIR"
tmp=$(mktemp "$DIR/.$NAME.XXXXXX")
trap 'rm -f "$tmp" "$tmp.gz"' EXIT

got=""
for month in "$this" "$last"; do
    if curl -fsS --retry 3 --max-time 900 -o "$tmp.gz" "$BASE/dbip-city-lite-$month.mmdb.gz"; then
        got=$month
        break
    fi
done
if [ -z "$got" ]; then
    echo "update-dbip-city: no file for $this or $last; the old file is kept" >&2
    exit 1
fi

gzip -dc "$tmp.gz" > "$tmp"
# A MaxMind file ends with its metadata, after this marker.
if ! tail -c 200000 "$tmp" | grep -q "MaxMind.com"; then
    echo "update-dbip-city: $got did not unpack to a MaxMind file; the old file is kept" >&2
    exit 1
fi
if [ "$(wc -c < "$tmp")" -lt 10000000 ]; then
    echo "update-dbip-city: $got is too small to be the whole file; the old file is kept" >&2
    exit 1
fi

chmod 0644 "$tmp"
mv -f "$tmp" "$DIR/$NAME"
echo "update-dbip-city: $DIR/$NAME is DB-IP's $got file"
