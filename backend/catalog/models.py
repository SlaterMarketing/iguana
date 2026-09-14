from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from iguana.ids import new_id


class Venue(models.Model):
    id = models.CharField(primary_key=True, max_length=40, default=new_id, editable=False)
    slug = models.SlugField(max_length=120, unique=True)
    name = models.CharField(max_length=200)
    address = models.CharField(max_length=300, blank=True)
    city = models.CharField(max_length=120, blank=True)
    country = models.CharField(max_length=120, blank=True, default='Mexico')
    description = models.TextField(blank=True)
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)
    time_zone = models.CharField(max_length=60, default='America/Cancun')
    capacity = models.PositiveIntegerField(default=0)
    image_url = models.URLField(max_length=500, blank=True)
    wheelchair_accessible = models.BooleanField(null=True, blank=True)
    listed = models.BooleanField(default=True, help_text='Show on the public locations pages.')

    class Meta:
        ordering = ['city', 'name']

    def __str__(self):
        return f'{self.name} ({self.city})' if self.city else self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:120] or new_id()
        super().save(*args, **kwargs)


class Artist(models.Model):
    id = models.CharField(primary_key=True, max_length=40, default=new_id, editable=False)
    slug = models.SlugField(max_length=120, unique=True)
    name = models.CharField(max_length=200)
    stage_name = models.CharField(max_length=200, blank=True)
    bio = models.TextField(blank=True)
    bio_es = models.TextField(blank=True)
    image_url = models.URLField(max_length=500, blank=True)
    website = models.URLField(max_length=500, blank=True)
    home_city = models.CharField(max_length=120, blank=True)
    residency = models.CharField(max_length=200, blank=True)
    socials = models.JSONField(default=dict, blank=True, help_text='{"instagram": "https://..."}')
    reels = models.JSONField(default=list, blank=True, help_text='[{"title": "", "url": "", "posterUrl": null}]')
    sort_order = models.IntegerField(default=0)
    listed = models.BooleanField(default=True)

    class Meta:
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:120] or new_id()
        super().save(*args, **kwargs)


class Tour(models.Model):
    id = models.CharField(primary_key=True, max_length=40, default=new_id, editable=False)
    slug = models.SlugField(max_length=120, unique=True)
    name = models.CharField(max_length=200)
    image_url = models.URLField(max_length=500, blank=True)

    def __str__(self):
        return self.name


class Event(models.Model):
    DRAFT, ACTIVE, SOLD_OUT, POSTPONED, CANCELLED = 'DRAFT', 'ACTIVE', 'SOLD_OUT', 'POSTPONED', 'CANCELLED'
    STATUS_CHOICES = [(s, s.replace('_', ' ').title()) for s in (DRAFT, ACTIVE, SOLD_OUT, POSTPONED, CANCELLED)]
    VISIBILITY_CHOICES = [('PUBLIC', 'Public'), ('UNLISTED', 'Unlisted'), ('MEMBERS', 'Members only')]
    TICKETING_CHOICES = [('INTERNAL', 'Sold here'), ('EXTERNAL', 'External link')]

    id = models.CharField(primary_key=True, max_length=40, default=new_id, editable=False)
    slug = models.SlugField(max_length=160, unique=True)
    name = models.CharField(max_length=200)
    date = models.DateTimeField(help_text='Show day. Imported rows are midnight in Cancun.')
    doors_open = models.CharField(max_length=10, blank=True, help_text='24h clock, e.g. 19:30')
    show_time = models.CharField(max_length=10, blank=True, help_text='24h clock, e.g. 20:00')
    end_time = models.CharField(max_length=10, blank=True)
    description = models.TextField(blank=True)
    long_description = models.TextField(blank=True)
    image_url = models.URLField(max_length=500, blank=True)
    image_url_mobile = models.URLField(max_length=500, blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=DRAFT)
    visibility = models.CharField(max_length=10, choices=VISIBILITY_CHOICES, default='PUBLIC')
    ticketing_type = models.CharField(max_length=10, choices=TICKETING_CHOICES, default='INTERNAL')
    external_ticket_url = models.URLField(max_length=500, blank=True)
    currency = models.CharField(max_length=3, default='usd')
    language = models.CharField(max_length=5, default='en')
    age_restriction = models.CharField(max_length=40, blank=True)
    tags = models.JSONField(default=list, blank=True)
    reviews = models.JSONField(default=list, blank=True, help_text='[{"quote": "", "stars": 5, "source": ""}]')
    venue = models.ForeignKey(Venue, null=True, blank=True, on_delete=models.SET_NULL, related_name='events')
    venue_label = models.CharField(max_length=200, blank=True, help_text='Venue name as exported, when no Venue row matched.')
    tour = models.ForeignKey(Tour, null=True, blank=True, on_delete=models.SET_NULL, related_name='events')
    members_eligible = models.BooleanField(default=True, help_text='Member free tickets / guest discount apply.')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['date']

    def __str__(self):
        return f'{self.name} ({self.date:%Y-%m-%d})'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:160] or new_id()
        super().save(*args, **kwargs)

    @property
    def is_public(self):
        return self.status != self.DRAFT and self.visibility != 'UNLISTED'


