"""Keep a database-level default on `is_addon`.

Django adds a NOT NULL column with a default, then drops the default again, because from Django's point of view
the application always supplies the value. That is only true once the application has been reloaded. In the
window between `migrate` and the workers re-importing, the old code inserts an order line without the column and
Postgres rejects it: measured 2026-09-21, two checkout POSTs from a Facebook in-app browser 500'd that way, and
because nothing was written the only trace was the access log.

The deploy now reloads the API directly after migrating, which shrinks that window to the length of a worker
roll. This closes it: an insert that omits the column gets `false`, which for this column is also the truthful
answer, since a line is a seat unless something says otherwise.
"""

from django.db import migrations


def _alter(schema_editor, clause):
    # Postgres only: SQLite, which is what local development runs on, cannot ALTER a column this way and does
    # not need to, because nothing is mid-deploy against it.
    if schema_editor.connection.vendor != 'postgresql':
        return
    schema_editor.execute(f'ALTER TABLE sales_orderitem ALTER COLUMN is_addon {clause}')


def set_default(apps, schema_editor):
    _alter(schema_editor, 'SET DEFAULT false')


def drop_default(apps, schema_editor):
    _alter(schema_editor, 'DROP DEFAULT')


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0005_orderitem_is_addon'),
    ]

    operations = [
        migrations.RunPython(set_default, drop_default),
    ]
