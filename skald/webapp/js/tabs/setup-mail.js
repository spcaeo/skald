// "Set up this site" > Mail recipient confirmed: turn the daily and the weekly
// mail on, enter or confirm who gets it, then see who still has to press the
// link in their confirm mail and send a test. The endpoints of Settings > Mail
// (prefs.js mail, settings_api.py): GET settings, POST settings/save
// {mail.daily, mail.weekly, mail.to} (only what changed), POST settings/test-mail {to}.

import { h } from "../ui.js";
import { call } from "./ipmanager.js";
import { ME } from "../access.js";
import { input, field, why } from "./forms.js";
import { wizard, answerBox } from "./conn-ui.js";

const listOf = (text) => String(text || "").split(/[\s,;]+/).map((x) => x.trim()).filter(Boolean);

function check(label, sub, on, set, disabled) {
  const box = h("input", { type: "checkbox", disabled: disabled || null });
  box.checked = !!on;
  box.addEventListener("change", () => set(box.checked));
  return h("label", { class: "chk" }, box, h("span", null, h("b", null, label), h("small", null, sub)));
}

export async function mailDialog(site, { onClose = null } = {}) {
  const r = await call("settings");
  const s = r.ok ? r.settings || {} : {};
  const st = {
    daily: !!s["mail.daily"]?.value, weekly: !!s["mail.weekly"]?.value,
    to: (s["mail.to"]?.value || []).join("\n") || ME.user || "", waiting: r.ok ? r.mail_waiting || [] : [], saved: false,
  };
  const locked = (k) => (s[k] && !s[k].editable ? s[k].reason || "You cannot change this." : "");

  function waitingBox() {
    const box = h("div");
    const again = h("button", { type: "button", class: "btn" }, "Check again");
    const draw = () => {
      const n = listOf(st.to).length;
      box.replaceChildren(st.waiting.length
        ? answerBox("wait", `Waiting for ${st.waiting.join(", ")} to press the link in their confirm mail.`, h("p", null, "Reports go to an address only once it is confirmed. Ask them to look in their inbox (and spam)."), h("div", { class: "acts" }, again))
        : answerBox("ok", `Every recipient has confirmed. The ${st.daily ? "daily" : "weekly"} mail goes to ${n} address${n === 1 ? "" : "es"}.`));
    };
    again.addEventListener("click", async () => {
      again.disabled = true;
      const got = await call("settings");
      again.disabled = false;
      if (got.ok) st.waiting = got.mail_waiting || [];
      draw();
    });
    draw();
    return box;
  }

  function testBox() {
    const to = input({ type: "email", autocomplete: "email", maxlength: "254" });
    to.value = ME.user || listOf(st.to)[0] || "";
    const send = h("button", { type: "button", class: "btn" }, "Send a test mail");
    const said = h("p", { class: "msg", role: "status", "aria-live": "polite" });
    send.addEventListener("click", async () => {
      send.disabled = true;
      const got = await call("settings/test-mail", { to: to.value.trim() });
      send.disabled = false;
      said.textContent = got.ok ? `Sent to ${got.to}. Check that inbox.` : why(got, "It was not sent.");
      said.className = `msg ${got.ok ? "ok" : "err"}`;
    });
    return h("div", null, h("div", { class: "af-row" }, field("Send a test to", to), send), said,
      h("p", { class: "note" }, "A test goes to your own address or to a recipient who has confirmed. At most 3 in 10 minutes."));
  }

  return wizard({
    title: "Get the daily mail", subtitle: `For ${site}.`, key: "setup-mail", onClose, state: st,
    steps: [
      { name: "Which mail",
        draw: () => [!r.ok ? h("p", { class: "msg err" }, why(r, "The settings could not be loaded.")) : null,
          h("p", null, "A short mail with the figures, so you need not open Skald to see how the site does."),
          h("div", { class: "af-col" },
            check("Daily mail", "After each morning's run: yesterday's figures.", st.daily, (v) => { st.daily = v; }, !!locked("mail.daily")),
            check("Weekly mail", "On Mondays: the week before.", st.weekly, (v) => { st.weekly = v; }, !!locked("mail.weekly"))),
          locked("mail.daily") ? h("p", { class: "note" }, locked("mail.daily")) : null],
        check: () => (!r.ok ? why(r, "The settings could not be loaded.") : st.daily || st.weekly ? "" : "Turn on the daily or the weekly mail, or both.") },
      { name: "Who gets it",
        draw: () => {
          const area = h("textarea", { rows: "3", spellcheck: "false", autocomplete: "off", disabled: locked("mail.to") ? true : null });
          area.value = st.to;
          area.addEventListener("input", () => { st.to = area.value; });
          return [field("Addresses, one per line", area, locked("mail.to") || "Each new address gets a mail with a link to confirm it. Reports go only to addresses that confirmed.")];
        },
        check: () => (listOf(st.to).some((x) => x.includes("@")) ? "" : "Type at least one email address."),
        next: async (w) => {
          const body = {};
          if (st.daily !== !!s["mail.daily"]?.value && !locked("mail.daily")) body["mail.daily"] = st.daily;
          if (st.weekly !== !!s["mail.weekly"]?.value && !locked("mail.weekly")) body["mail.weekly"] = st.weekly;
          const to = listOf(st.to);
          if (to.join("\n") !== (s["mail.to"]?.value || []).join("\n") && !locked("mail.to")) body["mail.to"] = to;
          if (!Object.keys(body).length) return true;
          const got = await call("settings/save", body);
          if (!got.ok) { w.say(why(got, "It was not saved.")); return false; }
          Object.assign(s, got.settings || {});
          st.waiting = got.mail_waiting || [];
          st.saved = true;
          return true;
        } },
      { name: "Confirm and test",
        draw: () => [st.saved ? h("p", { class: "msg ok" }, "Saved.") : null, waitingBox(), testBox()] },
    ],
  });
}
