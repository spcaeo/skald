## Step __N__. Connect the user's AI assistant to Skald (MCP)

Skald's MCP server lets the user ask their AI assistant about the site's traffic in plain
words. The token for it is `SKALD_MCP_TOKEN` in the keys file: it reads this one site's
figures only, sees no visitor addresses, and can change nothing.
__MCP_STATE__
**Check first.** Is Skald connected already? Claude Code: `claude mcp list` (or
`claude mcp get skald`). Cursor: `~/.cursor/mcp.json`. Claude Desktop:
`claude_desktop_config.json` (Settings > Developer > Edit Config). If one holds a `skald`
server with the address `__MCP_URL__`, ask the user whether it works; if it does, this job is
done already.

Ask the user which assistant to connect if it is not the one you run in, then, with their yes:

- **Claude Code** (one command; the token goes in through the environment, never shown, and
  into the user's own settings, never into a file of the site's repository):

      ( set -a; . __ENV_FILE__; set +a; claude mcp add --transport http --scope user skald "$SKALD_MCP_URL" --header "Authorization: Bearer $SKALD_MCP_TOKEN" )

- **Claude Desktop** needs the helper `mcp-remote` (Node.js). Add to its config, under
  `mcpServers`, a `skald` entry: `"command": "npx"`, `"args": ["mcp-remote",
  "__MCP_URL__", "--header", "Authorization:${SKALD_AUTH}"]` and `"env": {"SKALD_AUTH":
  "Bearer <SKALD_MCP_TOKEN>"}`. Write the token into that file from the keys file without
  showing it, or let the user paste it themselves; then they restart Claude Desktop.
- **Another client** (Cursor, Codex...): any that speaks Streamable HTTP and sends a custom
  header. Use its user-level settings, never a file in the site's repository, with the
  address above and the header `Authorization: Bearer <SKALD_MCP_TOKEN>`.

Check: Skald answers its tools to the token (the header goes through a pipe, never shown):

    grep '^SKALD_MCP_TOKEN=' __ENV_FILE__ | sed 's/^SKALD_MCP_TOKEN=/Authorization: Bearer /' | curl -sS -X POST -H @- -H 'Content-Type: application/json' --data '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}' '__MCP_URL__'

The answer lists Skald's tools. In Claude Code, `/mcp` then shows `skald` connected.
