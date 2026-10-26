// Settings > Connections: "Read your figures (API)" and "Connect an AI
// assistant (MCP)". Each dialog makes its token (tokens/create, team_api.py;
// shown once, kept in this page's memory only), shows what to paste where,
// and tests it from this browser: the API's overview file, or MCP's
// initialize and tools/list (skald/mcp/http.py: one JSON answer per
// POST, Authorization: Bearer, no session id).

import { h } from "../ui.js";
import { call } from "./ipmanager.js";
import { input, field, why } from "./forms.js";
import { DEMO } from "../demo.js";
import { apiWords, mcpWords } from "./conn-words.js";
import { wizard, codeBlock, answerBox, helpLink, steps } from "./conn-ui.js";

const today = () => new Date().toISOString().slice(0, 10);
const MADE = new Map();          // "api:<site>" | "mcp:<site>" -> {token, name}: this page's memory only

function tokenMaker(st, kind, { label, scopes, withPrivate = false }) {
  const slot = h("div");
  const name = input({ name: `${kind}-token-name`, autocomplete: "off", maxlength: "60" });
  name.value = `${label}: ${st.site}, ${today()}`;
  const priv = h("input", { type: "checkbox", name: "private" });
  priv.checked = false;
  const make = h("button", { type: "button", class: "btn primary" }, "Make the token");
  const said = h("p", { class: "msg", role: "status", "aria-live": "polite" });
  const show = () => {
    const got = MADE.get(`${kind}:${st.site}`);
    if (!got) { slot.replaceChildren(); return; }
    st.token = got.token;
    slot.replaceChildren(h("div", { class: "state ok", role: "status" }, h("div", null,
      h("p", null, h("strong", null, `"${got.name}". `), "Copy it now: it is shown only this once."),
      codeBlock(got.token, "the new token"))));
  };
  make.addEventListener("click", async () => {
    if (!name.value.trim()) { said.textContent = "Give the token a name first."; said.className = "msg err"; return; }
    make.disabled = true;
    const want = [...scopes, ...(withPrivate && priv.checked ? ["read_private"] : [])];
    const r = await call("tokens/create", { name: name.value.trim(), sites: [st.site], scopes: want });
    make.disabled = false;
    if (!r.ok || !r.token) { said.textContent = why(r, "The token was not made."); said.className = "msg err"; return; }
    MADE.set(`${kind}:${st.site}`, { token: r.token, name: name.value.trim() });
    said.textContent = "";
    show();
  });
  show();
  return [field("Name", name, "What uses it, so Your tokens says whose it is."),
    withPrivate ? h("label", { class: "chk" }, priv, h("span", null, h("b", null, "Can also read visitor addresses"),
      h("small", null, "The request log and AI activity hold visitors' IP addresses. Leave it off unless a script needs them."))) : null,
    h("div", { class: "acts" }, make), said, slot,
    h("p", { class: "note" }, `For ${st.site} only. Already have one? Press Next and put it where you see <token>.`)];
}

// The token the test uses: the one just made, else one pasted here.
function testToken(st) {
  const box = input({ name: "test-token", autocomplete: "off", placeholder: "skald_..." });
  box.value = st.token || "";
  return { box, get: () => box.value.trim() };
}

// ------------------------------------------------------------------- API

export async function testApi(origin, site, token, fetcher = fetch) {
  if (DEMO.on) return { kind: "bad", head: "The demo has no server to test." };
  let res;
  try {
    res = await fetcher(`${origin}/traffic-api/v1/${site}/overview`, { headers: { Authorization: `Bearer ${token}` }, credentials: "omit", cache: "no-store" });
  } catch {
    return { kind: "bad", head: apiWords(0) };
  }
  if (res.status !== 200) return { kind: "bad", head: apiWords(res.status) };
  let data = null;
  try { data = await res.json(); } catch { /* not JSON */ }
  const keys = data && typeof data === "object" ? Object.keys(data).slice(0, 3) : [];
  return { kind: "ok", head: `${apiWords(200)}${keys.length ? ` The answer starts with: ${keys.join(", ")}.` : ""}` };
}

