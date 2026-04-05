from django.urls import path
from . import views

urlpatterns = [
    path('', views.admin_dashboard_view, name='custom_dashboard'), # dashboard show 
    path('users/', views.user_list_view, name='admin_users'), # user fetch
    path('users/<int:user_id>/', views.user_detail_view, name='user_detail'), # user detail show 
    path('users/toggle/<int:user_id>/', views.toggle_user_status, name='toggle_user_status'), # block karne ke liye 
    path('inventory/update/<int:item_id>/', views.update_item_price, name='update_price'), # update price karne ke liye 
    path('inventory/category/add/', views.add_new_category, name='add_new_category'),# add category 
    path('inventory/add/', views.add_new_item, name='add_new_item'), # add item in category 
    path('dashboard/categories/', views.admin_categories_view, name='admin_categories'), # category 
    path('dashboard/categories/toggle/<int:cat_id>/', views.toggle_category_status, name='toggle_category'),
    path('dashboard/categories/delete/<int:cat_id>/', views.delete_category, name='delete_category'),
    path('dashboard/items/', views.admin_items_view, name='admin_items'), #item 
    path('dashboard/items/toggle/<int:item_id>/', views.toggle_item_status, name='toggle_item'),
    path('orders/', views.order_list_view, name='admin_orders'), # order list show 
    path('orders/update/<int:order_id>/', views.update_order_status, name='update_order_status'), # order status update
    path('orders/pending-action/', views.pending_orders_action_view, name='pending_orders_action'), # pending order action
    path('orders/assign/<int:order_id>/', views.assign_partner, name='assign_partner'), # assign partner fo order pending 
    path('complaints/', views.complaint_list_view, name='admin_complaints'), # compaint fetch
    path('complaints/resolve/<int:complaint_id>/', views.resolve_complaint, name='resolve_complaint'), # complaint solve
    path('orders/detail/<int:order_id>/', views.order_detail_view, name='order_detail'), # order detail show
    path('complaints/fine/<int:complaint_id>/', views.fine_partner_view, name='fine_partner'), # fine partner
    path('payouts/', views.payout_requests_view, name='admin_payouts'), # 1. Saari Payout Requests dekhne ke liye page
    path('payouts/approve/<int:payout_id>/', views.approve_payout, name='approve_payout'), # 2. Payout Approve karne ka logic (Specific ID ke liye)
    path('payouts/reject/<int:payout_id>/', views.reject_payout, name='reject_payout'), # 3. Payout Reject karne ka logic (Specific ID ke liye)
    path('partner-wallets/', views.admin_partner_wallets_view, name='admin_partner_wallets'), # Partner Wallet Details dekhne ke liye page
    path('bank-verifications/', views.admin_bank_verifications, name='admin_bank_verifications'),
    path('bank-verifications/approve/<int:detail_id>/', views.approve_bank_detail, name='approve_bank_detail'),
    path('bank-verifications/reject/<int:detail_id>/', views.reject_bank_detail, name='reject_bank_detail'),
    path('logout/', views.custom_logout, name='logout'),
    path('login/', views.custom_login, name='login'),

]