# spcaeo/ui in Skald

| | |
| --- | --- |
| Source | github.com/spcaeo/ui (public), MIT licence, `LICENSE` beside this file |
| Upstream version | 1.0.0 |
| Upstream commit | `ad511553306afe276c7c6acc04c683f43cac050d` (2026-08-23) |
| Vendored | 2026-10-12, for Skald 2.7.0 (the UI consolidation) |
| Taken | the vanilla builds and stylesheets of Folder Tabs and Data Grid only: no React build, demo, test or tool |

No npm and no build step: the files are plain ES modules and stylesheets, as upstream ships
them. They load from `_app/vendor/` on the dashboard's own origin, so the
Content-Security-Policy (`script-src 'self'`, no inline script, no eval) holds; none of them
names an outside address.

## Files

| Here | Upstream | Changed |
| --- | --- | --- |
| `folder-tabs/vanilla/folder-tabs.js` | `components/folder-tabs/vanilla/folder-tabs.js` | licence header only |
| `folder-tabs/folder-tabs.css` | `components/folder-tabs/folder-tabs.css` | licence header only |
| `data-grid/vanilla/data-grid.js` | `components/data-grid/vanilla/data-grid.js` | header, imports, patches 1-5 below |
| `data-grid/core/url-state.js` | `components/data-grid/core/url-state.mjs` | header, renamed, imports |
| `data-grid/core/query.js` | `components/data-grid/core/query.mjs` | header, renamed, import |
| `data-grid/core/filter-model.js` | `components/data-grid/core/filter-model.mjs` | header, renamed |
| `data-grid/data-grid.css` | `components/data-grid/data-grid.css` | licence header only |
| `spcaeo-ui-skald.css` | (Skald's own) | Skald's colours for both components |

Skald's adapters live outside this folder: `js/foldertabs.js` (Folder Tabs),
`js/grid.js` (Data Grid), `js/mounts.js` (tears down instances a redraw dropped).

## What was changed, and why

- **Licence header on every file.** The installer copies only `.js` and `.css` into `_app/`,
  so `LICENSE` does not ship; each file carries the MIT notice itself.
- **`.mjs` renamed to `.js`, and the imports that name them.** `webapp.install` copies only
  `.css` and `.js`, and a server may not send `.mjs` as JavaScript; under the old names the
  grid would have failed to load. `tests/test_webapp.py` checks every relative import in the
  installed app finds its file.
- **Patch 1: state in the hash, not `location.search`.** Skald keeps all state in the hash
  (`#traffic/pages?range=7d`). Upstream wrote `?pg_q=…` before the hash, changing the page's
  address, and its Reset wrote `location.pathname` with no hash, dropping the route. The grid
  now takes `params: { read(), write(params, { push }) }`; `js/grid.js` passes one that reads
  and writes the hash's query, keeping the route and every other key. Reset clears only this
  grid's keys (`clearNamespace`, unchanged). Without `params` the grid keeps upstream's
  behaviour, except that it never drops the hash.
- **Patch 2: Back and Forward listener removed on `destroy()`.** Upstream added a `popstate`
  listener per grid and never removed it; Skald redraws the panel on every state change, so
  listeners piled up on detached grids. Now a grid off the page ignores the event, and
  `destroy()` removes it (`js/mounts.js` calls it once a redraw has dropped the grid).
  Folder Tabs needed no patch: its teardown (window `resize`, observers) is called the same way.
- **Patch 3: the search box keeps focus.** Upstream rebuilds the toolbar on every render, so
  after each 250 ms pause in typing the box lost focus and the next keys went nowhere. The
  rebuilt box takes back focus and caret when the old one had them.

The test `tests/e2e/spcaeo-ui.mjs` fails on patches 2 and 3 removed (listeners 4 then 11;
"be" kept of "beta").

### Patch (data-grid.js; header and the core files' import renames left out)

```diff
--- a/components/data-grid/vanilla/data-grid.js
+++ b/vendor/spcaeo-ui/data-grid/vanilla/data-grid.js
@@ -30,9 +30,9 @@
   clearNamespace,
   readGridParams,
   writeGridParams,
-} from "../core/url-state.mjs";
-import { PAGE_SIZE_OPTIONS } from "../core/query.mjs";
-import { describeCondition, encodeFilter } from "../core/filter-model.mjs";
+} from "../core/url-state.js";
+import { PAGE_SIZE_OPTIONS } from "../core/query.js";
+import { describeCondition, encodeFilter } from "../core/filter-model.js";
 
 const h = (tag, props = {}, ...kids) => {
   const el = document.createElement(tag);
@@ -66,6 +66,20 @@
 
 let popoverSeq = 0;
 
+/* Skald patch 1: where the grid's state lives. Upstream read and wrote
+   location.search directly; a host whose state is in the hash passes
+   `params: { read(), write(params, { push }) }`. This default keeps upstream's
+   behaviour, except that writing (and Reset) never drops the page's hash. */
+const SEARCH_PARAMS = {
+  read: () => new URLSearchParams(location.search),
+  write(params, { push = false } = {}) {
+    const qs = params.toString();
+    const url = `${location.pathname}${qs ? `?${qs}` : ""}${location.hash}`;
+    if (push) history.pushState(null, "", url);
+    else history.replaceState(null, "", url);
+  },
+};
+
 export function createDataGrid(host, config) {
   const {
     namespace,
@@ -77,6 +91,7 @@
     load,
     emptyMessage = "Nothing here yet.",
     searchPlaceholder = "Search…",
+    params = SEARCH_PARAMS,
   } = config;
 
   const sortable = new Set(columns.filter((c) => c.sortable).map((c) => c.id));
@@ -90,7 +105,7 @@
   let searchTimer = 0;
 
   const readUrl = () =>
-    readGridParams(namespace, new URLSearchParams(location.search), {
+    readGridParams(namespace, params.read(), {
       sortableFields: sortable,
       filterFields,
       segmentIds,
@@ -122,28 +137,27 @@
     query = result.query;
     if (result.dropSelection) selection.clear();
 
-    const url = (() => {
-      const qs = writeGridParams(namespace, query, new URLSearchParams(location.search)).toString();
-      return qs
-        ? `${location.pathname}?${qs}${location.hash}`
-        : `${location.pathname}${location.hash}`;
-    })();
     // Native history writes rather than a router call: rapid refinement should
     // not re-render the whole page, and it must not stack one history entry per
     // keystroke or Back becomes unusable.
-    if (result.history === "push") history.pushState(null, "", url);
-    else history.replaceState(null, "", url);
+    params.write(writeGridParams(namespace, query, params.read()), {
+      push: result.history === "push",
+    });
 
     render();
     fetchRows();
   }
 
-  addEventListener("popstate", () => {
+  /* Skald patch 2: a grid that has left the page stops answering Back, and
+     destroy() removes the listener, so redraws do not pile them up. */
+  const onPopState = () => {
+    if (!host.isConnected) return;
     ({ query, droppedFilterFields } = readUrl());
     selection.clear();
     render();
     fetchRows();
-  });
+  };
+  addEventListener("popstate", onPopState);
 
   // --- data ---------------------------------------------------------------
 
@@ -182,6 +196,11 @@
   // --- toolbar ------------------------------------------------------------
 
   function renderToolbar() {
+    // Skald patch 3: the search box is rebuilt on every render; keep the
+    // reader's focus and caret in it, or typing stops after each pause.
+    const typing = el.toolbar.contains(document.activeElement) && document.activeElement.type === "search"
+      ? [document.activeElement.selectionStart, document.activeElement.selectionEnd]
+      : null;
     el.toolbar.replaceChildren();
 
     const input = h("input", {
@@ -220,6 +239,10 @@
         : null,
     );
     el.toolbar.append(search);
+    if (typing) {
+      input.focus({ preventScroll: true });
+      input.setSelectionRange(...typing);
+    }
 
     for (const field of filters) el.toolbar.append(filterMenu(field));
 
@@ -233,12 +256,8 @@
           type: "button",
           text: "Reset",
           onClick: () => {
-            const cleared = clearNamespace(namespace, new URLSearchParams(location.search));
-            history.replaceState(
-              null,
-              "",
-              cleared.toString() ? `${location.pathname}?${cleared}` : location.pathname,
-            );
+            // Skald patch 1: only this grid's keys go; the rest of the address stays.
+            params.write(clearNamespace(namespace, params.read()), { push: false });
             ({ query, droppedFilterFields } = readUrl());
             selection.clear();
             render();
@@ -770,6 +789,7 @@
     destroy() {
       inflight?.abort();
       clearTimeout(searchTimer);
+      removeEventListener("popstate", onPopState);
       host.replaceChildren();
     },
   };
```

The core files: `query.js` line 13 and `url-state.js` lines 26-27 import `./filter-model.js` and
`./query.js` instead of the `.mjs` names (and one JSDoc type path, line 100).

## Skald's colours (`spcaeo-ui-skald.css`)

Upstream's stylesheets are unchanged. The mapping sets their variables on the components'
own elements (`[data-folder-tabs]`, `.dg`) from Skald's tokens, so Skald's theme switch
(`data-theme` on `<html>`) and the OS setting both work. Folder Tabs need their dark order of
fills changed (Skald's `--sunk` is lighter than `--surface` in dark), under both dark selectors.

Upstream measured only its own palette. `tests/test_spcaeo_contrast.py` re-runs the same check
(upstream's pairs from each `component.json`, plus Skald's: chips, hover, the filter menu) on
Skald's tokens; `python3 tests/test_spcaeo_contrast.py --table` prints this table. A boundary
passes on its fills or on the edge stroke between them, as upstream's rule says. Every pair
passes; nothing needed fixing.

| Component | Pair | Light | Dark | Needs |
| --- | --- | --- | --- | --- |
| Folder Tabs | label on inactive tab | 5.90 | 8.59 | 4.5 |
| Folder Tabs | label on active tab | 15.86 | 14.19 | 4.5 |
| Folder Tabs | focus ring on inactive tab | 14.24 | 14.79 | 3 |
| Folder Tabs | focus ring on active tab | 15.86 | 14.19 | 3 |
| Folder Tabs | inactive tab vs rail | 1.07 fill, 3.50 edge | 1.04 fill, 5.70 edge | 3 |
| Folder Tabs | active tab vs rail | 1.19 fill, 3.50 edge | 1.09 fill, 5.47 edge | 3 |
| Folder Tabs | active tab vs inactive tab | 1.11 fill, 3.74 edge | 1.04 fill, 5.47 edge | 3 |
| Data Grid | body text on background | 15.86 | 14.19 | 4.5 |
| Data Grid | muted text on background | 6.57 | 8.24 | 4.5 |
| Data Grid | column header on header fill | 5.53 | 7.44 | 4.5 |
| Data Grid | primary button label | 15.86 | 15.41 | 4.5 |
| Data Grid | error text on background | 5.39 | 5.69 | 4.5 |
| Data Grid | focus ring on background | 15.86 | 14.19 | 3 |
| Data Grid | focus ring on header fill | 13.34 | 12.81 | 3 |
| Data Grid | text on muted fill (chips, counts) | 13.34 | 12.81 | 4.5 |
| Data Grid | text on hover / selection fill | 14.24 | 15.41 | 4.5 |
| Data Grid | text in the filter menu | 15.86 | 14.19 | 4.5 |
| Data Grid | menu title in the filter menu | 6.57 | 8.24 | 4.5 |
| Data Grid | control border vs background | 4.17 | 5.47 | 3 |
| Data Grid | control border vs header fill | 3.50 | 4.94 | 3 |
| Data Grid | primary button vs background | 15.86 | 14.19 | 3 |
| Data Grid | active segment underline vs background | 15.86 | 14.19 | 3 |

## Updating

Fetch the new upstream commit read-only (`gh api repos/spcaeo/ui/tarball` into a scratch
folder), copy the same files over, re-apply the header, the renames and the patch above, then
run `python3 -m unittest discover tests` and `tests/e2e/spcaeo-ui.mjs`, and update this file.

## Patch 4 (2.7.0): segments as a proper tab strip

`data-grid/vanilla/data-grid.js` `renderSegments`: the segment buttons have `role="tab"` but every one was a tab stop. Now only the selected one has `tabindex=0` (the others -1), and ArrowLeft/ArrowRight/Home/End move between them and pick one, as the WAI-ARIA tabs pattern asks. Found by the Traffic builder (a section with a segmented grid showed 4 tab stops).

## Patch 5 (2.10): centred columns

`data-grid/vanilla/data-grid.js` `alignClass`: upstream knew only `align: "right"` (class
`dg-num`). `align: "center"` now gives `dg-center`, for a yes/no or a small tag ("New",
"Blocked"). `js/grid.js` sets `align` from the column's type (`table.js` `alignOf`), and
`spcaeo-ui-skald.css` lines every grid up: cells at the top of the row, `dg-num` right
(upstream's `.dg-table td` outweighs its own `.dg-num`), `dg-center` centred.
