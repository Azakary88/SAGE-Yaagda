from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', RedirectView.as_view(pattern_name='login', permanent=False), name='login_alias'),
    path('', include('dashboard.urls')),
    path('ecoles/', include('schools.urls')),
    path('innovations/', include('innovations.urls')),
    path('comptes/', include('django.contrib.auth.urls')),
    path('comptes/', include('accounts.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
