from cProfile import Profile

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import api_view , permission_classes
from rest_framework.permissions import IsAuthenticated , AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from .models import Address
from .serializers import (
    RegisterSerializer,
    AddressSerializer,
    UserProfileSerializer,
    EditProfileSerializer
)

import google.oauth2.id_token
from google.auth.transport import requests as google_requests
from django.conf import settings # Agar client ID settings mein rakhi hai
import random
from .util import send_otp_via_email



User = get_user_model()

# 1. REGISTER VIEW (Signup hote hi OTP jayega)
from django.core.cache import cache

# 1. REGISTER VIEW (User abhi create NAHI hoga, sirf OTP jayega)
class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data) 
        
        if serializer.is_valid():
            email = serializer.validated_data['email']
            otp = str(random.randint(100000, 999999))
            
            # 🔥 Sabse bada badlaav: User save karne ki jagah sara data Cache mein daal do 5 minute ke liye
            signup_data = request.data
            signup_data['otp'] = otp
            # Key banayenge email ke naam se
            cache.set(f"signup_{email}", signup_data, timeout=300) 
            
            try:
                send_otp_via_email(email, otp)
                return Response({
                    "success": True, 
                    "message": "OTP sent to your email"
                }, status=200)
            except Exception as e:
                return Response({"error": "Failed to send email"}, status=500)
        
        return Response(serializer.errors, status=400)

# 2. VERIFY OTP VIEW (Ab yahan asli User create hoga)
@api_view(['POST'])
@permission_classes([AllowAny])
def verify_signup_otp(request):
    email = request.data.get('email')
    # OTP ko string mein convert karke extra space hata di
    otp_received = str(request.data.get('otp')).strip() 

    # 1. Cache se data nikaalo
    cached_data = cache.get(f"signup_{email}")

    if not cached_data:
        # Check: Kahin user pehle hi create toh nahi ho gaya?
        if User.objects.filter(email=email).exists():
            return Response({"success": True, "message": "User already verified"}, status=200)
        return Response({"success": False, "error": "OTP Expired. Please signup again."}, status=400)

    # 2. OTP Matching Logic
    if str(cached_data.get('otp')) == otp_received:
        try:
            user_data = cached_data.copy()
            user_data.pop('otp', None) # Serializer ke liye OTP hatao

            serializer = RegisterSerializer(data=user_data)
            if serializer.is_valid():
                user = serializer.save()
                user.is_verified = True
                user.is_active = True
                user.save()
                
                cache.delete(f"signup_{email}") # Kaam khatam, cache saaf
                
                # 🔥 EKDUM CLEAR SUCCESS RESPONSE
                return Response({
                    "success": True, 
                    "message": "Registration successful"
                }, status=201)
            else:
                # Agar phone ya email pehle se hai
                return Response({"success": False, "error": serializer.errors}, status=400)
        except Exception as e:
            return Response({"success": False, "error": str(e)}, status=500)
    else:
        # ❌ Agar OTP match nahi hua
        return Response({"success": False, "error": "Invalid OTP. Please check again."}, status=400)
    
    
@api_view(['POST'])
@permission_classes([AllowAny])
def resend_otp_view(request):
    email = request.data.get('email')
    # 🔥 Database ki jagah Cache mein dhoondo
    cached_data = cache.get(f"signup_{email}")
    
    if cached_data:
        otp = str(random.randint(100000, 999999))
        cached_data['otp'] = otp # Naya OTP update karo
        cache.set(f"signup_{email}", cached_data, timeout=300) # Wapas save karo
        
        try:
            send_otp_via_email(email, otp)
            return Response({"success": True, "message": "New OTP Sent"}, status=200)
        except Exception as e:
            return Response({"success": False, "error": "Email fail"}, status=500)
            
    return Response({"success": False, "error": "Signup session expired. Please signup again."}, status=404)
    

class LoginView(APIView):

    def post(self, request):
        input_value = request.data.get("email_or_phone")
        password = request.data.get("password")
        app_type = request.data.get("app_type")

        if not input_value or not password:
            return Response(
                {"error": "Email/Phone and password required"},
                status=400
            )

        try:
            if "@" in input_value:
                user = User.objects.get(email=input_value)
            else:
                user = User.objects.get(phone=input_value)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=400)

        if not user.check_password(password):
            return Response({"error": "Wrong password"}, status=400)
        
        if not user.is_active:
            return Response(
                {
                    "error": "Your account is blocked by admin. Please contact support.",
                    "is_active": False
                }, 
                status=403
            )
        
        # 🔥 NAYA: EMAIL VERIFICATION CHECK YAHAN LAGA HAI
        if not getattr(user, 'is_verified', True): # Agar kisi purane user mein field na ho toh error na de
            return Response(
                {
                    "error": "Your email is not verified. Please verify your email first.",
                    "is_verified": False
                }, 
                status=403
            )
        
         # 🔥 ROLE RESTRICTION
        if app_type == "partner" and user.role != "partner":
            return Response(
                {"error": "You are not registered as a partner"},
                status=403
            )

        if app_type == "customer" and user.role != "customer":
            return Response(
                {"error": "You are not registered as a customer"},
                status=403
            )

        refresh = RefreshToken.for_user(user)

        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "role": user.role,
            "username": user.username,
            "is_active": user.is_active,
        })


class CreateAddressView(generics.CreateAPIView):
    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated]
    
    
    # 🔥 Ye ensure karta hai ki logged-in user hi address ke sath jude
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

   
        


class UserAddressView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        addresses = Address.objects.filter(user=request.user)

        if addresses.exists():
            serializer = AddressSerializer(addresses.first())
            return Response(serializer.data)

        return Response({}) 


