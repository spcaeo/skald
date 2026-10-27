// Settings › This site (v2): Data and Site. Each tab shows the state and one action; what it is
// for is behind the "?" (settings-frame.js), the rest folds under "More options".
//
//   Data › Send logs        whether visits arrive, and "Connect the log" (Who will do it?,
//                           setup-finish.js, for the logs line); the log file under More options
//   Data › Script tag       the tag, visitor IDs and the goals (integrations.js, prefs.js)
//   Data › What counts      page assets, not pages; Next.js pages opened inside the site
//   Data › Test a sample    paste a few lines of a log (conn=sample, conn-sample.js)
//   Site › Names & time     host names, page groups, time zone, logo (prefs.js)
//   Site › Internal traffic ours.js

import { h } from "../ui.js";
import { sessions, isViewer, VIEWER } from "../access.js";
import { DEMO } from "../demo.js";
import { checkItems, keptItems, mayManage, openFinish } from "./checklist.js";
import { connOpener } from "./connections.js";
import { sites as siteCards } from "./prefs.js";
import { moreOptions } from "./forms.js";
import { integrationsPart } from "./integrations.js";
import { primary, statusRow, quietButton, quietLine } from "./set-ui.js";

const more = moreOptions;
const KIND = { done: ["good", "Working"], todo: ["warn", "To do"], wait: ["warn", "Waiting"], unknown: ["off", "Not checked"] };

/* Why this reader sees no button, or null when they may act. */
function cannot(basic = "On this server, the site's log is read where the config file says.") {
  if (DEMO.on) return h("p", { class: "note" }, "In the demo, setting up needs a running Skald.");
  if (!sessions()) return h("div", { class: "state" }, h("div", null, basic));
  if (isViewer()) return h("p", { class: "note" }, `${VIEWER} An admin sets this up.`);
  return null;
}

/* A set-up line as a row with its pill; while it is open, the page's one primary (Who will do
   it? for that line); once done, a quiet Change on the row. */
export function lineCard(m, act, { title, button, again, iconName = "server", basic = undefined }) {
  const slot = h("div", { class: "set-line" });
  const draw = (items) => {
    const i = items.find((x) => x.id === act) || { state: "unknown", says: "" };
    const [kind, word] = KIND[i.state] || KIND.unknown;
    const no = cannot(basic);
    const run = () => openFinish(m, items, { only: act, onDone: () => checkItems(m, true).then(draw) });
    const done = i.state === "done";
    const change = no || !done ? null : quietButton(again, run);
    if (change) change.classList.add("set-go");
    const go = no || done ? null : primary(button, run, { iconName: "next" });
    if (go) go.classList.add("set-go");
    slot.replaceChildren(...[h("section", { class: "s set-rows" }, h("div", { class: "set-list" },
      statusRow({ iconName, title, line: i.says, kind, word, action: change }))), go, no].filter(Boolean));
  };
  const kept = keptItems(m);
  draw(kept || []);
  if (mayManage() || DEMO.on) checkItems(m).then(draw);
  return slot;
}

/* Data › Send logs. */
export function dataLogs(m) {
  return [lineCard(m, "logs", { title: "Your server's log", button: "Connect the log", again: "Change how visits arrive" }),
    more(siteCards(m, "logs", { bare: true }))];
}

/* Data › Script tag & goals. */
export function dataScript(m) {
  return [lineCard(m, "script", { title: "The script tag", button: "Add the script tag", again: "Change", iconName: "code" }),
    siteCards(m, "script", { bare: true }), more(...integrationsPart("script").slice(1))];
}

/* Data › What counts. */
export function dataCounting(m) {
  const rsc = mayManage() && !DEMO.on ? h("section", { class: "s set-card" }, h("h2", null, "Next.js pages opened inside the site"),
    h("div", { class: "acts" }, h("button", { type: "button", class: "btn", onclick: async () => { const { openSetup } = await import("./setup-dialogs.js"); openSetup("rsc", m.site, {}); } }, "Set it up"))) : null;
  return [siteCards(m, "counting", { bare: true }), more(rsc)];
}

/* Data › Test a sample. */
export function dataSample(m) {
  const no = cannot();
  const go = no ? null : primary("Paste a sample", connOpener("sample", m.site), { iconName: "terminal" });
  if (go) go.classList.add("set-go");
  return [go, quietLine("Will Skald read your log?", "Paste a few lines of it: Skald says what it would count, and keeps nothing."), no];
}

/* Site › Names & time. */
export const siteDetails = (m) => siteCards(m, "details");
