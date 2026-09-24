"""The morning after: thank them, ask them to tell somebody, and ask what could have been better.

Three things make this worth sending at all, and each one shapes the copy:

It cannot claim they came. Nobody is scanned at the door (0 of 24 tickets on 2026-09-23), so a booking is the
only thing we know about, and "thanks for coming" to somebody who did not come reads as a form letter. It says
they had a seat and hopes they made it, which is true either way.

The ask is the open mic, not the show they just saw. That show is over, and the easiest thing in the world to
pass to a friend is a free seat at a night that runs every week. The link goes to the lander, which picks the
next bookable night itself, so this mail cannot go stale the way a pinned date would.

And it asks for a reply. `crm.mail` puts `MARKETING_REPLY_TO` (hello@) on every marketing message, which lands
in a mailbox a person actually reads, so "just reply" is a real invitation rather than a polite fiction.
"""

from datetime import timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone

from sales.i18n import normalize, tr
from sales.models import Order
from sales.sharing import EVENTS_PATH, OPEN_MIC_PATH, base_url, is_open_mic

CANCUN = ZoneInfo('America/Cancun')


def show_day(days_ago=1, now=None):
    """The calendar day, in Cancun, whose shows this run is following up on."""
    return ((now or timezone.now()).astimezone(CANCUN) - timedelta(days=days_ago)).date()


def orders_for(day):
    """Completed bookings for shows on that day that have not had their note yet."""
    return (Order.objects.filter(status=Order.COMPLETED, follow_up_sent_at__isnull=True,
                                 event__isnull=False, event__date__date=day)
            .exclude(customer_email='')
            .select_related('event', 'contact')
            .order_by('created_at'))


def next_up_url(lang, contact=None):
    """Where to send the friend. The open mic lander when there is one coming, the calendar otherwise."""
    from catalog.models import Event

    lang = normalize(lang)
    # Filtered in Python rather than with a `tags__contains` lookup: tags is a JSONField, and that lookup is
    # Postgres-only, so the query would work in production and raise in every test.
    upcoming = next((e for e in Event.objects.filter(status=Event.ACTIVE, date__gte=timezone.now())
                     .order_by('date')[:40] if is_open_mic(e)), None)
    if upcoming:
        return f'{base_url()}{OPEN_MIC_PATH[lang]}?night={normalize(upcoming.language or lang)}&ref=after-show'
    return f'{base_url()}{EVENTS_PATH[lang]}?ref=after-show'


def subject_for(lang):
    return tr(normalize(lang), 'How was last night?')


def body_for(order, lang=None):
    lang = normalize(lang or order.locale)
    name = (order.customer_name or '').strip().split(' ')[0]
    lines = [tr(lang, 'Hi {0},', name) if name else tr(lang, 'Hi there,'), '']
    lines.append(tr(lang, 'You had a seat for {0} last night. We hope you made it, and that it was a good one.',
                    order.event_name))
    # Written on one line each on purpose: the scanner in api.tests.TranslationTests reads string literals, so
    # a sentence split across two lines registers as its first fragment and its Spanish is never checked.
    ask = 'If you enjoyed it, tell somebody. The open mic is every week and free to reserve:'
    reply = 'And if anything could have been better, just reply to this email. We read every one.'
    lines += ['', tr(lang, ask), next_up_url(lang)]
    lines += ['', tr(lang, reply)]
    lines += ['', tr(lang, 'See you at the next one,'), 'Iguana Comedy', 'iguanacomedy.com']
    return '\n'.join(lines)


def contact_for(order):
    """The contact row this booking belongs to, which is what carries the unsubscribe state."""
    from crm.models import Contact

    return order.contact or Contact.objects.filter(email__iexact=order.customer_email).first()


def plan(days_ago=1, now=None):
    """What a run would do.

    Returns `(day, to_send, also_stamp)`. `to_send` is one (order, contact) pair per person. `also_stamp` is
    every other booking for that day: a second booking by somebody who is already getting one, and any booking
    with no contact row behind it. Those are stamped without a second email, so the next run does not keep
    picking them up forever.
    """
    day = show_day(days_ago, now)
    to_send, also_stamp, seen = [], [], set()
    for order in orders_for(day):
        key = (order.event_id, order.customer_email.lower())
        contact = contact_for(order) if key not in seen else None
        if contact:
            seen.add(key)
            to_send.append((order, contact))
        else:
            also_stamp.append(order)
    return day, to_send, also_stamp


__all__ = ['show_day', 'orders_for', 'next_up_url', 'subject_for', 'body_for', 'contact_for', 'plan', 'is_open_mic']
