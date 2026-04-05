# accounts/utils.py
import random
from django.core.mail import send_mail
from django.conf import settings

def send_otp_via_email(email, otp):
    subject = "Verify your Vastrafix Account"
    message = f"Your verification code is {otp}. Do not share it with anyone."
    email_from = settings.EMAIL_HOST_USER
    send_mail(subject, message, email_from, [email])