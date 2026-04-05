from django.db import models
from django.conf import settings
from accounts.admin import User
from django.db import transaction
from vastrafix.core.firebase import send_push # Aapka push notification wala function
from notification.models import Notification as AppNotification # Database notification ke liye



class Payment(models.Model):

    PAYMENT_METHODS = (
        ('cash', 'Cash'),
        ('online', 'Online'),
    )

    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    )
    
    razorpay_order_id = models.CharField(max_length=100)
    razorpay_payment_id = models.CharField(max_length=100)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payments'
    )

    order = models.OneToOneField(
        'orders.Order', 
        on_delete=models.CASCADE, 
        related_name='payment',
        null=True,   # ✅ Zaroori: Taaki bina order ke save ho sake
        blank=True
    )

    amount = models.IntegerField()  # Ye paise mein store hota hai (e.g. 15500 for ₹155)

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHODS
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )

    transaction_id = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.razorpay_payment_id} - ₹{self.amount/100}"
    
    

# 1. Partner ka Wallet
class PartnerWallet(models.Model):
    partner = models.OneToOneField(User, on_delete=models.CASCADE, related_name="wallet")
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_withdrawn = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=1.00)
    updated_at = models.DateTimeField(auto_now=True)
    

    def __str__(self):
        return f"{self.partner.username} - Balance: ₹{self.balance}"

# 2. Payout Requests (Jab partner paise maangega)
class PayoutRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processed', 'Processed'),
        ('rejected', 'Rejected'),
    ]
    partner = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    upi_id = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        if self.pk:
            old_obj = PayoutRequest.objects.get(pk=self.pk)
            
            # 1. Status Pending -> Processed (Paisa bhej diya gaya)
            if old_obj.status == 'pending' and self.status == 'processed':
                with transaction.atomic():
                    wallet = PartnerWallet.objects.get(partner=self.partner)
                    if wallet.balance >= self.amount:
                        wallet.balance -= self.amount
                        wallet.total_withdrawn += self.amount
                        wallet.save()
                        
                        # 🔥 PUSH NOTIFICATION BHEJO
                        try:
                            if self.partner.fcm_token:
                                send_push(
                                    token=self.partner.fcm_token,
                                    title="Payment Processed! 💸",
                                    body=f"Amount ₹{self.amount} has been sent to your bank account."
                                )
                            
                            # Database mein bhi entry kar do taaki Notification tab mein dikhe
                            AppNotification.objects.create(
                                user=self.partner,
                                title="Payout Success ✅",
                                message=f"Your payout of ₹{self.amount} has been successfully processed.",
                                icon_type="wallet"
                            )
                        except Exception as e:
                            print(f"Notification failed: {e}")
                    else:
                        raise ValueError("Insufficient balance")

            # 2. Status Pending -> Rejected (Agar koi gadbad ho)
            elif old_obj.status == 'pending' and self.status == 'rejected':
                try:
                    if self.partner.fcm_token:
                        send_push(
                            token=self.partner.fcm_token,
                            title="Payout Rejected ❌",
                            body="Your payout request has been rejected. Please check the details."
                        )
                except: pass

        super().save(*args, **kwargs)
    
    

    def __str__(self):
        return f"{self.partner.username} - ₹{self.amount} ({self.status})" 
    
  
class PartnerBankDetail(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Verification'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    ]
    
    partner = models.OneToOneField(User, on_delete=models.CASCADE, related_name="bank_details")
    account_holder_name = models.CharField(max_length=100)
    bank_name = models.CharField(max_length=100)
    account_number = models.CharField(max_length=25)
    ifsc_code = models.CharField(max_length=15)
    upi_id = models.CharField(max_length=100, blank=True, null=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_note = models.TextField(blank=True, null=True, help_text="Reason for rejection if any")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    passbook_image = models.ImageField(upload_to='bank_proofs/', null=True, blank=True)
    
    
    def save(self, *args, **kwargs):
        if self.pk: # Agar record pehle se exist karta hai (yani update ho raha hai)
            old_obj = PartnerBankDetail.objects.get(pk=self.pk)
            
            # 1. Check karo: Status Pending -> Verified hua?
            if old_obj.status == 'pending' and self.status == 'verified':
                try:
                    # A. Push Notification bhejo
                    if self.partner.fcm_token:
                        send_push(
                            token=self.partner.fcm_token,
                            title="Bank Account Verified! ✅",
                            body="Your bank details have been verified. You can now withdraw your earnings."
                        )
                    
                    # B. App ke andar Notification list mein entry
                    AppNotification.objects.create(
                        user=self.partner,
                        title="Bank Account Verified",
                        message="Your bank details have been verified. You can now withdraw your earnings.",
                        icon_type="check"
                    )
                except Exception as e:
                    print(f"Bank verification notification failed: {e}")

            # 2. Check karo: Status Pending -> Rejected hua?
            elif old_obj.status == 'pending' and self.status == 'rejected':
                try:
                    reason = self.admin_note if self.admin_note else "Details sahi nahi hain."
                    if self.partner.fcm_token:
                        send_push(
                            token=self.partner.fcm_token,
                            title="Bank Verification Failed ❌",
                            body=f"Reason: {reason}. Please check and resubmit your details."
                        )
                except: pass

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.partner.username} - {self.status}"  
    
