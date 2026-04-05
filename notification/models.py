from django.db import models
from django.contrib.auth.models import User # Ya jo bhi custom User model aap use kar rahe hain
from django.conf import settings

class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    icon_type = models.CharField(max_length=50, default='delivery') # jaise: 'delivery', 'offer', 'check'
    is_read = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        # Yahan self.user.username ki jagah self.user.email bhi ho sakta hai agar aapka custom model waise set hai
        return f"Notification for {self.user} - {self.title}"