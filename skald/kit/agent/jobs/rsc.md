## Step __N__. Add the Next.js log field

Next.js opens pages inside the site without a page request, so Skald counts them only when the
web server's log line also writes one request header, `Next-Router-Prefetch`.

**Check first.**

- Is the site built with Next.js (`"next"` in `package.json`)? If not, this job does not
  apply: report it as `skipped`.
- Is it served by its own nginx or Apache? On Vercel, Netlify or Cloudflare the log carries no
  request header and there is nothing to add: report it as `skipped` and say why.
- Is the field there already? `sudo grep -rn 'rsc_prefetch' /etc/nginx/` (Apache:
  `/etc/apache2/` or `/etc/httpd/`). If the site's own log line holds it, the job is done
  already.

Then ask the user: "Next.js sites need one field added to the web server's log line, so Skald
counts the pages opened inside the site. It only adds one request header's value to what the
log already writes: no new port, route or access. May I add it?" With their yes:

- nginx: back up the file, then end the site's `log_format` with
  ` rsc_prefetch=$http_next_router_prefetch`. Run `sudo nginx -t`; reload
  (`sudo systemctl reload nginx`) only when the test passes.
- Apache: end the site's `LogFormat` with ` rsc_prefetch=%{Next-Router-Prefetch}i`, run
  `sudo apachectl configtest`, then reload.
- If the server's nginx also serves other sites, change only this site's log line. If the
  site uses nginx's built-in `combined` format, add a `log_format` of its own (the same
  fields, then the new one) and point only this site's `access_log` at it.

Check: open a page of the site, then `sudo tail -n 3 <the site's access log>`: the newest
lines end with `rsc_prefetch=`. Without the user's yes, tell them it is missing and leave
it (report `left`). Put `nextjs_log_field` and the web server in the report.
