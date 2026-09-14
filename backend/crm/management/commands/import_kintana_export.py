"""Import the Kintana workspace CSV export (01_contacts.csv ... 12_events.csv). Safe to re-run: rows upsert by id."""
import csv
import json
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from catalog.models import Event, TicketType, Venue
from crm.models import Campaign, CampaignRecipient, Contact, ContactList, ContactListMember, InboxConversation, InboxMessage
from sales.models import Membership, MembershipPlan, Order, OrderItem, Ticket


def rows(folder, name):
    path = folder / name
    if not path.exists():
        raise CommandError(f'Missing {path}')
    with path.open(newline='', encoding='utf-8-sig') as fh:
        return list(csv.DictReader(fh))


def ts(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')) if value else None


def boolean(value):
    return str(value).strip().lower() == 'true'


def cents(value):
    return int(value) if value not in (None, '') else None


def loads(value, default):
    try:
        return json.loads(value) if value else default
    except ValueError:
        return default


class Command(BaseCommand):
    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument('folder', help='Directory holding the export CSVs')

    @transaction.atomic
    def handle(self, folder, **options):
        folder = Path(folder).expanduser()
        stats = {}

        # Events and the venues named on them
        for r in rows(folder, '12_events.csv'):
            venue = None
            if r['venue'] and ',' not in r['venue']:  # comma lists are multi-venue slugs; resolved by import_archive
                venue, _ = Venue.objects.get_or_create(slug=slugify(r['venue'])[:120] or 'venue',
                                                       defaults={'name': r['venue'], 'address': r['venue_address'] if r['venue_address'] != r['venue'] else ''})
            Event.objects.update_or_create(id=r['event_id'], defaults={
                'name': r['name'], 'slug': r['slug'], 'date': ts(r['date']), 'status': r['status'] or Event.DRAFT,
                'currency': r['currency'] or 'usd', 'venue': venue, 'venue_label': r['venue'],
                'ticketing_type': r['ticketing_type'] or 'INTERNAL', 'created_at': ts(r['created_at']),
            })
        stats['events'] = Event.objects.count()

        for r in rows(folder, '01_contacts.csv'):
            Contact.objects.update_or_create(id=r['contact_id'], defaults={
                'email': r['email'].strip().lower(), 'first_name': r['first_name'], 'last_name': r['last_name'],
                'phone': r['phone'], 'phone_e164': r['phone_e164'], 'subscribed': boolean(r['subscribed']),
                'subscribed_at': ts(r['subscribed_at']), 'unsubscribed_at': ts(r['unsubscribed_at']),
                'email_marketing_eligible': boolean(r['email_marketing_eligible']), 'source': r['source'],
                'source_event_id': r['source_event_id'], 'page_visitor_key': r['page_visitor_key'],
                'stripe_customer_id': r['stripe_customer_id'], 'stripe_card_brand': r['stripe_card_brand'],
                'stripe_card_last4': r['stripe_card_last4'], 'welcome_email_sent_at': ts(r['welcome_email_sent_at']),
                'custom_data': loads(r['custom_data'], {}), 'countries': r['countries'], 'cities': r['cities'],
                'tags': [t.strip() for t in r['tags'].split(';') if t.strip()], 'created_at': ts(r['created_at']),
            })
        stats['contacts'] = Contact.objects.count()
        by_email = {c.email: c for c in Contact.objects.all()}

        lists = {}
        for r in rows(folder, '06_contact_lists.csv'):
            lists[r['list_name']], _ = ContactList.objects.update_or_create(id=r['list_id'], defaults={'name': r['list_name'], 'created_at': ts(r['created_at'])})
        for r in rows(folder, '07_contact_list_members.csv'):
            contact = by_email.get(r['email'].strip().lower())
            if contact and r['list_name'] in lists:
                ContactListMember.objects.update_or_create(contact_list=lists[r['list_name']], contact=contact, defaults={'added_at': ts(r['added_at'])})
        stats['list_members'] = ContactListMember.objects.count()

        for r in rows(folder, '08_campaign_recipients.csv'):
            campaign, _ = Campaign.objects.get_or_create(name=r['campaign_name'], defaults={'status': r['campaign_status']})
            CampaignRecipient.objects.update_or_create(id=r['recipient_id'], defaults={
                'campaign': campaign, 'contact': by_email.get(r['email'].strip().lower()), 'email': r['email'],
                'status': r['recipient_status'], 'sent_at': ts(r['sent_at']), 'delivered_at': ts(r['delivered_at']),
                'opened_at': ts(r['opened_at']), 'clicked_at': ts(r['clicked_at']), 'bounced_at': ts(r['bounced_at']),
                'complained_at': ts(r['complained_at']), 'send_attempts': int(r['send_attempts'] or 0),
            })
        stats['campaign_recipients'] = CampaignRecipient.objects.count()

        for r in rows(folder, '09_inbox_conversations.csv'):
            InboxConversation.objects.update_or_create(id=r['conversation_id'], defaults={
                'channel_type': r['channel_type'], 'platform': r['platform'], 'subject': r['subject'], 'status': r['status'],
                'handler_mode': r['handler_mode'], 'auto_tag': r['auto_tag'], 'participant_name': r['participant_name'],
                'participant_username': r['participant_username'], 'account_username': r['account_username'],
                'contact': by_email.get(r['contact_email'].strip().lower()), 'last_message_preview': r['last_message_preview'],
                'last_message_at': ts(r['last_message_at']), 'unread_count': int(r['unread_count'] or 0),
                'created_at': ts(r['created_at']), 'updated_at': ts(r['updated_at']),
            })
        for r in rows(folder, '10_inbox_messages.csv'):
            InboxMessage.objects.update_or_create(id=r['message_id'], defaults={
                'conversation_id': r['conversation_id'], 'direction': r['direction'], 'content_type': r['content_type'],
                'content': r['content'], 'sender_name': r['sender_name'], 'sent_at': ts(r['sent_at']),
                'metadata': loads(r['metadata'], {}),
            })
        stats['inbox_messages'] = InboxMessage.objects.count()

        # Ticket types only exist in the export as order line items, so recreate the ones that were sold.
        items = rows(folder, '03_order_items.csv')
        orders = {r['order_id']: r for r in rows(folder, '02_orders.csv')}
        for r in orders.values():
            event = Event.objects.filter(pk=r['event_id']).first()
            Order.objects.update_or_create(id=r['order_id'], defaults={
                'status': r['status'], 'currency': r['currency'], 'total_amount_cents': int(r['total_amount_cents'] or 0),
                'discount_amount_cents': int(r['discount_amount_cents'] or 0), 'customer_name': r['customer_name'],
                'customer_email': r['customer_email'].strip().lower(), 'customer_phone': r['customer_phone'],
                'contact': by_email.get(r['customer_email'].strip().lower()), 'event': event, 'event_name': r['event_name'],
                'stripe_payment_intent_id': r['stripe_payment_intent_id'], 'stripe_charge_id': r['stripe_charge_id'],
                'completed_at': ts(r['completed_at']), 'refunded_at': ts(r['refunded_at']), 'created_at': ts(r['created_at']),
                'attribution': {k: r[k] for k in ('campaign_id', 'fbclid', 'ttclid', 'gclid') if r[k]},
            })
        for r in items:
            order = Order.objects.get(pk=r['order_id'])
            ticket_type = None
            if order.event and r['ticket_type_id']:
                ticket_type, _ = TicketType.objects.get_or_create(id=r['ticket_type_id'], defaults={
                    'event': order.event, 'name': r['ticket_type_name'], 'price_cents': int(r['unit_price_cents'] or 0)})
            OrderItem.objects.update_or_create(id=r['order_item_id'], defaults={
                'order': order, 'ticket_type': ticket_type, 'name': r['ticket_type_name'],
                'quantity': int(r['quantity'] or 1), 'unit_price_cents': int(r['unit_price_cents'] or 0)})
        for r in rows(folder, '04_tickets.csv'):
            Ticket.objects.update_or_create(id=r['ticket_id'], defaults={
                'order_id': r['order_id'], 'ticket_type_name': r['ticket_type_name'], 'checkin_token': r['checkin_token'],
                'checked_in_at': ts(r['checked_in_at'])})
        stats['orders'] = Order.objects.count()
        stats['missing_order_events'] = sorted({r['event_name'] for r in orders.values() if not Event.objects.filter(pk=r['event_id']).exists()})

        for r in rows(folder, '05_memberships.csv'):
            plan, _ = MembershipPlan.objects.get_or_create(name=r['plan_name'], defaults={
                'currency': r['plan_currency'] or 'mxn', 'monthly_cents': cents(r['plan_monthly_cents'])})
            contact = Contact.objects.filter(pk=r['contact_id']).first() or by_email.get(r['email'].strip().lower())
            if contact is None:
                continue
            Membership.objects.update_or_create(id=r['membership_id'], defaults={
                'contact': contact, 'plan': plan, 'status': r['status'], 'source': r['source'],
                'starts_at': ts(r['starts_at']), 'ends_at': ts(r['ends_at']), 'auto_renew': boolean(r['auto_renew']),
                'credit_balance_cents': int(r['credit_balance_cents'] or 0), 'stripe_subscription_id': r['stripe_subscription_id'],
                'stripe_customer_id': r['stripe_customer_id'], 'notes': r['notes'], 'created_at': ts(r['created_at']),
                'billing_interval': 'month' if r['source'] == 'RECURRING' else ''})
        stats['memberships'] = Membership.objects.count()

        for key, value in stats.items():
            self.stdout.write(f'{key}: {value}')
