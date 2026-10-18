# Where visitors come from, and their journeys

Most visits say **Direct**: the browser sent no referrer. Many of them are people coming back, who first found you through a search, an AI assistant or a post days before. This guide covers how Skald finds a visitor's first visit, where you see it, and the visitor drawer with every visit of one visitor.

## First touch: the first visit we know of

For every visit, Skald looks for the same visitor's first visit it knows of. It tries three links, in this order, and the first one that finds an earlier visit wins:

1. **The visitor ID**, when the script tag has visitor IDs on (Settings › Tracking). The visit is the ID's when the ID's page view of the landing page arrived within seconds of the visit, and no other ID did. Its first touch is the ID's earliest page view.
2. **The address and browser**, when the site keeps addresses (Settings › Data retention › People). The earliest kept visit from the same address with the same browser and system, even earlier the same day.
3. **The 30-day code**, when the visitor key is set. It gives the day and the source type of the first visit within 30 days, not the site that sent it.

When none finds an earlier visit, the visit says **first visit we know of**. Skald never guesses. A site that keeps no addresses uses only the visitor ID and the 30-day code, and says which one linked each visit.

One address can be several people (an office), and one person on two devices is two visitors. A visitor ID is one browser.

## Where you see it

- **Traffic › Visitors**, in **Each visit**: under a visit's source, a line such as "First came from google.com, 3 days ago". It shows only when the first visit came from somewhere else.
- **Overview › Real time**, in **Newest visits**: the same line, and each visit opens the visitor drawer.
- **Traffic › Sources**, in **Where returning visitors first came from**: for the period, how many Direct visits came before, by where they first came from and by the site that sent them; and every returning visit by where it first came from. Each day's figures are counted twice, by two separate roads; a day where the two disagree is withheld. A day counted before this existed is left out and said.

## The visitor drawer

Every visit and every visitor opens in the same drawer: a row of the visit list, a newest visit in Real time, a funnel's journey, a visit picked out of the visitor flow, a person found with **Find a person**, and a converted person or conversion under Leads & sales.

- **The title** names the visitor by city ("Visitor from Toronto"), else by country, and the line under it says how many visits over how many days, and any booked demo or lead.
- **At the top**: first seen, how many visits over how many days, where the visitor first came from (and how long ago; the link that tied the visits is on hover), the city (or the country) with its flag and three-letter code, the device with its browser and system, and the outcome: a booked demo, a lead, a form sent, or none linked.
- **Journey, newest visit first**: each visit as a card, its steps down a line. Where it came from, each page in order with the time between pages on the line, and how it ended: left, sent a form, a lead, or a booked demo. Between visits it says how long after ("12 days later"). The steps appear one by one when the drawer opens; **Replay**, beside the close button, plays the visits again, oldest first, at their real pace (one second per minute, at most four seconds a visit). With reduced motion on, it stays still. Hover or focus a page for its time; click it to open the page.
- **Every visit as a table**: open it for the same visits as rows, the first visit highlighted.
- **Leads and conversions** linked to the visits. A lead is matched to a visit by the time a form was sent: likely, never certain.
- **This visit**: the visit's own labels and campaign tags.

A visit alone is anonymous. Every visit of the visitor shows only to admins and owners, and only where the site keeps addresses. Each time it is opened, the audit log records it (never the address). Pages seen only by the script tag, with no visit in the server log, are marked "seen by the script".
