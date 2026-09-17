"""Write the hand-written Spanish copy in catalog/data/es_copy.py onto the catalogue.

    manage.py apply_es_copy --dry-run
    manage.py apply_es_copy
    manage.py apply_es_copy --overwrite   # also replace Spanish that is already there

Blank Spanish fields are filled; anything already written (in the admin, or by an earlier run) is left alone unless
--overwrite is passed. Slugs in the data file that no longer exist are reported, not skipped silently, so a renamed
event does not quietly lose its Spanish.
"""

from django.core.management.base import BaseCommand

from catalog.data.es_copy import ARTIST_BIOS, EVENT_COPY
from catalog.models import Artist, Event


class Command(BaseCommand):
    help = 'Apply the hand-written Spanish artist bios and event blurbs'

    def add_arguments(self, parser):
        parser.add_argument('--overwrite', action='store_true', help='Replace Spanish that is already set')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **opts):
        written = skipped = 0
        missing = []

        for slug, bio in ARTIST_BIOS.items():
            artist = Artist.objects.filter(slug=slug).first()
            if not artist:
                missing.append(f'artist {slug}')
                continue
            if artist.bio_es and not opts['overwrite']:
                skipped += 1
                continue
            if not opts['dry_run']:
                artist.bio_es = bio
                artist.save(update_fields=['bio_es'])
            written += 1
            self.stdout.write(f'  {artist.name}: {bio[:60]}...')

        for slug, copy in EVENT_COPY.items():
            event = Event.objects.filter(slug=slug).first()
            if not event:
                missing.append(f'event {slug}')
                continue
            fields = []
            for source, target in (('description', 'description_es'), ('long_description', 'long_description_es')):
                text = copy.get(source)
                if not text or (getattr(event, target) and not opts['overwrite']):
                    continue
                setattr(event, target, text)
                fields.append(target)
            if not fields:
                skipped += 1
                continue
            if not opts['dry_run']:
                event.save(update_fields=fields)
            written += 1
            self.stdout.write(f'  {event.name}: {", ".join(fields)}')

        for name in missing:
            self.stdout.write(self.style.WARNING(f'  no longer in the catalogue: {name}'))
        verb = 'would write' if opts['dry_run'] else 'wrote'
        self.stdout.write(self.style.SUCCESS(
            f'{verb} {written}, left {skipped} alone, {len(missing)} slug(s) not found'))
