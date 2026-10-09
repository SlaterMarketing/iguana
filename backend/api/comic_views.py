"""`/comic/`: a comedian who wants a show sends their photo, their clips and the dates they would like.

The photo is what the flyer is made from, and the clips are what the ads are cut from (30 seconds, a minute, and a
longer set), so the club can go from "this comic uploaded" to an event without chasing anybody for material.

Files are unpublished material and go to `COMICS_DIR/<submission id>/` (0700, files 0600), outside
`backend/media`, so nginx has no route to them. Staff download them from the admin, behind its login
(crm/admin.py), or copy them off with ansible. `manage.py comic_submission <id>` prints all of it.

Big uploads: nginx buffers the whole body to disk before it reaches gunicorn (proxy_request_buffering is on), so a
slow phone upload never holds one of the three sync workers. Django then spools each file to a temp file on the
same disk, and saving it here is a rename, not a copy. Duration is read with ffprobe in a background thread after
the response, so a missing or slow ffprobe never costs a submission.

Every visible string is English and Spanish (`tr`, `{% t %}`). The notification to the club is internal and English.
"""
import logging
import os
import shutil
import subprocess
import threading
from datetime import date, timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.move import file_move_safe
from django.core.mail import EmailMessage
from django.core.validators import validate_email
from django.db import connection, transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import formats, timezone, translation
from django.utils.text import get_valid_filename

from catalog.spam import HONEYPOT_FIELD, honeypot_tripped, looks_like_a_person_wrote_it
from crm.geo import client_ip
from crm.models import ComicFile, ComicSubmission
from sales.i18n import lang_from_request, normalize, tr
from sales.services import DATE_FORMATS

log = logging.getLogger(__name__)

MB = 1024 * 1024
PHOTO_TYPES = ('.jpg', '.jpeg', '.png', '.heic', '.heif', '.webp')
CLIP_TYPES = ('.mp4', '.mov', '.m4v')
MAX_PHOTOS = 6
PHOTO_MAX_MB = 25
CLIP_MAX_MB = 500
# The three clips asked for, in the order the ads use them.
CLIP_FIELDS = (('clip_short', ComicFile.CLIP_SHORT), ('clip_minute', ComicFile.CLIP_MINUTE),
               ('clip_long', ComicFile.CLIP_LONG))
MAX_DATES = 10
# Per address. A real comedian sends one; a second is a correction. More than this is a bot or a loop.
PER_HOUR, PER_DAY = 3, 8
# Refuse rather than fill the disk the database and the backups live on.
MIN_FREE_BYTES = 5 * 1024 * MB

TEXT_FIELDS = {  # form field -> max length
    'name': 200, 'stage_name': 200, 'email': 254, 'phone': 40, 'instagram': 200, 'tiktok': 200, 'links': 2000,
    'home_city': 200, 'lang_other': 100, 'bio': 4000, 'availability': 2000, 'show_name': 200, 'draw': 1000,
    'ticket_price': 200, 'guests': 1000, 'notes': 4000,
}
# Free text a person writes in sentences, judged by catalog.spam (a bio of one random token is a bot).
SENTENCE_FIELDS = ('bio', 'notes', 'availability')


def _lang(request):
    return normalize(request.GET.get('lang') or request.POST.get('lang') or lang_from_request(request))


def _wants_json(request):
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


def _ext(upload):
    return os.path.splitext(upload.name or '')[1].lower()


def _too_many(ip):
    if not ip:
        return False
    now = timezone.now()
    recent = ComicSubmission.objects.filter(ip=ip)
    return (recent.filter(created_at__gte=now - timedelta(hours=1)).count() >= PER_HOUR
            or recent.filter(created_at__gte=now - timedelta(days=1)).count() >= PER_DAY)


def _disk_is_full():
    path = settings.COMICS_DIR
    while path and not os.path.exists(path):
        path = os.path.dirname(path)
    try:
        return shutil.disk_usage(path or '/').free < MIN_FREE_BYTES
    except OSError:
        return False


