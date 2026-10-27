## Step __N__. Report

1. Tell the user, in short plain sentences: what each job came to (done now, done already,
   skipped and why, or left for them), which files you changed (paths), which secret settings
   you set (names only, never the values), what the checks showed, and anything left for
   them to do.
2. Send the same to Skald, so the user's set-up page shows it. No secret goes in it. Skald
   takes it only with the report key from the keys file (this needs curl 7.55 or newer). The key goes into curl as a header
   through a pipe (`-H @-`), so it is never on a command line, in a file, or shown. One
   command (leave out a field you do not know; no single quote inside the JSON):

       grep '^SKALD_REPORT_KEY=' __ENV_FILE__ | sed 's/^SKALD_REPORT_KEY=/X-Skald-Report-Key: /' | curl -sS -X POST -H @- -H 'Content-Type: application/json' --data '__REPORT_EXAMPLE__' '__REPORT_URL__'

   `jobs` says what each job of this line came to: `done` (you did it now), `already` (Check
   first found it done), `skipped` (it does not apply to this site: say why in `notes`) or
   `left` (the user must do it: say what in `left_for_user`).
<!-- if lead -->
   `tools` lists each booking, form or payment tool the site uses: `set` when its webhook
   now reaches Skald, `left` when the user still has to make it.
<!-- end -->
   Skald answers `{"ok": true}`. It keeps only these fields (`notes` at most 1000
   characters, `asset_paths` at most 10), and you can send it again until the code expires.
3. When everything works, ask the user whether to delete `__ENV_FILE__` (and any copy on a
   server) and the other files in `~/.config/skald/` you made for __SITE__: the keys are now
   kept where they are used.
__INVITES_DONE__
Help: __HELP__
