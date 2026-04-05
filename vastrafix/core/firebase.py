import firebase_admin
from firebase_admin import credentials, messaging
import os
from django.conf import settings
from accounts.models import User # User model import karna zaruri hai token cleanup ke liye

key_path = os.path.join(settings.BASE_DIR, "firebase_key.json")

if not firebase_admin._apps:
    cred = credentials.Certificate(key_path)
    firebase_admin.initialize_app(cred)


def send_push(token, title, body, channel='vastrafix_urgent_channel', data=None):
   
    message = messaging.Message(
        # Niche wali line add kardo, ye Android ko force karti hai jagane ke liye
        data={
            "title": title,
            "body": body,
            "click_action": "FLUTTER_NOTIFICATION_CLICK"
        },
        notification=messaging.Notification(
            title=title,
            body=body,
        ),

        android=messaging.AndroidConfig(
            priority='high',
            notification=messaging.AndroidNotification(
                channel_id=channel,
                sound='default',
            )
        ),
        
        token=token,
    )

    try:
        response = messaging.send(message)
        print("Successfully sent message:", response)
        return response
    except messaging.UnregisteredError:
        print("Invalid token, removing from DB")
        User.objects.filter(fcm_token=token).update(fcm_token=None)

    except Exception as e:
        print("Push failed:", e)
    
# --- 2. 🔥 NAYA: BROADCAST PUSH (Partners ke liye) ---
def send_broadcast_push(tokens, title, body, channel='partner_orders'):

    tokens = list(set(tokens))  # duplicates remove
    
    print("FINAL TOKENS:", tokens)

    for token in tokens:

        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data={
                "title": title,
                "body": body,
                "type": "new_order", # Default type
                "click_action": "FLUTTER_NOTIFICATION_CLICK",
            },
            android=messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(
                    channel_id=channel,
                    sound='default',
                )
            ),
            token=token,
        )

        try:
            response = messaging.send(message)
            print("Push sent:", response)

        except messaging.UnregisteredError:
            print("Invalid token, removing from DB")
            User.objects.filter(fcm_token=token).update(fcm_token=None)

        except Exception as e:
            print("Push failed:", e)