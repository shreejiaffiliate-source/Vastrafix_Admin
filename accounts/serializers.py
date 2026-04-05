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
            'username',
            'email',
            'phone',
            'password',
            'role',
            'address',
            'city',
            'state',
            'pincode',
          
        ]

    # 🔥 YE WALA FUNCTION ADD KAREIN (Duplicate Email Check)
    def validate_email(self, value):
        # Database mein check karega ki ye email pehle se hai ya nahi
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("This email is already registered. Please use another one.")
        return value

    # 🔥 YE WALA FUNCTION BHI ADD KAREIN (Duplicate Phone Check)
    def validate_phone(self, value):
        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError("This phone number is already registered.")
        return value    

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User.objects.create_user(
            password=password,
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
    profile_image = serializers.ImageField(required=False)

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "phone",
            "profile_image",
        ]