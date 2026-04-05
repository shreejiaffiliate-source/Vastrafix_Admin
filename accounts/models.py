from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from geopy.geocoders import Nominatim  # 🔥 Ise install kar lena: pip install geopy

class User(AbstractUser):

    ROLE_CHOICES = (
        ('customer', 'Customer'),
        ('partner', 'Partner'),
        ('admin', 'Admin'),
    )
    fcm_token = models.CharField(max_length=500, blank=True, null=True)
    otp= models.CharField(max_length=6, blank=True, null=True) # 🔥 Naya field OTP ke liye
    is_verified = models.BooleanField(default=False) # 🔥 Ye line add karein
    is_online = models.BooleanField(default=True) # 🔥 Naya: Duty status store karne ke liye

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='customer'
    )

    phone = models.CharField(
        max_length=25,
        unique=True,
        null=True,
        blank=True
    )
    address = models.TextField(null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    state = models.CharField(max_length=100, null=True, blank=True)
    pincode = models.CharField(max_length=10, null=True, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    profile_image = models.ImageField(
        upload_to="profiles/",
        null=True,
        blank=True
    )

    def __str__(self):
        return self.username
    
    
class Address(models.Model):
    user = models.ForeignKey(User, related_name="addresses", on_delete=models.CASCADE)
    house_no = models.CharField(max_length=100)
    street = models.CharField(max_length=255)
    area = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10)
    
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # 🔥 ASLI FIX: Save method jo coordinates nikalega
    def save(self, *args, **kwargs):
        # Ek poora address string banayein jise Google/OSM samajh sake
        full_address_string = f"{self.area}, {self.city}, {self.state}, {self.pincode}, India"
        
        try:
            geolocator = Nominatim(user_agent="vastrafix_app")
            location = geolocator.geocode(full_address_string)
            if location:
                self.latitude = location.latitude
                self.longitude = location.longitude
                print(f"✅ Auto-Geocoded: {self.latitude}, {self.longitude}")
        except Exception as e:
            print(f"❌ Geocoding error: {e}")
            
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.area}, {self.city} - {self.pincode}"
