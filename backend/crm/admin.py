import mimetypes
import os

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.urls import path, reverse
from django.utils.html import format_html

from .models import (Campaign, CampaignRecipient, ComicFile, ComicSubmission, Contact, ContactList, ContactListMember,
                     InboxConversation, InboxMessage, TrackedEvent)


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('email', 'first_name', 'last_name', 'source', 'locale', 'geo_country', 'geo_city', 'time_zone', 'created_at')
    list_filter = ('subscribed', 'source', 'locale', 'geo_country', 'lists')
    search_fields = ('email', 'first_name', 'last_name', 'phone')
    readonly_fields = ('stripe_customer_id', 'stripe_card_brand', 'stripe_card_last4', 'created_at', 'updated_at')


class ListMemberInline(admin.TabularInline):
    model = ContactListMember
    extra = 0
    raw_id_fields = ('contact',)


@admin.register(ContactList)
class ContactListAdmin(admin.ModelAdmin):
    list_display = ('name', 'member_count', 'created_at')
    inlines = [ListMemberInline]

    def member_count(self, obj):
        return obj.contactlistmember_set.count()


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'created_at')


@admin.register(CampaignRecipient)
class CampaignRecipientAdmin(admin.ModelAdmin):
    list_display = ('email', 'campaign', 'status', 'sent_at', 'opened_at', 'bounced_at')
    list_filter = ('campaign', 'status')
    search_fields = ('email',)
    raw_id_fields = ('contact',)


class MessageInline(admin.TabularInline):
    model = InboxMessage
    extra = 0
    fields = ('sent_at', 'direction', 'sender_name', 'content_type', 'content')
    readonly_fields = fields


@admin.register(InboxConversation)
class InboxConversationAdmin(admin.ModelAdmin):
    list_display = ('last_message_at', 'channel_type', 'platform', 'participant_name', 'subject', 'status', 'unread_count')
    list_filter = ('channel_type', 'platform', 'status')
    search_fields = ('participant_name', 'participant_username', 'subject', 'contact__email')
    raw_id_fields = ('contact',)
    inlines = [MessageInline]


@admin.register(TrackedEvent)
class TrackedEventAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'kind', 'name', 'url')
    list_filter = ('kind', 'name')


# Browsers draw these inline; anything else (HEIC, video) downloads.
PREVIEWABLE = ('.jpg', '.jpeg', '.png', '.webp')


class ComicFileInline(admin.TabularInline):
    model = ComicFile
    extra = 0
    can_delete = False
    fields = ('kind', 'preview', 'original_name', 'size_mb', 'duration', 'download')
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    def _url(self, obj, inline=False):
        url = reverse('admin:crm_comicsubmission_file', args=[obj.submission_id, obj.pk])
        return url + ('?inline=1' if inline else '')

    @admin.display(description='Preview')
    def preview(self, obj):
        if os.path.splitext(obj.stored_name)[1].lower() not in PREVIEWABLE:
            return ''
        return format_html('<a href="{0}" target="_blank"><img src="{0}" alt="" style="max-height:120px;max-width:160px"></a>',
                           self._url(obj, inline=True))

    @admin.display(description='Size')
    def size_mb(self, obj):
        return f'{obj.size / 1024 / 1024:.1f} MB'

    @admin.display(description='Length')
    def duration(self, obj):
        if obj.duration_seconds is None:
            return ''
        return f'{int(obj.duration_seconds // 60)}:{int(obj.duration_seconds % 60):02d}'

    @admin.display(description='File')
    def download(self, obj):
        return format_html('<a href="{}">Download</a>', self._url(obj))


@admin.register(ComicSubmission)
class ComicSubmissionAdmin(admin.ModelAdmin):
    """Comedians from iguanacomedy.com/comic. Photos and clips are served only through this admin (staff login)."""

    list_display = ('created_at', 'who', 'email', 'home_city', 'dates', 'file_count', 'status')
    list_filter = ('status', 'lang')
    search_fields = ('name', 'stage_name', 'email', 'instagram', 'tiktok', 'home_city', 'show_name')
    list_editable = ('status',)
    inlines = [ComicFileInline]
    fieldsets = (
        (None, {'fields': ('status', 'staff_notes', 'operator_command')}),
        ('The comedian', {'fields': ('name', 'stage_name', 'email', 'phone', 'instagram', 'tiktok', 'links',
                                      'home_city', 'languages', 'bio')}),
        ('The show they want', {'fields': ('dates', 'availability', 'show_name', 'draw', 'ticket_price', 'guests',
                                            'notes')}),
        ('Record', {'fields': ('created_at', 'lang', 'consent_at', 'ip', 'user_agent', 'folder_path')}),
    )
    readonly_fields = ('name', 'stage_name', 'email', 'phone', 'instagram', 'tiktok', 'links', 'home_city',
                       'languages', 'bio', 'dates', 'availability', 'show_name', 'draw', 'ticket_price', 'guests',
                       'notes', 'created_at', 'lang', 'consent_at', 'ip', 'user_agent', 'folder_path',
                       'operator_command')

    def has_add_permission(self, request):
        return False  # they come from the form, with files, or not at all

    @admin.display(description='Comedian')
    def who(self, obj):
        return obj.display_name

    @admin.display(description='Requested dates')
    def dates(self, obj):
        return ', '.join(obj.requested_dates)

    @admin.display(description='Files')
    def file_count(self, obj):
        files = list(obj.files.all())
        clips = sum(1 for f in files if f.is_clip)
        return f'{len(files) - clips} photo(s), {clips} clip(s)'

    @admin.display(description='On the server')
    def folder_path(self, obj):
        return obj.folder()

    @admin.display(description='Make an event from it')
    def operator_command(self, obj):
        return format_html('<code>manage.py comic_submission {}</code>', obj.pk)

    def get_urls(self):
        return [path('<str:submission_id>/file/<int:file_id>/', self.admin_site.admin_view(self.serve_file),
                     name='crm_comicsubmission_file')] + super().get_urls()

    def serve_file(self, request, submission_id, file_id):
        if not self.has_view_permission(request):
            raise PermissionDenied
        item = get_object_or_404(ComicFile, pk=file_id, submission_id=submission_id)
        if not os.path.isfile(item.path):
            raise Http404('That file is no longer on the server.')
        inline = bool(request.GET.get('inline')) and os.path.splitext(item.stored_name)[1].lower() in PREVIEWABLE
        content_type = mimetypes.guess_type(item.stored_name)[0] or 'application/octet-stream'
        response = FileResponse(open(item.path, 'rb'), as_attachment=not inline,
                                filename=item.original_name or item.stored_name, content_type=content_type)
        response['X-Content-Type-Options'] = 'nosniff'
        return response
