## Step __N__. Report each to-do to Skald

1. Tell the user, in short plain sentences, per to-do: what you changed and where (file paths,
   never a secret), what you checked (`curl` answers), and what is left for them and why.
2. Send Skald one report per to-do. It says what you did, with the exact change as text, so
   the user sees it in Skald beside the to-do:

   - `id`: the to-do's id (__IDS__)
   - `state`: `done` (every row is handled: changed, already fine, or "gone" with the user's
     yes), `partly` (some rows: the rest are in `left`) or `left` (nothing changed: say why)
   - `change`: the exact change, as text: the redirect lines you added, the rule, or `git diff`
     (at most 200,000 characters)
   - `files`: the files you changed (paths), `left`: the rows not handled, each
     `{"row": "<path or page>", "why": "<one short reason>"}`, `notes`: anything else, in one
     or two plain sentences. No secret in any of them.

   Put the change in a text file first (for example `__ENV_DIR__/__SITE__.change.txt`), and
   the rows left, one per line as `<path><TAB><why>`, in another (`__ENV_DIR__/__SITE__.left.tsv`,
   empty when none). Then build the report with python3, so every character is quoted right,
   and send it. Put the to-do's id, the state and your notes in place of the words in `<...>`:

       python3 -c 'import json,sys; L=[l.rstrip("\n").split("\t",1) for l in open(sys.argv[4]) if l.strip()]; print(json.dumps({"id": sys.argv[1], "state": sys.argv[2], "change": open(sys.argv[3]).read(), "left": [{"row": a[0], "why": (a[1:] or [""])[0]} for a in L], "notes": sys.argv[5]}))' '<id>' '<state>' __ENV_DIR__/__SITE__.change.txt __ENV_DIR__/__SITE__.left.tsv '<notes>' > __ENV_DIR__/__SITE__.fix.json
       grep '^SKALD_REPORT_KEY=' __ENV_FILE__ | sed 's/^SKALD_REPORT_KEY=/X-Skald-Report-Key: /' | curl -sS -X POST -H @- -H 'Content-Type: application/json' --data-binary @__ENV_DIR__/__SITE__.fix.json -w '\nHTTP %{http_code}\n' '__FIX_URL__'

   - **HTTP 200:** Skald answers `{"ok": true, ...}` and says what it did. A `done` report
     marks the to-do done in Skald: Skald then checks it with the same measure on every whole
     day after (for old pages: are the same addresses still answering "not found"?), and the
     user can undo the mark with one click. It changes no figure.
   - **Anything else:** show Skald's words; they hold no secret. Fix what they say and send again.

   You can send a newer report for the same to-do until the code expires; the newest one counts.
3. When the user is happy, ask whether to delete the files you made in `__ENV_DIR__/` for
   __SITE__ (the keys file, the rows, the change and the report).

Help: __HELP__
