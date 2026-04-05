from django.urls import path
from . import views

urlpatterns = [
    path('partner/', views.get_partner_notifications, name='partner-notifications'),
    # 🔥 FIX: Partner ke liye specific count path
    path('partner/count/', views.get_notification_count, name='partner-notification-count'),
    
    path('', views.get_user_notifications, name='get_notifications'),
    path('count/', views.get_notification_count, name='notification-count'),
    path('read-all/', views.mark_notifications_as_read, name='read-all'),
    path('clear-all/', views.clear_all_notifications, name='clear-all-notifications'),  # Naya endpoint for clearing notifications
]