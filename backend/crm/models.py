import os
import shutil

from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils import timezone

from iguana.ids import new_id


class Contact(models.Model):
    id = models.CharField(primary_key=True, max_length=40, default=new_id, editable=False)
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=200, blank=True)
    last_name = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    phone_e164 = models.CharField(max_length=20, blank=True)
    subscribed = models.BooleanField(default=True)
    subscribed_at = models.DateTimeField(null=True, blank=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)
    email_marketing_eligible = models.BooleanField(default=True)
    source = models.CharField(max_length=30, blank=True, help_text='IMPORT, CONTACT_FORM, NEWSLETTER, ORDER, MEMBERSHIP, SIGN_IN')
    source_event_id = models.CharField(max_length=40, blank=True)
    page_visitor_key = models.CharField(max_length=100, blank=True)
    stripe_customer_id = models.CharField(max_length=60, blank=True)
    stripe_card_brand = models.CharField(max_length=20, blank=True)
    stripe_card_last4 = models.CharField(max_length=4, blank=True)
    welcome_email_sent_at = models.DateTimeField(null=True, blank=True)
    custom_data = models.JSONField(default=dict, blank=True)
    # Latest language and location seen when they signed up or booked (crm.geo). countries/cities below came from the
    # Kintana export.
    locale = models.CharField(max_length=5, blank=True, help_text='Site language they used: en or es')
    browser_language = models.CharField(max_length=35, blank=True)
    time_zone = models.CharField(max_length=60, blank=True)
    geo_country = models.CharField(max_length=2, blank=True, help_text='From their IP address')
    geo_region = models.CharField(max_length=120, blank=True)
    geo_city = models.CharField(max_length=120, blank=True)
    last_ip = models.GenericIPAddressField(null=True, blank=True)
    countries = models.CharField(max_length=500, blank=True)
    cities = models.CharField(max_length=500, blank=True)
    tags = models.JSONField(default=list, blank=True)
    wallet_credit_cents = models.IntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        name = f'{self.first_name} {self.last_name}'.strip()
        return f'{name} <{self.email}>' if name else self.email

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()
        self.updated_at = timezone.now()
        super().save(*args, **kwargs)


class ContactList(models.Model):
    id = models.CharField(primary_key=True, max_length=40, default=new_id, editable=False)
    name = models.CharField(max_length=200, unique=True)
    created_at = models.DateTimeField(default=timezone.now)
    contacts = models.ManyToManyField(Contact, through='ContactListMember', related_name='lists')

    def __str__(self):
        return self.name


class ContactListMember(models.Model):
    contact_list = models.ForeignKey(ContactList, on_delete=models.CASCADE)
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE)
    added_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = [('contact_list', 'contact')]


class Campaign(models.Model):
    name = models.CharField(max_length=200, unique=True)
    status = models.CharField(max_length=20, default='DRAFT')
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.name


class CampaignRecipient(models.Model):
    id = models.CharField(primary_key=True, max_length=40, default=new_id, editable=False)
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='recipients')
    contact = models.ForeignKey(Contact, null=True, blank=True, on_delete=models.SET_NULL)
    email = models.EmailField()
    status = models.CharField(max_length=20)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    clicked_at = models.DateTimeField(null=True, blank=True)
    bounced_at = models.DateTimeField(null=True, blank=True)
    complained_at = models.DateTimeField(null=True, blank=True)
    send_attempts = models.PositiveIntegerField(default=0)


class InboxConversation(models.Model):
    id = models.CharField(primary_key=True, max_length=40, default=new_id, editable=False)
    channel_type = models.CharField(max_length=20)
    platform = models.CharField(max_length=30, blank=True)
    subject = models.CharField(max_length=300, blank=True)
    status = models.CharField(max_length=20, default='OPEN')
    handler_mode = models.CharField(max_length=20, blank=True)
    auto_tag = models.CharField(max_length=60, blank=True)
    participant_name = models.CharField(max_length=200, blank=True)
    participant_username = models.CharField(max_length=200, blank=True)
    account_username = models.CharField(max_length=200, blank=True)
    contact = models.ForeignKey(Contact, null=True, blank=True, on_delete=models.SET_NULL, related_name='conversations')
    last_message_preview = models.TextField(blank=True)
    last_message_at = models.DateTimeField(null=True, blank=True)
    unread_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-last_message_at']

    def __str__(self):
        return self.subject or self.participant_name or self.id


class InboxMessage(models.Model):
    id = models.CharField(primary_key=True, max_length=40, default=new_id, editable=False)
    conversation = models.ForeignKey(InboxConversation, on_delete=models.CASCADE, related_name='messages')
    direction = models.CharField(max_length=10)
    content_type = models.CharField(max_length=10, default='TEXT')
    content = models.TextField(blank=True)
    sender_name = models.CharField(max_length=200, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['sent_at']


class TrackedEvent(models.Model):
    """Pageviews and site events from /_t/k.js (replaces Kintana ingest)."""

    kind = models.CharField(max_length=40)
    name = models.CharField(max_length=80, blank=True)
    visitor_key = models.CharField(max_length=100, blank=True)
    url = models.URLField(max_length=1000, blank=True)
    referrer = models.URLField(max_length=1000, blank=True)
    properties = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)


