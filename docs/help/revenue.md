# Revenue

Which sources (AI assistants among them), pages and campaigns made money: send a value and a currency with each sale, and **Leads & sales > Revenue** sums them per currency, takes refunds off, counts new customers and renewals, and shows lifetime value by first source. No adapter per payment tool: any tool that can reach Zapier, Make, n8n or your own server can send its sales.

## What the Revenue tab shows

Open [Leads & sales > Revenue](#sales/revenue). The period is the one in the top bar.

- **The numbers, per currency.** **Net revenue** (what was sold, less what was refunded in the period), **Sales**, **Refunds**, **New customers** (a customer's first paid sale), **Renewals** (a paid sale of a customer who had paid before) and **Revenue per visitor**.
- **Revenue per visitor** is net revenue divided by the visitors of the same verified days: two counted figures, divided. It is given over at least 10 visitors, and only when every day of the figures has its whole visitor count.
- **Currency.** With sales in more than one currency, a **Currency** switch picks which one the numbers show. The others are listed under the numbers, never added. Skald never converts one currency into another: an exchange rate is not something it can check.
- **Breakdown.** The table shows net revenue and sales by **Source (last touch)**, **First touch**, **Campaign**, **Landing page**, **Country**, **Device**, **Reported by** (the tool), **Label** or **Tag**. A landing page has copy and open icons at its end, as every page does.
- **Tag.** Choose one tag (for example `plan = pro`) and the numbers become that tag's own net revenue and sales, and the table lists every value of that tag. Refunds, customers, renewals and the other breakdowns are not split by tag, so they show with **Every tag**.
- **Lifetime value, by first source** (folded at the bottom). Every customer, by the first source of their first paid sale: how many customers, what they paid in all (refunds taken off), the average per customer, their renewals and the share who paid again (given over at least 10 customers). It counts every sale Skald keeps, not the period in the top bar; **Settings > Data retention** applies.

The currency, the breakdown and the tag are in the page's address (`#sales/revenue?cur=EUR&by=campaign&tag=plan:pro`), so a link or a reload opens the same view.

A lead's drawer on [Leads](#sales/leads) shows the sale's own **Value**, what was **Refunded** on it, the **Customer** reference your tool sent (with a copy icon) and its **Tags**.

## The rules behind the numbers

- **A sale** is a completed or paid row that carries a value, counted once per sale (the paid step when a sale reports both). A sale without a valid value and currency is still a lead, as before; it is not revenue.
- **A refund** counts on the day it arrives, against the sale's own source, campaign and page, not on the sale's day. A refund sends the total refunded on that sale so far; a later, larger total counts the difference on its own day, so two part refunds of $10 and then $15 are sent as 10, then 25. It counts only against a sale Skald counts, in the sale's own currency, and never more than the sale's value. A refund with no value takes off the whole sale. A refund of 0 is no refund. A refund that arrives before its sale waits and joins the sale when it comes.
- **A refund that came before its sale gets no note later.** When the sale arrives, a refund that was waiting for it is cut to the sale's value, or kept without its value when the sale is in another currency. Skald answered the refund when it came, before the sale was known, so nobody is told about the cut: check the figures on this tab or the lead's drawer.
- **A renewal** is a paid sale with its own reference (the invoice) and the same customer reference as an earlier paid sale. The first paid sale of a customer is a new customer. A sale without a customer reference is its own customer.
- **A refund counted nowhere** is kept but never taken off: its sale is a test, was removed or never came, it was sent in another currency than its sale (kept without its value), or its value could not be read. The tab lists how many under the table, over every row kept, with the total of those kept with a value.
- **Test rows and removed rows never count.**
- **A withheld day.** Every revenue figure is counted twice, the second time on its own road (from the stored rows and again from the deliveries as they arrived). A day the two disagree on is left out of every figure and said once at the top: "1 day withheld (...): left out of every figure below, never counted as zero."
- **Not recorded is never zero.** Revenue is recorded from the first day a sale or a refund with a value was kept (in the site's time zone). The days before it have no revenue figures at all, not zero: the tab says from which day values are recorded, and revenue per visitor counts only the days with figures.

## Send value and currency

Add these to the lead body your site's server, Zapier, Make, n8n or a lead file already sends (see [Send leads from your backend](leads-from-your-backend.md) and [Webhooks](webhooks.md)):

```
{
  "external_ref": "inv_1042",
  "action": "paid",
  "stage": "paid",
  "value": 49.00,
  "currency": "USD",
  "customer_ref": "cus_1001",
  "tags": {"plan": "pro"}
}
```

| Field | What to send |
| --- | --- |
| `value` | The amount in the currency's normal units: `49.00` dollars, `1200` yen. A number, or a number as text (`"49.00"`), zero or more, with no more decimals than the currency has, and at most 30 characters long. Many tools send amounts in cents: divide by 100 first (not for a currency without decimals, such as JPY) |
| `currency` | The three-letter code: `USD`, `EUR`, `GBP`, `JPY`. Needed with `value`. Lower case is fine (`usd`) |
| `customer_ref` | Your customer's own ID in your system or tool (`cus_1001`, `u-119797`): letters, digits and `_ . : -`, at most 128. Never an email, a phone number (only digits and `+ ( ) . -`, with 7 or more digits) or the shape of an IP address: such a reference is dropped, with a note. It is what joins a renewal to the first sale |
| `tags` | Up to 5 labels of your own, such as `{"plan": "pro", "seats": "5"}`. Names: lowercase letters, digits and `_`, at most 24. Values: lowercase letters, digits and `_ . -`, at most 40, and never 7 or more digits in all (`-` and `.` not counted) or the shape of an IP address. A name that is a person's detail (`email`, `phone`, a name) is never kept |
| `stage: "refunded"` | A refund: the same `external_ref` as the sale, with `value` the total refunded on that sale so far: for a second part refund, send the new total (leave it out for a whole refund). At most the sale's value, in the sale's currency |

A bad value is never a refused lead: the lead is kept without the value, and the answer and the delivery log say what was dropped. The same for a bad currency, customer reference or tag.

**Renewals.** Send each paid invoice as its own sale: its own `external_ref` (the invoice ID) and the same `customer_ref`.

**From the lead files and the WordPress plugin.** The PHP, Node and Python lead files take `value`, `currency`, `customer_ref` and `tags` in their last argument (see [Send leads from your backend](leads-from-your-backend.md)). The WordPress plugin takes money only from your own code, through its `skald_leads_lead` filter: a form field never sets a value, since any visitor could post any amount.

## Stripe

Stripe needs no field mapping: Skald reads the amount, the currency and the Stripe customer from Stripe's own events. Subscribe the Stripe webhook to `checkout.session.completed`, `checkout.session.async_payment_succeeded`, `invoice.paid` (renewals), `invoice_payment.paid` (on Stripe's API 2025-03-31 and later, the only event that ties a renewal's payment to its invoice, so its refund finds it) and `charge.refunded` (refunds). See [Webhooks](webhooks.md).

## Other payment tools

Polar, Dodo Payments, Paddle, Lemon Squeezy and Gumroad send webhooks in their own shape. Point the tool's webhook at Zapier, Make or n8n (or a small script on your server), map its fields to the body above and post it to the **Zapier, Make, n8n (json)** hook. The field names for each tool, with a link to its own documentation: [docs/INTEGRATIONS-REVENUE.md](https://github.com/spcaeo/skald/blob/main/docs/INTEGRATIONS-REVENUE.md). Tools change their payloads: check your tool's payload against its test event before you rely on the mapping.

What to map, in short (amounts these tools send are in cents: divide by 100 for a two-decimal currency):

| Tool | Sale event | `external_ref` | `value` | `currency` | `customer_ref` | Refund event |
| --- | --- | --- | --- | --- | --- | --- |
| Polar | `order.paid` | `data.id` | `data.total_amount` / 100 | `data.currency` | `data.customer_id` | `order.refunded`: `data.refunded_amount` / 100 |
| Dodo Payments | `payment.succeeded` | `data.payment_id` | `data.total_amount` / 100 | `data.currency` | `data.customer.customer_id` | `refund.succeeded`: `data.amount` / 100, on `data.payment_id` (two refunds: send their sum) |
| Paddle | `transaction.completed` | `data.id` | `data.details.totals.total` / 100 | `data.currency_code` | `data.customer_id` | `adjustment.updated`, action `refund`, status `approved`: `data.totals.total` / 100, on `data.transaction_id` (two refunds: send their sum) |
| Lemon Squeezy | `order_created`; renewals `subscription_payment_success` | `data.attributes.identifier`; the invoice's `data.id` | `data.attributes.total` / 100 | `data.attributes.currency` | `data.attributes.customer_id` | `order_refunded`: `data.attributes.refunded_amount` / 100 |
| Gumroad (Ping) | `resource_name` = `sale` | `sale_id` | `price` / 100 | always `USD` (Gumroad's amounts are USD cents) | `subscription_id`, else `purchaser_id` | `resource_name` = `refund`: no value (the whole sale) |

For every tool, send `action` and `stage` as `paid`, and a refund as `stage` `refunded` on the sale's own `external_ref`. To join a sale to its visits, pass the page's visitor ID into the tool's custom data at checkout (Polar and Dodo `metadata.skv`, Paddle `custom_data.skv`, Lemon Squeezy `checkout[custom][skv]`, Gumroad `?skv=` on the product link) and map it back as `vid`.

## Troubleshooting

- **"No revenue yet"**: no sale has arrived with a value and a currency. Look at **Settings > Integrations > Status**: a delivery whose value was dropped says why.
- **The numbers look 100 times too big**: the tool sent cents and they were posted as `value`. Divide by 100 in the mapping.
- **A renewal shows as a new customer**: the renewal was sent without the same `customer_ref` as the first sale.
- **Two currencies, one total**: there is none, on purpose. Pick each currency with the **Currency** switch.
