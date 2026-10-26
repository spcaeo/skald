// Settings > Site details > Logo (2.6.0; logo_api.py, site_logos.py): the site's
// logo at the three sizes it is shown (picker, menu, browser tab), what the
// site itself gave and when it is asked again, and where the logo comes
// from - the site (automatic), an upload, or the first letter on one of four
// colours (also what shows while there is none). Saving the choice and the
// colour goes through settings/save (audited there); an upload through
// logo/upload, which also makes "upload" the choice; "Check the site again
// now" through logo/check, at most once a minute. Owners and admins change
// it; everyone else sees it, with the reason.

import { h } from "../ui.js";
import { call } from "./ipmanager.js";
import { status, when, why } from "./forms.js";
import { tile, letterOf } from "../logo.js";

const COLOR_NAME = { "#1d4ed8": "blue", "#0f766e": "teal", "#9a6400": "amber", "#17212b": "ink" };
const TYPES = ".png,.svg,.ico,image/png,image/svg+xml,image/x-icon,image/vnd.microsoft.icon";
let said = null;                   // the words to say again after the card is drawn anew

const days = (ts) => Math.max(0, Math.round((Date.parse(ts) - Date.now()) / 86400000));

export default function logoCard(m) {
  const box = h("section", { class: "sheet acct-card logo-card", "aria-labelledby": "logo-h" },
    h("h2", { id: "logo-h" }, "Logo"), h("p", { class: "sub" }, "Shown on the site picker, in the menu, in the site switcher and on the browser tab."),
    h("p", { class: "empty" }, "Loading the logo..."));
  const load = () => call("logo/state").then((r) => draw(r));
  function draw(r) {
    const head = [...box.children].slice(0, 2);
    if (!r.ok) { box.replaceChildren(...head, h("p", { class: "note" }, why(r, "The logo settings could not be loaded."))); return; }
    box.replaceChildren(...head, ...body(m, r, load));
  }
  load();
  return box;
}

