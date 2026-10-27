# Client reports

Branded reports for your clients: a mail with a PDF attached, sent on a schedule you set, with your agency's name, colour and logo.

Client reports come with accounts. Owners and admins of the site's organisation set them up in [Settings > This site > Mail & reports > Client reports](#settings/site/mail?sub=reports).

## Make a report

1. Open **Settings > This site > Mail & reports**, tab **Client reports**, for the site and select **New report**, the button beside the page title. The form opens in a panel. Each report you make is a row with its schedule, its next send and a status (**On schedule**, **No one confirmed yet**, **Last send failed** or **Paused**); select the row for **Preview**, **Download PDF**, **Send now**, **History**, **Edit** and **Delete**.
2. Give it a **name**. The client sees it at the top of the mail and the PDF.
3. Add the **recipients**, one address per line (20 at most).
4. Choose **when it goes**: weekly on a weekday, monthly on a day of the month, or every few days from a start date, at a time of day. Times are in the site's time zone (Settings > This site > Site > Names & time).
5. Choose the **period** it covers.
6. Tick the **sections** to include, and write any **notes** and a **footer** line.
7. Select **Preview** to see the mail, or **Download PDF** to see the attachment. Nothing is sent.
8. Select **Create the report**.

## Recipients confirm first

Every address you add gets one short mail with a confirm link, and nothing else until its owner follows the link. This is the rule for every mail Skald sends, so nobody can be put on a list without agreeing. With no mail server set up yet (Settings › This site › Mail & reports), no link goes out and the page says so: save the report again once mail is set up.

The list says how many recipients have confirmed and who is still waiting. A report goes to the confirmed ones only; the send record says how many were left out.

## When it goes and what it covers

| Schedule | Goes |
| --- | --- |
| Weekly | Every chosen weekday, at the time |
| Monthly | On the chosen day. Day 29, 30 or 31 in a shorter month: its last day |
| Every few days | Every 1 to 92 days from the start date |

| Period | Covers |
| --- | --- |
| Last week | Monday to Sunday of the week before |
| Last month | The whole calendar month before |
| Month to date | The 1st of this month to yesterday. Sent on the 1st, the whole month before |

The list shows, for each report, when it goes next and which days that send will cover.

## What a report shows

| Section | Shows |
| --- | --- |
| Summary | Visitors, pages read, visitors from AI, leads and returning visitors; visitors per day as a bar chart; which days are in the figures |
| Where visitors came from | Each source's visitors and share |
| Top pages | The 10 most-read pages |
| Countries and cities | The top countries and cities by visitors |
| AI and bots | Pages AI read because someone asked it, with the requests second (a page asked for again within seconds, or its files, is not a new read; a day before reads were counted leaves them not recorded), training crawlers, search engines; the busiest crawlers; the AI assistants that sent visitors |
| Leads | Leads in the period by kind: the dashboard's Leads tile (forms sent and demos booked, completed; test rows left out), counted a second time. A period that starts before leads were recorded gets no sum, and says so |
| Search Console | Google's clicks, impressions, CTR and average position for the period, with the top queries and pages, from the synced Search Console figures |
| Notes | Your own words, as you typed them |

**Search Console** needs the site connected first (Settings › This site › Leads & tools › Search Console & Bing); until then the section says it is not connected. Only days Google calls final are counted. The newest days, which Google may still change, are listed as provisional and left out, and so are days not synced yet. Search Console's days run on Pacific Time, and a click is not a visit, so these figures are never added to Skald's own.

## Figures you can stand behind

A report only shows figures Skald has already stored and checked:

- Only **verified, whole days** are counted. A day whose figures did not reconcile (withheld), a day the logs did not wholly cover (partial) and a day not recorded are listed by date under the summary, drawn as a pale stub in the chart, and **never counted as zero**.
- A change against the period before is shown only when both periods are whole.
- Before it is sent, a report's sums are counted a second time from the stored days. If they disagree, or no day of the period is verified, the report is not sent and the reason is recorded.
- If a breakdown (sources, countries, cities) was not recorded on every day of the period, that section says so instead of showing part of it.

## Your branding

The **Agency branding** card on the same page is for every report of every site in your organisation:

- **Agency name**: in each report's header, and as the mail's From name. The mail is still sent from the server's own address.
- **Brand colour**: the band at the top of each report. Text on it is white or dark, whichever reads better.
- **Agency logo**: a PNG or JPEG of at most 256 KB, shown on the right of the header. Untick **Show the agency logo** in a report to leave it out there.

The site's own logo (Settings > This site > Site > Names & time > Logo) is shown on the left. An SVG logo cannot travel in a mail or a PDF, so the site's letter is shown instead.

## Send now, history and pausing

- **Send now** sends the report at once to its confirmed recipients, for the period it would cover today. At most 3 sends by hand in 10 minutes.
- **History** lists every send: when, who started it (the schedule or a person), the period, the addresses it went to, and whether it went or why not.
- **Paused** keeps a report but stops its schedule. Send now still works.

## When a send fails

A scheduled send that fails (the mail server is down, say) is tried once more 30 minutes later. After that it waits for its next scheduled day. If the period's last day is not stored yet when the report is due, it waits for the morning run until 18:00, then goes with that day listed as not recorded.

A report needs a mail server (Settings > This site > Mail & reports). Without one, reports can still be made, previewed and downloaded, and the page says why they are not sent.
