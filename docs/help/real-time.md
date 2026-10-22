# Real time: who is on your site now

See how many people are on your site right now, where they are on a world map, what they are reading, and which AI assistants and crawlers are fetching pages at this moment. This guide covers where it is, what each figure means, and how fresh it is.

## Where to find it

- **Overview › Real time**: its own tab. It always shows now, whatever period is picked at the top.
- **Overview › Summary in Live mode**: turn on **Today · Live** in the top bar. The page opens on the short version: visitors on the site now, how many arrived in the last 5 minutes, the last 30 minutes minute by minute, the map and what visitors are doing now (the newest visitors and the pages they read), from the same figures as this tab and under one **Pause live** button. See **Today, live** below.

## How fresh it is

Real time has two clocks, and it shows both at the top:

- **Visitors as of 14:02:10**: the people figures. Skald counts them every 2 minutes, with the same rules as every other figure on the dashboard, so a crawler pretending to be a browser, your own office and the heartbeat are never in them.
- **Requests as of 14:03:45, read from the log every 15 s**: every request your server logged, read from the end of the log. These are not sorted into people and machines yet, so they are always called requests, never visitors.

The page asks for fresh figures every 15 seconds while it is open and visible. **Pause** holds everything still; **Resume** starts again. If the visitor clock says **late**, the 2-minute count has not run for more than 10 minutes: check Site › Data quality.

## What the figures mean

| Figure | What it is |
|---|---|
| Active now | Visitors with any request in the last 5 minutes. A visitor is a visit that read a page, the same count as **Visitors** everywhere else. |
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

Overview › Summary with **Today · Live** on keeps one place for each answer, each with a link to the tab that lists it all:

1. **The live strip.** Visitors on the site now (a request in the last 5 minutes), how many arrived in the last 5 minutes, and the last 30 minutes as bars. Beside it, **Visitors**, **Pages read**, **Leads** and **Visitors from AI** for today so far.
2. **Where visitors are**, the map across the page (today by country, a pulsing dot for each city with someone on the site in the last 30 minutes), and under it **What visitors are doing now**:
   - on the left, the five visitors with the newest activity: where they are, their device, where they came from, and the pages they read in order, `/ → /pricing → /book-a-demo`, the page they are on now marked, with "now on /pricing · 20 s ago". A long path is cut in the middle; point at it for the whole path. As visitors move, a new page joins their path, a new visitor slides in at the top, and one who has gone quiet fades out. Select one to open the visitor drawer with its journey. **See every visit** opens Traffic › Visitors.
   - on the right, **Pages read in the last 30 minutes**, the same figure as before. Press a page to see only the visitors who read it; press it again for the page's detail.
   - Point at a row and its city pulses on the map; point at a city and its rows stand out.
   - With a drill-down open (for example a country, `dd=country:CA`), the map shows that country and the list only its visitors, with a line saying how many are shown. The list can follow a country, a city, a source, a referring site or assistant, a device, a landing page or a page read; another kind of filter (a campaign, an hour) says so in one line and the list shows everyone. The pages read are always every visitor's.
3. **Where today's visitors came from** and **How today's visits moved** (the flow, two pages deep).
4. **What converted today** (forms sent and demos booked) and **AI & bots today** (pages assistants fetched for people, visitors they sent, crawler requests by bot).

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

The demo has no running Skald behind it, so its requests per minute come from the 2-minute count, and the page says so.
