"""The name lists of "Direct, likely <reason>" (direct_likely.py, and its
second count audit_direct_likely.py). Names only: each road reads a log line
and applies these lists with its own code, so this is all the two share.

A Direct visit (no referrer, no utm_source or utm_medium, no ad click id) is
split by what its own landing request and the log show, into at most one of
three reasons, in this order (CLASSIFICATION.md, "Inferred, not classified:
Direct, likely ..."):

  checkout   the landing address is a return from a payment page
  in_app     the visit's browser is an app's own browser
  shared     the landing address carries a share marker, or an app fetched
             a link preview of the same page just before

Anything else stays plain Direct. Every list is short on purpose: a name is
here only when it says one thing. Nothing here is a person's data.
"""
from __future__ import annotations

# The reasons, in the order a visit is tested. The first that matches wins.
REASONS = ("checkout", "in_app", "shared")
# How each reason reads after "Direct, likely ".
REASON_WORDS = {"checkout": "checkout or payment return", "in_app": "in-app browser",
                "shared": "shared link"}

# ------------------------------------------------------------- checkout

# A query parameter a payment provider adds when it sends the buyer back:
# (name, the start of its value, the provider). The name is compared without
# case; the value must start with the prefix as written ("" = any value with
# something in it). Each one is the provider's documented return parameter:
#   Stripe Checkout and Payment Links  success_url ?session_id=cs_...
#   Stripe Elements redirect           ?payment_intent=pi_... / ?setup_intent=seti_...
#   PayPal                             return_url ?token=...&PayerID=...; a
#                                      billing agreement ?ba_token=BA-...
#   Razorpay                           ?razorpay_payment_id=pay_...
#   Checkout.com (3-D Secure)          ?cko-session-id=sid_...
#   Adyen (redirect methods)           ?redirectResult=...
# PayPal's bare `token=` is not here: many sites use a `token` of their own.
CHECKOUT_PARAMS = (
    ("session_id", "cs_", "Stripe"),
    ("payment_intent", "pi_", "Stripe"),
    ("setup_intent", "seti_", "Stripe"),
    ("payerid", "", "PayPal"),
    ("ba_token", "BA-", "PayPal"),
    ("razorpay_payment_id", "pay_", "Razorpay"),
    ("cko-session-id", "sid_", "Checkout.com"),
    ("redirectresult", "", "Adyen"),
)
# The detail of a return found by its path alone (no provider parameter).
RETURN_PAGE = "(return page)"

# A path segment that is a checkout's end by itself (WooCommerce's
# /checkout/order-received/123/ has it before the order number). Compared
# lower case, with "_" read as "-", and a final .html, .htm, .php or .aspx
# taken off.
CHECKOUT_PAGES = (
    "payment-success", "payment-successful", "payment-complete", "payment-completed",
    "payment-confirmed", "checkout-success", "checkout-complete", "checkout-completed",
    "order-success", "order-complete", "order-completed", "order-confirmation",
    "order-confirmed", "order-received", "purchase-success", "purchase-complete",
    "purchase-completed", "thank-you-for-your-order", "thank-you-for-your-purchase",
    "thanks-for-your-order", "thanks-for-your-purchase",
)
# A done word counts only after a checkout section earlier in the same path:
# /checkout/success, /order/thank-you, /checkouts/c/abc/thank-you, /pay/done.
# A bare /success or /thank-you is not enough (a form's thank-you page looks
# the same), and stays plain Direct.
CHECKOUT_SECTIONS = ("checkout", "checkouts", "order", "orders", "payment", "payments",
                     "purchase", "billing", "pay", "cart", "subscribe", "subscription")
CHECKOUT_DONE = ("success", "successful", "thank-you", "thankyou", "thanks", "complete",
                 "completed", "confirmation", "confirmed", "return", "done", "receipt")
PAGE_ENDINGS = (".html", ".htm", ".php", ".aspx")

# --------------------------------------------------------------- in-app

# The browser labels of an app's own browser, as both roads name a browser
# (dimensions.IN_APP, audit_labels.browser_of). A link opened inside one of
# these apps usually arrives with no referrer. The generic two are a web view
# whose app did not say its name.
IN_APP_BROWSERS = (
    "Facebook app", "Instagram app", "LinkedIn app", "Gmail app", "Google app",
    "X (Twitter) app", "TikTok app", "Snapchat app", "Pinterest app", "WeChat", "Line app",
    "In-app browser (iOS)", "In-app browser (Android)",
)

# --------------------------------------------------------------- shared

# A query parameter only an app's share button adds to a link, and the app.
SHARE_PARAMS = {"igshid": "Instagram", "igsh": "Instagram", "mibextid": "Facebook"}
# Or a ref=, source=, src=, via=, from= or share= value one of whose words
# (split on anything not a letter or digit, lower case), or the whole value
# with those taken out, is one of these: the app it names, or "" for a plain
# share word. `ref=whatsapp`, `source=share`, `via=copy-link`. A value
# naming a site (ref=producthunt) is not a share. The first key in this
# order that matches decides.
SHARE_KEYS = ("ref", "source", "src", "via", "from", "share")
SHARE_WORDS = {"share": "", "shared": "", "sharing": "", "copylink": "", "sharelink": "",
               "whatsapp": "WhatsApp", "telegram": "Telegram", "messenger": "Messenger",
               "imessage": "iMessage", "sms": "SMS", "slack": "Slack", "discord": "Discord",
               "wechat": "WeChat", "viber": "Viber"}
# The detail of a share marker that names no app.
SHARE_TAG = "(share tag)"
# A link preview (classify.LINK_PREVIEWS: WhatsApp, Slack, iMessage, ...) of
# the page the visit landed on, fetched in the same minute as the visit's
# first request or up to this many minutes before (setting
# attribution.share_window_minutes). The preview comes from the app's
# servers or the sender's phone, never from the person who clicks, so it is
# matched by page and time only.
SHARE_WINDOW = 30
# Two or more apps previewed the page in the window: one visit, this detail.
MANY = "(more than one)"
