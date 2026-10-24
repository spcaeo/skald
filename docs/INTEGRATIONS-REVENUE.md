# Revenue on leads: value, currency, customers and tags (2.32.0)

Skald says which source, page, campaign and AI assistant made money, with refunds, renewals and
lifetime value, without an adapter per payment tool. A sale is a lead row (stage `paid` or
`completed`) that carries `value` and `currency`. Stripe's own events carry them already; any
other tool posts them through the `lead` hook (the site's server, the lead files, the WordPress
plugin) or the `json` hook (Zapier, Make, n8n, a script). The figures: Leads & sales > Revenue
(`js/tabs/sa-revenue.js`), the end-user guide: [help/revenue.md](help/revenue.md), the counting:
[DATA-CONTRACT-CONVERSIONS.md](DATA-CONTRACT-CONVERSIONS.md).

Money is summed per currency and never converted: an exchange rate is a figure Skald cannot
prove (HANDOVER/05, D91).

## The fields

Added to the lead body of [INTEGRATIONS.md](INTEGRATIONS.md) ("The lead body"); `lead` and
`json` read them the same way.

| field | rule | a bad value |
| --- | --- | --- |
| `value` | a number or a numeric string, `>= 0`, at most the currency's decimals (`49.00` USD, `1200` JPY), at most 30 characters (`MAX_AMOUNT_TEXT`; a longer one is never parsed). Kept as integer minor units (`value_minor`, cents), at most 10^12 | the lead is kept without a value; the answer's `notes` and the delivery log say so (never refused) |
| `currency` | ISO 4217, three letters, upper-cased (`usd` is read as `USD`). Needed with `value` | value and currency dropped, with a note |
| `customer_ref` | the customer's own ID in the site or the tool: 1 to 128 of `[A-Za-z0-9_.:-]`, no `@` (never an email), never the shape of an IP address, and never a phone number (only digits and `+ ( ) . -`, with 7 or more digits). Ids such as `cus_9`, `c_10293847` or a UUID are kept: unlike a tag, a reference with letters may hold many digits | dropped, with a note |
| `tags` | an object of at most 5 keys. Key `[a-z0-9_]{1,24}`; value a lower-cased token `[a-z0-9_.-]{1,40}`, never 7 or more digits in all (`-` and `.` not counted) and never shaped like an IP address; a key that names a person's detail (`email`, `phone`, a name) is never kept | that tag dropped, with a note |
| stage `refunded` | on the same `external_ref` as the sale. `value` is the total refunded on that sale so far (partial allowed); without it, the whole sale's value. For a second part refund send the new total (10, then 25). Skald keeps one refund row per sale: a later, larger total in the same currency raises it and counts the difference on its own day; a smaller or equal one changes nothing. It counts only against a counted sale (not test, not removed) in the sale's currency and at most up to the sale's value; a refund of 0 is no refund. Every other refund row is kept but never counted, and listed in `refunds_without_sale`: no counted sale, a value that could not be read, or another currency than the sale's (kept without its value). A refund that arrives before its sale joins it when the sale arrives. Never a lead, never a finish | a capped or other-currency refund: a note. **A refund that arrives before its sale and is later cut to the sale's value, or emptied because the sale is in another currency, gets no note**: its answer went out before the sale was known |

**Renewals.** Each paid invoice is a new `paid` row with its own `external_ref` (the invoice ID)
and the same `customer_ref`. A `paid` whose `customer_ref` had an earlier paid sale (any day) is
a renewal; the first is a new customer. A sale without a `customer_ref` is its own customer.

**Amounts in cents.** Most payment tools send amounts in minor units (cents). `value` is in the
currency's normal units: divide by 100 for a two-decimal currency, by 1 for a zero-decimal one
(JPY, KRW, VND...), by 1000 for a three-decimal one (KWD, BHD...). A value with more decimals
than its currency has is dropped with a note. A forgotten division is not caught (4900 cents
posted as `value` 4900 is a valid 4,900.00): check the first sale on Leads & sales > Revenue.

## Zapier, Make and n8n (the `json` hook)

