"""The name lists of "Social networks" (social_networks.py, and its second
count audit_social.py). Names only: each road reads a log line and applies
these lists with its own code, so this is all the two share.

A visit whose source type is Social media (CLASSIFICATION.md, "The source
type of a visit": decided before this, by each road's own rule, and never
changed here) is given exactly one network, by the first page's referrer
when it has one, else by its landing address's tags:

  referrer   its host (no "www.") is one of a network's HOSTS or under one
             (l.facebook.com is under facebook.com), or is <base>.<tld> for
             one of its ANY_TLD bases (pinterest.co.uk), or starts with one of
             its APPS (an android-app://com.linkedin.android/ referrer's host
             is the app's id)
  utm_       no referrer: the words of utm_source (split on anything not a
             letter or digit, lower case), else of utm_medium: a word that
             is one of a network's UTM_WORDS names it
  click id   else the first of SOCIAL_CLICK_IDS on the landing address
             (fbclid is Facebook's, as the campaign label
             "facebook / (fbclid) / -" says)

The first of these that names a network decides; one that names two
(utm_source=facebook-instagram) gives OTHER, and so does none
(utm_source=social). A visit is counted once, in one network.

The networks are tested in the order listed: the first that matches wins
(Threads' Android app id starts like Instagram's, so Threads comes first). A
Social media visit no list names is OTHER, "Social, network not named": the
networks always add up to the Social media visits.

Only hosts the existing rule already calls Social media are here. A host it
calls Other website stays one: producthunt.com, threads.com, fb.me and every
Mastodon server but mastodon.social (the servers cannot be listed, and the
referrer names only the server) are not reclassified by this list.
"""
from __future__ import annotations

# (id, the name shown, hosts, any-TLD bases, Android app id starts, utm words,
# click ids). The id is what the address and the stored blob carry: short,
# lower case, never a person's data.
NETWORKS = (
    ("x", "X", ("x.com", "twitter.com", "t.co"), (), ("com.twitter",), ("x", "twitter"),
     ("twclid",)),
    ("linkedin", "LinkedIn", ("linkedin.com", "lnkd.in"), (), ("com.linkedin",), ("linkedin",),
     ("li_fat_id",)),
    ("facebook", "Facebook", ("facebook.com", "fb.com"), (), ("com.facebook",), ("facebook",),
     ("fbclid",)),
    # Threads' Android app is com.instagram.barcelona: before Instagram.
    ("threads", "Threads", ("threads.net",), (), ("com.instagram.barcelona",), (), ()),
    ("instagram", "Instagram", ("instagram.com",), (), ("com.instagram",), ("instagram",), ()),
    ("reddit", "Reddit", ("reddit.com",), (), ("com.reddit",), ("reddit",), ()),
    ("youtube", "YouTube", ("youtube.com", "youtu.be"), (), ("com.google.android.youtube",),
     ("youtube",), ()),
    ("tiktok", "TikTok", ("tiktok.com",), (), (), ("tiktok",), ("ttclid",)),
    ("pinterest", "Pinterest", (), ("pinterest",), (), (), ()),
    ("bluesky", "Bluesky", ("bsky.app",), (), (), (), ()),
    # mastodon.social only: the one server the Social media rule names.
    ("mastodon", "Mastodon", ("mastodon.social",), (), (), (), ()),
    ("hackernews", "Hacker News", ("ycombinator.com",), (), (), (), ()),
    ("quora", "Quora", ("quora.com",), (), (), (), ()),
    ("telegram", "Telegram", ("t.me",), (), ("org.telegram.messenger",), (), ()),
    ("whatsapp", "WhatsApp", ("whatsapp.com",), (), ("com.whatsapp",), (), ()),
    ("slack", "Slack", ("slack.com",), (), ("com.slack",), (), ()),
    ("discord", "Discord", ("discord.com",), (), (), (), ()),
)
# A Social media visit no list above names (utm_source=social, say).
OTHER = "other"
OTHER_NAME = "Social, network not named"
NAMES = {**{n[0]: n[1] for n in NETWORKS}, OTHER: OTHER_NAME}
IDS = tuple(n[0] for n in NETWORKS) + (OTHER,)

# The ad click ids that make a visit with no referrer and no utm_ tag Social
# media, in the order the source type tests them (after Google's and
# Microsoft's, which make it a Search engine).
SOCIAL_CLICK_IDS = ("fbclid", "li_fat_id", "ttclid", "twclid")

# The source type these figures break down (the stored name).
SOCIAL = "Social media"

# How a visit was matched, beside its network ("via"): the referrer's host
# (no "www.", at most HOST_KEEP characters), an app as APP_PREFIX + its id,
# or the tag: "(utm_source)", "(utm_medium)", "(fbclid)", ...
APP_PREFIX = "android-app://"
HOST_KEEP = 60

# Each network's landing pages: the top LANDINGS_KEPT by visits (more visits
# first, then the path in code-point order), the rest summed into ALL_OTHERS,
# so the pages still add up to the network's visits. A path is the page as
# the journeys keep it (at most 70 characters, no query).
LANDINGS_KEPT = 20
ALL_OTHERS = "(all others)"
