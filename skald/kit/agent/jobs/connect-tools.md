## Step __N__. Connect the user's own tools (Google Analytics...)

Skald can show figures from the user's OWN marketing tools beside its own, in a separate
"From your tools" area, each figure labelled with the tool's name. It reads them with the
user's own key to each tool's free API, read-only where the tool allows it. It never mixes
them into its own counts and never calls an AI model with them.

**Check first.** What Skald had for __SITE__ when this line was made:

__TOOLS_NOW__

A tool that says "answering" is done already. Change only what is missing.

### 1. Find what the project has (names only)

Look in the site's project and on its server, without opening a value: `.env`, `.env.local`,
`.env.production`, `.env.example`, the hosting's environment settings, `docker-compose.yml`,
and key files (`*.json` that `GOOGLE_APPLICATION_CREDENTIALS` names). Use commands that print
**names only**, such as `grep -ho '^[A-Z0-9_]*' .env* 2>/dev/null | sort -u`. Never `cat` a
`.env` file or a key file, never print a value, never paste one into this chat.

What to look for, per tool:

__TOOLS_FIND__

### 2. List it and ask, one tool at a time

Tell the user, in one short list, what you found for each tool: the variable's or file's
**name** (never its value), and what is missing. Then ask about each key **on its own**, and
wait for the answer before you send it. For example:

"I found `GA4_PROPERTY_ID` and a Google key file named by `GOOGLE_APPLICATION_CREDENTIALS`.
May I send that key to your Skald, so it can read Google Analytics figures for __SITE__? It
needs Viewer (read-only) access on the property. Skald keeps it on its own server, private."

A "no" means: skip that tool, and report it as `skipped`. Prefer a read-only key: if the only
key you found can also change things in the tool, say so and ask whether the user would rather
make a read-only one (each tool below says how).

### 3. Send each key the user agreed to

Skald takes a key only from stdin, never from a command line, a file it can read, or a
chat. Each command below reads the report key from `__ENV_FILE__` into a header, and the
key from a file or a pipe. Then remove any key file you made.

__TOOLS_SEND__

Skald's answers:

- **HTTP 200:** `{"ok": true, "tool": ..., "who": ...}`. "who" is the key's robot address or
  account (never the key). Skald asks the tool within the hour and every 6 hours after.
- **HTTP 409:** Skald has a key for this tool already, and keeps it. Do not replace it unless
  the user asks you to: then add `&replace=1` to the address.
- **HTTP 400:** the key is not one the tool takes, or an option is wrong: Skald's words say
  which (they hold no secret). Tell the user.
- **HTTP 403:** this line may not set keys (it was not made by whoever runs Skald). Put the
  tool in `left_for_user`: "Paste the key in Skald, Settings > Leads & tools > Connect a
  tool" (__DASHBOARD__#settings/site/leads).

### 4. The one click left for the user

A tool whose key is a robot (a Google service account) needs the user to give that robot
read access in the tool itself. Each tool above says where. Put those clicks, with the
robot address filled in, in the report's `left_for_user`.

Report each tool as `your_tools`: `[{"tool": "ga4", "key": "sent"}]`, where `key` is `sent`
(Skald took it now), `already` (Skald had it), `left` (the user does it), or `skipped` (the
user said no, or the site does not use the tool).
