// Settings > Integrations (accounts, access.mode: sessions): the script tag
// to copy, each tool's incoming hook (its address, its secret made or
// rotated here and shown once, or, for a tool that makes its own signing
// secret (Stripe, HubSpot), pasted here write-only; a signed test event;
// Remove, which deletes the secret; the last 50 deliveries),
// and outgoing webhooks: Skald posts a signed summary of each conversion to
// the owner's CRM, Zapier or Slack. For admins; install admins may pick any
// site of the install. GET/POST <page>/integrations (integrations_api.py).

import { h } from "../ui.js";
import { call } from "./ipmanager.js";
import { isViewer, sessions, VIEWER } from "../access.js";
import { head1, copyable, field, input, status, confirmIn, when, why } from "./forms.js";
import { howTo } from "./help.js";

const EVENT_WORDS = {
  "conversion.started": "an action started (a form or booking opened)",
  "conversion.completed": "an action completed (a form sent, a demo booked, a payment)",
  "conversion.cancelled": "a booking cancelled",
  "conversion.rescheduled": "a booking moved",
  "conversion.no_show": "a booked call nobody came to",
  "conversion.abandoned": "started and not finished within the abandon window",
  "lead.won": "a lead marked won",
  "lead.lost": "a lead marked lost",
};
const OUTCOME = { recorded: "kept", duplicate: "already had it", ignored: "not a conversion", test: "test, read and not kept", test_failed: "test refused", bad_signature: "bad signature", bad_body: "not readable", too_large: "too large", no_length: "no length", rate_limited: "too many", error: "error" };

// A secret just made: kept in this page's memory only, until it is copied.
let fresh = null;
let chosen = "";

function deliveriesTable(rows, caption, cols) {
  if (!rows.length) return h("p", { class: "empty" }, "No deliveries yet.");
  return h("div", { class: "scroll" }, h("table", null, h("caption", { class: "vh" }, caption),
    h("thead", null, h("tr", null, cols.map(([t, , cls]) => h("th", { scope: "col", class: cls === "n" ? "n" : null }, t)))),
    h("tbody", null, rows.map((r) => h("tr", null, cols.map(([, get, cls]) => h("td", { class: cls || null }, get(r))))))));
}

function scriptBox(r) {
  const sc = r.script || {};
  const consent = h("input", { type: "checkbox" });
  const share = h("input", { type: "checkbox" });
  const accept = h("input", { type: "checkbox" });
  const links = input({ placeholder: "app.example.net, shop.example.org", maxlength: "300", autocomplete: "off" });
  const out = h("div");
  const draw = () => {
    const extra = [];
    if (consent.checked) extra.push('data-consent="required"');
    if (share.checked) extra.push('data-share-subdomains="true"');
    if (accept.checked) extra.push('data-accept-id="true"');
    const domains = links.value.split(/[\s,]+/).filter((d) => /^[a-z0-9.-]+$/i.test(d));
    if (domains.length) extra.push(`data-link-domains="${domains.join(",")}"`);
    const tag = `<script src="${sc.src || "/traffic-js/skald.js"}" data-site="${r.site}"${extra.length ? ` ${extra.join(" ")}` : ""} defer></script>`;
    out.replaceChildren(copyable(tag, "the script tag"));
  };
  [consent, share, accept].forEach((c) => c.addEventListener("change", draw));
  links.addEventListener("input", draw);
  draw();
  return h("section", { class: "s" }, h("h2", null, "The script tag"),
    h("p", { class: "sub" }, "One line in every page's <head>: page views, form steps, phone and email clicks, and Calendly, Cal.com and HubSpot booking embeds. It loads from your own site, never a third party."),
    out,
    h("div", { class: "af-col" },
      h("label", { class: "chk" }, consent, h("span", null, h("b", null, "Wait for consent"), h("small", null, "send nothing and keep no ID until the page calls skald('consent', true)"))),
      h("label", { class: "chk" }, share, h("span", null, h("b", null, "Share across subdomains"), h("small", null, "www. and app. see the same anonymous ID (a first-party cookie)"))),
      field("Other domains you own", links, "Links to them carry the anonymous ID (?skv=), so a visit there joins the journey."),
      h("label", { class: "chk" }, accept, h("span", null, h("b", null, "Accept the ID from your other domains"), h("small", null, "on this site, take a ?skv= ID a link brought, keep it and take it out of the address. Without this, it is taken only from a domain listed above")))),
    howTo("tracking-script", "How do I add the script tag, and what does it track?"),
    h("p", { class: "note" }, sc.visitor_ids
      ? "Anonymous visitor IDs are on for this site: journeys and abandoned actions are counted."
      : "Anonymous visitor IDs are off for this site (beacon.visitor_ids in the config): the tag sends events, but journeys and abandoned actions need the IDs on."));
}