class LineupEntry(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='lineup')
    artist = models.ForeignKey(Artist, on_delete=models.CASCADE, related_name='lineup_entries')
    role = models.CharField(max_length=60, blank=True)
    headliner = models.BooleanField(default=False)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'id']
        unique_together = [('event', 'artist')]


class TicketType(models.Model):
    MEMBER_ACCESS_CHOICES = [('ALL', 'Everyone'), ('MEMBERS_ONLY', 'Members only'), ('NON_MEMBERS', 'Non-members only')]

    id = models.CharField(primary_key=True, max_length=40, default=new_id, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='ticket_types')
    name = models.CharField(max_length=120)
    description = models.CharField(max_length=300, blank=True)
    price_cents = models.PositiveIntegerField()
    member_price_cents = models.PositiveIntegerField(null=True, blank=True)
    member_access = models.CharField(max_length=14, choices=MEMBER_ACCESS_CHOICES, default='ALL')
    capacity = models.PositiveIntegerField(null=True, blank=True, help_text='Blank = unlimited')
    active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'price_cents']

    def __str__(self):
        return f'{self.event.name}: {self.name}'


class SiteFile(models.Model):
    id = models.CharField(primary_key=True, max_length=40, default=new_id, editable=False)
    name = models.CharField(max_length=255, help_text='Brand stems such as site-hero-video are matched by the site.')
    file = models.FileField(upload_to='files/%Y/%m/')
    content_type = models.CharField(max_length=100, blank=True)
    public = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class StoreCollection(models.Model):
    id = models.CharField(primary_key=True, max_length=40, default=new_id, editable=False)
    slug = models.SlugField(max_length=120, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    image_url = models.URLField(max_length=500, blank=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name


class StoreProduct(models.Model):
    id = models.CharField(primary_key=True, max_length=40, default=new_id, editable=False)
    slug = models.SlugField(max_length=160, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    currency = models.CharField(max_length=3, default='usd')
    collections = models.ManyToManyField(StoreCollection, blank=True, related_name='products')
    external_url = models.URLField(max_length=500, blank=True, help_text='Where "Buy" sends people until on-site merch checkout exists.')
    active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name


class StoreProductImage(models.Model):
    product = models.ForeignKey(StoreProduct, on_delete=models.CASCADE, related_name='images')
    url = models.URLField(max_length=500)
    alt = models.CharField(max_length=200, blank=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'id']


class StoreVariant(models.Model):
    id = models.CharField(primary_key=True, max_length=40, default=new_id, editable=False)
    product = models.ForeignKey(StoreProduct, on_delete=models.CASCADE, related_name='variants')
    name = models.CharField(max_length=120, default='Default')
    sku = models.CharField(max_length=80, blank=True)
    price_cents = models.PositiveIntegerField()
    compare_at_cents = models.PositiveIntegerField(null=True, blank=True)
    available_quantity = models.PositiveIntegerField(null=True, blank=True, help_text='Blank = unlimited')
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'price_cents']


class FormEndpoint(models.Model):
    INTENTS = [(i, i) for i in ('show_request', 'contact', 'newsletter', 'external_lead', 'custom')]

    slug = models.SlugField(max_length=80, unique=True)
    intent = models.CharField(max_length=20, choices=INTENTS, default='contact')
    title = models.CharField(max_length=200, blank=True)
    success_message = models.CharField(max_length=300, blank=True, default='Thanks! We will be in touch soon.')
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.slug


class FormSubmission(models.Model):
    endpoint = models.ForeignKey(FormEndpoint, on_delete=models.PROTECT, related_name='submissions')
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)
    fields = models.JSONField(default=dict, blank=True)
    context = models.JSONField(default=dict, blank=True)
    visitor_key = models.CharField(max_length=100, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    handled = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.endpoint.slug}: {self.email}'
