from django.urls import path

from payments import views

# 1. Remove the "from payments import ..." line entirely.

# 2. Add the payment functions to your local views import
from .views import (
    CreateOrderView, PartnerAcceptedOrders, PartnerAssignedOrdersView, 
    PartnerPendingOrdersView, UserOrderListView, accept_order, cancel_order, check_service_area, 
    complete_order, create_payout_request, get_order_detail, get_wallet_details, manage_bank_details, partner_earnings, partner_new_orders, partner_accepted_orders, 
    partner_order_history, get_delivery_configs, update_order_address, 
    update_order_status,
    create_razorpay_order,      # <--- Add this
    verify_razorpay_payment,
    partner_complaints,
    partner_earnings
  
)

urlpatterns = [
    path('create/', CreateOrderView.as_view(), name='create-order'),
    path('', UserOrderListView.as_view(), name='order-list'),
    path('my-orders/', UserOrderListView.as_view(), name='my-orders'),
    path('partner/new-orders/', partner_new_orders, name='partner-new-orders'),
    path('partner/pending/', PartnerPendingOrdersView.as_view()),
    path("partner/accepted/", partner_accepted_orders),
    path("orders/partner/accepted/", PartnerAcceptedOrders.as_view()),
    path('partner/my-orders/', PartnerAssignedOrdersView.as_view()),
    path("orders/<int:order_id>/complete/", complete_order),
    path("cancel/<int:pk>/", cancel_order, name="cancel-order"),
    path("<int:order_id>/accept/", accept_order),
    path("<int:order_id>/complete/", complete_order),
    path("partner/history/", partner_order_history),
    path('delivery-configs/', get_delivery_configs, name='delivery_configs'),
    path('<int:order_id>/update-address/', update_order_address, name='update-order-address'),
    path('<int:order_id>/update-status/', update_order_status, name='update_order_status'),
    
    # 3. Remove "views." prefix here since we imported them directly
    path('payment/create-order/', create_razorpay_order, name='create_razorpay_order'),
    path('payment/verify/', verify_razorpay_payment, name='verify_razorpay_payment'),
    path('partner/complaints/', partner_complaints, name='partner_complaints'),
    path('partner/earnings/', partner_earnings, name='partner_earnings'),
    
    #customer radius
    
    path('check-area/', check_service_area, name='check-area'),
    
    # orders/urls.py
    path('partner/wallet/', get_wallet_details, name='partner_wallet'),
    path('partner/payout-request/', create_payout_request, name='payout_request'),
    
    # 🏦 Bank Details Manage (GET & POST)
    path('bank-details/', manage_bank_details, name='manage_bank_details'),
    
    # orders/urls.py mein urlpatterns list ke andar add karein:

    path('<int:order_id>/', get_order_detail, name='order-detail'),
]