The address and the key: Settings > Integrations > **Zapier, Make, n8n (json)** > Make secret.
The plain key (`Authorization: Bearer <secret>`, [INTEGRATIONS.md](INTEGRATIONS.md), "The plain
key") is the no-code way; signing is the default for a script.

```
POST https://analytics.example.com/traffic-hooks/example.com/json
Authorization: Bearer <the hook's secret>
Content-Type: application/json

{"external_ref": "inv_1042", "action": "paid", "stage": "paid", "value": 49.00, "currency": "USD",
 "customer_ref": "cus_1001", "vid": "skv_Q2xhc3NpY0V4YW1wbGVJRA", "tags": {"plan": "pro"}}
```

- **Zapier.** Trigger: the payment tool's own app, or **Webhooks by Zapier > Catch Hook** with
  the tool's webhook pointed at it. Add a **Formatter > Numbers > Perform Math Operation** step
  (divide by 100) when the tool sends cents. Action: **Webhooks by Zapier > POST**, Payload Type
  `json`, Data `external_ref`, `action` `paid`, `stage` `paid`, `value`, `currency`,
  `customer_ref`, Headers `Authorization: Bearer <secret>`.
- **Make.** A **Webhooks > Custom webhook** trigger, then **HTTP > Make a request**: method POST,
  body type Raw, content type JSON, the body above with the mapped fields (`{{divide(1.total; 100)}}`
  for cents), the same header. Make can sign instead: header `X-Skald-Signature` set to
  `t={{timestamp}},v1={{sha256(timestamp + "." + body; "hex"; secret)}}`.
- **n8n.** A **Webhook** node (the tool posts to it), a **Set** or **Code** node that builds the
  body (`value: $json.body.data.total_amount / 100`), and an **HTTP Request** node: POST, JSON
  body, header `Authorization: Bearer <secret>` from n8n's credentials, not a plain field.

One delivery may carry up to 100 records (`{"records": [...]}`): a refund and its sale may go
together. Resending a record changes nothing: a row is kept once per site, tool, ref and stage
(a refund's row is raised to a larger total, never added to; the difference counts on the day it arrives).

## Recipes per tool

What each tool's webhook sends, from its own public documentation, and what to map it to. The
visitor ID (`vid`) joins the sale to its visits: pass the page's `skv_...` into the tool's
custom data at checkout (each recipe says where) and map it back. Without it, the sale still
counts, with its source "Not recorded". **Tools change their payloads: check your tool's payload
(its test event, or the first real delivery in Zapier, Make or n8n) before you rely on a
mapping.**

### Polar

Events: `order.paid` (a paid order: a one-time purchase, a subscription's first order or its
renewal) and `order.refunded`. Fields of the order (`data`): `id`, `customer_id`,
`total_amount` ("Amount in cents, after discounts and taxes"), `currency` (lower case, e.g.
`usd`), `billing_reason` (`purchase`, `subscription_create`, `subscription_cycle`,
`subscription_update`, `subscription_meter_cycle`), `refunded_amount` ("Amount refunded in
cents"), `metadata`, and `customer.external_id` (your own ID for the customer, when you set it).
Source: Polar's API schema, `Order` and `OrderCustomer`
(https://polar.sh/docs/api-reference/webhooks/order.paid, the OpenAPI file it links).

| Skald | Polar `order.paid` |
| --- | --- |
| `external_ref` | `data.id` |
| `action`, `stage` | `paid`, `paid` |
| `value` | `data.total_amount / 100` (for a two-decimal currency) |
| `currency` | `data.currency` |
| `customer_ref` | `data.customer.external_id`, else `data.customer_id` |
| `vid` | `data.metadata.skv`, when the checkout was created with `metadata: {"skv": "skv_..."}` |
| `tags` | e.g. `{"plan": "<your product's short name>"}` |

`order.refunded`: `external_ref` = `data.id`, `stage` = `refunded`, `value` =
`data.refunded_amount / 100` (Polar's running total, which Skald keeps as the latest).

### Dodo Payments

Events: `payment.succeeded`, `refund.succeeded`, `subscription.renewed`. The envelope:
`type`, `timestamp`, `data`. The payment (`data`): `payment_id`, `total_amount` ("Total amount
charged to the customer including tax, in the currency's smallest unit"), `currency`,
`customer.customer_id`, `subscription_id` (null for a one-time payment), `metadata`. The refund
(`data`): `refund_id`, `payment_id`, `amount` (the refunded amount), `currency`, `is_partial`.
Source: https://docs.dodopayments.com/developer-resources/webhooks/intents/webhook-events-guide,
https://docs.dodopayments.com/api-reference/payments/get-payments-1 and
https://docs.dodopayments.com/api-reference/refunds/get-refunds-1.

| Skald | Dodo `payment.succeeded` |
| --- | --- |
| `external_ref` | `data.payment_id` |
| `action`, `stage` | `paid`, `paid` |
| `value` | `data.total_amount / 100` (for a two-decimal currency) |
| `currency` | `data.currency` |
| `customer_ref` | `data.customer.customer_id` |
| `vid` | `data.metadata.skv`, set in the checkout session's `metadata` |

`refund.succeeded`: `external_ref` = `data.payment_id` (the sale's), `stage` = `refunded`,
`value` = `data.amount / 100`. Each refund carries its own amount: when a sale has two partial
refunds, send their sum (Skald keeps the refunded total, never adds). Each renewal is its own `payment.succeeded` with its own
`payment_id` and the same customer: post it as a sale, nothing else to do.

### Paddle (Billing)

Events: `transaction.completed` (a paid transaction; a renewal has `data.origin` =
`subscription_recurring`) and `adjustment.updated` (a refund once approved). The transaction
(`data`): `id` (`txn_...`), `customer_id` (`ctm_...`), `subscription_id`, `currency_code`,
`details.totals.total` (a string; Paddle's prices are "in the lowest denomination for the
currency", and the totals' examples read the same way: check your payload), `custom_data`,
`origin`. The adjustment (`data`): `id`, `action` (`refund`, `credit`, `chargeback`...),
`transaction_id`, `currency_code`, `totals.total`, `status` (`pending_approval`, `approved`,
`rejected`, `reversed`; most live refunds start `pending_approval`). Source:
https://developer.paddle.com/webhooks/transactions/transaction-completed and
https://developer.paddle.com/webhooks/adjustments/adjustment-created.

| Skald | Paddle `transaction.completed` |
| --- | --- |
| `external_ref` | `data.id` |
| `action`, `stage` | `paid`, `paid` |
| `value` | `data.details.totals.total / 100` (a string: make it a number; two-decimal currency) |
| `currency` | `data.currency_code` |
| `customer_ref` | `data.customer_id` |
| `vid` | `data.custom_data.skv`, passed as `customData` when the checkout opens |

Refunds: send only an `adjustment.updated` with `data.action` = `refund` and `data.status` =
`approved` (filter the rest in Zapier, Make or n8n): `external_ref` = `data.transaction_id`,
`stage` = `refunded`, `value` = `data.totals.total / 100`. Each approved refund adjustment is
its own amount: when a sale has two partial refunds, send their sum (Skald keeps one refunded
row per sale and raises it to the larger total; it never adds two).

### Lemon Squeezy

Events: `order_created`, `order_refunded`, and for subscriptions `subscription_payment_success`
(each paid invoice, the first and the renewals). The order (`data.attributes`): `identifier`,
`order_number`, `customer_id`, `currency`, `total` ("A positive integer in cents"),
`refunded`, `refunded_amount` (cents). The subscription invoice (`data.attributes`):
`subscription_id`, `customer_id`, `billing_reason` (`initial`, `renewal`, `updated`), `currency`,
`total` (cents), `refunded_amount`. Custom data given at checkout as
`checkout[custom][skv]=skv_...` comes back in `meta.custom_data`. Source:
https://docs.lemonsqueezy.com/help/webhooks/event-types,
https://docs.lemonsqueezy.com/api/orders/the-order-object,
https://docs.lemonsqueezy.com/api/subscription-invoices/the-subscription-invoice-object and
https://docs.lemonsqueezy.com/help/checkout/passing-custom-data.

| Skald | Lemon Squeezy `order_created` | `subscription_payment_success` (renewal) |
| --- | --- | --- |
| `external_ref` | `data.attributes.identifier` | `data.id` (the invoice) |
| `action`, `stage` | `paid`, `paid` | `paid`, `paid` |
| `value` | `data.attributes.total / 100` | `data.attributes.total / 100` |
| `currency` | `data.attributes.currency` | `data.attributes.currency` |
| `customer_ref` | `data.attributes.customer_id` | `data.attributes.customer_id` |
| `vid` | `meta.custom_data.skv` | `meta.custom_data.skv` |

Send `subscription_payment_success` only when `billing_reason` is `renewal`: the first invoice
comes with its `order_created` already. `order_refunded`: `external_ref` =
`data.attributes.identifier`, `stage` = `refunded`, `value` = `data.attributes.refunded_amount / 100`.

### Gumroad

Gumroad's Ping posts a form-encoded body (not JSON) for each sale and again when the sale is
refunded, so it goes through Zapier, Make or n8n. Fields: `sale_id`, `price` ("The price paid,
in USD cents"; `currency` is the currency the product is listed in, while "price and the other
amount fields are always USD cents"), `purchaser_id` (only when the buyer has a Gumroad
account), `subscription_id`, `is_recurring_charge` (a renewal), `refunded`, `resource_name`
(`sale`, or `refund` when the same purchase is later refunded), `test`, `url_params`. Source:
Gumroad's Ping documentation (https://gumroad.com/ping) and its source,
`app/modules/purchase/ping_notification.rb` in github.com/antiwork/gumroad.

| Skald | Gumroad Ping (`resource_name` = `sale`) |
| --- | --- |
| `external_ref` | `sale_id` |
| `action`, `stage` | `paid`, `paid` |
| `value` | `price / 100` |
| `currency` | `USD`, always (not the `currency` field: the amounts are USD cents) |
| `customer_ref` | `subscription_id` for a subscription (the same on every renewal), else `purchaser_id` when present |
| `vid` | `url_params[skv]`, when the product link carries `?skv=skv_...` |
| `test` | `true` when Gumroad sends `test` |

`resource_name` = `refund`: `external_ref` = `sale_id`, `stage` = `refunded`, no `value` (the
Ping does not carry the refunded amount, so Skald takes off the whole sale). Check a partial
refund against your Gumroad dashboard: Skald has no amount for it from the Ping.

## Stripe

Read directly, no mapping (`skald/conversions/adapters/stripe.py`): subscribe to
`checkout.session.completed`, `checkout.session.async_payment_succeeded`, `invoice.paid`
(renewals: `billing_reason` `subscription_cycle`), `invoice_payment.paid` (since Stripe's API
2025-03-31 the only event that ties a renewal's payment intent to its invoice, so a renewal's
refund finds it) and `charge.refunded`. Skald keeps the amount
(`amount_total`, `amount_paid`, `amount_refunded`), the currency, the Stripe customer (`cus_...`)
as `customer_ref` and the payment intent to match refunds; it still never reads the customer's
name, email or address. Details: [INTEGRATIONS.md](INTEGRATIONS.md), "Stripe".

## Where the values show

- Leads & sales > Revenue: [help/revenue.md](help/revenue.md).
- The lead's drawer (Leads & sales > Leads): value, refunded amount, customer reference, tags.
- `GET /traffic-hooks/<site>/leads` ([INTEGRATIONS-LEADS.md](INTEGRATIONS-LEADS.md)) and
  `skald conversions list` return value, currency, customer reference and tags, so a site can
  check that Skald holds every sale it sent.
- Sale alerts (2.33, off by default): one alert per counted sale, and per counted refund
  part, through the site's alert mail and the `alert.opened` webhook (Slack too), with an
  optional minimum per currency; settings and rules in [SETTINGS.md](SETTINGS.md) "Sale
  alerts", the alert's fields in [DATA-CONTRACT-ALERTS.md](DATA-CONTRACT-ALERTS.md).
