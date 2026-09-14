"""Import comedians, venue details, event content and merch recovered from Wayback captures.

Reads the JSON written by ~/iguana-migration/extracted/extract.py. By default only fills fields that are
blank, so edits made in the admin survive a re-run; pass --overwrite to replace them. Event status and
visibility are never changed, and events that exist only in the archive are created as drafts.
"""
import json
import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.dateparse import parse_date
from django.utils.text import slugify

from catalog.models import Artist, Event, LineupEntry, StoreCollection, StoreProduct, StoreProductImage, StoreVariant, Venue
from crm.management.commands.import_kintana_export import ts

FILES_ROOT = Path('~/iguana-migration/files').expanduser()


class Command(BaseCommand):
    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument('folder', nargs='?', default='~/iguana-migration/extracted')
        parser.add_argument('--overwrite', action='store_true', help='Replace non-blank fields too')
        parser.add_argument('--publish-store', action='store_true', help='Mark imported products active')

    def handle(self, folder, overwrite, publish_store, **options):
        self.folder = Path(folder).expanduser()
        self.overwrite = overwrite
        self.counts = {}
        with transaction.atomic():
            venues = self.import_venues()
            artists = self.import_artists()
            self.import_events(venues, artists)
            self.import_store(publish_store)
        for key, value in self.counts.items():
            self.stdout.write(f'{key}: {value}')

    def load(self, name):
        path = self.folder / name
        if not path.exists():
            raise CommandError(f'Missing {path}')
        return json.loads(path.read_text())

    def bump(self, key, n=1):
        self.counts[key] = self.counts.get(key, 0) + n

    def media_path(self, image_file, fallback_url):
        """Copy a mirrored file into MEDIA_ROOT/archive and return its /media/ path; fall back to the source URL."""
        if image_file and Path(image_file).exists():
            src = Path(image_file)
            try:
                rel = src.relative_to(FILES_ROOT)
            except ValueError:
                rel = Path(src.name)
            dest = Path(settings.MEDIA_ROOT) / 'archive' / rel
            if not dest.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dest)
            return f'{settings.MEDIA_URL}archive/{rel.as_posix()}'
        return fallback_url or ''

    def assign(self, obj, **values):
        changed = False
        for attr, value in values.items():
            if value in (None, '', [], {}):
                continue
            current = getattr(obj, attr)
            if self.overwrite or current in (None, '', [], {}, 0):
                if current != value:
                    setattr(obj, attr, value)
                    changed = True
        return changed

    def import_venues(self):
        by_key = {}
        for row in self.load('venues.json'):
            names = [n for n in row.get('export_venue_names') or [] if n]
            venue = (Venue.objects.filter(slug=row['slug']).first()
                     or Venue.objects.filter(name__in=names).first()
                     or Venue.objects.filter(slug__in=[slugify(n) for n in names]).first())
            created = venue is None
            if created:
                venue = Venue(slug=row['slug'][:120], name=row['name'])
            self.assign(venue, name=row.get('name'), city=row.get('city'), country=row.get('country'),
                        address=row.get('address'), capacity=row.get('capacity') or 0, description=row.get('description'),
                        lat=row.get('lat'), lng=row.get('lng'),
                        image_url=self.media_path(row.get('image_file'), row.get('image_url')))
            venue.save()
            self.bump('venues_created' if created else 'venues_updated')
            for key in [row['slug'], *names, *[slugify(n) for n in names]]:
                by_key[key] = venue
        return by_key

    def import_artists(self):
        by_slug = {}
        for row in self.load('artists.json'):
            artist = Artist.objects.filter(slug=row['slug']).first()
            created = artist is None
            if created:
                artist = Artist(slug=row['slug'][:120], name=row['name'])
            self.assign(artist, name=row.get('name'), stage_name=row.get('stage_name') if row.get('stage_name') != row.get('name') else None,
                        bio=row.get('bio_en'), bio_es=row.get('bio_es'), website=row.get('website'),
                        socials=row.get('socials') or {}, home_city=row.get('home_city'),
                        image_url=self.media_path(row.get('image_file'), row.get('image_url')))
            artist.save()
            by_slug[artist.slug] = artist
            self.bump('artists_created' if created else 'artists_updated')
        return by_slug

    def import_events(self, venues, artists):
        for row in self.load('events.json'):
            event = Event.objects.filter(pk=row['export_event_id']).first() if row.get('export_event_id') else None
            if event is None and row.get('slug'):
                event = Event.objects.filter(slug=row['slug']).first()
            created = event is None
            if created:
                day = parse_date(row.get('date') or '')
                if day is None:
                    self.bump('events_skipped_no_date')
                    continue
                slug = row.get('slug') or slugify(row['name'])
                if Event.objects.filter(slug=slug).exists():
                    slug = f'{slug}-{day:%Y%m%d}'
                event = Event(name=row['name'], slug=slug[:160], status=Event.DRAFT,
                              date=ts(f'{day.isoformat()}T05:00:00Z'))
            slugs = row.get('venue_slugs') or ([row['venue_slug']] if row.get('venue_slug') else [])
            matched = [venues[s] for s in slugs if s in venues]
            if len(matched) == 1 and (event.venue_id is None or self.overwrite):
                event.venue = matched[0]
            if len(matched) > 1 and (not event.venue_label or ',' in event.venue_label or self.overwrite):
                event.venue_label = ' / '.join(v.name for v in matched)
            self.assign(event, doors_open=row.get('doors_open'), show_time=row.get('show_time'),
                        description=row.get('description'), long_description=row.get('long_description'),
                        image_url=self.media_path(row.get('image_file'), row.get('image_url')),
                        currency=(row.get('currency') or '').lower() or None,
                        external_ticket_url=row.get('external_ticket_url'))
            event.save()
            self.bump('events_created_as_draft' if created else 'events_enriched')
            for i, entry in enumerate(row.get('lineup') or []):
                artist = artists.get(entry.get('artist_slug'))
                if artist is None:
                    self.bump('lineup_unmatched_artist')
                    continue
                _, made = LineupEntry.objects.get_or_create(event=event, artist=artist, defaults={
                    'role': (entry.get('role') or '')[:60], 'headliner': bool(entry.get('headliner')), 'sort_order': i})
                self.bump('lineup_entries_created' if made else 'lineup_entries_existing')

    def import_store(self, publish):
        data = self.load('store.json')
        collections = {}
        for i, row in enumerate(data.get('collections') or []):
            collections[row['slug']], _ = StoreCollection.objects.get_or_create(slug=row['slug'][:120], defaults={'name': row['name'], 'sort_order': i})
        for i, row in enumerate(data.get('products') or []):
            product, created = StoreProduct.objects.get_or_create(slug=row['slug'][:160], defaults={
                'name': row['name'], 'active': publish, 'sort_order': i})
            self.assign(product, name=row.get('name'), description=row.get('description'),
                        currency=(row.get('currency') or '').lower() or None, external_url=row.get('product_url'))
            product.save()
            product.collections.add(*[collections[s] for s in row.get('collection_slugs') or [] if s in collections])
            if row.get('price_cents') is not None and not product.variants.exists():
                StoreVariant.objects.create(product=product, price_cents=row['price_cents'], compare_at_cents=row.get('compare_at_cents'))
            if not product.images.exists():
                for j, image in enumerate(row.get('images') or []):
                    url = self.media_path(image.get('file'), image.get('url'))
                    if url:
                        StoreProductImage.objects.create(product=product, url=url, alt=row['name'][:200], sort_order=j)
            self.bump('products_created' if created else 'products_updated')
