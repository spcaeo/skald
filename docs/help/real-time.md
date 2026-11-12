# Real time: who is on your site now

See who is on your site right now: each person, the page they are on, whether they are new, returning, a lead or a customer, where they are on a world map, and which AI assistants and crawlers are fetching pages at this moment. This guide covers where it is, what each figure means, how fresh it is and how to count it again at once.

## Where to find it

Real time is part of **Overview** (since 2.47; it was a tab of its own before). The **Right now** card sits at the top of Overview whatever period is picked. With **Today** picked, the rest of Real time follows today's four tiles: requests per minute, the world map, pages being read, the newest visits, sources, devices and machines now, and how today's visits moved. An old link to Overview › Real time opens Overview for today.

## Right now

The card at the top of Overview answers "who is on my site now?".

- **People on your site now**: visitors with a request in the last 5 minutes, and how many arrived in those 5 minutes. Press the number to open the list of everyone.
- **Minute by minute**: the last 30 minutes as bars; the last one is the minute still running.
- **In the last 30 minutes**: visitors with any request in the last 30 minutes.
- **The people here now**: one row per visit, those active in the last 5 minutes first. Each row says where they are and their device, the page they are on now (**Now on /pricing/**, with copy and open icons; **Last on** when their last request was 5 to 30 minutes ago), how long they have been on the site, how many pages they read and where they came from. A pill says who they are:
  - **New**: not seen on an earlier day in the last 30 days.
  - **Returning**: seen on an earlier day, with how many of the last 30 days and where they first came from.
  - **Lead** or **Customer**: this visit sent a lead, or sent a form for someone who has paid (proven matches only).
  - No pill: Skald could not tell (no visitor key set). It is never shown as New.

  Select a row to open the visitor drawer with their journey. The first six are listed; the rest are under **Everyone else in the last 30 minutes**.

## How fresh it is

**Updated 40 s ago** beside **Right now** says how old the visitor count is. Skald counts every site in turn, so on a busy server the count can be a few minutes old. The page asks for the newest count every 15 seconds while it is open and visible.

- **Refresh now** counts this site at once, instead of waiting for its turn, and draws the answer. It counts this one site only; one count runs at a time.
- **Pause** holds everything still; **Resume** starts again.
- If **Updated** turns orange, the count has not run for more than 10 minutes: check Site › Data quality.

**Requests per minute**, under the tiles, has a clock of its own: every request your server logged, read from the end of the log every 15 seconds. These are not sorted into people and machines yet, so they are always called requests, never visitors.

## What the figures mean

| Figure | What it is |
|---|---|
| People on your site now | Visitors with any request in the last 5 minutes. A visitor is a visit that read a page, the same count as **Visitors** everywhere else. |
| Last 30 minutes | Visitors with any request in the last 30 minutes. |
| Visitors today | Today so far, the same number as Overview's Visitors tile. |
| Pages read, 30 min | Page views by visitors in the last 30 minutes. |
| Visitors on the site, minute by minute | For each of the last 30 minutes, the visitors whose visit was under way: their first request before the minute ended and their last one in it or after. The tooltip also says how many arrived in that minute. The last bar is the minute still running. |
| Requests per minute | Every request the server logged in each minute: pages, images, scripts, bots and people alike. A spike here with no visitors is usually a crawler. |

## The world map

Each country is shaded by its **visits today**: the darker the blue, the more visits. The legend under the map gives the range of each shade. A **green bubble** marks a country with visitors active in the last 30 minutes; the bigger the bubble, the more of them.

- Point at a country, or move to it with **Tab**, to see its visits today and how many are active.
- Click it, or press **Enter**, to open the country's detail, as from any country in the dashboard.
- The **By country** table beside the map has the same figures, so you can search, sort and download them. On a phone the table sits under the map.

### Cities on the map

When a city file is set (see [Places & devices](getting-started.md#cities)), the map also shows cities. A **pulsing green dot** sits on each city with visitors active in the last 30 minutes, at the city's own point; a small **hollow dot** marks a city with visits today and nobody active now. A country's own bubble then counts only its active visitors whose city is not recorded. Point at a dot for its figures; click it to open the city's detail. The **By city** table under the countries holds the same figures, and says how many of today's visits have no city recorded.

Countries too small for the map's outlines (Singapore, Malta and others) are drawn as a dot. The map is drawn from Natural Earth's public-domain outlines and is part of the page: no map service is asked for anything.

## The lists

- **Pages being read**: page views in the last 30 minutes, by page.
- **Newest visits**: the ten newest visits, with time, city (or country, when no city is recorded), device, where they came from, the page they landed on and how many pages they have read so far. **active now** means a request in the last 5 minutes. No address and no browser string is shown here.
- **Sources now** and **Devices now**: visitors active in the last 30 minutes, by where they came from and by device.
- **AI and crawlers now**: requests in the last 30 minutes by AI assistants and search crawlers, by name, and other bots and scanners as one count. These are machines, counted in requests, never as visitors.

Select any page, source, device or crawler to open its detail.

## Today, live

Overview with **Today** picked opens on what is current, then today's figures:

1. **Right now** (above): the people on the site now and the page each is on, with **Refresh now**.
2. **Visitors**, **Pages read**, **Leads** and **Visitors from AI** for today so far, each against yesterday at this hour. Select a tile for its full tab.
3. The rest of Real time: requests per minute, the map, pages being read, the newest visits, sources, devices and machines now, then **How today's visits moved** (the flow, two pages deep, with **Full flow** for Traffic › Visitors).

Where today's visitors came from is on Traffic › Sources, and what converted on Leads & sales (they left this page in 2.47).

The **?** beside the title says what "today so far" covers and how often each part is counted. While set-up is not finished, one line sits under the title, for example **Set-up: 2 left · Send your logs**, with **Finish set-up** (Settings › This site › Set-up checklist) and **Show the list**.

### Vs yesterday at this hour

Each of the four tiles compares today so far with **yesterday up to the same time of day**: at 14:33 today, yesterday from midnight to 14:33. Never with all of yesterday, which would make every morning look like a fall. The small chart under each tile is the running total by hour: today as a line, yesterday dashed. Point at it for the totals at each hour.

- Visitors, pages read and visitors from AI: Skald counts yesterday again from the log up to that time, every 2 minutes, with the same rules as today's figures.
- Leads: yesterday's completed forms and demo bookings up to that time, from the lead store. Test rows are never counted.
- Under 10 yesterday, the change is a count (**+2**); from 10, a percent (**+18%**).
- **Not recorded** means yesterday cannot be compared: it was withheld (its second count disagreed), is only partly in the log, or was not recorded. It never shows as a fall to zero.
- On a page group, the comparison says not recorded: it is counted for the whole site.

`skald audit --live` counts yesterday at this hour again from the raw log lines, hour by hour, and the leads again from the lead store.

## Page groups

Real time always covers the whole site. On a page group, a note says so.

## How the figures are checked

Every Real time figure is counted a second time from the raw log lines by `skald audit --live`, which also recounts the last 15-second request count and yesterday at this hour. If the second count of today's figures disagrees, today's figures are withheld and Real time shows no visitor figures until they match; the request count stays, because it is a plain count of log lines. The 15-second count is recounted only when it is less than 5 minutes older than today's figures: Skald saves it only while someone has Real time open, and lines that reach the log late (from a log shipper, say) would make an old count look wrong. An older one is reported as skipped, with its time.

## In the demo

The demo has no running Skald behind it, so its requests per minute come from the 2-minute count, and **Refresh now** says it needs a running Skald.
