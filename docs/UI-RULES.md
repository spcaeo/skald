# UI rules

Read this before you change a screen. It is the one file builders need: the rules, the
shared pieces in `skald/webapp/js/ui/` and `css/ui.css`, and how to use them.

The reasons and the measurements are in the UX audit of 2026-10-26
(`docs/plans/ux-audit-2026-10-26/AUDIT.md` on branch `ux-audit-2026-10-26`).

## The 19 rules

1. **One primary button per screen.** It uses the accent colour, and nothing else does.
2. **A primary button opens a dialog that asks one plain question first**: "What do you
   need?" or "Who will do it? Me / My developer / My AI agent". Then only that path shows.
3. **Fill every default Skald knows**: the site, the period, the web server, the time zone,
   the role, the signed-in person's address and browser, and the last choice. Never ask a
   question whose answer is known.
4. **Never show a step Skald knows is not needed** (a proof step, a confirm mail to the
   signed-in owner, a "Check" button when Skald can watch by itself).
5. **The choice is in the URL** (`by=`, `step=`, `agent=`, a tab's own keys). Back and
   Forward work. Opaque ids only: never an IP, an email or a name.
6. **One door per thing.** If two controls open the same dialog, one of them goes.
7. **Answer first, details after.** A page opens on the answer to its own question (tiles,
   one short list). Tables and logs go behind "Open the details", a fold or a tab.
8. **No page longer than about two screens at 1440 px.** Past that, split it into tabs or
   folds.
9. **Help on demand.** An intro is one sentence at most. Method, definitions and caveats
   go behind a "?" (`help()`), with "Read the guide" into Help. Help has one entry point in
   the menu.
10. **Done things fold to one line.** A finished set-up, a closed alert or an unused tool is
    one quiet line (`fold()`, `doneFold()`), not a card.
11. **Empty or "Not set up" shows once**, as one line with a Set up button, not as a card per
    figure.
12. **One Save per form**, at its foot, active only when something changed.
13. **Every status gets a pill** (`pill()`): good, warn, bad, off or info. Never a status in
    plain text like "Open" or "active".
14. **Counts on one screen agree**, or the line says why they differ.
15. **A row that looks clickable is clickable.**
16. **Copy and open icons, not Copy buttons**, on every URL, path, IP, email, token and line
    of code (`withUrl`, `withCopy` in `js/urlactions.js`).
17. **Hide the controls that do nothing on this tab** (the period on a tab with its own).
18. **No card grid that repeats the menu.**
19. **The menu's line icons only** (16 px, stroke 1.5, round caps). No unicode glyphs
    (✓ ✗ ◐ ▲ ▼ ⋯ →) in new buttons or labels.

## The pieces

All of them live in `skald/webapp/js/ui/` and draw with `css/ui.css`. Every class
starts with `ui-`, so a page that does not use them does not change. Tests:
`tests/js/ui.mjs` and `tests/test_ui_system.py`.

### `primary.js`: the one action

```js
import { primary, screenHead, primaries } from "../ui/primary.js";
const fix = primary("Fix", () => openFix(), { icon: WRENCH_SVG });
const head = screenHead("Alerts", { help: help("Alerts", { guide: "what-to-fix" }), action: fix, lede: "3 things need you." });
primaries(panel) === 1;   // a test holds each screen to one
```

`screenHead(title, { help, action, lede, level })` draws the title, its "?", a gap, and
the action at the top right. `lede` is one line at most.

### `help.js`: the "?"

```js
import { help } from "../ui/help.js";
help("Visitors", { text: "Visits that read at least one page.", guide: "where-visitors-come-from" });
help("Lost pages", { guide: "what-to-fix" });          // no text: the guide's own summary
help("Alerts", { text: ["Two short", "paragraphs."] });
```

It opens on a press (a phone has no hover), closes on Escape, on its ×, on a second
press or on a press outside, and puts the focus back on the "?". One is open at a time.
Its aria-label is "Help: <label>". `guide` is a guide id from `docs/help/<id>.md`; an id
that is not a guide gets no link. Use this instead of a paragraph under a heading.

The older `info()` in `js/tabs/tiles.js` (the "i" on tiles) still works. New screens use
`help()`.

### `pill.js`: status

```js
import { pill, kindOf } from "../ui/pill.js";
pill("good", "Working");  pill("warn", "Waiting for logs");  pill("bad", "Urgent");
pill("off", "Paused");    pill("info", "New");
pill(kindOf(alert.severity), "Urgent");   // high → bad, medium → warn, low → info
```

Five kinds only. The words always say the status; the colour only repeats it. Each pair
reads at 4.5:1 or more in light and dark (measured by the test).

### `fold.js`: one quiet line that opens

```js
import { fold, doneFold } from "../ui/fold.js";
fold("12 closed in the last 30 days", () => closedTable());   // drawn the first time it opens
doneFold(doneItems, (i) => row(i));                            // "3 done" with a tick; null when none
```

### `who.js`: "Who will do it?"

```js
import { whoDialog, whoStep, agentPath, devPath, mePath } from "../ui/who.js";
await whoDialog({
  title: "Fix: possible exposure",
  route: { key: "alfix", value: "security_exposure" },   // the dialog's own address key
  fallback: "me",
  paths: {
    me: mePath(() => stepsByHand()),                                       // the steps you already draw
    dev: devPath({ site, message: "What to do, in plain words", link }),  // or { site, task: "send" | "script" | "hook" | "nextjs", method }
    agent: agentPath({ site, jobs: ["logs"], route }),                     // only for a job kit/agent_jobs.py knows
  },
  footer: [primary("I have done it", done)],
});
```

- A path you do not give is not offered. Give `agent` only when the work is a job the
  agent kit knows (`js/tabs/agent-words.js JOBS`); never offer a choice that leads nowhere.
- `agent` is the existing agent line: the agent tiles, then `linePanel` (POST
  `sites/agentlink` with the jobs), then its watch. From a link it never makes a line by
  itself.
- `dev` with a `task` is the existing Share with your developer link (POST `sites/share`).
  Without one, it is the message to copy, with copy and open icons on the link.
- `me` is whatever by-hand steps you already draw.
- The answers are in this order and these words: Me, My developer, My AI agent.
- The choice is `by=me|dev|agent` in the address, inside your dialog's key, and is
  remembered per person in this browser (a code of their address, never the address).
  It opens on: the address's choice, else the remembered one, else your `fallback`.
  Insights' first Fix this links (`fixby=agent|me|someone`) are read the same way,
  `someone` as `dev`. `who=` is Find a person's; Revenue's breakdown moved to `rby=`
  (old `by=campaign` links are rewritten).
- Your dialog's key must be listed in `js/routekeys.js` (kind `overlay`), restored in
  `js/overlays.js` `RESTORE`, and added to `STEPPED` there so `by`, `agent` and `link`
  leave the address when the dialog closes.

`whoStep({ paths, route, fallback, question, subs, from })` is the same question without the
drawer, for a step inside a wizard of your own (Insights' Fix this uses it). `subs` gives each
tile a second line; `from` is the answer to start on (an older key, such as `fixby=`). Each path
is called with `{ pressed }`: true when the person pressed a tile, false when it was drawn from
the address or the remembered answer, so a path can start work only on a press.

### `connect.js`: "not connected yet" (2.43)

A page that is empty because its source is not connected never shows an empty table: it shows
this card. What each need is, what fits the site and the way recommended live in
`js/connect-plan.js` (no DOM; `tests/js/connect.mjs`); the card in `js/ui/connect.js`, its
styles in `css/connect.css`.

```js
import { connectCard, partlyLine, sourceLink } from "../ui/connect.js";
connectCard(m, "leads", { s });                    // page: need, found, Recommended, one primary Connect, Other ways
connectCard(m, "journeys", { s, mode: "line" });   // a part of a page: one quiet line, a plain Connect
connectCard(m, "ai", { mode: "plain" });           // the state only, no push (AI answers)
partlyLine(m, "leads");                            // "Leads arrive from Calendly; your forms are not connected."
sourceLink("bookings");                            // the head's way back: #settings/site/leads?lt=bookings
```

- needs: leads, bookings, payments, search, tools, journeys, script, ai.
- Connect only writes the existing dialog's own address key (`setup=lead&way=<tool>`,
  `setup=search`, `setup=script`, `setup=tool-<id>`, `setup=finish-tools`, `rjc=connect`), so
  every dialog keeps its own "Who will do it?" and its link.
- A viewer (or anyone who may not connect) reads "Ask an admin to connect it" with the
  dialog's link and its copy and open icons; never GET integrations (it answers 403).
- What Skald found comes from GET integrations' `found` (the set-up's site check). Never fetch
  the site for it.

