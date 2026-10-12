"""The sign-up mails, in the account mails' frame (accounts/mails.py):
"Finish signing up" with the link, or, for an address that already has an
account, "You already have an account" with the sign-in and forgot-password
pages. Either way the page said the same words; only the mailbox learns
which. A link is never logged.
"""
from __future__ import annotations

from email.message import EmailMessage

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