def _dates(raw, lang, errors):
    today = timezone.localdate()
    picked = []
    for value in raw:
        value = (value or '').strip()
        if not value:
            continue
        try:
            day = date.fromisoformat(value)
        except ValueError:
            errors.append(tr(lang, 'One of the dates is not a date. Use the date picker.'))
            continue
        if day < today:
            errors.append(tr(lang, 'Choose dates from today on.'))
        elif day > today + timedelta(days=550):
            errors.append(tr(lang, 'Choose dates within the next 18 months.'))
        elif day.isoformat() not in picked:
            picked.append(day.isoformat())
    return picked[:MAX_DATES]


def format_dates(iso_dates, lang):
    with translation.override(lang):
        return [formats.date_format(date.fromisoformat(d), DATE_FORMATS[lang]) for d in iso_dates]


def _validate(request, lang):
    """(cleaned fields, photos, clips, errors)."""
    post = request.POST
    errors = []
    fields = {key: post.get(key, '').strip()[:limit] for key, limit in TEXT_FIELDS.items()}
    fields['email'] = fields['email'].lower()

    if not fields['name']:
        errors.append(tr(lang, 'Write your name.'))
    try:
        validate_email(fields['email'])
    except ValidationError:
        errors.append(tr(lang, 'Write an email address we can reach you at.'))
    if any(not looks_like_a_person_wrote_it(fields[key]) for key in SENTENCE_FIELDS):
        errors.append(tr(lang, 'Write your bio and notes in words, a sentence or two is plenty.'))

    photos = [f for f in request.FILES.getlist('photos') if f.size]
    if not photos:
        errors.append(tr(lang, 'Add at least one photo of you. It is what the flyer is made from.'))
    elif len(photos) > MAX_PHOTOS:
        errors.append(tr(lang, 'Send up to {0} photos.', MAX_PHOTOS))
    for upload in photos[:MAX_PHOTOS]:
        if _ext(upload) not in PHOTO_TYPES:
            errors.append(tr(lang, '{0} is not a photo we can use. Send JPG, PNG, HEIC or WebP.', upload.name))
        elif upload.size > PHOTO_MAX_MB * MB:
            errors.append(tr(lang, '{0} is larger than {1} MB.', upload.name, PHOTO_MAX_MB))

    clips = []
    for field, kind in CLIP_FIELDS:
        upload = request.FILES.get(field)
        if not upload or not upload.size:
            continue
        if _ext(upload) not in CLIP_TYPES:
            errors.append(tr(lang, '{0} is not a video we can use. Send MP4 or MOV.', upload.name))
        elif upload.size > CLIP_MAX_MB * MB:
            errors.append(tr(lang, '{0} is larger than {1} MB.', upload.name, CLIP_MAX_MB))
        else:
            clips.append((kind, upload))
    if not clips and not fields['links']:
        errors.append(tr(lang, 'Send at least one clip, or a link to one.'))

    fields['dates'] = _dates(post.getlist('dates'), lang, errors)
    languages = [label for key, label in (('lang_en', 'English'), ('lang_es', 'Spanish')) if post.get(key)]
    if fields['lang_other']:
        languages.append(fields['lang_other'])
    fields['languages'] = ', '.join(languages)
    if not post.get('consent'):
        errors.append(tr(lang, 'Tick the box that lets us use your photos and clips to promote the show.'))
    return fields, photos[:MAX_PHOTOS], clips, list(dict.fromkeys(errors))


def _store(submission, photos, clips):
    folder = submission.folder()
    os.makedirs(settings.COMICS_DIR, mode=0o700, exist_ok=True)
    os.makedirs(folder, mode=0o700)
    rows = []
    for n, (kind, upload) in enumerate([(ComicFile.PHOTO, p) for p in photos] + clips, start=1):
        safe = get_valid_filename(os.path.basename(upload.name or 'file'))[-100:] or 'file'
        stored = f'{n:02d}-{kind.lower()}__{safe}'
        dest = os.path.join(folder, stored)
        if hasattr(upload, 'temporary_file_path'):
            # Same disk as the temp dir, so this is a rename: a 500 MB clip costs nothing to keep.
            file_move_safe(upload.temporary_file_path(), dest, allow_overwrite=False)
        else:
            with open(dest, 'xb') as out:
                for chunk in upload.chunks():
                    out.write(chunk)
        os.chmod(dest, 0o600)
        rows.append(ComicFile(submission=submission, kind=kind, original_name=(upload.name or '')[:255],
                              stored_name=stored, size=upload.size))
    ComicFile.objects.bulk_create(rows)


