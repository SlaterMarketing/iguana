from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = 'Iguana Comedy'
admin.site.site_title = 'Iguana Comedy admin'
admin.site.index_title = 'Shows, fans and sales'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('api.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