export function apiDialog(site, data = {}, { onClose = null, route = null, start = 0 } = {}) {
  const origin = String(data.api_base || "").replace(/\/traffic-api\/v1\/?$/, "") || location.origin;
  const st = { site, token: "" };
  const base = `${origin}/traffic-api/v1/${site}/`;
  const files = h("div", { class: "api-files" }, h("p", { class: "empty" }, "Loading the list..."));
  const loadFiles = () => call("api/v1/").then((r) => {
    if (!r.ok || !Array.isArray(r.files)) { files.replaceChildren(h("p", { class: "empty" }, r.missing ? "The API is not switched on for this page yet." : r.error)); return; }
    files.replaceChildren(...r.files.map((name) => h("span", { class: "api-f" }, name)));
  });
  return wizard({ route, start,
    title: "Read your figures (API)", subtitle: "Every figure these pages show, as JSON, for a script or a spreadsheet. Read-only.", key: "conn-api", state: st, onClose,
    steps: [
      { name: "Token", draw: () => [h("p", null, "A token reads; it can change nothing."), ...tokenMaker(st, "api", { label: "Reading figures", scopes: ["read"], withPrivate: true })] },
      { name: "Use it", draw: () => { loadFiles(); return [
        h("p", null, "The base address. Add a file's name to it:"), codeBlock(base, "the base address"),
        h("p", null, "With curl:"), codeBlock(`curl -H "Authorization: Bearer ${st.token || "<token>"}" ${base}overview`, "the curl command"),
        h("h4", null, "Files this site serves"), h("p", { class: "sub" }, "Each is described in the data contract; they are rewritten every 2 minutes."), files,
        h("p", { class: "note" }, "Answers: 200 with the file; 401 for a missing, wrong or revoked token, or one for another site; 404 for a file this site does not have. ", helpLink("api", "The API guide"), " has more examples.")]; } },
      { name: "Test", draw: () => {
        const t = testToken(st);
        const out = h("div");
        const btn = h("button", { type: "button", class: "btn primary" }, "Test");
        btn.addEventListener("click", async () => {
          if (!t.get()) { out.replaceChildren(answerBox("bad", "Paste a token first.")); return; }
          btn.disabled = true;
          const v = await testApi(location.origin, site, t.get());
          btn.disabled = false;
          out.replaceChildren(answerBox(v.kind, v.head));
        });
        return [h("p", null, `This browser asks for ${base}overview with the token, as a script would.`), field("Token", t.box), h("div", { class: "acts" }, btn), out];
      } },
    ],
  });
}

// ------------------------------------------------------------------- MCP

