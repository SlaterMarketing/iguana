"""No event offers member pricing, because the club sells no membership.

The default change alone would have left 51 nights carrying the flag, 7 of them still to come: dead until
somebody marked a plan active in the admin, and then suddenly not dead across the whole calendar. The pricing
code stays (removing it is surgery on the checkout for no gain while nobody holds a membership); what is
removed is every way for it to switch itself back on by accident.
"""

from django.db import migrations, models


def stop_offering_membership(apps, schema_editor):
    apps.get_model('catalog', 'Event').objects.update(members_eligible=False)


def noop(apps, schema_editor):
    """Deliberately not reversible: turning it back on is a product decision, not a migration."""


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0008_tickettype_sold_elsewhere'),
    ]

    operations = [
        migrations.AlterField(
            model_name='event',
            name='members_eligible',
            field=models.BooleanField(default=False, help_text='Dead unless the club sells memberships again.'),
        ),
        migrations.RunPython(stop_offering_membership, noop),
    ]
