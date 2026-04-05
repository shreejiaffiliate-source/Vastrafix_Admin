# orders/tasks.py
from celery import shared_task
from datetime import datetime, time, timedelta
from django.utils import timezone

from vastrafix.core.firebase import send_push
from .models import Order
from firebase_admin.messaging import Message, Notification, send

@shared_task
def send_delivery_reminder_notifications():
    # 🔥 Ab se theek 2 ghante baad ka time
    reminder_time = timezone.now() + timedelta(hours=2)
    
    # Wo orders dhundo jo 'accepted' hain aur jinka delivery time ~2 hours bacha hai
    # (Hum 5 minute ka window rakhte hain taaki miss na ho)
    upcoming_orders = Order.objects.filter(
        status="accepted",
        delivery_date__gte=reminder_time - timedelta(minutes=5),
        delivery_date__lte=reminder_time + timedelta(minutes=5)
    )

    for order in upcoming_orders:
        partner = order.partner
        if partner and partner.fcm_token: # Partner ke paas token hona chahiye
            message = Message(
                notification=Notification(
                    title="Time Running Out! ⏰",
                    body=f"Order #{order.id} ke liye sirf 2 ghante bache hain. Jaldi complete karein!",
                ),
                token=partner.fcm_token,
            )
            send(message)
            print(f"Notification sent for Order {order.id}")
            
            
def send_deadline_push(order_id):

    try:
        order = Order.objects.get(id=order_id)

        if not order.partner:
            return

        # deadline se 2 hour pehle time calculate
        seconds = (order.deadline - timezone.now()).total_seconds() - (2 * 3600)

        if seconds > 0:
            time.sleep(seconds)

        partner = order.partner

        if partner.fcm_token:
            send_push(
                token=partner.fcm_token,
                title="Deadline Alert ⏰",
                body=f"Order #{order.id} ki delivery ke liye sirf 2 ghante bache hain!"
            )

    except Exception as e:
        print("Deadline notification error:", e)            