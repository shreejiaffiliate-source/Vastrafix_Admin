from django.contrib import admin
from .models import PartnerBankDetail, Payment
from django.contrib import admin
from .models import PartnerWallet, PayoutRequest
from django.db import transaction
from vastrafix.core.firebase import send_push # Push notification utility
from notification.models import Notification as AppNotification # DB Notification model

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    # 'amount' ki jagah 'get_amount_in_inr' use karenge
    list_display = ('order_id_display', 'user', 'get_amount_in_inr', 'payment_method', 'status_badge', 'created_at')
    list_filter = ('status', 'payment_method', 'created_at')
    search_fields = ('razorpay_payment_id', 'razorpay_order_id', 'user__username')

    # 1. Amount ko ₹ mein dikhane ke liye logic
    def get_amount_in_inr(self, obj):
        return f"₹{obj.amount / 100}"
    get_amount_in_inr.short_description = 'Amount'

    # 2. Order ID ko saaf-saaf dikhane ke liye logic
    def order_id_display(self, obj):
        if obj.order:
            return f"#VF-{obj.order.id}"
        return "-"
    order_id_display.short_description = 'Order'

    # 3. Status ko thoda clean dikhane ke liye
    def status_badge(self, obj):
        from django.utils.html import format_html
        color = "green" if obj.status.lower() == 'success' else "red"
        return format_html('<span style="color: {}; font-weight: bold;">{}</span>', color, obj.status.upper())
    status_badge.short_description = 'Status'
    
    

@admin.register(PartnerWallet)
class PartnerWalletAdmin(admin.ModelAdmin):
    list_display = ('partner', 'balance','commission_rate', 'total_withdrawn', 'updated_at')
    list_editable = ('commission_rate',) # Admin seedha list se badal sakega
     
# payments/admin.py

from django.utils.html import format_html
from .models import PartnerBankDetail

@admin.register(PayoutRequest)
class PayoutRequestAdmin(admin.ModelAdmin):
    # List view mein kya dikhega
    list_display = ('partner', 'amount', 'status', 'display_bank_info', 'created_at')
    
    # Detail view (aapka screenshot wala page) mein kya dikhega
    readonly_fields = ('partner', 'amount', 'upi_id', 'bank_details_display', 'created_at')
    fields = ('status', 'partner', 'amount', 'upi_id', 'bank_details_display', 'created_at')

    # 🔥 Yeh function partner ki bank details fetch karke ek mast table banayega
    def bank_details_display(self, obj):
        bank = PartnerBankDetail.objects.filter(partner=obj.partner).first()
        if bank:
            return format_html(
                '<div style="background-color: #f8f9fa; padding: 15px; border-left: 5px solid #007bff; border-radius: 5px;">'
                '<b>🏦 Bank Name:</b> {} <br>'
                '<b>👤 Holder Name:</b> {} <br>'
                '<b>🔢 Account No:</b> <span style="font-size: 1.1em; color: #d63384;">{}</span> <br>'
                '<b>🔑 IFSC Code:</b> {} <br>'
                '<b>📱 UPI ID:</b> {}'
                '</div>',
                bank.bank_name,
                bank.account_holder_name,
                bank.account_number,
                bank.ifsc_code,
                bank.upi_id or "N/A"
            )
        return "❌ No Bank Details Found"

    bank_details_display.short_description = "Partner's Bank Account Info"

    # List view ke liye chota info
    def display_bank_info(self, obj):
        bank = PartnerBankDetail.objects.filter(partner=obj.partner).first()
        if bank:
            return f"{bank.bank_name} ({bank.account_number[-4:]})"
        return "None"
    
    display_bank_info.short_description = "Bank Info"
        
from django.utils.html import format_html

@admin.register(PartnerBankDetail)
class PartnerBankDetailAdmin(admin.ModelAdmin):
    list_display = ('partner', 'status', 'view_proof')
    readonly_fields = ('show_image',)

    def view_proof(self, obj):
        if obj.passbook_image:
            return format_html('<a href="{}" target="_blank">View Proof</a>', obj.passbook_image.url)
        return "No Proof"

    def show_image(self, obj):
        if obj.passbook_image:
            return format_html('<img src="{}" width="300" />', obj.passbook_image.url)
        return "No image uploaded"
     