from django.utils import timezone
from django.contrib import admin
from .models import Order, OrderItem, DeliveryConfig


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0

# 🔥 FIX: Admin panel me charges control karne ka option add kiya
@admin.register(DeliveryConfig)
class DeliveryConfigAdmin(admin.ModelAdmin):
    list_display = ('title', 'mode_id', 'subtitle', 'charge_percent', 'is_active')
    list_editable = ('charge_percent', 'is_active')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user','delivery_mode','payment_mode','status', 'total_amount','pickup_datetime','created_at_local')
    list_filter = ('status','delivery_mode','payment_mode','created_at')
    inlines = [OrderItemInline]
    
    def user_phone(self, obj):
        return obj.user.phone if obj.user else "-" # User model ka phone field

    def address_city(self, obj):
        return obj.address.city if obj.address else "-"
    
    
    def created_at_local(self, obj):
     if obj.created_at:
        local_time = timezone.localtime(obj.created_at)
        return local_time.strftime("%d-%m-%Y %I:%M %p")  # Example: 21-02-2026 12:40 PM
     return "-"

    
    user_phone.short_description = 'Phone'
    user_phone.admin_order_field = "user__phone"

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'item', 'quantity', 'price',)
    list_filter = ('order__user','created_at',)
    
    def order_created(self, obj):
        return obj.order.created_at
    
    order_created.short_description = "Created At"
    order_created.admin_order_field = "order__created_at"
    
    search_fields = (
        'order__id',          # Order ID se search
        'order__user__username',  # User name se search
        'item__name',         # Item/Product name se search
    )

