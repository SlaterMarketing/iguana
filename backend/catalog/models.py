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
    image_url = models.CharField(max_length=500, blank=True, help_text='Absolute URL or /media/... path')
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
    image_url = models.CharField(max_length=500, blank=True, help_text='Absolute URL or /media/... path')
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
    image_url = models.CharField(max_length=500, blank=True, help_text='Absolute URL or /media/... path')

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
    name_es = models.CharField(max_length=200, blank=True, help_text='Spanish name; blank falls back to the name.')
    date = models.DateTimeField(help_text='Show day. Imported rows are midnight in Cancun.')
    doors_open = models.CharField(max_length=10, blank=True, help_text='24h clock, e.g. 19:30')
    show_time = models.CharField(max_length=10, blank=True, help_text='24h clock, e.g. 20:00')
    end_time = models.CharField(max_length=10, blank=True)
    description = models.TextField(blank=True)
    description_es = models.TextField(blank=True, help_text='Spanish description; blank falls back.')
    long_description = models.TextField(blank=True)
    long_description_es = models.TextField(blank=True, help_text='Spanish long description; blank falls back.')
    image_url = models.CharField(max_length=500, blank=True, help_text='Absolute URL or /media/... path')
    image_url_mobile = models.CharField(max_length=500, blank=True, help_text='Absolute URL or /media/... path')
    # Posters whose artwork carries Spanish text; blank falls back to the ones above.
    image_url_es = models.CharField(max_length=500, blank=True, help_text='Spanish poster; blank falls back.')
    image_url_mobile_es = models.CharField(max_length=500, blank=True, help_text='Spanish mobile poster.')
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=DRAFT)
    visibility = models.CharField(max_length=10, choices=VISIBILITY_CHOICES, default='PUBLIC')
    ticketing_type = models.CharField(max_length=10, choices=TICKETING_CHOICES, default='INTERNAL')
    external_ticket_url = models.CharField(max_length=500, blank=True, help_text='Absolute URL or /media/... path')
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

    def _localized(self, lang, spanish, english):
        return spanish if lang == 'es' and spanish else english

    def label(self, lang):
        return self._localized(lang, self.name_es, self.name)

    def details(self, lang):
        return self._localized(lang, self.description_es, self.description)

    def long_details(self, lang):
        return self._localized(lang, self.long_description_es, self.long_description)

    def poster(self, lang):
        return self._localized(lang, self.image_url_es, self.image_url)

    def poster_mobile(self, lang):
        return self._localized(lang, self.image_url_mobile_es, self.image_url_mobile)


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
    name_es = models.CharField(max_length=120, blank=True, help_text='Spanish name; blank falls back to the name.')
    description = models.CharField(max_length=300, blank=True)
    description_es = models.CharField(max_length=300, blank=True, help_text='Spanish description; blank falls back.')
    price_cents = models.PositiveIntegerField()
    member_price_cents = models.PositiveIntegerField(null=True, blank=True)
    member_access = models.CharField(max_length=14, choices=MEMBER_ACCESS_CHOICES, default='ALL')
    capacity = models.PositiveIntegerField(null=True, blank=True, help_text='Blank = unlimited')
    max_per_order = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Blank = 20')
    pay_at_door = models.BooleanField(
        default=False, help_text='Reserve online, pay at the door. No online payment is taken for this type.')
    active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'price_cents']

    def __str__(self):
        return f'{self.event.name}: {self.name}'

    def label(self, lang):
        return self.name_es if lang == 'es' and self.name_es else self.name

    def details(self, lang):
        return self.description_es if lang == 'es' and self.description_es else self.description


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
    image_url = models.CharField(max_length=500, blank=True, help_text='Absolute URL or /media/... path')
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
    url = models.CharField(max_length=500, help_text='Absolute URL or /media/... path')
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
