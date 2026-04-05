from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Notification
from .serializers import NotificationSerializer
from django.utils import timezone
from datetime import timedelta
from orders.models import Order  # 🔥 Order model import karen, kyunki partner notifications ke liye zaroori hai

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_notifications(request):
    # Logged-in user ki notifications fetch karke date ke hisab se descending order mein lagayen
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    serializer = NotificationSerializer(notifications, many=True)
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_notification_count(request):
    # Sirf login user ki unread notifications count karein
    count = Notification.objects.filter(user=request.user, is_read=False).count()
    return Response({'unread_count': count})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_notifications_as_read(request):
    # Jab user notification screen khol le, tab sabko read mark kar dein
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return Response({'message': 'All marked as read'})


# notification/views.py
# Partner ke liye special view
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_partner_notifications(request):
    if request.user.role != "partner":
        return Response({"error": "Unauthorized"}, status=403)

    # 1. Purani notifications jo DB mein save hain
    notifications = Notification.objects.filter(user=request.user).order_by('-id')
    
    # 2. 🔥 Deadline Logic (Next 2 hours)
    # Check karein koi aisa order hai jiski delivery 2 ghante mein hai
    reminder_time = timezone.now() + timedelta(hours=2)
    
    upcoming_orders = Order.objects.filter(
        partner=request.user,
        status="accepted",
        deadline__lte=reminder_time,
        deadline__gt=timezone.now()
    )
    
    data = []
    
    # Pehle "Deadline Alert" ko top par rakhein (Dynamic)
    for order in upcoming_orders:
        data.append({
            "id": 999 + order.id, # Unique temp ID
            "title": "Deadline Alert! ⏰",
            "message": f"Order #{order.id} ki delivery ke liye sirf 2 ghante bache hain!",
            "icon_type": "timer", # UI mein alag icon dikhane ke liye
            "created_at": timezone.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "is_read": False
        })
        
    # Phir baaki saari notifications add karein
    serializer = NotificationSerializer(notifications, many=True)
    data.extend(serializer.data)
        
    return Response(data)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def clear_all_notifications(request):
    Notification.objects.filter(user=request.user).delete()
    return Response({"message": "All notifications cleared"}, status=200)