class AdSpend(models.Model):
    """One campaign's spend on one day, as Meta reported it when we last looked.

    Kept in the database rather than fetched per request. The ad account's rate limit clears only by waiting,
    so a page that called Meta on every load would eventually take itself down and take the numbers with it,
    and a Graph outage would turn a dashboard into a 500. A cron writes these rows; `/stats/` only reads them,
    which also means the page still renders, with an honest "last updated" line, when Meta is unreachable.

    Rows are upserted on (day, campaign_id): today's figure is restated as the day goes on and settles after it.
    """

    FREE = 'FREE'
    PAID = 'PAID'

    DAY, WEEK = 'DAY', 'WEEK'

    day = models.DateField(db_index=True)
    # A DAY row is that day's figures. A WEEK row is the seven days ENDING on `day`, fetched as one window
    # rather than summed, because reach counts PEOPLE: adding seven days of reach counts somebody who saw the
    # ad on Monday and Thursday twice, and the frequency derived from it would be quietly wrong.
    window = models.CharField(max_length=5, default=DAY, choices=[(DAY, 'Day'), (WEEK, 'Week')])
    campaign_id = models.CharField(max_length=40)
    campaign_name = models.CharField(max_length=200)
    kind = models.CharField(max_length=8, default=PAID, help_text='Whether this campaign sells free seats or tickets.')
    spend_cents = models.PositiveIntegerField(default=0)
    impressions = models.PositiveIntegerField(default=0)
    clicks = models.PositiveIntegerField(default=0)
    reported_purchases = models.PositiveIntegerField(default=0, help_text="Meta's own count, which is not ours.")
    reach = models.PositiveIntegerField(default=0, help_text='People who saw it at least once, deduplicated.')
    frequency = models.FloatField(default=0, help_text='Impressions per person. Meta reports it; never summed.')
    fetched_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-day', 'campaign_name']
        constraints = [models.UniqueConstraint(fields=['day', 'window', 'campaign_id'],
                                               name='one_row_per_campaign_per_window')]

    def __str__(self):
        return f'{self.day} {self.campaign_name} {self.spend_cents / 100:.2f}'


class ComicSubmission(models.Model):
    """A comedian asking for a show, from iguanacomedy.com/comic (api/comic_views.py).

    The photos and clips are unpublished material, so they live in `COMICS_DIR/<id>/`, outside backend/media where
    nginx would serve them; staff fetch them through the admin (login required) or copy them off with ansible.
    `manage.py comic_submission <id>` prints everything needed to turn one into an event.
    """

    NEW, IN_TALKS, BOOKED, DECLINED = 'NEW', 'IN_TALKS', 'BOOKED', 'DECLINED'
    STATUS_CHOICES = [(NEW, 'New'), (IN_TALKS, 'In talks'), (BOOKED, 'Booked'), (DECLINED, 'Declined')]

    id = models.CharField(primary_key=True, max_length=40, default=new_id, editable=False)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=NEW)
    staff_notes = models.TextField(blank=True, help_text='Ours only, never shown to the comedian.')
    lang = models.CharField(max_length=2, default='en', help_text='The language they filled the form in.')

    name = models.CharField(max_length=200)
    stage_name = models.CharField(max_length=200, blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True, help_text='Phone or WhatsApp')
    instagram = models.CharField(max_length=200, blank=True)
    tiktok = models.CharField(max_length=200, blank=True)
    links = models.TextField(blank=True, help_text='YouTube, specials, other clips')
    home_city = models.CharField(max_length=200, blank=True)
    languages = models.CharField(max_length=200, blank=True, help_text='Languages they perform in')
    bio = models.TextField(blank=True)

    requested_dates = models.JSONField(default=list, blank=True, help_text='ISO dates they would like, in order')
    availability = models.TextField(blank=True)
    show_name = models.CharField(max_length=200, blank=True)
    draw = models.TextField(blank=True, help_text='Expected draw, followers')
    ticket_price = models.CharField(max_length=200, blank=True)
    guests = models.TextField(blank=True, help_text='Do they bring an opener or guests')
    notes = models.TextField(blank=True)

    consent_at = models.DateTimeField(help_text='When they agreed we may use the photos and clips to promote the show')
    ip = models.CharField(max_length=64, blank=True, db_index=True)
    user_agent = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.stage_name or self.name} ({self.created_at:%Y-%m-%d})'

    @property
    def display_name(self):
        if self.stage_name and self.stage_name != self.name:
            return f'{self.stage_name} ({self.name})'
        return self.name

    def folder(self):
        from django.conf import settings

        return os.path.join(settings.COMICS_DIR, self.id)


class ComicFile(models.Model):
    PHOTO, CLIP_SHORT, CLIP_MINUTE, CLIP_LONG = 'PHOTO', 'CLIP_30', 'CLIP_60', 'CLIP_LONG'
    KIND_CHOICES = [(PHOTO, 'Photo'), (CLIP_SHORT, 'Clip, about 30 seconds'), (CLIP_MINUTE, 'Clip, about 1 minute'),
                    (CLIP_LONG, 'Clip, 2 to 5 minutes')]

    submission = models.ForeignKey(ComicSubmission, on_delete=models.CASCADE, related_name='files')
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    original_name = models.CharField(max_length=255)
    stored_name = models.CharField(max_length=255, help_text="File name inside the submission's folder")
    size = models.BigIntegerField(default=0)
    duration_seconds = models.FloatField(null=True, blank=True, help_text='Read with ffprobe after upload, when available')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['kind', 'id']

    def __str__(self):
        return f'{self.get_kind_display()}: {self.original_name}'

    @property
    def path(self):
        return os.path.join(self.submission.folder(), self.stored_name)

    @property
    def is_clip(self):
        return self.kind != self.PHOTO


@receiver(post_delete, sender=ComicSubmission)
def _remove_comic_files(sender, instance, **kwargs):
    """Deleting a submission (admin, bulk delete or the command) takes its photos and clips with it."""
    shutil.rmtree(instance.folder(), ignore_errors=True)
