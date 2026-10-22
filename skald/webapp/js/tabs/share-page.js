// The page a "Share with your developer" link opens (/traffic-auth/setup/<id>,
// share_api.py): one task's steps for one site, with no sign-in. The same
// steps as the dialog (conn-install.js), the secret shown once on request,
// and the Test. The lead hook adds the body and the signed examples of the
// guide "Send leads from your backend in 5 minutes", with this site's address.
// The Next.js task (nextjs) shows the log_format line of setup-nextjs.js and a
// Test that polls the doctor's Next.js line (share_page.next_status).

import { h } from "../ui.js";
import { installFor } from "./conn-install.js";
import { testPanel, troubleTable } from "./conn-send.js";
import { codeBlock, answerBox, steps } from "./conn-ui.js";
import { guideParts, hookSteps } from "./setup-hook.js";
import { nextStepsNodes, nextTest } from "./setup-nextjs.js";

const TITLES = { send: "Send this site's visits to Skald", script: "Add the script tag", hook: "Send leads from the site's backend", nextjs: "Count pages opened inside the site" };

async function getJSON(url, body) {
  try {
    const res = await fetch(url, body ? { method: "POST", credentials: "omit", cache: "no-store", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
      : { credentials: "omit", cache: "no-store" });
    let data = null;
    try { data = await res.json(); } catch { /* not JSON */ }
    return data && typeof data === "object" ? { ...data, ok: res.ok && data.ok !== false, status: res.status } : { ok: false, status: res.status, error: `Refused (${res.status}).` };
  } catch {
    return { ok: false, status: 0, error: "Skald's server could not be reached." };
  }
}

// The secret, shown once: a sending token or a hook secret, made when pressed.
function secretBox(info, base, onSecret) {
  if (!info.secret) return null;
  if (info.shown) return answerBox("wait", info.shown_words || "The secret was shown already. Ask for a new link.");
  const out = h("div");
  const btn = h("button", { type: "button", class: "btn primary" }, "Show the secret");
  btn.addEventListener("click", async () => {
    btn.disabled = true;
    const r = await getJSON(`${base}/reveal`, {});
    if (!r.ok || !r.secret) { out.replaceChildren(answerBox("bad", r.error || "The secret could not be shown.")); return; }
    out.replaceChildren(answerBox("ok", `The ${r.kind}. Copy it now: this page does not show it again.`, codeBlock(r.secret, `the ${r.kind}`),
      h("p", { class: "note" }, info.task === "hook" ? "Keep it in an environment variable on the backend, such as SKALD_HOOK_SECRET. Never in the code, never in the browser." : "The steps below have it filled in.")));
    btn.remove();
    onSecret(r.secret);
  });
  return h("section", { class: "s" }, h("h2", null, `The ${info.secret}`),
    h("p", null, `It is made when you press the button, and shown only once. ${info.task === "hook" ? "An older secret for this hook stops working then." : "It can only send log lines for this one site."}`),
    h("div", { class: "acts" }, btn), out);
}

function hookTest(base) {
  const out = h("div");
  const send = h("button", { type: "button", class: "btn primary" }, "Send a test lead");
  const look = h("button", { type: "button", class: "btn" }, "Check the last deliveries");
  send.addEventListener("click", async () => {
    send.disabled = true;
    const r = await getJSON(`${base}/test`, {});
    send.disabled = false;
    out.replaceChildren(r.ok ? answerBox(r.status === 200 || r.status === 202 ? "ok" : "bad", `Skald answered ${r.status}${r.status < 300 ? ": the hook works. A test lead is never counted." : "."}`)
      : answerBox("bad", r.error || "The test was not sent."));
  });
  look.addEventListener("click", async () => {
    const r = await getJSON(`${base}/status`);
    if (!r.ok) { out.replaceChildren(answerBox("bad", r.error || "Could not check.")); return; }
    const rows = r.deliveries || [];
    out.replaceChildren(answerBox(rows.length ? "ok" : "wait", r.words || (rows.length ? "Deliveries arrive." : "Nothing has arrived yet."),
      rows.length ? h("ul", null, rows.map((d) => h("li", null, `${d.received_at}: ${d.outcome} (${d.http_status})${d.error ? `, ${d.error}` : ""}`))) : null));
  });
  return h("section", { class: "s" }, h("h2", null, "Test"), h("p", null, "Send a signed test lead from Skald itself, marked as a test, or check what your backend's posts got."),
    h("div", { class: "acts" }, send, look), out);
}

// "29 Oct 2026, 16:17 UTC" for the link's end, never the raw stamp.
export function until(stamp) {
  const t = new Date(stamp);
  if (Number.isNaN(t.getTime())) return String(stamp || "");
  return `${t.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" })}, ${t.toISOString().slice(11, 16)} UTC`;
}

export async function draw(root, id) {
  const base = `/traffic-auth/setup/${id}`;
  const info = await getJSON(`${base}/info`);
  if (!info.ok) { root.replaceChildren(h("h1", null, "This link does not work any more"), h("p", null, info.error || "Ask for a new link.")); return; }
  const st = { site: info.site, method: info.task === "script" ? "script" : info.method, token: "", base: info.base, url: info.send_url,
    kit: info.kit, kitUrl: `${base}/kit`, tokenHint: "Press Show the secret above: the steps then have the token filled in." };
  const stepsSlot = h("div", { class: "cn-step" });
  const fill = () => {
    if (info.task === "nextjs") {
      stepsSlot.replaceChildren(h("p", null, "The site is built with Next.js. A page opened by a link inside it sends no page request, only Next.js's data request, which Next.js also sends for links it prefetches. This one line lets Skald tell the two apart."),
        ...nextStepsNodes());
      return;
    }
    if (info.task === "hook") {
      const how = hookSteps(info.method, info.hook_url, "<the secret above>");
      stepsSlot.replaceChildren(h("h3", null, "The address"), codeBlock(info.hook_url, "the hook address"),
        steps(...how.lines), how.code ? codeBlock(how.code, "the example") : "");
      if (info.method === "lead" || info.method === "json") guideParts(info.hook_url).then((parts) => stepsSlot.append(h("h3", null, "The body, and examples in curl, Node, Python and PHP"), ...parts));
      return;
    }
    stepsSlot.replaceChildren(...installFor(st.method, st));
  };
  fill();
  const head = [h("h1", null, `${TITLES[info.task] || "Set-up steps"}: ${info.site}`),
    h("p", { class: "sub" }, `A private page with only these steps. It works until ${until(info.expires_at)}.`)];
  const test = info.task === "hook" ? hookTest(base) : info.task === "nextjs"
    ? h("section", { class: "s" }, h("h2", null, "Test"), h("p", null, "After the reload, open the site and click a link to another page. Then press Test: Skald looks at the log's newest lines every 5 seconds, for up to 2 minutes."),
      nextTest(() => getJSON(`${base}/status`)))
    : h("section", { class: "s" }, h("h2", null, "Test"),
    testPanel(st, { statusOf: () => getJSON(`${base}/status`), pageCheck: null }), troubleTable());   // the page check needs a session
  root.replaceChildren(...head, secretBox(info, base, (secret) => { if (info.task === "send") { st.token = secret; fill(); } }) || "",
    h("section", { class: "s" }, h("h2", null, "Steps"), stepsSlot), test,
    info.task === "send" ? steps("If something seems wrong on the server, run sudo bash check.sh from the kit, and send its last block to whoever gave you this link.") : "");
}

const root = typeof document !== "undefined" ? document.getElementById("share") : null;
if (root && root.getAttribute("data-id")) draw(root, root.getAttribute("data-id"));