function body(m, r, reload) {
  const ro = !r.editable;
  const msg = status();
  if (said) { msg.say(said[0], said[1]); said = null; }
  let source = r.source, color = r.color, file = null, picked = null;   // picked: a data: URL of the chosen file
  const src = (which, sha) => `logo?src=${which}&v=${sha}`;
  const shown = () => {
    if (source === "upload" && picked) return { url: picked, letter: r.letter, color };
    if (source === "upload" && r.upload) return { url: src("upload", r.upload.sha), letter: r.letter, color };
    if (source !== "letter" && r.found) return { url: src("fetched", r.found.sha), letter: r.letter, color };
    return { url: null, letter: r.letter || letterOf(m.site), color };
  };
  const previews = h("div", { class: "lg-sizes" });
  const paint = () => {
    const l = shown();
    previews.replaceChildren(
      h("span", { role: "img", "aria-label": "The logo on the site picker" }, tile(l, 64)),
      h("span", { role: "img", "aria-label": "The logo in the menu" }, tile(l, 34)),
      h("span", { role: "img", "aria-label": "The logo on the browser tab" }, tile(l, 16)));
    choices.forEach(([k, el]) => el.classList.toggle("on", k === source));
  };

  const found = r.found
    ? [h("b", null, "Found on the site"), h("small", null, `${r.found.url} · checked ${when(r.checked_at)}${r.next_check ? ` · next check in ${days(r.next_check)} day${days(r.next_check) === 1 ? "" : "s"}` : ""}`)]
    : [h("b", null, r.checked_at ? "Nothing found on the site" : "Not asked yet"),
      h("small", null, r.checked_at ? `${r.error || "no icon"} · checked ${when(r.checked_at)}` : `Skald asks ${r.hosts?.[0] || "the site"} in the next morning run, or now with the button below.`)];

  // The three choices, each a bordered row with its radio.
  const radio = (k) => {
    const el = h("input", { type: "radio", name: "logo-src", value: k, checked: k === source, disabled: ro });
    el.addEventListener("change", () => { source = k; paint(); });
    return el;
  };
  const fileIn = h("input", { type: "file", accept: TYPES, class: "vh", tabindex: "-1", "aria-hidden": "true", disabled: ro });
  const pick = h("button", { type: "button", class: "btn", disabled: ro }, "Choose a file…");
  const picked1 = h("small", { class: "lg-file" }, r.upload ? `Uploaded: ${r.upload.kind.toUpperCase()}${r.upload.size ? `, ${r.upload.size.join(" × ")}` : ""}, ${when(r.upload.at)}` : "");
  pick.addEventListener("click", () => fileIn.click());
  fileIn.addEventListener("change", () => {
    const f = fileIn.files?.[0];
    if (!f) return;
    if (f.size > (r.max_kb || 256) * 1024) { msg.say(`The file is over ${r.max_kb || 256} KB.`); fileIn.value = ""; return; }
    const reader = new FileReader();
    reader.onload = () => { file = f; picked = String(reader.result); source = "upload"; up.checked = true; picked1.textContent = `Chosen: ${f.name}. Save to use it.`; paint(); };
    reader.readAsDataURL(f);
  });
  const swatches = h("span", { class: "lg-colors", role: "radiogroup", "aria-label": "The letter's colour" }, (r.colors || []).map((c) => {
    const b = h("button", { type: "button", role: "radio", "aria-checked": String(c === color), "aria-label": COLOR_NAME[c] || c, disabled: ro, class: "lg-sw" },
      tile({ url: null, letter: r.letter, color: c }, 34));
    b.addEventListener("click", () => {
      color = c;
      swatches.querySelectorAll(".lg-sw").forEach((x) => x.setAttribute("aria-checked", String(x === b)));
      if (source !== "letter") { source = "letter"; lt.checked = true; }
      paint();
    });
    return b;
  }));
  const auto = radio("auto"), up = radio("upload"), lt = radio("letter");
  const choices = [
    ["auto", h("label", { class: "lg-choice" }, auto, h("span", null, h("b", null, "From the site (automatic)"),
      h("small", null, "Skald asks the site itself for its app icon, then its favicon. Never an outside icon service.")))],
    ["upload", h("label", { class: "lg-choice" }, up, h("span", null, h("b", null, "Upload my own"),
      h("small", null, "PNG, SVG or ICO, square, at least 64 × 64. Admins and owners only."), h("span", { class: "lg-row" }, pick, fileIn, picked1)))],
    ["letter", h("label", { class: "lg-choice" }, lt, h("span", { class: "lg-row" }, h("span", null, h("b", null, "A letter on a colour"),
      h("small", null, "Also the fallback when the site has no icon.")), swatches))],
  ];

  const save = h("button", { type: "button", class: "btn primary", disabled: ro }, "Save");
  const again = h("button", { type: "button", class: "btn", disabled: ro }, "Check the site again now");
  save.addEventListener("click", async () => {
    save.disabled = true;
    try {
      if (source === "upload" && file) {
        const data = picked.split(",", 2)[1] || "";
        const u = await call("logo/upload", { data, name: file.name.slice(0, 100) });
        if (!u.ok) { msg.say(why(u, "The file was not kept.")); return; }
      } else if (source === "upload" && !r.upload) { msg.say("Choose a file to upload first."); return; }
      const change = {};
      if (source !== r.source && !(source === "upload" && file)) change["site.logo.source"] = source;
      if (color !== r.color) change["site.logo.color"] = color;
      if (Object.keys(change).length) {
        const s = await call("settings/save", change);
        if (!s.ok) { msg.say(why(s)); return; }
      } else if (!(source === "upload" && file)) { msg.say("Nothing changed."); return; }
      said = ["Saved. The menu and the browser tab show it the next time a page is opened.", true];
      reload();
    } finally { save.disabled = ro; }
  });
  again.addEventListener("click", async () => {
    again.disabled = true;
    msg.say(`Asking ${r.hosts?.[0] || "the site"}...`, true);
    const c = await call("logo/check", {});
    again.disabled = ro;
    if (!c.ok) { msg.say(why(c, "The site could not be asked.")); return; }
    said = c.found ? [`Found on the site: ${c.found.url}.`, true] : [`Nothing found: ${c.error || "no icon"}.`, false];
    reload();
  });
  paint();
  return [
    h("div", { class: "lg-top" }, previews, h("div", { class: "lg-found" }, found)),
    h("fieldset", { class: "lg-set" }, h("legend", null, "Where the logo comes from"), choices.map(([, el]) => el)),
    ro ? h("p", { class: "note ro-why" }, r.reason || "Only an admin or an owner can change this.") : h("div", { class: "acts" }, save, again),
    msg,
  ];
}
