"""The sign-up mails and the usage alert, in the account mails' frame (accounts/mails.py):
"Finish signing up" with the link, or, for an address that already has an
account, "You already have an account" with the sign-in and forgot-password
pages. Either way the page said the same words; only the mailbox learns
which. A link is never logged. The usage alert (usage_alerts.py) says how
much of the month's requests is used and links to Settings > Billing.
"""
from __future__ import annotations

from email.message import EmailMessage

from .. import mailer as mailers
from ..accounts import mails
from .signups import SIGNUP_HOURS


def signup_mail(config, to: str, link: str) -> EmailMessage:
    lines = ["Someone asked to start a Skald account with this address.",
             f"The link works once, for {SIGNUP_HOURS} hours. On the page you choose your "
             "name, a password, your organisation's name and your first site."]
    foot = "If you did not ask for this, ignore this mail: nothing is made without the link."
    text = (f"Finish signing up\n\n{lines[0]}\n\nFinish here:\n{link}\n\n{lines[1]}\n\n"
            f"{foot}\n")
    return mails._build(config, to, "Finish signing up", text,
                        mails._html("Finish signing up", lines, link, "Finish signing up",
                                    foot))


def exists_mail(config, to: str, login: str, forgot: str) -> EmailMessage:
    lines = ["Someone asked to start a Skald account with this address, but it already has "
             "one. Sign in with it instead.",
             f"Forgot the password? Choose a new one here: {forgot}"]
    foot = "If you did not ask for this, ignore this mail: nothing has changed."
    text = (f"You already have an account\n\n{lines[0]}\n\nSign in here:\n{login}\n\n"
            f"{lines[1]}\n\n{foot}\n")
    return mails._build(config, to, "You already have an account", text,
                        mails._html("You already have an account", lines, login, "Sign in",
                                    foot))


def usage_mail(config, to: str, org: str, plan: str, used: int, limit: int, month: str,
               mark: int, link: str | None) -> EmailMessage:
    """A usage alert (usage_alerts.py): `mark` (80, 90 or 100) % of this month's requests
    used. `link` opens Settings > Billing on the organisation's own dashboard."""
    from .usage_alerts import percent, resets_on
    org = mailers.display_name(org, "Your organisation")
    plan = mailers.display_name(plan, "your")
    pct = percent(used, limit)
    if mark >= 100:
        subject = f"{org} has used all of this month's requests"
        title = "This month's requests are used up"
    else:
        subject = f"{org} has reached {mark}% of this month's requests"
        title = f"{pct}% of this month's requests used"
    lines = [f"{org} has used {used:,} of the {limit:,} requests its {plan} plan allows this "
             f"month ({pct}%). The count starts again on {resets_on(month)}.",
             "Once the limit is passed, Skald turns new log lines away until the month turns "
             "or the plan is bigger. Skald's shipper keeps them and sends them again later. Lines from a "
             "Cloudflare Worker are lost.",
             "To keep every line, choose a bigger plan in Settings > Billing."]
    foot = (f"You get this as an owner or admin of {org}: one mail at 80%, 90% and 100% "
            "each month. The count is the days stored so far; today is added after it ends.")
    where = f"Open Billing:\n{link}\n\n" if link else ""
    text = f"{title}\n\n" + "\n\n".join(lines) + f"\n\n{where}{foot}\n"
    return mails._build(config, to, subject, text,
                        mails._html(title, lines, link, "Open Billing", foot))
