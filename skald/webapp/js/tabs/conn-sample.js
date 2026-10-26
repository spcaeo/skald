// Settings > Collect data > Send logs: "Test a sample" (2.35), the dry run of a log source.
// Paste up to MAX_LINES lines of a log (a server's access log, or a CDN or host
// export); POST <page>/sites/trylog {site, text, format} (connections_api.try_sample,
// skald/try_log.py) reads them with Skald's own readers, judged with the
// site's settings, and answers a report. Nothing is stored on the server.
//
// In the address: conn=sample&step=1|2 (js/overlays.js), and the chosen reader as
// lfmt=<format> (absent: Detect it). The pasted lines never go in the address (they
// hold visitors' IP addresses): they stay in this page's memory only (PASTED), so a
// link or a reload at step 2 opens step 1 to paste again. The report never holds a
// raw line: unreadable lines are named by number, IP addresses in hosts or paths are
// masked by the server.
//
// Copy and open (owner, 2026-10-25): every page path has both icons (withUrl); a host,
// a format name, a reason, a warning and the command have the copy icon (withCopy,
// codeBlock).

import { h, n } from "../ui.js";
import * as S from "../state.js";
import { call } from "./ipmanager.js";
import { field, why } from "./forms.js";
import { wizard, answerBox, codeBlock, helpLink } from "./conn-ui.js";
import { withUrl, withCopy } from "../urlactions.js";

// The readers, as try_log.FORMATS lists them (tests/js/conn-sample.mjs checks the two match).
export const FORMATS = ["auto", "akamai_json", "apache_combined", "caddy_json", "cloudflare_json",
  "cloudfront_w3c", "edge_json", "fastly_json", "netlify_json", "nginx_combined", "nginx_extended", "vercel_json"];
export const FORMAT_NAMES = {
  auto: "Detect it (auto)", nginx_extended: "nginx, Skald's extended layout", nginx_combined: "nginx combined",
  apache_combined: "Apache combined", caddy_json: "Caddy (JSON)", cloudflare_json: "Cloudflare Logpush (JSON)",
  edge_json: "Skald's Cloudflare Worker (JSON)", cloudfront_w3c: "CloudFront standard log", fastly_json: "Fastly (JSON)",
  akamai_json: "Akamai DataStream 2 (JSON)", vercel_json: "Vercel log drain (JSON)", netlify_json: "Netlify log drain (JSON)",
};
export const MAX_LINES = 200;
export const MAX_BYTES = 256 * 1024;

const PASTED = new Map();      // site -> the pasted text: this page's memory only, never the address
const SURE = { sure: "sure", likely: "likely", unsure: "not sure", none: "no reader fits", chosen: "chosen by you" };
const KIND = { ok: "ok", warn: "warn", bad: "bad" };

/* How many content lines a paste holds, and whether it is over the limits. */
export function measure(text) {
  const t = String(text || "");
  const lines = t.split(/\r?\n/).filter((x) => x.trim()).length;
  return { lines, bytes: new Blob([t]).size, over: new Blob([t]).size > MAX_BYTES };
}

const copyable = (text, label = null) => withCopy(h("span", null, text), text, { label });
const code = (text) => withCopy(h("code", null, text), text);
const plural = (v, one, many) => `${n(v)} ${v === 1 ? one : many}`;
const when = (iso) => String(iso || "").replace("T", " ").replace(/\.\d+/, "");

