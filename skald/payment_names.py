"""The name lists of "Returned from payment" (owner's decision 6, 11 Nov 2026).

A visit whose referrer is a payment page is a buyer coming back from paying,
not a new source: it is "Returned from payment". It never counts as a
referral ("Other website"), it never opens a new visit inside the visit gap
(it continues the open visit, like a page from the site itself), and a lead
or sale made after it keeps the source of the visit before it.

Names only: the main road (dimensions.py, conversions/normalise.py,
conversions/fill.py, leads.py) and the second counts (audit_labels.py,
audit.py, audit_filled.py, audit_leads.py) each apply these lists with their
own code, so this is all they share.

  PAYMENT_HOSTS   a referrer's host (lower case, compared whole) that is a
                  payment page. "www." is taken off a referrer's host before
                  it is compared, so www.paypal.com is paypal.com; both are
                  listed so the list reads as decided.
  CHECKOUT_KEY    where a site names its own checkout host(s), when it has
                  one on a host of its own that is not in `site.hosts`
                  (`site.checkout_hosts: [<its host>]`). A host listed
                  in `site.hosts` is the site itself ("This site") and stays so.
"""
from __future__ import annotations

RETURNED = "Returned from payment"

PAYMENT_HOSTS = ("checkout.stripe.com", "paypal.com", "www.paypal.com",
                 "checkout.paypal.com")

CHECKOUT_KEY = ("site", "checkout_hosts")

# The referrer label (the Referrers breakdown) of a payment page: one row,
# like "(this site)", never a referring site.
PAYMENT_REFERRER = "(payment page)"
