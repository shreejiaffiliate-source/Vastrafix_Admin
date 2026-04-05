from django.conf import settings
from django.urls import include, path

from accounts import views
from .views import BannerListView, CategoryListView, ItemListView, RaiseComplaintView, service_items, submit_complaint
from django.conf.urls.static import static

urlpatterns = [
    path('category/', CategoryListView.as_view(), name='category-list'),
    path('subcategories/', service_items, name='service-items'),
    path('items/', ItemListView.as_view(), name='item-list'),
    path('chaining/', include('smart_selects.urls')),
    path('complaint/', RaiseComplaintView.as_view(), name='raise-complaint'),# 🔥 REQUIRED
    path('banners/', BannerListView.as_view()),

    path('complaint/submit-complaint/',submit_complaint, name='submit_complaint'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
