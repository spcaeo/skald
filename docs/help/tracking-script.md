# The tracking script

How to add Skald's one-line `skald.js` tag to your pages, what it sees, what it never collects, and how to check that it works.

## What it is for

Your server log already counts visits and pages. It cannot see what happens *inside* a page: a form started and not sent, a phone link clicked, a demo booked in a widget. The `skald.js` tag reports those.

- It is under 6.5 KB of plain JavaScript.
- It sends events to the address it loads from: your Skald server, or your own site if you serve the tag from there (below). Never to anyone else.
- It uses no cookies, unless you ask it to share an ID across subdomains (below). What it keeps in the browser is listed under "What the tag keeps in the browser" below.
- Skald's figures from the log never depend on it. Without the tag, you lose nothing you already have.

## Add the tag

You need to be an admin of the site.

1. Open **Settings > This site > Integrations**, or go to [Integrations](#settings/integrations).
2. If you manage more than one site, choose the site at the top.
3. Under **The script tag**, tick the options you need (see "Options" below). The tag updates as you tick.
4. Copy the tag.
5. Paste it into the `<head>` of every page of your site. In most site builders this is a "custom code" or "head code" setting that applies to all pages.
6. Publish your site.

The tag looks like this. Always copy yours from the page, because the address and site name are your own:

```
<script src="https://skald.example.com/traffic-js/skald.js" data-site="example.com" defer></script>
```

> Nothing changes on your web server. The page loads the tag from your Skald server and sends its events there. You can also serve it from your own domain (below).

If the Integrations page is not in your Settings menu, your server does not use accounts, or you are not an admin. Ask the person who runs your Skald server for the tag.

## More than one site

Since Skald 2.9.0, every site on your Skald can use the tag, not only the first one.

- Each site's events go to that site. Skald knows the site by the address the page is on.
- A site added from the dashboard takes events from its own **Host names** ([Sites](#settings/sites), under **Settings > This site > Sites**). Nothing else to set. This works once the person who runs your Skald server has turned the tag on for the first site.
- A host name you add there works within a minute.
- Anonymous visitor IDs (below) are set per site. One site can have them on and another off.

### A site on another server

The tag sends its events to the address it was loaded from. With the tag as Skald gives it, that is your Skald server, so a site on any server works with no change there. Skald takes an event only from a page on one of the site's own host names.

Before Skald 2.24.0 the tag sent its events to the page's own address. If your browser's Network panel shows requests to your own site's `/traffic-beacon` answered 308, 404 or 405, the page still has an older tag or an older copy of the script: copy the tag again.

### Serve it from your own domain (optional)

Some ad blockers stop scripts that load from another address. To keep the tag on your own domain, your web server passes two addresses on to Skald: `/traffic-js/` and `/traffic-beacon`. Your developer or host sets this up once (a "reverse proxy" or "rewrite"). The tag then loads from your own site, and sends its events there:

```
<script src="/traffic-js/skald.js" data-site="example.net" defer></script>
```

The person who runs your Skald server must also tell it to trust your site's server for the visitor's address. Without that, every visitor looks like one address, and the limit on events per visitor applies to all of them together. Skald uses the address only in memory and never keeps it.

The set-up dialog **Add the script tag**, step 2, has these lines for nginx, Apache and Caddy under **Advanced: serve it from your own domain**. [Connections](#settings/api) > **Send this site's visits to Skald** > **Only the script tag** shows them too, and tests the tag. See [Connections](connections.md).

## Options

| Tick box on the page | Adds to the tag | What it does |
| --- | --- | --- |
| Wait for consent | `data-consent="required"` | sends nothing and keeps no ID until your consent banner says yes |
| Share across subdomains | `data-share-subdomains="true"` | `www.` and `app.` see the same anonymous ID, kept in a first-party cookie. An admin can switch this on in Skald instead (below) |
| Other domains you own | `data-link-domains="..."` | links to those domains carry the anonymous ID |
| Accept the ID from your other domains | `data-accept-id="true"` | this site takes the ID a link from your other domains brought (below) |

## What it tracks by itself

Once the tag is on a page, it reports these events with no extra work:

| Event | When |
| --- | --- |
| Page view | the page loads; each time a single-page app changes the address (a link inside the page, the back and forward buttons); and when the browser shows the page again from its back-forward cache |
| Form started | a field of a form is first used (once per form per page) |
| Form sent | a form is submitted |
| Sign-up started, Sign-up sent | the same, for a form marked `data-skald="signup"` |
| Contact sent | a form marked `data-skald="contact"` is submitted |
| Early access sent | a form marked `data-skald="waitlist"` is submitted |
| Phone click | a `tel:` link is clicked (never the number) |
| Email click | a `mailto:` link is clicked (never the address) |
| Link out | a link to another site is clicked (the other site's name only) |
| Button click | an element marked `data-skald-cta="<name>"` is clicked |
| Read ¾ | the reader scrolls to three quarters of the page (once per page) |
| Copied | text is copied from the page (once per page; never the text) |
| Not found | a page marked `data-skald="404"` is shown, such as your "page not found" page |
| Calendly opened, time chosen, booked | inside a Calendly embed on your page |
| Cal.com opened, booked | inside a Cal.com embed |
| HubSpot meeting booked | inside a HubSpot meetings embed |

A form records only its own `id` or `name`, such as `contact`. It never reads what a person typed.

### Marking forms and buttons

- To track a button or link by name, add `data-skald-cta="pricing_top"` to it. It is reported as a Button click named `pricing_top`.
- To count a form as a sign-up, add `data-skald="signup"` to the form.
- To count a form as a contact form, add `data-skald="contact"`; for an early-access or waiting list form, `data-skald="waitlist"`. Starting either one still counts as Form started.
- To leave a form out, add `data-skald="off"`. Search forms (`role="search"`) are always left out.
- To count your "page not found" page, add `data-skald="404"` to its `<body>`, or put `<div data-skald="404" hidden></div>` anywhere on it. This also works in a single-page app.

> A form whose own code refuses the submit (for example, a missing field) still counts as sent. If that matters, your developer can send the event only after success: `skald('track', 'form_submit', {id: 'contact'})`.

### What it does not track by itself

Two events on [Leads & sales > Events](#sales/events) come only from your site's own code: **Demo opened** (`book_demo_open`) and **Demo booked** (`demo_booked`). Until your site sends them, the Events tab shows them as **Not set up**, with the line to add. Any event your site has never sent shows the same way, never as 0 or "0% went on". Your developer sends them when your own booking step opens and succeeds:

```
skald('track', 'demo_booked', {id: 'header'})
```

A booking made inside a Calendly, Cal.com or HubSpot embed is already counted by the tag as Calendly booked, Cal.com booked or HubSpot meeting booked.

Time on page, pages per visit and one-page visits come from your server log, not from the tag.

### Page views from the tag are not the log's page views

On a Next.js or other single-page site, a click inside the site loads no new HTML page. The tag still sends a page view then, and when the browser restores a page from its back-forward cache (the back button, with no request to your server at all). These are the tag's own events, a separate road: they can show that a browser really drew the page, and with visitor IDs on they make up the visitor's journey, but they never add people or page views to the figures Skald counts from your server's log. For the log to count a page opened inside a Next.js site, its `log_format` needs one more field: see [Troubleshooting connections](troubleshooting-connections.md).

## What it never collects

- No text a person typed, and no form field's value.
- No phone number or email address from a link.
- No IP address and no browser details are stored. Skald uses the address only in memory, to find the country and to limit abuse, and then drops it.
- No third-party code, and nothing sent anywhere but your Skald server (or your own site, if you serve the tag from there).
- No fingerprinting.

With visitor IDs on, the tag also keeps one random ID per browser (below). It holds no name or email.

## What the tag keeps in the browser

- **Always, with visitor IDs on or off: the visit's source, for the tab only.** When a page is opened from another site, or from an address with a `utm_source` tag, the tag keeps that site's name (for example `news.example.org`) and the `utm_source` value in the tab's session storage, under `skald.src`. Later pages of the same visit then send the same source, after the address has lost its tag. Session storage belongs to that one tab, and the browser deletes it when the tab is closed. It holds no ID, no name and no email.
- **With visitor IDs on, also:** the random ID in local storage (`skald.vid`), which stays until the visitor clears the site's data; a note of whether Skald shares the ID across subdomains, renewed each day (`skald.sh`, below; not when the tag itself has `data-share-subdomains="true"`); and with sharing on, the `skald_vid` cookie.
- **Nothing at all** when the browser sends Do Not Track or Global Privacy Control, and nothing before consent with **Wait for consent**. When your banner calls `skald('consent', false)`, the tag deletes the ID, the cookie and the stored source.

## Anonymous visitor IDs

Visitor IDs let Skald follow one browser's anonymous journey up to a conversion. They make "abandoned", "assisted" and "pages seen before converting" possible. See [Leads and conversions](leads-and-conversions.md).

- They are **off by default**. The person who runs your Skald server turns them on per site.
- The Integrations page says, under the tag, whether they are on for your site.
- When they are off, the tag makes no ID at all. It still keeps the visit's source in the tab's session storage until the tab is closed (above).
- When they are on, the ID is kept in the browser's local storage. With "Share across subdomains", it is also kept in a first-party cookie called `skald_vid` for up to 400 days.

### Share across subdomains without changing the tag

If your web developer cannot add `data-share-subdomains="true"` to the tag, an admin can switch sharing on in Skald instead of the tag: **Settings > Sites > Script tag > Share the ID across subdomains**. The tag stays exactly as it is.

- The tag learns it from Skald's answer to its first page view, and remembers the answer for a day in the browser's local storage (`skald.sh`). So a visitor's browser starts sharing on its next visit, and at the latest a day after you switch it on.
- Switching it off works the same way: within a day, each browser stops sharing and deletes the shared cookie.
- It needs visitor IDs on. Do Not Track, Global Privacy Control and **Wait for consent** work exactly as before: no ID, no cookie.
- The Integrations page says, under the tag, when sharing is on in Skald. The privacy notice wording then has the cookie line ready, without "Keep this line only if".

> Turn visitor IDs on only when your privacy notice says so. See [Privacy](privacy.md).

## Consent and Do Not Track

- **Do Not Track and Global Privacy Control**: when the browser sends either one, the tag does nothing at all. No ID, no storage, no event.
- **Consent first**: in places that need consent before any ID (the EU, Quebec, often the rest of Canada), tick **Wait for consent**. The tag then waits.

When the visitor agrees, your consent banner must call this on every page:

```
skald('consent', true)
```

If the visitor says no, or withdraws consent, call `skald('consent', false)`. This deletes the ID, the cookie and the stored source in that browser.

To call `skald` before the tag has loaded, your developer can put this line before the tag:

```
<script>window.skald=window.skald||function(){(skald.q=skald.q||[]).push(arguments)}</script>
```

## Your other domains (data-link-domains)

If your visitors move between domains you own, such as `example.com` and `app.example.net`, type the other domains in **Other domains you own**, separated by commas.

When a visitor clicks a link to one of them, the tag adds `?skv=<the visitor ID>` to the link.

On the other domain, the same tag picks the ID up, so the visit continues the same anonymous journey:

1. Put the tag on the other domain's pages too (it can report to the same site, or to its own).
2. On that domain's tag, either list your first domain in **Other domains you own** (for example `example.com`), or tick **Accept the ID from your other domains** (`data-accept-id="true"`).
3. Publish both.

When a page opens with a valid `skv` in its address, the tag keeps that ID as the visitor's ID and takes `skv` out of the address bar, so it is not bookmarked or shared. Without `data-accept-id`, it takes the ID only when the visitor came from a domain listed in **Other domains you own**; any other `skv` is ignored and left alone.

- With **Wait for consent**, the ID is kept only after `skald('consent', true)`. The address is cleaned at once either way.
- With Do Not Track or Global Privacy Control, the tag does nothing, so `skv` stays in the address.
- If your other domain does not run the tag, its own code can read `skv` and pass it to Skald, for example as `vid` in your site's lead push. See [Webhooks](webhooks.md).

For subdomains of one domain (`www.` and `app.`), tick **Share across subdomains** instead, or switch it on in Skald (above). If the shared cookie does not work on your host (some free hosting addresses refuse it), the ID still works on each subdomain on its own.

## Calendly links get utm_content

With visitor IDs on, the tag adds the visitor ID to every Calendly embed and Calendly link on your page, as `utm_content=<the visitor ID>`. Calendly sends this back in its webhook, so the booking joins the visitor's journey.

- If a Calendly link already has a `utm_content`, the tag leaves it alone. That booking then has no journey.
- This works for Calendly iframes, inline widgets and plain links. A popup opened only from your own JavaScript is not changed.
- You also need the Calendly webhook. See [Webhooks](webhooks.md), section "Calendly".

## Check that it works

1. Open your site in a normal browser window. Make sure Do Not Track and Global Privacy Control are off in that browser, or the tag sends nothing.
2. Open a page, click a link and start a form.
3. In Skald, open [Leads & sales > Events](#sales/events) and choose **Today**.
4. You should see "Today so far, not yet checked" and your events. Today's events are checked after midnight.
5. At the bottom of the Events tab, a line says what the beacon took in today: accepted, declined, from machines, from your own addresses, refused.

> Your own office is likely marked as internal traffic. Its events are kept apart as "ours" and not shown with people's. Test from a phone on mobile data, or see [Internal traffic](internal-traffic.md).

An admin can also press **Test connection** in [Connections](#settings/api) > **Send this site's visits to Skald**, with **Only the script tag** chosen. It says whether a page opened with the tag and how many events were counted.

If you know your browser's developer tools, open the Network panel. Each event is a request to `traffic-beacon`, on your Skald server (or on your own site, if you serve the tag from there). An answer of 204 means it was counted. An answer of 202 means it was taken and nothing was kept, which is normal for page views when visitor IDs are off.

### If nothing shows

- The tag is not on the page: view the page's source and look for `skald.js`.
- `skald.js` does not load: copy the tag again. If you serve it from your own domain, your web server does not pass `/traffic-js/` on to Skald yet.
- Requests go to your own site's `/traffic-beacon` and are answered 308, 404 or 405: an older tag or script. Copy the tag again, or pass `/traffic-beacon` on to Skald.
- Your page's Content-Security-Policy leaves your Skald server out of `connect-src`: the browser blocks every event. Add it.
- Requests to `/traffic-beacon` are refused (403): the page's address is not on the server's list of allowed origins. For a site added from the dashboard, check that the page's exact host name (with or without `www.`) is in its **Host names** under **Settings > This site > Sites**.
- Your browser sends Do Not Track or Global Privacy Control.
- The tag waits for consent and your banner never calls `skald('consent', true)`.
