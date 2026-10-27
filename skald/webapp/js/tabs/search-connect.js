// Settings > Leads & tools > Search Console & Bing (P1-6): connecting Google Search Console and Bing
// Webmaster Tools from the dashboard, no shell. GET/POST <page>/integrations/search
// (skald/search/api.py).
//
//   The keys (install admins): the Google service-account key file, uploaded and
//   checked, kept on the server; afterwards only its email shows. The Bing API key,
//   write-only (its last four characters shown).
//   Per site, a wizard: A. give the service account read-only access in Search
//   Console (its email, the steps, text to send a client); B. find the properties
//   the key can see that cover this site's host names; C. test (the last 3 days,
//   never stored), choose the history to sync (none, 3 or 16 months) and connect.
//   Bing the same with its site address. Connected: when it last synced and syncs
//   next, the days stored, what is provisional, the history's progress (polled every
//   5 seconds while it runs), the last error in plain words, Sync now, Disconnect.

import { h, n } from "../ui.js";
import { call } from "./ipmanager.js";
import { time as tzTime } from "../tz.js";
import { copyable, field, input, status, confirmIn, why } from "./forms.js";

const BACKFILL = [[0, "No history: from today on"], [3, "The last 3 months"], [16, "All 16 months Search Console keeps"]];
const NAMES = { google: "Google Search Console", bing: "Bing Webmaster Tools" };
const POLL_MS = 5000;

async function copyText(btn, text) {
  try { await navigator.clipboard.writeText(text); btn.textContent = "Copied"; } catch { btn.textContent = "Select the text below and copy it"; }
  setTimeout(() => { btn.textContent = "Copy text to send"; }, 1800);
}

function ext(href, words) {
  return h("a", { href, target: "_blank", rel: "noopener noreferrer" }, words);
}

