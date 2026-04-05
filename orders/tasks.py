# orders/tasks.py
import threading

from celery import shared_task
from datetime import datetime, time, timedelta
from django.utils import timezone
from vastrafix.core.firebase import send_push
from .models import Order
from firebase_admin.messaging import Message, Notification, send
from notification.models import Notification as AppNotification

# -------------------------------------------------------------------------
# 1. PERIODIC TASK (CELERY BEAT)
# Ye function background mein har 5-10 minute mein khud chalega (Scanning logic)
# -------------------------------------------------------------------------
@shared_task
def send_delivery_reminder_notifications():
    # 🔥 Window: Ab se lekar agle 2 ghante tak jo bhi order expire hone wale hain
    now = timezone.now()
    reminder_limit = timezone.now() + timedelta(hours=2)
    
    # Filter: Jo orders accepted hain aur jinka deadline 2 hour ke andar hai
    upcoming_orders = Order.objects.filter(
        status="accepted",
        deadline__lte=reminder_limit,
        deadline__gt=timezone.now(), # Expired ko ignore karo
        partner__isnull=False 
    ).select_related('partner')
    
    # Notification model ko function ke andar import karo crash se bachne ke liye
    from notification.models import Notification as AppNotification

    for order in upcoming_orders:
        partner = order.partner 
        
        # 🚨 Logic: Check karo kya humne is Order #ID ke liye pehle hi "Deadline Alert" bheja hai?
        already_sent = AppNotification.objects.filter(
            user=partner, 
            message__contains=f"#{order.id}",
            title="Deadline Alert! ⏰"
        ).exists()

        if not already_sent and partner.fcm_token:
            # 1. Mobile Push (App ke bahar ke liye)
            send_push(
                token=partner.fcm_token,
                title="Deadline Alert ⏰",
                body=f"Less than 2 hours remaining for Order #{order.id}!",
                data={
                    "type": "deadline_alert", 
                    "order_id": str(order.id),
                    "title": "Deadline Alert ⏰",
                    "body": f"Less than 2 hours remaining for Order #{order.id}!"
                },
                channel='deadline_alerts'
            )
            # 2. Database Entry (App ke andar bell icon ke liye)
            AppNotification.objects.create(
                user=partner,
                title="Deadline Alert! ⏰",
                message=f"You have less than 2 hours to deliver Order #{order.id}!",
                icon_type="timer"
            )
            print(f"✅ Notification sent to {partner.username} for Order {order.id}")
# -------------------------------------------------------------------------
# 2. REAL-TIME THREADING TASK
# Ye function tab chalta hai jab partner order 'Accept' karta hai. 
# Ye thread ko 'Sleep' par rakh kar theek deadline se 2 ghante pehle jagta hai.
# -------------------------------------------------------------------------
import time 
def send_deadline_push(order_id):
    """
    Background thread jo sirf us Partner ke liye chalti hai jisne order accept kiya ho.
    """
    def run_timer():
        try:
            # 1. Fresh data fetch karein
            order = Order.objects.get(id=order_id)
            partner = order.partner

            if not partner or not partner.fcm_token:
                print(f"❌ Partner or Token missing for Order {order_id}")
                return

            # 2. Calculation: Deadline se theek 2 ghante pehle jagna hai
            notification_time = order.deadline - timedelta(hours=2)
            wait_seconds = (notification_time - timezone.now()).total_seconds()

            # 3. Agar abhi time baki hai (2 ghante se zyada), toh Thread ko sula do
            if wait_seconds > 0:
                print(f"⏳ Thread Sleeping: Order {order.id} ke liye {wait_seconds/60:.1f} min wait...")
                time.sleep(wait_seconds)

            # 4. Jagne ke baad RE-CHECK: Kya status abhi bhi 'accepted' hai? 
            # (Ho sakta hai tab tak order deliver ho gaya ho)
            order.refresh_from_db()
            
            # Check: Kya humne is order ka notification pehle hi database mein daal diya hai?
            from notification.models import Notification as AppNotification
            already_sent = AppNotification.objects.filter(
                user=partner, 
                message__icontains=f"#{order.id}",
                title="Deadline Alert! ⏰"
            ).exists()

            if not already_sent and order.status == "accepted":
                # ✅ SIRF US PARTNER KO PUSH JAYEGA
                send_push(
                    token=partner.fcm_token,
                    title="Deadline Alert ⏰",
                    body=f"Only 2 hours left for Order #{order.id} delivery!",
                    data={
                        "type": "deadline_alert",
                        "order_id": str(order.id),
                    },
                    channel='deadline_alerts'
                )
                
                # ✅ USI PARTNER KE APP MEIN ENTRY HOGI
                AppNotification.objects.create(
                    user=partner,
                    title="Deadline Alert! ⏰",
                    message=f"Only 2 hours remaining for the delivery of Order #{order.id}!",
                    icon_type="timer"
                )
                print(f"✅ Target Notification sent to {partner.username} for Order {order.id}")
            else:
                print(f"⏭️ Notification skipped for Order {order.id} (Already sent or status changed)")

        except Exception as e:
            print(f"❌ Deadline Thread Error: {e}")

    # 🔥 Thread start karein background mein
    threading.Thread(target=run_timer).start()