def _size(n):
    return f'{n / MB:.1f} MB'


def admin_url(submission):
    return f'{settings.BACKEND_URL}/admin/crm/comicsubmission/{submission.pk}/change/'


def notify_club(submission):
    """The mail to hello@: everything needed to say "make an event from this comic" without opening anything."""
    files = list(submission.files.all())
    photos = [f for f in files if not f.is_clip]
    clips = [f for f in files if f.is_clip]
    one_line = lambda text: ' '.join(str(text).split())
    rows = [
        ('Email', submission.email), ('Phone / WhatsApp', submission.phone), ('Instagram', submission.instagram),
        ('TikTok', submission.tiktok), ('Links', submission.links), ('Home city', submission.home_city),
        ('Performs in', submission.languages), ('Show name', submission.show_name),
        ('Requested dates', ', '.join(format_dates(submission.requested_dates, 'en'))),
        ('Availability', submission.availability), ('Expected draw / followers', submission.draw),
        ('Ticket price idea', submission.ticket_price), ('Opener / guests', submission.guests),
        ('Form language', 'Spanish' if submission.lang == 'es' else 'English'),
    ]
    lines = [f'{submission.display_name} sent their photo and clips through iguanacomedy.com/comic.', '']
    lines += [f'{label}: {value}' for label, value in rows if value]
    for label, value in (('Bio', submission.bio), ('Notes', submission.notes)):
        if value:
            lines += ['', f'{label}:', value]
    lines += ['', f'Files ({len(photos)} photo(s), {len(clips)} clip(s), {_size(sum(f.size for f in files))} in all):']
    lines += [f'  {f.get_kind_display()}: {f.original_name}, {_size(f.size)}' for f in files]
    lines += ['', f'Admin, with every file to download: {admin_url(submission)}',
              f'On the server: manage.py comic_submission {submission.pk}  (files in {submission.folder()})',
              '', 'Reply to this email to answer them directly.']
    subject = one_line(f'Comedian submission: {submission.display_name}, {len(photos)} photo(s), {len(clips)} clip(s)')
    EmailMessage(subject[:200], '\n'.join(lines), settings.DEFAULT_FROM_EMAIL, list(settings.NOTIFY_EMAILS),
                 reply_to=[submission.email]).send(fail_silently=False)


def receipt(submission):
    """The comedian's copy, in the language they filled the form in. No marketing footer: it is a receipt."""
    lang = submission.lang
    files = list(submission.files.all())
    photos = sum(1 for f in files if not f.is_clip)
    lines = [tr(lang, 'Hi {0},', ' '.join((submission.stage_name or submission.name).split())), '',
             tr(lang, 'Thank you for sending your material to Iguana Comedy. We received {0} photo(s) and {1} clip(s).',
                photos, len(files) - photos)]
    if submission.requested_dates:
        lines.append(tr(lang, 'Dates you asked about: {0}.', ', '.join(format_dates(submission.requested_dates, lang))))
    lines += ['', tr(lang, 'We will look at everything and write back to this address. We may cut and adjust your clips for the ads and use your photo for the flyer.'),
              tr(lang, 'To add or change anything, or if a file did not go through, reply to this email or write to hello@iguanacomedy.com.'), '', 'Iguana Comedy', 'iguanacomedy.com']
    reply_to = list(settings.NOTIFY_EMAILS)[:1] or None
    EmailMessage(tr(lang, 'We got your photos and clips'), '\n'.join(lines), settings.DEFAULT_FROM_EMAIL,
                 [submission.email], reply_to=reply_to).send(fail_silently=True)


def probe_durations(file_ids):
    """Seconds per clip, via ffprobe. Runs in a thread after the response; anything going wrong leaves it blank."""
    ffprobe = shutil.which('ffprobe')
    if not ffprobe:
        return
    try:
        for clip in ComicFile.objects.filter(pk__in=file_ids).select_related('submission'):
            try:
                out = subprocess.run([ffprobe, '-v', 'error', '-show_entries', 'format=duration', '-of',
                                      'default=noprint_wrappers=1:nokey=1', clip.path],
                                     capture_output=True, text=True, timeout=30)
                clip.duration_seconds = float(out.stdout.strip())
            except (OSError, ValueError, subprocess.SubprocessError):
                continue
            clip.save(update_fields=['duration_seconds'])
    finally:
        connection.close()