### `css/ui.css`: the visual system

| Class | What it is |
| --- | --- |
| `.ui-card` | The one card: surface, 1 px rule, radius `--r`, shadow, 16/24 px padding |
| `.ui-card.quiet` | No shadow, half-way to the page: "not set up", "closed", "see also" |
| `.ui-card.good` `.warn` `.bad` | A 4 px left edge in the status colour |
| `.ui-card-h`, `.ui-meta` | A card's head row and its one grey line |
| `.ui-pill.<kind>` | The status pill |
| `.btn.ui-primary` | The accent button (the one per screen) |
| `.ui-head`, `.ui-act`, `.ui-lede` | A screen's head, its action, its one line |
| `.ui-help`, `.ui-help-pop` | The "?" and its popover |
| `.ui-fold`, `.ui-strip` | A fold, and a one-line strip with one button |
| `.ui-ic` | An icon in a soft tile of the area's hue |
| `.ui-who*` | "Who will do it?" |

Tokens it adds, all made from app.css's own: `--accent`, `--accent-ink`, `--area`, the
radii `--r-s` (6), `--r-m` (10), `--r-l` (14), `--r-pill`, and six type sizes `--t-xs`
(12) to `--t-xl` (17) plus `--t-fig` (32, a tile's figure). Spacing stays `--sp-1` to
`--sp-6`. ui.css sets no colour of its own (the test checks).

**The area tint.** `main.js` sets `data-area` on `#app` (overview, traffic, sales, ai,
threats, site, settings, help, about). `--area` is that area's hue: Overview `--ink-2`,
Traffic `--g-people`, Leads & sales `--leads`, AI & bots `--g-answer_engines`, Security
`--warn`, Site `--g-search_engines`, Settings and Help `--ink-3`. It tints the top bar's
band, the menu's mark and `.ui-ic` tiles. Data colours stay data colours.

## Checklist for a screen

- One `.ui-primary` (or none on a read-only page).
- The first screen at 1440 px shows the answer; the page is under about two screens.
- No paragraph of method on the page: it is in a `help()`.
- Every status is a `pill()`; every URL, path and value has its copy (and open) icons.
- Every dialog and its choices are in the address; Back closes it.
- Light and dark, 1440×830 and 390×844, screenshotted before and after.