export default function integrations() {
  const title = head1("Integrations", "The script tag, incoming hooks and outgoing webhooks.");
  if (!sessions()) return [title, h("div", { class: "state" }, h("div", null, "Integrations are set up here with accounts. On this server, use skald hooks secret and docs/INTEGRATIONS.md."))];
  if (isViewer()) return [title, h("div", { class: "state" }, h("div", null, `${VIEWER} Integrations are for admins.`))];
  const body = h("div", null, h("p", { class: "empty" }, "Loading the integrations..."));
  const msg = status();
  const shown = h("div");
  const reload = () => call(`integrations${chosen ? `?site=${encodeURIComponent(chosen)}` : ""}`).then(draw);

  function showFresh() {
    if (!fresh) { shown.replaceChildren(); return; }
    const done = h("button", { type: "button", class: "btn" }, "I have copied it");
    done.addEventListener("click", () => { fresh = null; shown.replaceChildren(); });
    shown.replaceChildren(h("div", { class: "state ok acct-link", role: "status" }, h("div", null,
      h("p", null, h("strong", null, `${fresh.what}. `), "Copy it now: it is shown only this once. A new secret replaces the old one at once."),
      copyable(fresh.secret, "the secret"), fresh.url ? copyable(fresh.url, "the address") : null, h("div", { class: "acts" }, done))));
    shown.scrollIntoView({ block: "nearest" });
  }

  async function act(path, payload, done) {
    const r = await call(`integrations/${path}`, { site: chosen, ...payload });
    if (!r.ok) { msg.say(why(r)); return r; }
    if (r.secret) { fresh = { secret: r.secret, url: r.url, what: done }; showFresh(); msg.say(""); } else msg.say(done, true);
    reload();
    return r;
  }

  function toolRow(t) {
    const acts = h("div", { class: "acts" });
    const drawActs = () => {
      let make = null;
      if (t.make !== false) {
        make = h("button", { type: "button", class: "btn", disabled: !t.rotatable }, t.set ? "Rotate secret" : "Make secret");
        if (!t.rotatable) make.title = "This secret is set in the server's environment.";
        make.addEventListener("click", () => {
          if (!t.set) { act("secret", { tool: t.tool }, `The secret for ${t.name}`); return; }
          confirmIn(acts, `Rotate the secret for ${t.name}? The tool must be given the new one.`, "Yes, rotate", () => act("secret", { tool: t.tool }, `The new secret for ${t.name}`), drawActs);
        });
      }
      // Remove: the secret goes, so the address refuses further deliveries; the log stays.
      let rm = null;
      if (t.set && t.rotatable) {
        rm = h("button", { type: "button", class: "btn danger" }, "Remove");
        rm.addEventListener("click", () => confirmIn(acts, `Remove the ${t.name} hook? Its secret is deleted and further deliveries are refused. Past deliveries and conversions stay.`, "Yes, remove", () => act("hooks/remove", { tool: t.tool }, `${t.name}: removed. Its address now refuses deliveries.`), drawActs));
      }
      const test = h("button", { type: "button", class: "btn", disabled: !t.set }, "Send a test event");
      test.addEventListener("click", async () => {
        test.disabled = true;
        const r = await call("integrations/test", { site: chosen, tool: t.tool });
        test.disabled = false;
        if (!r.ok) { msg.say(why(r)); return; }
        const a = r.answer || {};
        msg.say(r.status === 200 ? `${t.name}: the test was signed, received and read (${a.records ?? 0} record${a.records === 1 ? "" : "s"}); nothing was kept.` : `${t.name}: the receiver answered ${r.status}: ${a.error || "refused"}.`, r.status === 200);
        reload();
      });
      acts.replaceChildren(...[make, test, rm].filter(Boolean));
    };
    drawActs();
    const badge = h("span", { class: `tf ${t.set ? "on" : "off"}` }, t.set ? (t.where === "env" ? `set (environment ${t.env})` : "secret set") : "no secret");
    const log = h("details", null, h("summary", null, `Last deliveries (${t.deliveries.length})`),
      deliveriesTable(t.deliveries, `Deliveries from ${t.name}`, [
        ["When", (d) => when(d.received_at, ""), "muted"], ["Answer", (d) => String(d.http_status), "n"],
        ["Outcome", (d) => OUTCOME[d.outcome] || d.outcome], ["Detail", (d) => d.error || "", "muted"]]));
    return h("div", { class: "sheet integ" }, h("h3", null, t.name, " ", badge),
      t.problem ? h("p", { class: "msg err" }, t.problem) : null, copyable(t.url, `the address for ${t.name}`),
      t.paste && t.rotatable ? pasteForm(t) : null, acts, log);
  }

  // A signing secret the tool made (Stripe, HubSpot; Calendly, Cal.com and Typeform
  // may give their own): typed in once, sent to the server, never shown again.
  function pasteForm(t) {
    const box = input({ type: "password", autocomplete: "off", maxlength: "500", placeholder: t.set ? "set: paste to replace" : "not set" });
    const save = h("button", { type: "submit", class: "btn" }, "Save secret");
    const hint = t.make === false ? `${t.name} makes its own signing secret; Skald cannot make one for it. Write-only: it is never shown again.` : `Or use Make secret and give that to ${t.name}. Write-only: it is never shown again.`;
    const form = h("form", { class: "af-row", novalidate: true }, field(`Paste the signing secret from ${t.secret_from || t.name}`, box, hint), save);
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!box.value.trim()) { msg.say(`Paste the signing secret from ${t.secret_from || t.name} first.`); box.focus(); return; }
      save.disabled = true;
      const r = await act("hooks/paste", { tool: t.tool, secret: box.value }, `${t.name}: the signing secret is saved. It is not shown again.`);
      save.disabled = false;
      if (r.ok) box.value = "";
    });
    return form;
  }

  function hookRow(w) {
    const acts = h("div", { class: "acts" });
    const drawActs = () => {
      const test = h("button", { type: "button", class: "btn" }, "Send a test");
      test.addEventListener("click", async () => {
        test.disabled = true;
        const r = await call("integrations/webhooks/test", { site: chosen, id: w.id });
        test.disabled = false;
        if (!r.ok) { msg.say(why(r)); return; }
        const res = r.result || {};
        msg.say(res.state === "sent" ? `Sent: the address answered ${res.http_status}.` : `Not delivered: ${String(res.error || "refused").replace(/\.+$/, "")}.`, res.state === "sent");
        reload();
      });
      const rot = h("button", { type: "button", class: "btn" }, "Rotate secret");
      rot.addEventListener("click", () => confirmIn(acts, "Rotate this webhook's secret? Your receiver must check the new one.", "Yes, rotate", () => act("webhooks/rotate", { id: w.id }, "The webhook's new secret"), drawActs));
      const rm = h("button", { type: "button", class: "btn danger" }, "Remove");
      rm.addEventListener("click", () => confirmIn(acts, "Remove this webhook? Nothing more is sent to it.", "Yes, remove", () => act("webhooks/remove", { id: w.id }, "Removed."), drawActs));
      acts.replaceChildren(test, rot, rm);
    };
    drawActs();
    const log = h("details", null, h("summary", null, `Last deliveries (${w.deliveries.length})`),
      deliveriesTable(w.deliveries, "Outgoing deliveries", [
        ["Made", (d) => when(d.created_at, ""), "muted"], ["Event", (d) => d.event],
        ["State", (d) => (d.state === "pending" ? `waiting, try ${d.attempts + 1} at ${when(d.next_at, "")}` : d.state)],
        ["Answer", (d) => (d.http_status == null ? "" : String(d.http_status)), "n"], ["Detail", (d) => d.error || "", "muted"]]));
    return h("div", { class: "sheet integ" }, h("h3", { class: "path" }, w.url),
      h("p", { class: "muted" }, `${w.events.join(", ")}. Added ${when(w.created_at, "")}${w.created_by ? ` by ${w.created_by}` : ""}.`), acts, log);
  }

  function addForm(r) {
    const url = input({ type: "url", placeholder: "https://hooks.example.com/skald", maxlength: "500", autocomplete: "off", inputmode: "url" });
    const boxes = (r.events || []).map((e) => h("label", { class: "chk" }, h("input", { type: "checkbox", value: e, checked: e === "conversion.completed" || e === "lead.won" }), h("span", null, h("b", null, e), h("small", null, EVENT_WORDS[e] || ""))));
    const add = h("button", { type: "submit", class: "btn primary" }, "Add webhook");
    const form = h("form", { class: "af-col", novalidate: true }, field("Address", url, "https only. Skald signs each POST: X-Skald-Signature: t=<time>,v1=<HMAC-SHA256 of \"<t>.<body>\">."),
      h("fieldset", { class: "af-set" }, h("legend", null, "Events"), boxes), h("div", null, add));
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const events = boxes.map((l) => l.querySelector("input")).filter((c) => c.checked).map((c) => c.value);
      if (!url.value.trim()) { msg.say("Give the address first."); url.focus(); return; }
      if (!events.length) { msg.say("Choose at least one event."); return; }
      add.disabled = true;
      const got = await act("webhooks/add", { url: url.value.trim(), events }, "The new webhook's secret");
      add.disabled = false;
      if (got.ok) url.value = "";
    });
    return h("div", { class: "sheet" }, h("h3", null, "Add an outgoing webhook"), form);
  }

  function draw(r) {
    if (!r.ok) { body.replaceChildren(h("p", { class: "empty" }, why(r, "The integrations could not be loaded."))); return; }
    chosen = r.site;
    const pick = (r.sites || []).length > 1 ? h("select", { "aria-label": "Site" }, r.sites.map((s) => h("option", { value: s, selected: s === r.site }, s))) : null;
    if (pick) pick.addEventListener("change", () => { chosen = pick.value; fresh = null; showFresh(); msg.say(""); reload(); });
    body.replaceChildren(
      pick ? h("section", { class: "s" }, field("Site", pick, r.install_admin ? "As an install admin you may set up any site." : "The sites of your organisation.")) : "",
      r.locked ? h("p", { class: "msg err" }, r.locked) : "",
      scriptBox(r),
      h("section", { class: "s" }, h("h2", null, "Incoming hooks"),
        h("p", { class: "sub" }, "Your site's server and the tools you use tell Skald what happened: a booking, a payment, a form. Give each tool its address and its secret; Stripe and HubSpot make their own secret, which you paste here. The Webhooks guide says where in each tool."),
        howTo("webhooks", "How do I connect Calendly, Cal.com, HubSpot, Typeform, Stripe, Zapier or my own site?"),
        r.takes_hooks ? null : h("p", { class: "msg err" }, "This install does not report on this site yet, so its hooks are not answered."),
        (r.tools || []).map(toolRow)),
      h("section", { class: "s" }, h("h2", null, "Outgoing webhooks"),
        h("p", { class: "sub" }, "Skald posts a signed summary of each conversion to your CRM, Zapier or Slack: the action, its source, campaign, landing page, country, device, visits and time before converting, and the anonymous journey. Never a name or an email. A failed delivery is tried again for about 15 hours."),
        (r.webhooks || []).length ? r.webhooks.map(hookRow) : h("p", { class: "empty" }, "No outgoing webhooks yet."),
        howTo("webhooks", "How do I send each conversion to my CRM, Zapier or Slack?"),
        addForm(r)));
  }

  showFresh();
  reload();
  return [title, shown, body, msg];
}
