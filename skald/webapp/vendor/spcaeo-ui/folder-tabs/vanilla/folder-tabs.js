/* spcaeo/ui (folder-tabs/vanilla/folder-tabs.js), from github.com/spcaeo/ui at ad51155, vendored by Skald.
   Changes and the reason for each: VERSION.md beside this folder.

   MIT License. Copyright (c) 2026 spcaeo.
   Permission is hereby granted, free of charge, to any person obtaining a copy of this software
   and associated documentation files (the "Software"), to deal in the Software without
   restriction, including without limitation the rights to use, copy, modify, merge, publish,
   distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the
   Software is furnished to do so, subject to the following conditions:
   The above copyright notice and this permission notice shall be included in all copies or
   substantial portions of the Software.
   THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
   BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
   NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
   DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
   OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE. */
/**
 * VB-INSPIRED FOLDER TABS — no framework, no dependencies.
 *
 * The same control as the React version, for a page that has no React. Give it
 * the markup below and call `initFolderTabs()`.
 *
 *   <div data-folder-tabs>
 *     <div class="fldr-rail" role="tablist" aria-label="Sections">
 *       <div class="fldr-scroll">
 *         <button class="fldr-tab" role="tab" id="t1" aria-controls="p1"
 *                 data-state="active"   aria-selected="true">Rules</button>
 *         <button class="fldr-tab" role="tab" id="t2" aria-controls="p2"
 *                 data-state="inactive" aria-selected="false">Dates</button>
 *       </div>
 *       <div class="fldr-arrows">
 *         <button class="fldr-arrow" data-dir="-1" tabindex="-1" aria-label="Scroll tabs left">‹</button>
 *         <button class="fldr-arrow" data-dir="1"  tabindex="-1" aria-label="Scroll tabs right">›</button>
 *       </div>
 *     </div>
 *     <div class="fldr-panel" id="p1" role="tabpanel" aria-labelledby="t1" tabindex="0">…</div>
 *     <div class="fldr-panel" id="p2" role="tabpanel" aria-labelledby="t2" tabindex="0" hidden>…</div>
 *   </div>
 *
 * Every tab needs an `id` and an `aria-controls`; every panel needs a matching
 * `id`, `role="tabpanel"`, `aria-labelledby` and `tabindex="0"`. That pairing is
 * what a screen reader reads — without it the panel is an anonymous div.
 *
 * Nest by putting another `[data-folder-tabs]` inside a panel and adding
 * `fldr-nested` to it.
 *
 * A tab can be disabled two ways, and they are not the same:
 *   disabled          — removed from the page entirely, not focusable
 *   aria-disabled     — still focusable, so a screen-reader user can find it and
 *                       be told why it is unavailable. Preferred by WAI-ARIA.
 * Both are skipped by the arrow keys and both refuse to activate.
 */

const HOSTS = new WeakSet();

/**
 * Wire up every `[data-folder-tabs]` inside `root`. Safe to call more than once
 * and safe to call after injecting new markup — hosts already wired are skipped.
 *
 * @param {ParentNode} [root=document]
 * @returns {() => void} teardown for everything this call wired up
 */
export function initFolderTabs(root = document) {
  const teardowns = [];
  for (const host of root.querySelectorAll("[data-folder-tabs]")) {
    if (HOSTS.has(host)) continue;
    const off = setup(host);
    if (off) {
      HOSTS.add(host);
      teardowns.push(() => {
        HOSTS.delete(host);
        off();
      });
    }
  }
  return () => teardowns.forEach((fn) => fn());
}

const isDisabled = (tab) => tab.disabled || tab.getAttribute("aria-disabled") === "true";

