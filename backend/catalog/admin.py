from django.contrib import admin
from django.utils.html import format_html

from .models import (Artist, Event, FormEndpoint, FormSubmission, LineupEntry, SiteFile, StoreCollection, StoreProduct,
                     StoreProductImage, StoreVariant, TicketType, Tour, Venue)


def thumb(url):
    return format_html('<img src="{}" style="height:40px;border-radius:6px">', url) if url else ''


@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    list_display = ('name', 'city', 'country', 'capacity', 'listed')
    list_filter = ('city', 'listed')
    search_fields = ('name', 'city', 'address')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Artist)
class ArtistAdmin(admin.ModelAdmin):
    list_display = ('photo', 'name', 'home_city', 'listed', 'sort_order')
    list_display_links = ('photo', 'name')
    list_editable = ('listed', 'sort_order')
    search_fields = ('name', 'stage_name', 'home_city')
    prepopulated_fields = {'slug': ('name',)}

    @admin.display(description='')
    def photo(self, obj):
        return thumb(obj.image_url)


class TicketTypeInline(admin.TabularInline):
    model = TicketType
    extra = 0
    fields = ('name', 'description', 'price_cents', 'member_price_cents', 'member_access', 'capacity', 'max_per_order',
              'pay_at_door', 'active', 'sort_order')


class LineupInline(admin.TabularInline):
    model = LineupEntry
    extra = 0
    autocomplete_fields = ('artist',)


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('poster', 'name', 'date', 'venue_name', 'status', 'visibility', 'ticketing_type')
    list_display_links = ('poster', 'name')
    list_filter = ('status', 'visibility', 'ticketing_type', 'venue__city')
    search_fields = ('name', 'slug', 'venue__name', 'venue_label')
    date_hierarchy = 'date'
    prepopulated_fields = {'slug': ('name',)}
    autocomplete_fields = ('venue',)
    inlines = [TicketTypeInline, LineupInline]
    fieldsets = (
        (None, {'fields': ('name', 'slug', 'status', 'visibility', 'date', 'doors_open', 'show_time', 'end_time', 'venue', 'venue_label')}),
        ('Listing', {'fields': ('description', 'long_description', 'image_url', 'image_url_mobile', 'language', 'age_restriction', 'tags', 'reviews', 'tour')}),
        ('Ticketing', {'fields': ('ticketing_type', 'external_ticket_url', 'currency', 'members_eligible')}),
    )

    @admin.display(description='')
    def poster(self, obj):
        return thumb(obj.image_url)

    @admin.display(description='Venue')
    def venue_name(self, obj):
        return obj.venue.name if obj.venue else obj.venue_label


admin.site.register(Tour)


@admin.register(SiteFile)
class SiteFileAdmin(admin.ModelAdmin):
    list_display = ('name', 'content_type', 'public', 'created_at')


class StoreImageInline(admin.TabularInline):
    model = StoreProductImage
    extra = 0


class StoreVariantInline(admin.TabularInline):
    model = StoreVariant
    extra = 0


@admin.register(StoreProduct)
class StoreProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'currency', 'active', 'sort_order')
    list_editable = ('active', 'sort_order')
    prepopulated_fields = {'slug': ('name',)}
    filter_horizontal = ('collections',)
    inlines = [StoreVariantInline, StoreImageInline]


@admin.register(StoreCollection)
class StoreCollectionAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'sort_order')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(FormEndpoint)
class FormEndpointAdmin(admin.ModelAdmin):
    list_display = ('slug', 'intent', 'title', 'active')


@admin.register(FormSubmission)
class FormSubmissionAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'endpoint', 'email', 'phone', 'handled')
    list_filter = ('endpoint', 'handled')
    list_editable = ('handled',)
    search_fields = ('email', 'phone')
    readonly_fields = ('endpoint', 'email', 'phone', 'fields', 'context', 'visitor_key', 'ip', 'created_at')
