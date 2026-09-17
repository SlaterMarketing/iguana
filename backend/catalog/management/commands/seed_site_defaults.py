"""Rows the Astro site depends on that were configured in the Kintana dashboard, not exported. Safe to re-run."""
from django.core.management.base import BaseCommand

from catalog.models import FormEndpoint
from sales.models import MembershipPlan

ENDPOINTS = [
    ('contact', 'contact', 'Contact'),
    ('perform-with-us', 'show_request', 'Perform with us'),
    ('hotels-and-resorts', 'external_lead', 'Hotels and resorts'),
    ('newsletter', 'newsletter', 'Newsletter'),
]

# Matches src/content/membership.ts: MX$99 / month, MX$999 / year, two free tickets, 10% off guests.
MEMBER_BENEFITS = [
    'Two free tickets on eligible shows',
    '10% off for guests',
    'Early access and presales',
    'Members-only nights',
    'Cancel anytime',
]
MEMBER_BENEFITS_ES = [
    'Dos boletos gratis en shows elegibles',
    '10% de descuento para tus invitados',
    'Acceso anticipado y preventas',
    'Noches solo para miembros',
    'Cancela cuando quieras',
]


class Command(BaseCommand):
    help = __doc__

    def handle(self, **options):
        for slug, intent, title in ENDPOINTS:
            FormEndpoint.objects.get_or_create(slug=slug, defaults={'intent': intent, 'title': title})
        plan, created = MembershipPlan.objects.get_or_create(name='Iguana Member', defaults={'currency': 'mxn'})
        changed = []
        for attr, value in (('monthly_cents', 9900), ('annual_cents', 99900), ('benefits', MEMBER_BENEFITS),
                            ('benefits_es', MEMBER_BENEFITS_ES), ('name_es', 'Iguana Member'),
                            ('free_tickets_per_order', 2), ('guest_discount_percent', 10)):
            if not getattr(plan, attr):
                setattr(plan, attr, value)
                changed.append(attr)
        plan.save()
        self.stdout.write(f'endpoints: {FormEndpoint.objects.count()}, plan {plan.name}: set {", ".join(changed) or "nothing"}')
