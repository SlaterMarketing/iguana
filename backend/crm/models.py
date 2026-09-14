from django.db import models
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
    source = models.CharField(max_length=30, blank=True, help_text='IMPORT, CONTACT_FORM, ORDER, MEMBERSHIP, SIGN_IN')
    source_event_id = models.CharField(max_length=40, blank=True)
    page_visitor_key = models.CharField(max_length=100, blank=True)
    stripe_customer_id = models.CharField(max_length=60, blank=True)
    stripe_card_brand = models.CharField(max_length=20, blank=True)
    stripe_card_last4 = models.CharField(max_length=4, blank=True)
    welcome_email_sent_at = models.DateTimeField(null=True, blank=True)
    custom_data = models.JSONField(default=dict, blank=True)
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
