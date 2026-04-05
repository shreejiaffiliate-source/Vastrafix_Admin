from django.contrib import admin
from .models import Notification

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    # Admin panel ki table mein kon-kon se columns dikhne chahiye
    list_display = ('id', 'user', 'title', 'icon_type', 'is_read', 'created_at')
    
    # Right side mein filter karne ke options (jaise sirf unread dekhna ho)
    list_filter = ('is_read', 'icon_type', 'created_at')
    
    # Search box jisse aap kisi specific user ya title ki notification dhund sakein
    search_fields = ('user__username', 'user__email', 'title', 'message')
    
    # Default sorting (sabse nayi notification sabse upar dikhegi)
    ordering = ('-created_at',)