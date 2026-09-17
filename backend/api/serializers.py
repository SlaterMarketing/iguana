"""JSON shapes matching @kintana/sdk types, so the Astro site works unchanged."""
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db.models import Sum
from django.utils import timezone

from catalog.models import Event
from sales.models import MembershipPlan, Order, OrderItem

CANCUN = ZoneInfo('America/Cancun')


def media(value):
    """Image fields hold absolute URLs or backend-relative /media/ paths."""
    if not value:
        return None
    return f'{settings.BACKEND_URL}{value}' if value.startswith('/') else value


def iso(dt):
    if dt is None:
        return None
    return dt.astimezone(ZoneInfo('UTC')).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def event_day(event):
    """Date-only string: the site formats `YYYY-MM-DD` without timezone drift."""
    return event.date.astimezone(ZoneInfo(event.venue.time_zone if event.venue else 'America/Cancun')).date().isoformat()


def today_local():
    return timezone.now().astimezone(CANCUN).date()


def venue_json(venue, listed=False):
    if venue is None:
        return None
    data = {
        'id': venue.id,
        'slug': venue.slug,
        'name': venue.name,
        'city': venue.city or None,
        'country': venue.country or None,
        'address': venue.address or None,
        'description': venue.description or None,
        'lat': venue.lat,
        'lng': venue.lng,
        'timeZone': venue.time_zone,
        'wheelchairAccessible': venue.wheelchair_accessible,
    }
    if listed:
        data.update(capacity=venue.capacity, imageUrl=media(venue.image_url))
    return data


def artist_json(artist, locale='en'):
    bio = artist.bio_es if locale == 'es' and artist.bio_es else artist.bio
    return {
        'id': artist.id,
        'slug': artist.slug,
        'name': artist.name,
        'bio': bio or None,
        'imageUrl': media(artist.image_url),
        'website': artist.website or None,
        'stageName': artist.stage_name or None,
        'homeCity': artist.home_city or None,
        'residency': artist.residency or None,
        'socials': artist.socials or {},
        'reels': artist.reels or [],
    }


def sold_quantity(ticket_type):
    return (
        OrderItem.objects.filter(ticket_type=ticket_type, order__status=Order.COMPLETED).aggregate(n=Sum('quantity'))['n'] or 0
    )


def remaining(ticket_type):
    if ticket_type.capacity is None:
        return None
    return max(0, ticket_type.capacity - sold_quantity(ticket_type))


def listing_status(event, ticket_types=None):
    if event.status == Event.CANCELLED:
        return 'cancelled'
    if event.status == Event.POSTPONED:
        return 'postponed'
    if event.date.astimezone(CANCUN).date() < today_local():
        return 'past'
    if event.status == Event.SOLD_OUT:
        return 'sold-out'
    types = ticket_types if ticket_types is not None else [t for t in event.ticket_types.all() if t.active]
    if event.ticketing_type == 'INTERNAL' and types and all(remaining(t) == 0 for t in types):
        return 'sold-out'
    return 'on-sale'


def lineup_entry_json(entry):
    return {
        'id': entry.artist.id,
        'slug': entry.artist.slug,
        'name': entry.artist.stage_name or entry.artist.name,
        'role': entry.role or None,
        'sortOrder': entry.sort_order,
        'imageUrl': media(entry.artist.image_url),
    }


def active_plan():
    return MembershipPlan.objects.filter(active=True).first()


def event_urls(event):
    embed = f'{settings.BACKEND_URL}/embed/event/{event.id}'
    if event.ticketing_type == 'EXTERNAL' and event.external_ticket_url:
        return event.external_ticket_url, embed
    return embed, f'{embed}?embedded=1'


