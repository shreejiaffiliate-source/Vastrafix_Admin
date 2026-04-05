from .models import Notification

def create_notification(user, title, message, icon_type="default"):
    Notification.objects.create(
        user=user,
        title=title,
        message=message,
        icon_type=icon_type
        
    )