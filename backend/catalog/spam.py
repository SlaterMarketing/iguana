"""Is this form submission from a person?

The contact form had no gate at all, and a bot found it. Fifteen submissions in three days, every one a random
string with no name and no spaces (`qjWYpEHreBSHUKwJlWwkQGD`, `txfyHCRLeIwqciJGuOgYO`), and every one emailed
hello@ because the endpoint alerts on any enquiry. That is the failure that matters: not the rows, which are
cheap, but that the owner's inbox learns to ignore the alert that a real customer's enquiry arrives in.

Two gates, because they catch different bots.

A honeypot catches anything that renders the form and fills every input it finds. It costs a real person
nothing, since the field is hidden and stays empty.

A honeypot does NOT catch a bot posting straight at the API, which is what this one does, so the message
itself is judged too. The test is deliberately crude and only ever applied to free text a human wrote: real
enquiries have spaces in them. Someone typing a single word is rejected with a message telling them to write
a sentence, which is a far better outcome than their note being buried under fifty random strings.
"""

import re

# What the form renders hidden. A browser leaves it empty; a form-filling bot does not.
HONEYPOT_FIELD = 'company_website'

# Free-text fields, as opposed to a name or a city, which are legitimately one word.
MESSAGE_FIELDS = ('message', 'notes', 'details', 'comments')

_RANDOM_RUN = re.compile(r'^[A-Za-z0-9]{12,}$')


def honeypot_tripped(fields):
    return bool(str(fields.get(HONEYPOT_FIELD, '')).strip())


def looks_like_a_person_wrote_it(text):
    """True when the free text reads like a sentence rather than a generated token."""
    text = str(text or '').strip()
    if not text:
        return True  # an empty optional field is not evidence of a bot
    if ' ' in text or '\n' in text:
        return True
    # One unbroken run of letters and digits, long enough to be a token rather than a word: "hola" passes,
    # "qjWYpEHreBSHUKwJlWwkQGD" does not.
    return not _RANDOM_RUN.match(text)


def rejection_reason(fields):
    """Why this submission should not be treated as an enquiry, or '' when it is fine.

    Returned rather than raised so the caller can record the row and stay quiet, instead of arguing with a bot.
    """
    if honeypot_tripped(fields):
        return 'honeypot'
    for key in MESSAGE_FIELDS:
        if key in fields and not looks_like_a_person_wrote_it(fields[key]):
            return 'random_text'
    return ''