class UserAllAddressView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        addresses = Address.objects.filter(user=request.user).order_by('-id')
        serializer = AddressSerializer(addresses, many=True)
        return Response(serializer.data)

class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        print(f"User: {request.user}") # Terminal mein check karein
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)


class EditUserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request):
        serializer = EditProfileSerializer(
            request.user,
            data=request.data,
            partial=True
        )

        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "message": "Profile updated successfully",
                    "data": serializer.data
                },
                status=status.HTTP_200_OK
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
# delete address 

@api_view(['DELETE'])
@permission_classes([IsAuthenticated]) # Ye line add karein
def delete_address(request, pk):
    try:
        address = Address.objects.get(pk=pk, user=request.user)
        address.delete()
        return Response(status=204)
    except Address.DoesNotExist:
        return Response({"error": "Not Found"}, status=404)
    
    
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_address(request):
    data = request.data
    # 🔥 Yahan lat aur long get karna zaroori hai
    lat = data.get('latitude')
    lng = data.get('longitude')
    
    address = Address.objects.create(
        user=request.user,
        house_no=data.get('house_no'),
        street=data.get('street'),
        area=data.get('area'),
        city=data.get('city'),
        state=data.get('state'),
        pincode=data.get('pincode'),
        latitude=lat,   # <--- YEH LINE ADD KARO
        longitude=lng   # <--- YEH LINE ADD KARO
    )
    return Response({"id": address.id, "message": "Address saved"}, status=201) 

@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_address(request, address_id):
    try:
        # Pata karo ki ye address is user ka hai ya nahi (Security ke liye)
        address = Address.objects.get(id=address_id, user=request.user)
    except Address.DoesNotExist:
        return Response({"error": "Address not found or unauthorized"}, status=404)

    # Naya data request se nikal kar update karein
    data = request.data
    
    address.house_no = data.get('house_no', address.house_no)
    address.street = data.get('street', address.street)
    address.area = data.get('area', address.area)
    address.city = data.get('city', address.city)
    address.state = data.get('state', address.state)
    address.pincode = data.get('pincode', address.pincode)

    # Location (Lat/Lng) update karein (agar user ne provide kiya hai)
    if 'latitude' in data and data['latitude'] is not None:
        address.latitude = data['latitude']
    if 'longitude' in data and data['longitude'] is not None:
        address.longitude = data['longitude']

    # Database mein save kar dein
    address.save()

    return Response({
        "message": "Address updated successfully",
        "id": address.id
    }, status=200)   
    
# accounts/views.py
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_duty_status(request):
    user = request.user
    # Flutter se "is_online" key bhej rahe hain hum
    new_status = request.data.get('is_online')
    
    if new_status is not None:
        user.is_online = new_status
        user.save()
        return Response({
            "status": "success", 
            "is_online": user.is_online,
            "message": f"Partner is now {'Online' if user.is_online else 'Offline'}"
        })
    
    return Response({"error": "Data missing"}, status=400) 


from accounts.models import User

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_fcm_token(request):

    token = request.data.get("token")

    if token:

        # 🔥 same token agar kisi aur user me hai to remove
        User.objects.filter(
            fcm_token=token
        ).exclude(id=request.user.id).update(fcm_token=None)

        request.user.fcm_token = token
        request.user.save()

    return Response({"status": "token updated"})


#google login
import firebase_admin
from firebase_admin import auth as firebase_auth, credentials
import os

# Firebase Initialization (Ise views.py ke top par rakhein)
# Make sure path sahi ho
JSON_PATH = os.path.join(settings.BASE_DIR, 'config', 'vastrafix-firebase-adminsdk-fbsvc-c4483113b3.json')

# accounts/views.py ke top par initialize aise karein:

if not firebase_admin._apps:
    cred = credentials.Certificate(JSON_PATH)
    firebase_admin.initialize_app(cred) # projectId yahan se hata dein
    
    
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_auth_requests

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def google_login_view(request):
    token = request.data.get("idToken")
    # Partner app hai isliye default role "partner" rakhenge
    app_type = request.data.get("app_type", "partner") 

    if not token:
        return Response({"error": "Token missing"}, status=400)

    try:
        # Google token verify karein
        # (Yahan aapka pichla working verification logic use karein)
        CLIENT_ID = "601085863126-vd5n9r4147620li5fk8p0e3vnho2qvm6.apps.googleusercontent.com"
        id_info = google_id_token.verify_oauth2_token(
            token, 
            google_auth_requests.Request(), 
            CLIENT_ID
        )

        email = id_info.get('email')
        name = id_info.get('name', email.split('@')[0]) # Agar name na mile toh email ka prefix lele
        # 🔥 STEP: User dhoondhein ya banayein
        # 🔥 STEP: User dhoondhein ya banayein
        
        # 🔥 STEP 1: User ko dhoondhein ya naya banayein (get_or_create)
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'username': name,
                'role': app_type, # Naya user hai toh "partner" banega
                'first_name': name.split()[0],
                'is_verified': True,
            }
        )

        # 🔥 STEP 2: Agar user pehle se hai par uska role "customer" hai
        # Toh hum use allow nahi karenge (Security ke liye)
        if not created and user.role != app_type:
            return Response({
                "error": f"Ye account pehle se ek {user.role} ke taur par registered hai."
            }, status=403)

        # Success! Token generate karein
        refresh = RefreshToken.for_user(user)
        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "role": user.role,
            "username": user.username,
            "is_new_user": created # Flutter ko batane ke liye ki naya account bana hai
        })

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return Response({"error": "Google Verification Failed"}, status=400)