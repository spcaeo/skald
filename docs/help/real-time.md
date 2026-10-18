# Real time: who is on your site now

See how many people are on your site right now, where they are on a world map, what they are reading, and which AI assistants and crawlers are fetching pages at this moment. This guide covers where it is, what each figure means, and how fresh it is.

## Where to find it

- **Overview › Real time**: its own tab. It always shows now, whatever period is picked at the top.
- **Overview › Summary in Live mode**: turn on **Today · Live** in the top bar and Real time is the first thing on the page, above today's tiles.

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

Countries too small for the map's outlines (Singapore, Malta and others) are drawn as a dot. The map is drawn from Natural Earth's public-domain outlines and is part of the page: no map service is asked for anything.

## The lists

- **Pages being read**: page views in the last 30 minutes, by page.
- **Newest visits**: the ten newest visits, with time, country, device, where they came from, the page they landed on and how many pages they have read so far. **active now** means a request in the last 5 minutes. No address and no browser string is shown here.
- **Sources now** and **Devices now**: visitors active in the last 30 minutes, by where they came from and by device.
- **AI and crawlers now**: requests in the last 30 minutes by AI assistants and search crawlers, by name, and other bots and scanners as one count. These are machines, counted in requests, never as visitors.

Select any page, source, device or crawler to open its detail.

## Page groups

Real time always covers the whole site. On a page group, a note says so.

## How the figures are checked

Every Real time figure is counted a second time from the raw log lines by `skald audit --live`, which also recounts the last 15-second request count. If the second count of today's figures disagrees, today's figures are withheld and Real time shows no visitor figures until they match; the request count stays, because it is a plain count of log lines.

## In the demo

The demo has no running Skald behind it, so its requests per minute come from the 2-minute count, and the page says so.
