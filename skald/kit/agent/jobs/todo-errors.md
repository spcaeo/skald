## Step __N__. Server errors: find the failing route and fix it

The to-do "Fix the server errors": these addresses answered a server error (5xx) to whoever
asked. The rows: __ROWS__. Each row has `path` and `errors` (how many 5xx answers), most first.
`(all others)` is the rest added up: not an address.

**Check first:** does each address still fail? One GET each, at most 20 addresses, never a
POST, never a burst:

    curl -s -o /dev/null -w '%{http_code}\n' 'https://__SITE__<path>'

A row that answers 200, 301, 404 or 410 now is not failing any more: count it as fixed, and say
so. For the rows that still fail:

1. **Find why.** The server's error log (`/var/log/nginx/error.log`, the site's own log), the
   app's log (`journalctl -u <service> --since today`, `docker logs <container>`, `vercel logs`,
   the host's log page). Look for the path and the time.
2. **Find the code.** The route or page that serves the path in this repository. Read the stack
   trace and the code; find the cause.
3. **Fix the cause** with the smallest change that fixes it, and run the project's tests. Never
   hide an error (an empty 200, a catch-all 404) unless the path is something the site should
   not serve at all (a probe for a file the site never had): then ask the user first.
4. **Not in this code** (another service, a plugin, the host, a path no code serves, a bot's
   probe): change nothing. Put the row in `left`, with what you found.

Deploy only with the user's yes. Afterwards, the same `curl` for each fixed row. Your diff (or
the lines you changed, with their file) goes in the report as `change`. When you only found the
cause, the state is `left` and `notes` says what you found: that is useful too.
