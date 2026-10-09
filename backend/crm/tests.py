import io
import os
import shutil
import stat
import tempfile
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from crm.models import ComicFile, ComicSubmission

JPEG = b'\xff\xd8\xff\xe0' + b'0' * 2000
MP4 = b'\x00\x00\x00\x18ftypmp42' + b'0' * 4000


def photo(name='me.jpg', data=JPEG):
    return SimpleUploadedFile(name, data, content_type='image/jpeg')


def clip(name='set.mp4', data=MP4):
    return SimpleUploadedFile(name, data, content_type='video/mp4')


@mock.patch('api.comic_views._start_probe')
class ComicSubmissionTests(TestCase):
    """iguanacomedy.com/comic: a comedian's photo, clips and dates, stored privately and mailed to hello@."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.comics = os.path.join(self.dir, 'comics')
        override = override_settings(COMICS_DIR=self.comics, NOTIFY_EMAILS=['hello@iguanacomedy.com'],
                                     DEFAULT_FROM_EMAIL='"Iguana Comedy" <noreply@iguanacomedy.com>')
        override.enable()
        self.addCleanup(override.disable)
        self.addCleanup(shutil.rmtree, self.dir, True)

    def data(self, **extra):
        day = (timezone.localdate() + timedelta(days=30)).isoformat()
        body = {'name': 'Ana Prueba', 'stage_name': 'La Ana', 'email': 'Ana@Example.com', 'phone': '+52 984 000 0000',
                'instagram': '@ana', 'home_city': 'CDMX', 'lang_es': '1', 'bio': 'Comedia de observación desde 2015.',
                'dates': [day, '', day], 'availability': 'Libre en noviembre.', 'consent': '1', 'lang': 'es',
                'photos': [photo(), photo('second.PNG')], 'clip_short': clip('short.mov'), 'clip_long': clip('long.mp4')}
        body.update(extra)
        return body

    def test_submission_stores_files_privately_and_mails_the_club_and_the_comic(self, probe):
        response = self.client.post('/comic/', self.data())
        self.assertRedirects(response, '/comic/thanks/?lang=es', fetch_redirect_response=False)

        s = ComicSubmission.objects.get()
        self.assertEqual((s.email, s.lang, s.languages, len(s.requested_dates)), ('ana@example.com', 'es', 'Spanish', 1))
        self.assertIsNotNone(s.consent_at)
        files = list(s.files.all())
        self.assertEqual(sorted(f.kind for f in files), ['CLIP_30', 'CLIP_LONG', 'PHOTO', 'PHOTO'])
        self.assertEqual(s.folder(), os.path.join(self.comics, s.pk))
        self.assertEqual(stat.S_IMODE(os.stat(s.folder()).st_mode), 0o700)
        for f in files:
            self.assertTrue(os.path.isfile(f.path))
            self.assertEqual(stat.S_IMODE(os.stat(f.path).st_mode), 0o600)
            self.assertEqual(os.path.getsize(f.path), f.size)
        self.assertNotIn('media', s.folder())
        probe.assert_called_once()

        club, receipt = mail.outbox
        self.assertEqual(club.to, ['hello@iguanacomedy.com'])
        self.assertEqual(club.reply_to, ['ana@example.com'])
        self.assertIn('La Ana (Ana Prueba)', club.subject)
        self.assertIn('2 photo(s), 2 clip(s)', club.subject)
        for text in ('@ana', 'CDMX', 'Requested dates:', 'Libre en noviembre.', f'/admin/crm/comicsubmission/{s.pk}/change/',
                     f'comic_submission {s.pk}', 'short.mov'):
            self.assertIn(text, club.body)
        self.assertEqual(receipt.to, ['ana@example.com'])
        self.assertEqual(receipt.subject, 'Recibimos tus fotos y tus clips')
        self.assertIn('Hola, La Ana:', receipt.body)
        self.assertIn('Recibimos 2 foto(s) y 2 clip(s).', receipt.body)
        self.assertNotIn('unsubscribe', receipt.body.lower())

    def test_xhr_gets_json(self, probe):
        response = self.client.post('/comic/?lang=en', self.data(lang='en'), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.json(), {'redirect': '/comic/thanks/?lang=en'})
        response = self.client.post('/comic/', self.data(lang='en', name='', consent=''),
                                    HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Write your name.', response.json()['errors'])

    def test_validation_keeps_nothing_and_answers_in_their_language(self, probe):
        bad = self.data(name='', email='nope', consent='', photos=[photo('doc.pdf')], clip_short=clip('a.avi'),
                        clip_long='', dates=['2001-01-01'])
        response = self.client.post('/comic/', bad)
        self.assertEqual(response.status_code, 400)
        page = response.content.decode()
        for text in ('Escribe tu nombre.', 'Escribe un correo donde podamos contactarte.',
                     'doc.pdf no es una foto que podamos usar', 'a.avi no es un video que podamos usar',
                     'Elige fechas de hoy en adelante.', 'Marca la casilla'):
            self.assertIn(text, page)
        self.assertFalse(ComicSubmission.objects.exists())
        self.assertFalse(os.path.exists(self.comics) and os.listdir(self.comics))
        self.assertEqual(mail.outbox, [])

        response = self.client.post('/comic/', self.data(photos=[], clip_short='', clip_long=''))
        self.assertContains(response, 'Agrega al menos una foto', status_code=400)
        self.assertContains(response, 'Manda al menos un clip', status_code=400)

    def test_files_spooled_to_disk_are_moved_into_place(self, probe):
        # Anything over FILE_UPLOAD_MAX_MEMORY_SIZE arrives as a temp file, which is how every real clip arrives.
        with override_settings(FILE_UPLOAD_MAX_MEMORY_SIZE=100, FILE_UPLOAD_TEMP_DIR=self.dir):
            self.assertEqual(self.client.post('/comic/', self.data()).status_code, 302)
        for f in ComicSubmission.objects.get().files.all():
            self.assertEqual(os.path.getsize(f.path), f.size)
        self.assertEqual(sorted(os.listdir(self.dir)), ['comics'])  # nothing left behind in the temp dir

    def test_a_link_stands_in_for_clips(self, probe):
        response = self.client.post('/comic/', self.data(clip_short='', clip_long='', links='https://youtu.be/x'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ComicSubmission.objects.get().files.count(), 2)

    def test_size_limit(self, probe):
        with mock.patch('api.comic_views.PHOTO_MAX_MB', 0):
            response = self.client.post('/comic/', self.data())
        self.assertContains(response, 'pesa más de 0 MB', status_code=400)

    def test_honeypot_is_thanked_and_dropped(self, probe):
        response = self.client.post('/comic/', self.data(company_website='http://spam.example'))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(ComicSubmission.objects.exists())
        self.assertEqual(mail.outbox, [])

    def test_random_token_bio_is_refused(self, probe):
        response = self.client.post('/comic/', self.data(bio='qjWYpEHreBSHUKwJlWwkQGD'))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(ComicSubmission.objects.exists())

    def test_rate_limited_by_address(self, probe):
        for _ in range(3):
            self.assertEqual(self.client.post('/comic/', self.data()).status_code, 302)
        response = self.client.post('/comic/', self.data())
        self.assertContains(response, 'Demasiados envíos', status_code=400)
        self.assertEqual(ComicSubmission.objects.count(), 3)

    def test_page_is_bilingual(self, probe):
        self.assertContains(self.client.get('/comic/?lang=es'), '¿Quieres un show en Iguana Comedy?')
        english = self.client.get('/comic/', HTTP_ACCEPT_LANGUAGE='en-US')
        self.assertContains(english, 'Want a show at Iguana Comedy?')
        self.assertContains(english, 'name="photos"')
        self.assertContains(self.client.get('/comic/thanks/?lang=es'), 'Gracias, ya tenemos todo')
        self.assertContains(self.client.get('/comic/thanks/?lang=en'), 'Thank you, we have it all')

    def test_admin_serves_files_to_staff_only_and_delete_removes_them(self, probe):
        self.client.post('/comic/', self.data())
        s = ComicSubmission.objects.get()
        item = s.files.filter(kind=ComicFile.PHOTO).first()
        url = f'/admin/crm/comicsubmission/{s.pk}/file/{item.pk}/'
        self.assertEqual(self.client.get(url).status_code, 302)  # to the admin login

        admin = get_user_model().objects.create_superuser('boss', 'boss@example.com', 'x')
        self.client.force_login(admin)
        page = self.client.get(f'/admin/crm/comicsubmission/{s.pk}/change/')
        self.assertContains(page, url)
        response = self.client.get(url)
        self.assertEqual(b''.join(response.streaming_content), JPEG)
        self.assertIn('attachment', response['Content-Disposition'])

        out = io.StringIO()
        call_command('comic_submission', s.pk, stdout=out)
        self.assertIn(item.path, out.getvalue())
        self.assertIn('Requested dates:', out.getvalue())
        call_command('comic_submission', s.pk, '--delete', stdout=io.StringIO())
        self.assertFalse(os.path.exists(s.folder()))
        self.assertFalse(ComicFile.objects.exists())
