## Step __N__. Take the keys, once

Take them even when every job turns out to be done already: the report at the end needs the
report key that is in the file.

In a shell on the machine where you run the commands. The keys can be taken once, so first
check that you have not taken them already:

    grep -qs '^SKALD_REPORT_KEY=' __ENV_FILE__.part && mv __ENV_FILE__.part __ENV_FILE__; test -s __ENV_FILE__ && echo "the keys file is there: use it, do not fetch again" || echo "no keys file yet"

If the keys file is there, skip to the end of this step. Else take the keys, in one line. It
puts the file in place only when it holds the keys:

    umask 077 && mkdir -p ~/.config/skald && curl -sS -o __ENV_FILE__.part -w 'HTTP %{http_code}\n' '__KEYS_URL__' && grep -q '^SKALD_REPORT_KEY=' __ENV_FILE__.part && mv __ENV_FILE__.part __ENV_FILE__

- **HTTP 200:** the keys are in `__ENV_FILE__`. Do not print it.
  Check the names only: `cut -d= -f1 __ENV_FILE__`. It holds __KEY_NAMES__.
- **Anything else:** the `.part` file holds only Skald's words, no key. Show them and remove
  it: `cat __ENV_FILE__.part && rm __ENV_FILE__.part`. HTTP 410 means the keys were taken
  already, or the code expired or was cancelled: ask the user to make a new line in Skald
  (__DASHBOARD__) and start again.