def event_json(event, plan=None, lang='en'):
    types = [t for t in event.ticket_types.all() if t.active]
    lineup = list(event.lineup.all())
    headliner = next((e for e in lineup if e.headliner), None)
    ticket_url, embed_url = event_urls(event)
    venue = venue_json(event.venue)
    if venue is None and event.venue_label:
        venue = {'id': None, 'slug': None, 'name': event.venue_label, 'city': None, 'country': None, 'address': None,
                 'description': None, 'lat': None, 'lng': None, 'timeZone': 'America/Cancun', 'wheelchairAccessible': None}
    data = {
        'id': event.id,
        'slug': event.slug,
        'name': event.label(lang),
        'date': event_day(event),
        'city': event.venue.city if event.venue and event.venue.city else None,
        'country': event.venue.country if event.venue and event.venue.country else None,
        'imageUrl': media(event.poster(lang)),
        'imageUrlMobile': media(event.poster_mobile(lang)),
        'ticketUrl': ticket_url,
        'embedUrl': embed_url,
        'doorsOpen': event.doors_open or None,
        'showTime': event.show_time or None,
        'endTime': event.end_time or None,
        'description': event.details(lang) or None,
        'longDescription': event.long_details(lang) or None,
        'status': listing_status(event, types),
        'language': event.language or 'en',
        'venue': venue,
        'tour': {'id': event.tour.id, 'slug': event.tour.slug, 'name': event.tour.name, 'imageUrl': media(event.tour.image_url)} if event.tour else None,
        'lineup': [lineup_entry_json(e) for e in lineup],
        'headliner': lineup_entry_json(headliner) if headliner else None,
        'ticketingType': event.ticketing_type,
        'ageRestriction': event.age_restriction or None,
        'priceFrom': min((t.price_cents for t in types), default=None),
        'priceCurrency': event.currency.upper() if types else None,
        'tags': event.tags or [],
        'reviews': event.reviews or [],
        'isShared': False,
        'hostWorkspace': {'slug': 'iguana-comedy', 'name': 'Iguana Comedy'},
        'promoter': None,
    }
    if plan and event.members_eligible:
        data['goldMembership'] = {'status': 'eligible', 'planName': plan.name, 'freeTickets': plan.free_tickets_per_order}
    return data


def plan_json(plan):
    prices = {}
    if plan.monthly_cents is not None:
        prices['monthly'] = {'amountCents': plan.monthly_cents}
    if plan.annual_cents is not None:
        prices['annual'] = {'amountCents': plan.annual_cents}
    if plan.lifetime_cents is not None:
        prices['lifetime'] = {'amountCents': plan.lifetime_cents}
    if plan.pass_cents is not None and plan.pass_days:
        prices['pass'] = {'amountCents': plan.pass_cents, 'durationDays': plan.pass_days}
    primary = plan.monthly_cents if plan.monthly_cents is not None else (plan.annual_cents or plan.lifetime_cents or plan.pass_cents or 0)
    return {
        'id': plan.id,
        'name': plan.name,
        'description': plan.description or None,
        'benefits': [{'label': b, 'sortOrder': i} for i, b in enumerate(plan.benefits or [])],
        'currency': plan.currency,
        'prices': prices,
        'priceCents': primary,
        'billingInterval': 'month' if plan.monthly_cents is not None else ('year' if plan.annual_cents is not None else 'one_time'),
        'durationDays': plan.pass_days,
    }


def membership_json(m):
    return {
        'id': m.id,
        'status': m.status,
        'startsAt': iso(m.starts_at),
        'endsAt': iso(m.ends_at),
        'creditBalanceCents': m.credit_balance_cents,
        'plan': {
            'id': m.plan.id,
            'name': m.plan.name,
            'billingInterval': m.billing_interval or 'month',
            'priceCents': (m.plan.annual_cents if m.billing_interval == 'year' else m.plan.monthly_cents) or 0,
            'currency': m.plan.currency,
        },
        'stripeSubscriptionId': m.stripe_subscription_id or None,
    }


def order_ticket_json(order):
    event = order.event
    tz = event.venue.time_zone if event and event.venue else 'America/Cancun'
    return {
        'id': order.id,
        'totalAmount': order.total_amount_cents,
        'currency': order.currency,
        'completedAt': iso(order.completed_at),
        'event': {
            'id': event.id if event else '',
            'name': event.name if event else order.event_name,
            'slug': event.slug if event else '',
            'date': event_day(event) if event else '',
            'doorsOpen': event.doors_open or None if event else None,
            'showTime': event.show_time or None if event else None,
            'venue': (event.venue.name if event.venue else event.venue_label) if event else '',
            'venueAddress': (event.venue.address or None) if event and event.venue else None,
            'venueTimeZone': tz,
            'currency': order.currency,
        },
        'orderItems': [{'name': i.name, 'quantity': i.quantity, 'unitPrice': i.unit_price_cents} for i in order.items.all()],
        'tickets': [
            {
                'id': t.id,
                'ticketTypeName': t.ticket_type_name,
                'checkinUrl': f'{settings.BACKEND_URL}/checkin/{t.checkin_token}/',
                'checkedInAt': iso(t.checked_in_at),
            }
            for t in order.tickets.all()
        ],
        'ticketsPageUrl': f'{settings.BACKEND_URL}/orders/{order.public_view_token}/',
        'publicViewToken': order.public_view_token,
        'wallets': {'google': False, 'apple': False},
    }
