from django.db import models
from smart_selects.db_fields import ChainedForeignKey
from django.contrib.auth import get_user_model
from django.utils.text import slugify


User = get_user_model()


class Category(models.Model):   # Ye hi tumhara Category hai
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    slug = models.SlugField(unique=True, null=True, blank=True)
    icon = models.CharField()
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


# ✅ NEW MODEL
class SubCategory(models.Model):
    type = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="subcategories"
    )
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Sub Category"
        verbose_name_plural = "Sub Categories"

    def __str__(self):
        return f"{self.type.name} - {self.name}"


class Item(models.Model):
    type = models.ForeignKey(
        Category,
        on_delete=models.CASCADE
    )

    # ✅ Ye important part hai (filtered dropdown)
    subcategory = ChainedForeignKey(
        SubCategory,
        chained_field="type",
        chained_model_field="type",
        show_all=False,
        auto_choose=True,
        sort=True,
        null=True,      # 👈 TEMPORARY
        blank=True,
        on_delete=models.CASCADE
    )

    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Item"
        verbose_name_plural = "Items"

    def __str__(self):
       type_name = self.type.name if self.type else "No Category"
       sub_name = self.subcategory.name if self.subcategory else "No SubCategory"
       return f"{type_name} - {sub_name} - {self.name}"

# support and services models

class Complaint(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('In Progress', 'In Progress'),
        ('Resolved', 'Resolved'),
    ]

    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE)    
    order = models.ForeignKey('orders.Order', on_delete=models.SET_NULL, null=True, blank=True) # Yeh add karna hoga
    issue = models.TextField()
    user_name = models.CharField(max_length=150, blank=True) # Flutter se bhejenge
    subject = models.CharField(max_length=200, default="Order Issue") # Example: "Late Delivery"
    message = models.TextField() # Optional field for additional details
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)
    image = models.ImageField(upload_to='complaints/', null=True, blank=True)

    def __str__(self):
        # Safety check for admin panel
        display_name = self.user_name if self.user_name else self.user.username
        order_id = self.order.id if self.order else "N/A"
        return f"{display_name} - Order #{order_id}"
    
class Banner(models.Model):
    title = models.CharField(max_length=100, blank=True)
    image = models.ImageField(upload_to='banners/')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title or "Banner"    