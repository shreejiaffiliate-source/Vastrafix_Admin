from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Address
from geo import get_lat_lng_from_address

User = get_user_model()

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            'username', 'email', 'phone', 'password', 'role',
            'address', 'city', 'state', 'pincode',
        ]

    # 🔥 Email Check with Custom Message
    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            # Yahan humne saaf message likha hai
            raise serializers.ValidationError("This email is already registered. Please use another one.")
        return value

    # 🔥 Phone Check with Custom Message
    def validate_phone(self, value):
        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError("This phone number is already registered. Please choose another number.")
        return value 
    
    # 🔥 Username Check (Underscore Logic)
    def validate_username(self, value):
        # Agar koi manually space bhej de toh yahan fix ho jayega
        formatted_username = value.replace(' ', '_').lower()
        if User.objects.filter(username=formatted_username).exists():
            raise serializers.ValidationError("Username already taken. Try adding numbers or underscore.")
        return formatted_username

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User.objects.create_user(
            password=password,
            is_active=True,
            is_verified=True,
            **validated_data
        )
        return user


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = [
            "id",
            "house_no",
            "street",
            "area",
            "city",
            "state",
            "pincode",
            "latitude",   # 🔥 Ye dono yahan hone zaruri hain
            "longitude"
        ]

# 🔥 Yahan se neeche jo 'def create(self, validated_data):' wala poora function tha, wo main ne hata diya hai. Tum bhi hata do!



class UserProfileSerializer(serializers.ModelSerializer):
    addresses = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "email", "phone", "profile_image", "addresses"]

    def get_addresses(self, obj):
        addresses = obj.addresses.all()
        return AddressSerializer(addresses, many=True).data


class EditProfileSerializer(serializers.ModelSerializer):
    # 🔥 Sab ko optional bana do taaki sirf phone update ho sake
    username = serializers.CharField(required=False)
    email = serializers.EmailField(required=False)
    phone = serializers.CharField(required=False)
    profile_image = serializers.ImageField(required=False, allow_null=True)

    class Meta: 
        model = User
        fields = ['username', 'email', 'phone', 'profile_image']

    def validate_phone(self, value):
        request = self.context.get('request')
        if not request or not value:
            return value

        user = request.user
        # ⚠️ Check: Kya ye number kisi AUR user ke paas hai?
        if User.objects.exclude(pk=user.pk).filter(phone=value).exists():
            raise serializers.ValidationError("Bhai, ye number pehle se kisi aur account mein hai.")
        return value