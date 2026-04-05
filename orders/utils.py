import threading
import time
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count



# orders/utils.py mein ye naya logic add karein

# orders/utils.py

def check_pickup_reminders():
    from orders.models import Order
    from vastrafix.core.firebase import send_push
    from notification.models import Notification as AppNotification
    from accounts.models import User

    now = timezone.now()
    
    # Do alag windows: 1 Ghanta aur 30 Minute
    check_windows = [
        (now + timedelta(minutes=30), "30 MINS", "half_hour"),
        (now + timedelta(hours=1), "1 HOUR", "one_hour"),
    ]

    for limit_time, label, suffix in check_windows:
        # 🔥 Step 1: Sirf 'accepted' orders uthao jinka pickup time is window mein hai
        # Group by 'partner' taaki har partner ka count alag mile
        upcoming_pickups = Order.objects.filter(
            status='accepted',
            pickup_datetime__lte=limit_time,
            pickup_datetime__gt=now,
            partner__isnull=False
        ).values('partner').annotate(total_orders=Count('id'))

        for entry in upcoming_pickups:
            partner_id = entry['partner']
            order_count = entry['total_orders']
            
            # Partner ka data fetch karo
            try:
                partner = User.objects.get(id=partner_id)
            except User.DoesNotExist:
                continue

            # 🔥 Step 2: Unique ID check taaki double notification na jaye
            # Format: pickup_partnerID_YYYYMMDDHH_suffix
            # example: pickup_5_2026031317_half_hour
            unique_key = f"pickup_{partner.id}_{now.strftime('%Y%m%d%H')}_{suffix}"
            
            already_sent = AppNotification.objects.filter(
                user=partner,
                message__contains=f"REF:{unique_key}"
            ).exists()

            # 🔥 Step 3: Agar pehle nahi bheja aur partner ka token hai
            if not already_sent and partner.fcm_token:
                title = f"Pickup Alert ({label})! 🧺"
                body = f"Bhai, agle {label} mein aapko {order_count} orders pickup karne jaana hai!"
                
                # 1. Mobile Push Notification (Bahar ke liye)
                send_push(
                    token=partner.fcm_token,
                    title=title,
                    body=body,
                    data={
                        "type": "pickup_reminder",
                        "click_action": "FLUTTER_NOTIFICATION_CLICK"
                    }
                )

                # 2. Database Entry (Bell icon screen ke liye)
                AppNotification.objects.create(
                    user=partner,
                    title=title,
                    message=f"{body} REF:{unique_key}",
                    icon_type="pickup"
                )
                print(f"✅ {label} Reminder sent to {partner.username} (Orders: {order_count})")

def start_deadline_checker():
    def check_loop():
        # Imports function ke andar rakhe hain taaki "AppRegistryNotReady" error na aaye
        from orders.models import Order
        from vastrafix.core.firebase import send_push
        from notification.models import Notification as AppNotification

        print("🚀 Deadline Background Checker Started...")

        while True:
            try:
                now = timezone.now()
                # Window: Agle 2 ghante mein expire hone wale orders
                reminder_limit = now + timedelta(hours=2)

                upcoming_orders = Order.objects.filter(
                    status="accepted",
                    deadline__lte=reminder_limit,
                    deadline__gt=now,
                    partner__isnull=False
                )

                for order in upcoming_orders:
                    partner = order.partner
                    
                    # Check karo kya is order ke liye pehle hi "Deadline Alert" bhej diya hai?
                    already_sent = AppNotification.objects.filter(
                        user=partner, 
                        message__contains=f"#{order.id}",
                        title="Deadline Alert! ⏰"
                    ).exists()

                    if not already_sent and partner.fcm_token:
                        # 1. Bahar ka Push Notification
                        send_push(
                            token=partner.fcm_token,
                            title="Deadline Alert ⏰",
                            body=f"Only 2 hours left for Order #{order.id} delivery!",
                            data={"type": "deadline_alert", "order_id": str(order.id)}
                        )
                        # 2. App ke andar Bell Icon ke liye
                        AppNotification.objects.create(
                            user=partner,
                            title="Deadline Alert! ⏰",
                            message=f"Only 2 hours remaining for the delivery of Order #{order.id}!",
                            icon_type="timer"
                        )
                        print(f"🔔 Notification Sent: Order {order.id}")
                        
                        # Naya Pickup Logic call karo
                check_pickup_reminders()

            except Exception as e:
                print(f"❌ Checker Error: {e}")

            # Har 60 seconds mein ek baar check karega
            time.sleep(60)

    # Thread ko start karo
    thread = threading.Thread(target=check_loop, daemon=True)
    thread.start()