function setup(host) {
  const rail = host.querySelector(":scope > .fldr-rail");
  const strip = rail?.querySelector(":scope > .fldr-scroll");
  // `:scope >` keeps a nested control's tabs out of its parent's list.
  const tabs = strip ? [...strip.querySelectorAll(':scope > [role="tab"]')] : [];
  if (!tabs.length) return null;

  const cleanup = [];
  const on = (el, type, fn, opts) => {
    el.addEventListener(type, fn, opts);
    cleanup.push(() => el.removeEventListener(type, fn, opts));
  };

  const panelFor = (tab) => {
    const id = tab.getAttribute("aria-controls");
    return id ? host.querySelector(`#${CSS.escape(id)}`) : null;
  };

  // Roving focus: exactly one tab in the tab sequence, so Tab moves PAST the
  // strip rather than through every tab in it.
  let current = Math.max(
    0,
    tabs.findIndex((t) => t.dataset.state === "active"),
  );
  tabs.forEach((t, i) => (t.tabIndex = i === current ? 0 : -1));

  const nextUsable = (from, step) => {
    for (let n = 0; n < tabs.length; n++) {
      from = (from + step + tabs.length) % tabs.length;
      if (!isDisabled(tabs[from])) return from;
    }
    return -1;
  };

  /*
    Bring a tab fully into view by moving the STRIP's scrollLeft, not by calling
    `scrollIntoView`. scrollIntoView walks every scrollable ancestor including
    the document, so arrow-keying along a tab strip could jump the whole page —
    which is worse than the problem it solves.
  */
  function reveal(tab) {
    const pad = 12;
    const left = tab.offsetLeft - pad;
    const right = tab.offsetLeft + tab.offsetWidth + pad;
    if (left < strip.scrollLeft) strip.scrollLeft = left;
    else if (right > strip.scrollLeft + strip.clientWidth) {
      strip.scrollLeft = right - strip.clientWidth;
    }
  }

  function select(index, { focus = false } = {}) {
    const tab = tabs[index];
    if (!tab || isDisabled(tab)) return;
    current = index;

    for (let i = 0; i < tabs.length; i++) {
      const t = tabs[i];
      const active = i === index;
      t.dataset.state = active ? "active" : "inactive";
      t.setAttribute("aria-selected", String(active));
      t.tabIndex = active ? 0 : -1;
      /*
        Only touch a panel this tab actually owns. An earlier version hid the
        outgoing panel unconditionally, so a tab wired without `aria-controls`
        left the rail floating above nothing — the mechanic gone, and the exact
        failure this control exists to avoid.
      */
      const panel = panelFor(t);
      if (panel) panel.hidden = !active;
    }

    /*
      preventScroll matters. Focusing an element that is out of view makes the
      browser scroll EVERY scrollable ancestor to reveal it, the document
      included — so arrow-keying along a tab strip could drag the whole page.
      We suppress that and do the one scroll we actually want ourselves.
    */
    if (focus) tab.focus({ preventScroll: true });
    reveal(tab);
    host.dispatchEvent(
      new CustomEvent("folder-tabs:change", {
        bubbles: true,
        detail: { index, tab, panel: panelFor(tab) },
      }),
    );
  }

  // One listener on the strip rather than two per tab.
  on(strip, "click", (event) => {
    const tab = event.target.closest('[role="tab"]');
    const index = tab ? tabs.indexOf(tab) : -1;
    if (index >= 0 && !isDisabled(tab)) select(index);
  });

  on(strip, "keydown", (event) => {
    const tab = event.target.closest('[role="tab"]');
    const from = tab ? tabs.indexOf(tab) : -1;
    if (from < 0) return;

    let target = null;
    if (event.key === "ArrowRight") target = nextUsable(from, 1);
    else if (event.key === "ArrowLeft") target = nextUsable(from, -1);
    else if (event.key === "Home") target = isDisabled(tabs[0]) ? nextUsable(0, 1) : 0;
    else if (event.key === "End") target = nextUsable(0, -1);
    else if (event.key === "Enter" || event.key === " ") {
      // aria-disabled tabs stay focusable, so they can still receive the key.
      if (isDisabled(tab)) return;
      event.preventDefault();
      select(from);
      return;
    } else return;

    if (target === null || target < 0) return;
    event.preventDefault();
    select(target, { focus: true });
  });

  // --- overflow arrows ---------------------------------------------------
  const arrows = rail.querySelector(":scope > .fldr-arrows");
  if (arrows) {
    const left = arrows.querySelector('.fldr-arrow[data-dir="-1"]');
    const right = arrows.querySelector('.fldr-arrow[data-dir="1"]');

    let queued = false;
    const sync = () => {
      queued = false;
      const max = strip.scrollWidth - strip.clientWidth;
      arrows.dataset.overflowing = String(max > 1);
      if (left) left.disabled = strip.scrollLeft <= 1;
      if (right) right.disabled = strip.scrollLeft >= max - 1;
    };
    // Scroll fires per frame; measuring layout on every one of those is the
    // easiest way to make a smooth strip feel slow.
    const queueSync = () => {
      if (queued) return;
      queued = true;
      requestAnimationFrame(sync);
    };

    for (const button of [left, right]) {
      if (!button) continue;
      on(button, "click", () => {
        const step = Math.max(140, strip.clientWidth * 0.7);
        strip.scrollBy({ left: Number(button.dataset.dir) * step });
      });
    }

    on(strip, "scroll", queueSync, { passive: true });
    on(window, "resize", queueSync);

    if (window.ResizeObserver) {
      // Tabs can change after mount — a count arrives, a role hides one — so the
      // arrows follow the elements rather than being decided once at startup.
      const ro = new ResizeObserver(queueSync);
      ro.observe(strip);
      for (const tab of tabs) ro.observe(tab);
      cleanup.push(() => ro.disconnect());
    }
    sync();
  }

  // Make sure the starting state is actually applied, not just asserted in HTML.
  select(current);

  return () => cleanup.forEach((fn) => fn());
}

export default initFolderTabs;
