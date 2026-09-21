"""Which language a contact actually reads, learned from the link they click.

Most of this list came out of the Kintana export with no language on it, and a contact who never fills a form
in never tells us one: 734 of 794 are blank. The weekly email is the one thing that reaches all of them, and it
carries both languages, so which block somebody clicks from is a real answer to the question. The language is
in the path already (`/es/...` against `/en/...`), so a click needs to carry only who it was.

The marker is the contact's own id, not a signed address. It is 24 random characters, so it is unguessable and,
unlike the signed token on the unsubscribe link, it cannot be decoded back into an email address by anyone who
gets hold of the URL. A forwarded link records the wrong person's language once, which the next thing they do
corrects; a forwarded link that spells out an email address does not undo.
"""

import re

CLICK_PARAM = 'ic'

# The locale segment the site puts at the front of every path.
_LOCALE_IN_PATH = re.compile(r'https?://[^/]+/(en|es)(?:/|$)')


def tag(url, contact):
    """Add the marker that says who is clicking. No contact, no marker."""
    if contact is None or not getattr(contact, 'id', ''):
        return url
    separator = '&' if '?' in url else '?'
    return f'{url}{separator}{CLICK_PARAM}={contact.id}'


def contact_id_from(url):
    match = re.search(rf'[?&]{CLICK_PARAM}=([a-z0-9]{{1,40}})', str(url or ''))
    return match.group(1) if match else ''


def locale_from(url):
    """'https://iguanacomedy.com/es/open-mic/?ic=...' -> 'es'. Blank when the URL names no language."""
    match = _LOCALE_IN_PATH.match(str(url or ''))
    return match.group(1) if match else ''


def remember_click(url, visitor_key=''):
    """Record the language of whoever clicked, and tie their browsing to their contact row.

    Returns the contact when one was recognised, so a caller can log it. Never raises: this runs inside the
    tracking endpoint, which must stay a 204 whatever happens.
    """
    from .models import Contact

    contact_id, locale = contact_id_from(url), locale_from(url)
    if not contact_id or not locale:
        return None
    contact = Contact.objects.filter(pk=contact_id).first()
    if contact is None:
        return None
    changed = []
    if contact.locale != locale:
        contact.locale = locale
        changed.append('locale')
    # Their visitor key ties everything else they do on the site back to this contact.
    if visitor_key and contact.page_visitor_key != visitor_key:
        contact.page_visitor_key = visitor_key[:100]
        changed.append('page_visitor_key')
    if changed:
        contact.save(update_fields=changed)
    return contact
