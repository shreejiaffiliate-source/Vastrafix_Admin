from datetime import timedelta, timezone
from django.db import models
from django.conf import settings
from accounts.models import Address, User
from services.models import Item
from django.utils import timezone
from accounts.admin import User
from django.db.models import Max # 🔥 Max number nikalne ke liye


class Order(models.Model):

    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('pickup', 'Picked Up'),
        ('processing', 'Processing'),
        ('shipping', 'Shipping'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='orders'
    )
    
    
    
    # Razorpay Payment Fields
    amount = models.DecimalField(max_digits=10, decimal_places=2)  # ✅ ADD THIS
    razorpay_order_id = models.CharField(max_length=100, null=True, blank=True)
    razorpay_payment_id = models.CharField(max_length=100, null=True, blank=True)
    razorpay_signature = models.CharField(max_length=200, null=True, blank=True)
    is_paid = models.BooleanField(default=False)
    
    # pickup date and time
    
    pickup_datetime = models.DateTimeField(null=True, blank=True)
    
    
    partner = models.ForeignKey(
         settings.AUTH_USER_MODEL,
         on_delete=models.SET_NULL,
         null=True,
         blank=True,
         related_name='assigned_orders'
)
    
    partner_order_number = models.PositiveIntegerField(null=True, blank=True)
    
    address = models.ForeignKey(
        Address,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="orders"
    )    
    
    phone = models.CharField(max_length=255, null=True, blank=True)

    # 🔥 FIX 1: Ye dono fields miss thi!
    delivery_mode = models.CharField(max_length=50, default='Normal')
    delivery_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )

    # 🔥 NAYA FIELD PAYMENT KE LIYE
    PAYMENT_CHOICES = (
        ('COD', 'Cash on Delivery'),
        ('ONLINE', 'Online Payment'), # Future ke liye ready
    )
    payment_mode = models.CharField(
        max_length=20, 
        choices=PAYMENT_CHOICES, 
        default='COD'
    )

    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True,blank=True)
    deadline = models.DateTimeField(null=True, blank=True)
    is_deadline_notified = models.BooleanField(default=False) # 🔥 Ye naya field add karein
    
    def save(self, *args, **kwargs):
        # 1. 🔥 NAYA LOGIC: Jaise hi partner assign ho (chahe pending ho), usko permanent number de do
        if self.partner and not self.partner_order_number:
            from django.db.models import Max
            max_val = Order.objects.filter(partner=self.partner).aggregate(Max('partner_order_number'))['partner_order_number__max']
            
            if max_val is None:
                self.partner_order_number = 1
            else:
                self.partner_order_number = max_val + 1

        # 2. PURANA LOGIC: Jab status 'accepted' ho
        if self.status == 'accepted':
            # Agar accepted_at nahi hai toh abhi ka time set karo
            if not self.accepted_at:
                self.accepted_at = timezone.now()
            
            # Deadline calculation (Force calculation)
            mode = (self.delivery_mode or "Normal").lower()
            
            if 'premium' in mode:
                self.deadline = self.accepted_at + timedelta(hours=6)
            elif '1 day' in mode or 'one day' in mode:
                self.deadline = self.accepted_at + timedelta(hours=24)
            else:
                # Normal: 48 Hours
                self.deadline = self.accepted_at + timedelta(hours=48)
                
        super().save(*args, **kwargs) 

    def __str__(self):
        return f"Order : {self.user.id}"
    
    
class UserFCMToken(models.Model):

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.user.username} - {self.token}"    


class OrderItem(models.Model):

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='order_items'
    )

    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE
    )

    quantity = models.PositiveIntegerField(default=1)

    price = models.DecimalField(
        max_digits=8,
        decimal_places=2
    )
    created_at = models.DateTimeField(auto_now_add=True) 

    def __str__(self):
        return f"{self.item.name} x {self.quantity}"

    def save(self, *args, **kwargs):
        self.price = self.item.price
        super().save(*args, **kwargs)

        # 🔥 FIX 2: Total me delivery_charge add kiya
        items_total = sum(oi.price * oi.quantity for oi in self.order.order_items.all())
        self.order.total_amount = items_total + self.order.delivery_charge
        self.order.save()
        
class ServiceType(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name        
    
# Delivery Config 
    
class DeliveryConfig(models.Model):
    mode_id = models.CharField(max_length=50, unique=True, help_text="e.g., normal, 1_day, premium")
    title = models.CharField(max_length=50, help_text="e.g., Premium")
    subtitle = models.CharField(max_length=50, help_text="e.g., 5-6 Hours")
    charge_percent = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0.00, 
        help_text="e.g., 0.05 for 5%, 0.10 for 10%"
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.title} ({self.charge_percent * 100}%)"

class Item(models.Model):
    name = models.CharField(max_length=100)
    type = models.ForeignKey(ServiceType, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=8, decimal_places=2)

    def __str__(self):
        return f"{self.type.name} - {self.name}"
    
    