def _start_probe(file_ids):
    if file_ids and shutil.which('ffprobe'):
        threading.Thread(target=probe_durations, args=(file_ids,), daemon=True).start()


def _render_form(request, lang, errors=(), values=None, status=200):
    values = values or {}
    dates = list(values.get('dates') or [])
    context = {
        'lang': lang, 'other_lang': 'en' if lang == 'es' else 'es', 'errors': errors, 'v': values,
        'dates': dates + [''] * max(0, 3 - len(dates)), 'today': timezone.localdate().isoformat(),
        'honeypot': HONEYPOT_FIELD, 'photo_types': ','.join(PHOTO_TYPES) + ',image/*',
        'clip_types': ','.join(CLIP_TYPES) + ',video/mp4,video/quicktime', 'max_photos': MAX_PHOTOS,
        'photo_max_mb': PHOTO_MAX_MB, 'clip_max_mb': CLIP_MAX_MB,
        'posted': {key: True for key in ('lang_en', 'lang_es', 'consent') if request.POST.get(key)},
    }
    return render(request, 'embed/comic.html', context, status=status)


def _refuse(request, lang, errors, values=None):
    if _wants_json(request):
        return JsonResponse({'errors': errors}, status=400)
    return _render_form(request, lang, errors, values, status=400)


def comic(request):
    lang = _lang(request)
    if request.method != 'POST':
        return _render_form(request, lang)

    thanks = f'/comic/thanks/?lang={lang}'
    if honeypot_tripped(request.POST):
        # Answer a bot exactly as a person is answered, and keep nothing.
        log.info('comic: honeypot submission dropped')
        return JsonResponse({'redirect': thanks}) if _wants_json(request) else redirect(thanks)

    ip = client_ip(request)
    if _too_many(ip):
        return _refuse(request, lang, [tr(lang, 'Too many submissions from here. Try again later, or write to hello@iguanacomedy.com.')])
    if _disk_is_full():
        log.critical('comic: refusing a submission, less than %s free in %s', _size(MIN_FREE_BYTES), settings.COMICS_DIR)
        return _refuse(request, lang, [tr(lang, 'We cannot take uploads right now. Write to hello@iguanacomedy.com and we will sort it out.')])

    fields, photos, clips, errors = _validate(request, lang)
    if errors:
        return _refuse(request, lang, errors, fields)

    submission = ComicSubmission(
        lang=lang, name=fields['name'], stage_name=fields['stage_name'], email=fields['email'],
        phone=fields['phone'], instagram=fields['instagram'], tiktok=fields['tiktok'], links=fields['links'],
        home_city=fields['home_city'], languages=fields['languages'][:200], bio=fields['bio'],
        requested_dates=fields['dates'], availability=fields['availability'], show_name=fields['show_name'],
        draw=fields['draw'], ticket_price=fields['ticket_price'], guests=fields['guests'], notes=fields['notes'],
        consent_at=timezone.now(), ip=ip, user_agent=request.headers.get('User-Agent', '')[:300])
    try:
        with transaction.atomic():
            submission.save()
            _store(submission, photos, clips)
    except Exception:
        shutil.rmtree(submission.folder(), ignore_errors=True)
        raise
    log.info('comic: submission %s, %s file(s)', submission.pk, len(photos) + len(clips))

    try:
        notify_club(submission)
    except Exception:
        # The files and the row are safe; the admin shows them. Losing the mail must not lose the comedian.
        log.exception('comic: notification for %s failed', submission.pk)
    receipt(submission)
    _start_probe(list(submission.files.filter(kind__in=[k for _, k in CLIP_FIELDS]).values_list('pk', flat=True)))
    return JsonResponse({'redirect': thanks}) if _wants_json(request) else redirect(thanks)


def thanks(request):
    lang = _lang(request)
    return render(request, 'embed/comic_thanks.html', {'lang': lang, 'other_lang': 'en' if lang == 'es' else 'es'})
