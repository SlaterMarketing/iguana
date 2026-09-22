from django.urls import path, re_path

from . import embed_views, fan_views, menu_views, public_views

urlpatterns = [
    # Public catalogue (@kintana/sdk KintanaClient)
    path('api/public/v1/events', public_views.events),
    path('api/public/v1/events/<str:key>', public_views.event_detail),
    path('api/public/v1/artists', public_views.artists),
    path('api/public/v1/artists/<str:key>', public_views.artist_detail),
    path('api/public/v1/venues', public_views.venues),
    path('api/public/v1/venues/<str:key>', public_views.venue_detail),
    path('api/public/v1/endpoints', public_views.endpoints),
    path('api/public/v1/endpoints/<str:slug>/submit', public_views.endpoint_submit),
    path('api/public/v1/forms', public_views.forms),
    path('api/public/v1/files', public_views.files),
    path('api/public/v1/store/products', public_views.store_products),
    path('api/public/v1/store/products/<str:key>', public_views.store_product_detail),
    path('api/public/v1/store/collections', public_views.store_collections),
    path('api/public/v1/store/collections/<str:key>', public_views.store_collection_detail),
    # The bar menu, and a round ordered from a table. One path for both languages, because a printed QR can
    # never be re-printed with a different URL: the page picks its own language.
    path('api/public/v1/menu', menu_views.menu),
    path('api/public/v1/table-orders', menu_views.table_order),
    path('api/public/v1/site', public_views.site),
    path('api/public/v1/site/manifest', public_views.site_manifest),
    # Fans
    path('api/fan/v1/config', fan_views.config),
    path('api/fan/v1/auth/request', fan_views.auth_request),
    path('api/fan/v1/auth/verify', fan_views.auth_verify),
    path('api/fan/v1/account/profile', fan_views.account_profile),
    path('api/fan/v1/events', fan_views.fan_events),
    path('api/fan/v1/events/<str:slug>', fan_views.fan_event_detail),
    path('api/fan/v1/tickets', fan_views.tickets),
    path('api/fan/v1/tickets/<str:order_id>', fan_views.ticket_detail),
    path('api/fan/v1/membership/plans', fan_views.membership_plans),
    path('api/fan/v1/membership/status', fan_views.membership_status),
    path('api/fan/v1/membership/redeem-code', fan_views.redeem_code),
    path('api/fan/v1/membership/credits/transfer', fan_views.credits_transfer),
    path('api/fan/v1/membership/credits/transfers', fan_views.credits_transfers),
    path('api/fan/v1/membership/subscribe', fan_views.membership_subscribe),
    path('api/fan/v1/membership/oneoff', fan_views.membership_oneoff),
    path('api/fan/v1/membership/billing-portal', fan_views.billing_portal),
    # Checkout widget, tracker, tickets
    path('_t/k.js', embed_views.tracker_js),
    path('embed/event/<str:key>', embed_views.event_checkout),
    path('unsubscribe/<str:token>', embed_views.unsubscribe),
    path('newsletter/confirm/<str:token>', embed_views.newsletter_confirm),
    path('unsubscribe/<str:token>/', embed_views.unsubscribe),
    path('api/checkout/<str:event_id>/quote', embed_views.checkout_quote),
    path('api/checkout/<str:event_id>/start', embed_views.checkout_start),
    path('api/checkout/<str:event_id>/engaged', embed_views.checkout_engaged),
    path('api/checkout/orders/<str:order_id>/confirm', embed_views.checkout_confirm),
    path('orders/<str:token>/', embed_views.order_page),
    path('checkin/<str:token>/', embed_views.checkin, name='checkin'),
    path('api/stripe/webhook', embed_views.stripe_webhook),
    re_path(r'^api/ingest/(?P<kind>pageview|event|identify)$', embed_views.ingest),
]
