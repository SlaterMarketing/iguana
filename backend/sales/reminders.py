"""The morning-of reminder, and giving an open mic seat back.

Every booking for a show tonight gets one email in the morning with the time, the place and its tickets. The two
kinds of night differ on purpose (owner, 2026-09-27):

OPEN MIC: the seat was free, and 60 of them fill while people are turned away at the door. So the reminder
carries a link to give the seat back, and doing so frees it at once: the order becomes CANCELLED, every count in
the site reads only COMPLETED orders, so the seat is back on sale on the lander, the demand line and the ads
autopilot without anything else being told.

PAID SHOW: the reminder only. A paid ticket given back is a refund question, and that is a conversation, not a
link.
"""

import logging
from datetime import datetime, time

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.utils import formats, timezone, translation

from catalog.models import Event

from .i18n import normalize, tr
from .links import order_url, public_base
from .models import Order
from .services import DATE_FORMATS
from .sharing import is_open_mic

log = logging.getLogger(__name__)

# A test booking is never a person to remind.
PROBE_PREFIX = 'e2e-'


def release_url(order):
    return f'{public_base()}/orders/{order.public_view_token}/release/'


def show_starts(event):
    day = timezone.localtime(event.date).date()
    clock = event.show_time or event.doors_open or '21:00'
    try:
        hours, minutes = (int(x) for x in clock.split(':')[:2])
    except ValueError:
        hours, minutes = 21, 0
    return timezone.make_aware(datetime.combine(day, time(hours, minutes)))


def can_release(order, now=None):
    """Only a free open mic seat, still booked, for a show that has not started, and nobody has come in on it."""
    now = now or timezone.now()
    return (order.status == Order.COMPLETED and order.event is not None and is_open_mic(order.event)
            and order.total_amount_cents - order.pay_at_door_cents == 0
            and now < show_starts(order.event)
            and not order.tickets.filter(checked_in_at__isnull=False).exists())


def release(order_id, now=None):
    """Give the seat back. Returns 'released', 'already' or 'refused'. Safe to press twice."""
    now = now or timezone.now()
    with transaction.atomic():
        # of=('self',): event is a nullable FK, and Postgres refuses FOR UPDATE on the nullable side of a join.
        order = Order.objects.select_for_update(of=('self',)).select_related('event').get(pk=order_id)
        if order.released_at:
            return 'already'
        if not can_release(order, now):
            return 'refused'
        order.status = Order.CANCELLED
        order.released_at = now
        order.save(update_fields=['status', 'released_at'])
    log.info('order %s released its seat for %s', order.id, order.event_name)
    return 'released'


def orders_for_today(now=None):
    """Completed bookings for tonight's shows that have not had their reminder yet."""
    today = timezone.localtime(now or timezone.now()).date()
    return (Order.objects.filter(status=Order.COMPLETED, reminder_sent_at__isnull=True, source='',
                                 event__isnull=False, event__date__date=today,
                                 event__status__in=(Event.ACTIVE, Event.SOLD_OUT))
            .exclude(customer_email='').exclude(customer_email__istartswith=PROBE_PREFIX)
            .select_related('event__venue').order_by('created_at'))


def message_for(order, now=None):
    """(subject, body) in the language they booked in."""
    lang = normalize(order.locale)
    event = order.event
    name = (order.customer_name or '').strip().split(' ')[0]
    seats = sum(i.quantity for i in order.items.all() if not i.is_addon)
    free_mic = can_release(order, now)
    with translation.override(lang):
        when = formats.date_format(timezone.localtime(event.date), DATE_FORMATS[lang])
    lines = [tr(lang, 'Hi {0},', name) if name else tr(lang, 'Hi there,'), '',
             tr(lang, 'See you tonight at {0}, {1}.', order.event_name, when)]
    if event.show_time:
        lines.append(tr(lang, 'Doors {0} · Show {1}', event.doors_open, event.show_time) if event.doors_open
                     else tr(lang, 'Show {0}', event.show_time))
    if event.venue:
        lines.append(', '.join(x for x in (event.venue.name, event.venue.address) if x))
    elif event.venue_label:
        lines.append(event.venue_label)
    if free_mic:
        lines += ['', tr(lang, 'Arrive when doors open so your seat is still yours.')]
    lines += ['', tr(lang, 'Your seats (show this at the door): {0}', order_url(order)) if free_mic
              else tr(lang, 'Your tickets (show this at the door): {0}', order_url(order))]
    if free_mic:
        give_back = ('Cannot make it any more? Give your seat back so somebody else can come in:'
                     if seats == 1 else
                     'Cannot make it any more? Give your seats back so somebody else can come in:')
        lines += ['', tr(lang, give_back), release_url(order)]
    lines += ['', tr(lang, 'See you there,'), 'Iguana Comedy', 'iguanacomedy.com']
    subject = tr(lang, 'Tonight: {0}', order.event_name)
    return subject, '\n'.join(lines)


def send(order, now=None):
    subject, body = message_for(order, now)
    reply_to = [settings.MARKETING_REPLY_TO] if getattr(settings, 'MARKETING_REPLY_TO', '') else None
    message = EmailMessage(subject, body, settings.DEFAULT_FROM_EMAIL, [order.customer_email], reply_to=reply_to)
    # Transactional, like the confirmation: it is about a booking they made, so no unsubscribe footer, and a
    # refused address is logged rather than raised so one bad address cannot stop the rest of the run.
    try:
        sent = message.send()
    except Exception:
        log.exception('reminder for order %s to %s failed', order.id, order.customer_email)
        sent = 0
    return sent
