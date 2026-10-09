"""Everything about one comedian's /comic/ submission, for turning it into an event.

    manage.py comic_submission                 # the latest submissions, one line each
    manage.py comic_submission <id>            # the full summary, file paths, and how to copy them off
    manage.py comic_submission <id> --probe    # read clip lengths with ffprobe now, if the upload thread did not
    manage.py comic_submission <id> --delete   # remove the row and its folder (a test, or on request)
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from api.comic_views import admin_url, probe_durations
from crm.models import ComicSubmission


def _mb(n):
    return f'{n / 1024 / 1024:.1f} MB'


class Command(BaseCommand):
    help = "Print a comedian's /comic/ submission: details, requested dates and the paths of their photos and clips."

    def add_arguments(self, parser):
        parser.add_argument('id', nargs='?')
        parser.add_argument('--limit', type=int, default=20)
        parser.add_argument('--probe', action='store_true', help='Read clip durations with ffprobe now.')
        parser.add_argument('--delete', action='store_true', help='Delete the submission and its files.')

    def handle(self, *args, id=None, limit=20, probe=False, delete=False, **options):
        out = self.stdout.write
        if not id:
            for s in ComicSubmission.objects.prefetch_related('files')[:limit]:
                files = list(s.files.all())
                clips = sum(1 for f in files if f.is_clip)
                out(f'{s.pk}  {s.created_at:%Y-%m-%d %H:%M}  {s.status:<8}  {s.display_name}  '
                    f'{len(files) - clips} photo(s) {clips} clip(s)  dates: {", ".join(s.requested_dates) or "-"}')
            return

        s = ComicSubmission.objects.filter(pk=id).first()
        if not s:
            raise CommandError(f'No submission {id}.')
        if delete:
            name = s.display_name
            s.delete()
            out(f'Deleted {id} ({name}) and its folder.')
            return
        if probe:
            probe_durations(list(s.files.filter(kind__startswith='CLIP').values_list('pk', flat=True)))

        rows = [('Submitted', f'{s.created_at:%Y-%m-%d %H:%M} ({s.lang})'), ('Status', s.status),
                ('Name', s.name), ('Stage name', s.stage_name), ('Email', s.email), ('Phone', s.phone),
                ('Instagram', s.instagram), ('TikTok', s.tiktok), ('Links', s.links), ('Home city', s.home_city),
                ('Performs in', s.languages), ('Show name', s.show_name),
                ('Requested dates', ', '.join(s.requested_dates)), ('Availability', s.availability),
                ('Draw', s.draw), ('Ticket price', s.ticket_price), ('Guests', s.guests), ('Bio', s.bio),
                ('Notes', s.notes), ('Staff notes', s.staff_notes)]
        for label, value in rows:
            if value:
                out(f'{label + ":":<17}{value}')
        out('')
        out(f'Folder: {s.folder()}')
        for f in s.files.all():
            length = f'  {f.duration_seconds:.0f}s' if f.duration_seconds is not None else ''
            out(f'  {f.kind:<9} {_mb(f.size):>9}{length}  {f.path}  (sent as {f.original_name})')
        out('')
        out(f'Admin: {admin_url(s)}')
        out('Copy them off (from ansible/):')
        out(f'  ansible all --become -m shell -a "umask 077 && tar -C {settings.COMICS_DIR} -cf /tmp/{s.pk}.tar {s.pk}" '
            '</dev/null')
        out(f'  ansible all --become -m fetch -a "src=/tmp/{s.pk}.tar dest=./ flat=yes" </dev/null')
        out(f'  ansible all --become -m file -a "path=/tmp/{s.pk}.tar state=absent" </dev/null')
        out('Then fit the photo to the flyer with scripts/fit-poster.py --source <photo> --stem <slug>, '
            'and make the event in the admin.')
