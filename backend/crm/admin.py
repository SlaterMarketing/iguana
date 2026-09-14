from django.contrib import admin

from .models import Campaign, CampaignRecipient, Contact, ContactList, ContactListMember, InboxConversation, InboxMessage, TrackedEvent


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('email', 'first_name', 'last_name', 'phone', 'subscribed', 'source', 'cities', 'created_at')
    list_filter = ('subscribed', 'source', 'cities')
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
