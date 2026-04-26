import random
from django.core.mail import send_mail
from django.conf import settings

def send_otp_via_email(email, otp):
    # 🔥 1. SUBJECT: Isse notification mein hi App ka naam dikhega
    subject = f"{otp} is your Vastrafix verification code"
    
    # 🔥 2. MESSAGE: Body mein bhi branding honi chahiye
    message = (
        f"Hello,\n\n"
        f"Thank you for choosing Vastrafix. Your 6-digit verification code is:\n\n"
        f"👉 {otp}\n\n"
        f"This code is valid for 5 minutes. Please do not share it with anyone.\n\n"
        f"Regards,\n"
        f"Team Vastrafix"
    )
    
    # settings.py se 'Vastrafix <shreejiaffiliate@gmail.com>' uthayega
    email_from = settings.DEFAULT_FROM_EMAIL 
    recipient_list = [email]

    try:
        send_mail(
            subject, 
            message, 
            email_from, 
            recipient_list, 
            fail_silently=False
        )
        print(f"✅ Vastrafix OTP sent to {email}")
    except Exception as e:
        print(f"❌ Mail fail: {str(e)}")