/* The report as nodes: the answer, then one block per question. */
export function reportView(r, site) {
  if (!r) return [answerBox("bad", "No report yet. Go back and paste some lines.")];
  const out = [answerBox(KIND[r.verdict] || "warn", r.headline)];
  const f = r.format || {};
  const some = (f.candidates || []).filter((c) => c.read);
  out.push(h("h4", null, "Format"),
    h("p", null, f.picked ? [code(f.picked), ` ${FORMAT_NAMES[f.picked] ? `(${FORMAT_NAMES[f.picked]}), ` : ""}${SURE[f.sure] || f.sure}.`] : "No reader takes these lines."),
    some.length ? h("p", { class: "sub" }, "Lines read by each reader: ", some.map((c, i) => [i ? ", " : "", code(c.format), ` ${n(c.read)}`]),
      some.length < (f.candidates || []).length ? `; the other ${(f.candidates || []).length - some.length} read none.` : ".") : null);
  out.push(h("h4", null, "Lines"), h("p", null, `${n(r.lines)} lines: ${n(r.read || 0)} read, ${n(r.unread || 0)} could not be read.`));
  if ((r.reasons || []).length) {
    out.push(h("ul", { class: "cn-list ts-why" }, r.reasons.map((x) => h("li", null, `${n(x.lines)} `, copyable(x.why, "the reason"),
      h("small", null, ` (line ${x.examples.join(", ")})`)))));
  }
  if (r.times) {
    out.push(h("h4", null, "Times"), h("p", null, `${when(r.times.first)} to ${when(r.times.last)}. Time zone in the lines: ${r.times.zones.join(", ")}; the site's zone: `,
      copyable(r.times.site_zone, "the time zone"), "."));
  }
  if ((r.hosts || []).length || r.no_host) {
    out.push(h("h4", null, "Hosts"), h("ul", { class: "cn-list ts-hosts" },
      (r.hosts || []).map((x) => h("li", null, x.host.startsWith("(") ? x.host : copyable(x.host, "the host"),
        ` ${n(x.lines)}${x.site == null ? "" : x.site ? " (this site)" : " (another host)"}`)),
      r.no_host ? h("li", null, `No host field: ${n(r.no_host)}`) : null));
  }
  const c = r.counted;
  if (c) {
    out.push(h("h4", null, `Skald's five groups, for ${site}`),
      h("table", { class: "ts-groups" }, h("thead", null, h("tr", null, h("th", { scope: "col" }, "Group"), h("th", { scope: "col", class: "num" }, "Requests"), h("th", { scope: "col" }, ""))),
        h("tbody", null, r.groups.map((g) => h("tr", null, h("th", { scope: "row" }, g.label), h("td", { class: "num" }, n(g.requests)),
          h("td", null, g.group === "people" ? `${plural(g.views, "page view", "page views")}, ${plural(g.readers, "reader", "readers")}` : ""))))),
      h("p", { class: c.adds_up ? "sub" : "msg err" }, `${r.groups.map((g) => n(g.requests)).join(" + ")} = ${n(c.groups_sum)}: ${c.adds_up ? "adds up" : "does not add up"}. `,
        `${n(c.lines)} lines = ${n(c.site_requests)} for the site`, c.other_hosts ? ` + ${n(c.other_hosts)} for other hosts` : "",
        ` + ${n(c.unreadable)} unreadable`, c.duplicates ? ` + ${n(c.duplicates)} repeated request ids` : "", "."));
  }
  if ((r.pages || []).length) {
    out.push(h("h4", null, "The pages people viewed most"), h("ul", { class: "cn-list ts-pages" },
      r.pages.map((p) => h("li", null, withUrl(h("code", null, p.path), p.path), ` ${plural(p.views, "view", "views")}`))));
  } else if (c) out.push(h("p", { class: "note" }, "No page view by a person in the sample."));
  for (const [title, items] of [["Warnings", r.warnings], ["Notes", r.notes]]) {
    if ((items || []).length) out.push(h("h4", null, title), h("ul", { class: "cn-list" }, items.map((x) => h("li", null, copyable(x, title === "Warnings" ? "the warning" : "the note")))));
  }
  out.push(h("p", { class: "note" }, "This tests the first lines only. On the server, the same test reads a whole file:"),
    codeBlock(`skald try-log <the log file> --site ${site}`, "the try-log command"),
    h("p", { class: "note" }, helpLink("connections", "The Connections guide"), " (Test a sample of a log) says what each warning means."));
  return out;
}

function picker(st, w) {
  const sel = h("select", { name: "format", "aria-label": "Which reader" },
    FORMATS.map((x) => h("option", { value: x, selected: x === st.fmt ? true : null }, FORMAT_NAMES[x] || x)));
  sel.value = st.fmt;
  sel.addEventListener("change", () => { st.fmt = sel.value; w.keep({ lfmt: st.fmt === "auto" ? "" : st.fmt }); });
  return field("Format", sel, "Detect it tries every reader and keeps the one that reads the most lines.");
}

function pasteStep(st) {
  return {
    name: "Paste", title: "Paste some lines of the log",
    check: () => (PASTED.get(st.site)?.trim() ? "" : "Paste some lines of the log first."),
    draw: (w) => {
      const box = h("textarea", { name: "sample", rows: "12", spellcheck: "false", autocomplete: "off", class: "ts-box",
        "aria-label": "Lines of the log", placeholder: "Paste the first lines of the access log or the export here" });
      box.value = PASTED.get(st.site) || "";
      const count = h("p", { class: "sub", "aria-live": "polite" });
      const show = () => {
        const m = measure(box.value);
        count.textContent = m.over ? `Too long: paste at most ${MAX_BYTES / 1024} KB.`
          : `${n(m.lines)} lines${m.lines > MAX_LINES ? `: the first ${MAX_LINES} are tested` : ""}.`;
      };
      box.addEventListener("input", () => { PASTED.set(st.site, box.value); show(); });
      show();
      return [h("p", null, `Paste up to ${MAX_LINES} lines of the log you want Skald to read for ${st.site}: a server's access log, or a Cloudflare, CloudFront, Fastly, Akamai, Vercel or Netlify export. Skald reads them and says what a daily run would count. Nothing is stored.`),
        picker(st, w), field("Lines", box), count,
        h("p", { class: "note" }, "The lines stay in this browser and are sent once to this Skald for the test. They are not kept, and never go in the page address.")];
    },
    next: async (w) => {
      const text = PASTED.get(st.site) || "";
      if (measure(text).over) { w.say(`Too long: paste at most ${MAX_BYTES / 1024} KB.`); return false; }
      const r = await call("sites/trylog", { site: st.site, text, format: st.fmt });
      if (!r.ok || !r.report) { w.say(why(r, "The test did not run.")); return false; }
      st.report = r.report;
      return true;
    },
  };
}

export function sampleDialog(site, data = {}, { onClose = null, route = null } = {}) {
  const asked = S.read().lfmt || "";
  const st = { site, fmt: FORMATS.includes(asked) ? asked : "auto", report: null };
  const steps = [pasteStep(st),
    { name: "Report", title: "What Skald would count", draw: () => reportView(st.report, site) }];
  // A link or a reload at step 2 has no report in memory (`start` is not used): step 1 again.
  return wizard({ route, start: 0, title: "Test a sample of a log", key: "conn-sample", state: st, onClose, done: "Close",
    subtitle: "Can Skald read this log source? Find out before the next daily run.", steps });
}