/* The Search Console & Bing tab of Settings > Leads & tools for one site. */
export function searchBox(site) {
  const box = h("section", { class: "s se-connect" }, h("h2", null, "Search: Google Search Console and Bing"),
    h("p", { class: "sub" }, "Queries, impressions, clicks and position come only from the search engines. Connect them once and Skald syncs their figures every 6 hours, shown under Traffic › Search beside its own."),
    h("p", { class: "empty" }, "Loading..."));
  const msg = status();
  let timer = null;
  const picked = { google: "", bing: "" };
  const tested = { google: "", bing: "" };

  const reload = () => call(`integrations/search?site=${encodeURIComponent(site)}`).then(draw);

  async function post(path, payload, done) {
    const r = await call(`integrations/search/${path}`, { site, ...payload });
    if (!r.ok) { msg.say(why(r)); return r; }
    if (done) msg.say(typeof done === "function" ? done(r) : done, true);
    return r;
  }

  // ------------------------------------------------------------ the keys

  function googleKey(k, admin) {
    const wrap = h("div", { class: "sheet integ" }, h("h3", null, "Google service-account key ",
      h("span", { class: `tf ${k.client_email ? "on" : k.problem ? "warn" : "off"}` }, k.client_email ? "in place" : k.problem ? "needs attention" : "not set")));
    if (k.problem) wrap.append(h("p", { class: "msg err" }, k.problem));
    if (k.client_email) {
      wrap.append(h("p", { class: "muted" }, "The service account's email, the one Search Console needs. The key itself stays on the server and is never shown."),
        copyable(k.client_email, "the service account's email"));
      if (k.where && k.where !== "uploaded") wrap.append(h("p", { class: "note" }, "Set on the server (its environment or a key file), so it is changed there."));
    }
    if (!admin) {
      if (!k.client_email) wrap.append(h("p", { class: "note" }, "An install admin uploads it: one key serves every site of the install."));
      return wrap;
    }
    const acts = h("div", { class: "acts" });
    if (k.set && (!k.where || k.where === "uploaded")) {
      const drawRm = () => {
        const rm = h("button", { type: "button", class: "btn danger" }, "Remove");
        rm.addEventListener("click", () => confirmIn(acts, "Remove the service-account key? Every site's Search Console sync stops until a key is uploaded again.", "Yes, remove",
          async () => { const r = await post("googleremove", {}, "The key is removed from the server."); if (r.ok) reload(); else drawRm(); }, drawRm));
        acts.replaceChildren(rm);
      };
      drawRm();
    }
    if (!k.where || k.where === "uploaded") {
      const file = h("input", { type: "file", accept: ".json,application/json" });
      const up = h("button", { type: "submit", class: "btn primary" }, k.set ? "Upload a new key" : "Upload key");
      const form = h("form", { class: "af-col", novalidate: true },
        field("Service-account key (.json)", file, "Google Cloud console › IAM & Admin › Service accounts › your account › Keys › Add key › JSON. Enable the Google Search Console API in the same project."), h("div", null, up));
      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const f = file.files?.[0];
        if (!f) { msg.say("Choose the key file first."); return; }
        if (f.size > 20000) { msg.say("That file is too big to be a service-account key."); return; }
        up.disabled = true;
        const text = await f.text();
        const r = await post("googlekey", { key: text }, (x) => `Key saved. Its email is ${x.client_email}.`);
        up.disabled = false;
        file.value = "";
        if (r.ok) reload();
      });
      wrap.append(form);
    }
    wrap.append(acts);
    return wrap;
  }

  function bingKey(k, admin) {
    const wrap = h("div", { class: "sheet integ" }, h("h3", null, "Bing API key ",
      h("span", { class: `tf ${k.set ? "on" : k.problem ? "warn" : "off"}` }, k.set ? `set${k.hint ? ` (${k.hint})` : ""}` : "not set")));
    if (k.problem) wrap.append(h("p", { class: "msg err" }, k.problem));
    if (!admin) {
      if (!k.set) wrap.append(h("p", { class: "note" }, "An install admin types it: one key serves every site of the install."));
      return wrap;
    }
    if (k.where && k.where !== "uploaded" && k.set) {
      wrap.append(h("p", { class: "note" }, "Set in the server's environment, so it is changed there."));
      return wrap;
    }
    const acts = h("div", { class: "acts" });
    const box = input({ type: "password", autocomplete: "off", maxlength: "64", placeholder: k.set ? "set: type to replace" : "not set" });
    const save = h("button", { type: "submit", class: "btn" }, "Save key");
    const form = h("form", { class: "af-row", novalidate: true }, field("API key", box, "Bing Webmaster Tools › Settings › API access › API key. Write-only: it is never shown again."), save);
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!box.value.trim()) { msg.say("Type the API key first."); box.focus(); return; }
      save.disabled = true;
      const r = await post("bingkey", { key: box.value.trim() }, "The Bing API key is saved. It is not shown again.");
      save.disabled = false;
      if (r.ok) { box.value = ""; reload(); }
    });
    if (k.set) {
      const drawRm = () => {
        const rm = h("button", { type: "button", class: "btn danger" }, "Remove");
        rm.addEventListener("click", () => confirmIn(acts, "Remove the Bing API key? Every site's Bing sync stops.", "Yes, remove",
          async () => { const r = await post("bingremove", {}, "The Bing API key is removed."); if (r.ok) reload(); else drawRm(); }, drawRm));
        acts.replaceChildren(rm);
      };
      drawRm();
    }
    wrap.append(form, acts);
    return wrap;
  }

  // ------------------------------------------------------------ connected

  function connected(e, part, r) {
    const st = part.status || {};
    const sum = part.summary || {};
    const lines = [];
    const when = [st.last_sync ? `Last synced ${tzTime(st.last_sync, { date: true })}` : "Not synced yet",
      st.next_sync ? `next ~${tzTime(st.next_sync, { date: true, label: false })}` : null].filter(Boolean).join(" · ");
    lines.push(h("p", null, h("strong", null, part.connected), h("br"), when));
    if (sum.days) lines.push(h("p", { class: "muted" }, `${n(sum.days)} day${sum.days === 1 ? "" : "s"} stored, ${sum.first} to ${sum.last}${sum.provisional ? `; ${n(sum.provisional)} provisional (the engine may still change them; each sync fetches them again)` : ""}.`));
    const b = st.backfill;
    if (b && (b.state === "queued" || b.state === "running")) lines.push(h("p", { class: "msg ok" }, `Syncing the history (${b.months} months): ${b.of ? `${n(b.done || 0)} of ${n(b.of)} weeks` : "starting"}...`));
    if (b && b.state === "failed") lines.push(h("p", { class: "msg err" }, `The history sync stopped: ${b.error || "no reason given"}`));
    if (b && b.state === "done") lines.push(h("p", { class: "muted" }, `History synced (${b.months} months).`));
    if (st.error) lines.push(h("p", { class: "msg err" }, `Failing${st.error_since ? ` since ${tzTime(st.error_since, { date: true })}` : ""}: ${st.error}${st.error_mailed ? " One mail was sent about it." : ""}`));
    if (st.audit && st.audit.ok === false) lines.push(h("p", { class: "msg err" }, `The second check found a difference: ${(st.audit.problems || []).slice(0, 2).join("; ")}.`));
    if (part.busy) lines.push(h("p", { class: "muted" }, "A sync is running now."));
    const acts = h("div", { class: "acts" });
    const drawActs = () => {
      const now = h("button", { type: "button", class: "btn", disabled: !!r.locked || part.busy }, "Sync now");
      now.addEventListener("click", async () => {
        now.disabled = true;
        const x = await post("sync", {}, `Syncing in the background. This page shows the result in a minute.`);
        if (x.ok) setTimeout(reload, 4000); else now.disabled = false;
      });
      const off = h("button", { type: "button", class: "btn danger", disabled: !!r.locked }, "Disconnect");
      off.addEventListener("click", () => confirmIn(acts, `Disconnect ${NAMES[e]} for ${site}? Syncing stops; the figures already synced stay.`, "Yes, disconnect",
        async () => { const x = await post("disconnect", { engine: e }, `${NAMES[e]} is disconnected. Its synced figures stay.`); if (x.ok) reload(); else drawActs(); }, drawActs));
      acts.replaceChildren(now, off);
    };
    drawActs();
    return [...lines, acts];
  }

  // ------------------------------------------------------------ the wizard

  function wizard(e, r) {
    const google = e === "google";
    const keyOk = google ? !!r.keys?.google?.client_email : !!r.keys?.bing?.set;
    const out = [];
    if (!keyOk) out.push(h("p", { class: "msg err" }, google ? "First the install's service-account key is needed (an install admin uploads it above)." : "First the install's Bing API key is needed (an install admin types it above)."));
    // Step A
    if (google) {
      const g = r.google_steps || {};
      const send = h("button", { type: "button", class: "btn" }, "Copy text to send");
      send.addEventListener("click", () => copyText(send, g.send_text || ""));
      out.push(h("div", { class: "se-step" }, h("h4", null, "1. Give Skald read-only access in Search Console"),
        g.email ? copyable(g.email, "the service account's email") : null,
        h("ol", null, (g.steps || []).map((x) => h("li", null, x))),
        h("p", null, ext(g.link || "https://search.google.com/search-console/users", "Open Search Console's Users and permissions")),
        h("p", { class: "muted" }, "A client's site: the client does this step in their own Search Console. Send them the text:"),
        h("div", { class: "acts" }, send),
        h("details", null, h("summary", null, "The text"), h("pre", { class: "se-send" }, g.send_text || ""))));
    } else {
      out.push(h("div", { class: "se-step" }, h("h4", null, "1. The site in Bing Webmaster Tools"),
        h("ol", null, [
          "Add and verify the site in Bing Webmaster Tools, under the account whose API key is set above.",
          "A client's site: the client adds that account as a user of their site, in Bing Webmaster Tools › Settings › User management.",
        ].map((x) => h("li", null, x))),
        h("p", null, ext(r.bing_link || "https://www.bing.com/webmasters/usermanagement", "Open Bing's user management"))));
    }
    // Step B
    const list = h("div", { class: "se-props" });
    const find = h("button", { type: "button", class: "btn", disabled: !keyOk }, google ? "Find my properties" : "Find my sites");
    const testBtn = h("button", { type: "button", class: "btn", disabled: !picked[e] }, "Test connection");
    const testSays = h("p", { class: "msg", role: "status", "aria-live": "polite" });
    const connectBtn = h("button", { type: "button", class: "btn primary", disabled: !(tested[e] && tested[e] === picked[e]) || !!r.locked }, "Connect");
    find.addEventListener("click", async () => {
      find.disabled = true;
      list.replaceChildren(h("p", { class: "muted" }, "Asking..."));
      const x = await call("integrations/search/properties", { site, engine: e });
      find.disabled = false;
      if (!x.ok) { list.replaceChildren(h("p", { class: "msg err" }, why(x))); return; }
      if (!(x.properties || []).length) { list.replaceChildren(h("p", { class: "msg err" }, x.hint || "None found.")); return; }
      list.replaceChildren(h("fieldset", { class: "af-set" }, h("legend", null, google ? "Properties for this site" : "Sites for this site"),
        x.properties.map((p) => {
          const radio = h("input", { type: "radio", name: `se-${e}`, value: p.siteUrl, checked: picked[e] === p.siteUrl });
          radio.addEventListener("change", () => { picked[e] = p.siteUrl; tested[e] = ""; testBtn.disabled = false; connectBtn.disabled = true; testSays.textContent = ""; });
          const kind = p.siteUrl.startsWith("sc-domain:") ? "Domain property: every address under it" : google ? "URL-prefix property" : (p.verified ? "verified" : "not verified yet");
          return h("label", { class: "chk" }, radio, h("span", null, h("b", null, p.siteUrl), h("small", null, `${kind}${p.permissionLevel ? ` · ${p.permissionLevel}` : ""}`)));
        })));
    });
    out.push(h("div", { class: "se-step" }, h("h4", null, google ? "2. Pick the property" : "2. Pick the site"),
      h("p", { class: "muted" }, `Only the ones that cover this site's host names${(r.hosts || []).length ? ` (${r.hosts.join(", ")})` : ""} are listed.`),
      h("div", { class: "acts" }, find), list));
    // Step C
    testBtn.addEventListener("click", async () => {
      testBtn.disabled = true;
      testSays.className = "msg";
      testSays.textContent = "Testing: reading the last days...";
      const x = await call("integrations/search/test", { site, engine: e, source: picked[e] });
      testBtn.disabled = false;
      if (!x.ok) { testSays.className = "msg err"; testSays.textContent = why(x); return; }
      tested[e] = picked[e];
      testSays.className = "msg ok";
      testSays.textContent = `OK: ${n(x.rows)} rows read, ${n(x.clicks)} clicks and ${n(x.impressions)} impressions over ${x.days?.length ? `${x.days[0]} to ${x.days[x.days.length - 1]}` : "the last days"}.${x.note ? ` ${x.note}` : ""} Nothing was stored.`;
      connectBtn.disabled = !!r.locked;
    });
    const months = google ? h("fieldset", { class: "af-set" }, h("legend", null, "History to sync now, in the background"),
      BACKFILL.map(([v, w]) => h("label", { class: "chk" }, h("input", { type: "radio", name: `se-bf-${e}`, value: String(v), checked: v === 3 }), h("span", null, w)))) : null;
    connectBtn.addEventListener("click", async () => {
      connectBtn.disabled = true;
      const m = google ? Number(months.querySelector("input:checked")?.value || 0) : 0;
      const x = await post("connect", { engine: e, source: picked[e], backfill_months: m },
        (y) => `Connected. ${y.started ? (m ? `Syncing ${m} months of history in the background.` : "The first sync runs in the background.") : "The first sync runs with the next scheduled one."} Then every 6 hours by itself.`);
      if (x.ok) reload(); else connectBtn.disabled = false;
    });
    out.push(h("div", { class: "se-step" }, h("h4", null, "3. Test and connect"),
      h("div", { class: "acts" }, testBtn), testSays, months, h("div", { class: "acts" }, connectBtn)));
    return out;
  }

  function engineCard(e, r) {
    const part = r.engines?.[e] || {};
    const badge = h("span", { class: `tf ${part.status?.error ? "warn" : part.connected ? "on" : "off"}` }, part.connected ? (part.status?.error ? "failing" : "connected") : "not connected");
    return h("div", { class: "sheet integ" }, h("h3", null, NAMES[e], " ", badge), ...(part.connected ? connected(e, part, r) : wizard(e, r)));
  }

  function draw(r) {
    clearTimeout(timer);
    const keep = [box.firstChild, box.children[1]];
    if (!r.ok) { box.replaceChildren(...keep, h("p", { class: "empty" }, why(r, "The search connection could not be loaded.")), msg); return; }
    box.replaceChildren(...keep,
      r.locked ? h("p", { class: "msg err" }, r.locked) : "",
      h("h3", { class: "se-h" }, r.install_admin ? "The keys (for every site of the install)" : "The keys"),
      googleKey(r.keys?.google || {}, r.install_admin), bingKey(r.keys?.bing || {}, r.install_admin),
      h("h3", { class: "se-h" }, `This site: ${r.site}`),
      engineCard("google", r), engineCard("bing", r), msg);
    // While a history sync is queued or running, look again every few seconds.
    const running = Object.values(r.engines || {}).some((p) => ["queued", "running"].includes(p.status?.backfill?.state));
    if (running) timer = setTimeout(() => { if (box.isConnected) reload(); }, POLL_MS);
  }

  reload();
  return box;
}
