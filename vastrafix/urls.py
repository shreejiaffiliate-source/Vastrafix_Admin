from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('apipayments/', include('payments.urls')),
    path('api/orders/', include('orders.urls')),
    path('api/services/', include('services.urls')),
    path('api/accounts/', include('accounts.url')),
    path('chaining/', include('smart_selects.urls')),  # 🔥 REQUIRED
    path("admin/", admin.site.urls),
    path('api/notification/', include('notification.urls')),
    path('dashboard/', include('dashboard.urls')),  # Dashboard app ke URLs
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
