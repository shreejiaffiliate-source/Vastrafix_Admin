from django.urls import path
from . import views

from .views import (
    CreateAddressView,
    RegisterView,
    LoginView,
    UserAddressView,
    UserAllAddressView,
    UserProfileView,
    EditUserProfileView,
    update_duty_status,
    update_fcm_token,
    verify_signup_otp
)

urlpatterns = [
    path("register/", RegisterView.as_view()),
    path("login/", LoginView.as_view()),
    path("profile/", UserProfileView.as_view()),
    path("profile/edit/", EditUserProfileView.as_view()),
# Sahi tarika (Class-based view ke liye)
    path('address/create/', views.CreateAddressView.as_view(), name='create-address'),    path("address/", UserAddressView.as_view()),
    path("addresses/", UserAllAddressView.as_view()),
    path('addresses/<int:pk>/', views.delete_address, name='delete_address'),
    path('address/<int:address_id>/update/', views.update_address, name='update_address'),
    path('update-status/', update_duty_status, name='update_duty_status'),
    path('update-fcm-token/', update_fcm_token),
    path('update-fcm/', views.update_fcm_token, name='update-fcm'),
    
    path('google-login/', views.google_login_view, name='google_login'),
    
    path('verify-otp/', verify_signup_otp, name='verify-otp'),
    path('send-otp/', views.resend_otp_view, name='resend-otp'),
    
]