export async function testMcp(url, token, fetcher = fetch) {
  if (DEMO.on) return { kind: "bad", head: "The demo has no server to test." };
  const post = async (id, method, params) => {
    const res = await fetcher(url, { method: "POST", credentials: "omit", cache: "no-store",
      headers: { "Content-Type": "application/json", Accept: "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ jsonrpc: "2.0", id, method, params }) });
    let data = null;
    try { data = await res.json(); } catch { /* not JSON */ }
    return { status: res.status, data };
  };
  try {
    const init = await post(1, "initialize", { protocolVersion: "2025-06-18", capabilities: {}, clientInfo: { name: "skald-connections-test", version: "1" } });
    if (init.status !== 200 || !init.data || init.data.error) return { kind: "bad", head: mcpWords(init.status, init.data?.error?.message || init.data?.error) };
    const list = await post(2, "tools/list", {});
    if (list.status !== 200 || !list.data || list.data.error) return { kind: "bad", head: mcpWords(list.status, list.data?.error?.message) };
    const n = (list.data.result?.tools || []).length;
    return { kind: "ok", head: `Connected: ${n} tools.`, server: init.data.result?.serverInfo?.name || "" };
  } catch {
    return { kind: "bad", head: mcpWords(0) };
  }
}

/* The MCP guide (docs/help/mcp.md), as a clear button at the top of the dialog (2.39, the
   owner: "there is no documentation link"). It opens in a new tab, so the dialog stays. */
export function mcpGuideButton() {
  const href = `${location.pathname || "/"}#help?part=mcp`;
  return h("div", { class: "cn-guide" }, h("a", { class: "btn", href, target: "_blank", rel: "noopener", "aria-label": "Read the MCP guide (opens in a new tab)" }, "Read the MCP guide"),
    h("small", null, "Every step for Claude Code, Claude Desktop, ChatGPT and other assistants, and what each tool answers."));
}

export function mcpDialog(site, data = {}, { onClose = null, route = null, start = 0, wrap = null } = {}) {
  const url = data.mcp_url || `${location.origin}/traffic-mcp`;
  const st = { site, token: "" };
  const tok = () => st.token || "<token>";
  return wizard({ route, start, wrap, top: mcpGuideButton(),
    title: "Connect an AI assistant (MCP)", subtitle: "Ask Claude, ChatGPT or another assistant about your traffic in plain words.", key: "conn-mcp", state: st, onClose,
    steps: [
      { name: "Token", draw: () => [
        data.mcp_enabled === false ? answerBox("bad", "MCP is not switched on here.", h("p", null, "Ask whoever runs your Skald server to turn it on (mcp.enabled; on Docker, SKALD_MCP=true). You can make the token now.")) : null,
        h("p", null, "The assistant uses this token to read this site's figures. It cannot change anything."),
        ...tokenMaker(st, "mcp", { label: "AI assistant", scopes: ["mcp"] })] },
      { name: "Connect", draw: () => [
        h("p", null, "The MCP address:"), codeBlock(url, "the MCP address"),
        h("h4", null, "Claude Code"), h("p", null, "Run this in a terminal, then type /mcp in Claude Code:"),
        codeBlock(`claude mcp add --transport http skald ${url} --header "Authorization: Bearer ${tok()}"`, "the Claude Code command"),
        h("h4", null, "Claude Desktop"),
        steps("Settings > Developer > Edit Config opens claude_desktop_config.json.", "Add this (it needs Node.js, for mcp-remote), save, and restart Claude Desktop:"),
        codeBlock(JSON.stringify({ mcpServers: { skald: { command: "npx", args: ["mcp-remote", url, "--header", "Authorization:${SKALD_AUTH}"], env: { SKALD_AUTH: `Bearer ${tok()}` } } } }, null, 2), "the Claude Desktop config"),
        h("h4", null, "ChatGPT"),
        h("p", null, "The ChatGPT app's connectors ask for OAuth or no sign-in, so they cannot send the token yet. Through the OpenAI API, a developer adds Skald as a remote MCP server with the address above and the header ", h("code", null, `Authorization: Bearer ${tok()}`), "."),
        h("p", { class: "note" }, "Other clients: any that speaks Streamable HTTP and sends a custom header. ", helpLink("mcp", "The MCP guide"), " has every step.")] },
      { name: "Test", draw: () => {
        const t = testToken(st);
        const out = h("div");
        const btn = h("button", { type: "button", class: "btn primary" }, "Test");
        btn.addEventListener("click", async () => {
          if (!t.get()) { out.replaceChildren(answerBox("bad", "Paste a token first.")); return; }
          btn.disabled = true;
          const v = await testMcp(`${location.origin}/traffic-mcp`, t.get());
          btn.disabled = false;
          out.replaceChildren(answerBox(v.kind, v.head));
        });
        return [h("p", null, "This browser starts an MCP session with the token and lists the tools, as an assistant would."), field("Token", t.box), h("div", { class: "acts" }, btn), out];
      } },
    ],
  });
}
