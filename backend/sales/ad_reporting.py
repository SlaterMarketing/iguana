"""Tell Meta what an ad was worth, from the order it produced.

`crm.meta_capi` knows how to talk to Meta; this knows what an Iguana order looks like. Split that way because the
checkout runs in an iframe on the API domain: the browser cookies Meta matches on (`_fbp`, `_fbc`) belong to the
SITE origin, so they can only reach us by riding along in the checkout payload. `k.js` reads them on the site and
posts them as attribution, `checkout_start` stores them on the order, and both functions here read them back.

Matching is everything. An event with only a hashed email attributes far fewer sales than one that also carries
the click id, the browser id, the IP and the user agent, and an unattributed sale teaches the algorithm that the
ad did not work.
"""

from crm import meta_capi


def _attribution(order):
    return order.attribution if isinstance(order.attribution, dict) else {}


def _visitor(order):
    visitor = _attribution(order).get('visitor')
    return visitor if isinstance(visitor, dict) else {}


def _split_name(order):
    parts = str(order.customer_name or '').strip().split()
    if not parts:
        return '', ''
    return parts[0], parts[-1] if len(parts) > 1 else ''


def _user(order):
    attribution, visitor = _attribution(order), _visitor(order)
    first, last = _split_name(order)
    contact = order.contact
    return meta_capi.user_data(
        email=order.customer_email or (contact.email if contact else ''),
        phone=order.customer_phone or (contact.phone if contact else ''),
        first_name=(contact.first_name if contact and contact.first_name else first),
        last_name=(contact.last_name if contact and contact.last_name else last),
        city=visitor.get('city', ''),
        region=visitor.get('region', ''),
        country=visitor.get('country', ''),
        ip=visitor.get('ip', ''),
        user_agent=attribution.get('userAgent', ''),
        # Set by the pixel on the site and carried across the iframe boundary by k.js.
        fbp=attribution.get('fbp', ''),
        fbc=attribution.get('fbc', ''),
    )


def _custom(order):
    items = list(order.items.all())
    # What actually reached us online. A pay-at-the-door reservation is a real booking worth optimising for, but it
    # is worth nothing yet, and telling Meta otherwise inflates the ROAS it learns from.
    charged_cents = max(order.total_amount_cents - order.pay_at_door_cents, 0)
    return {
        'currency': (order.currency or 'mxn').upper(),
        'value': round(charged_cents / 100, 2),
        'content_type': 'product',
        'content_ids': [order.event_id] if order.event_id else [],
        'content_name': order.event_name or '',
        'num_items': sum(item.quantity for item in items),
        'order_id': order.id,
    }


def _source_url(order):
    """The page the fan was on, not the iframe. Meta uses it to group results by landing page."""
    return _attribution(order).get('pageUrl', '')


def report_checkout_started(order):
    meta_capi.send('InitiateCheckout', event_id=f'ic-{order.id}', user=_user(order), custom=_custom(order),
                   source_url=_source_url(order))


def report_purchase(order):
    """One Purchase per order, keyed on the order id so a Stripe webhook retry cannot double-count it."""
    meta_capi.send('Purchase', event_id=f'purchase-{order.id}', user=_user(order), custom=_custom(order),
                   source_url=_source_url(order))
