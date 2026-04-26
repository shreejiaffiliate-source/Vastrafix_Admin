from rest_framework import serializers
from .models import Order, OrderItem, DeliveryConfig
from accounts.models import Address
from decimal import Decimal

# 🔥 FIX: Isko add kiya taaki api me data bheja ja sake
class DeliveryConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryConfig
        fields = '__all__'


class OrderItemSerializer(serializers.ModelSerializer):
    item_name = serializers.ReadOnlyField(source='item.name')
    category_name = serializers.CharField(source='item.type.name', read_only=True)
    service_name = serializers.CharField(source='item.type.name', read_only=True)
    item_price = serializers.ReadOnlyField(source='price') 

    class Meta:
        model = OrderItem
        fields = ['item', 'item_name', 'category_name', 'service_name', 'item_price', 'quantity']

# DONO PURANE OrderSerializer HATA KAR YEH EK USE KARNA HAI
class OrderSerializer(serializers.ModelSerializer):
    order_items = OrderItemSerializer(many=True)
    address_id = serializers.IntegerField(write_only=True)
    phone = serializers.CharField(required=False, allow_null=True)
    partner_phone = serializers.CharField(source="partner.phone", read_only=True) # "partner" ya jo bhi related name unhone Order model me delivery boy ke liye rakha hai

    class Meta:
        model = Order
        # 🔥 'partner_order_number' add kiya
        fields = [
            "id", "partner_order_number", "status", "total_amount", 
            "pickup_datetime", "delivery_mode", "delivery_charge", 
            "payment_mode", "order_items", "address_id", "created_at", "partner_phone","phone",
            "delivery_otp"  # 🔥 YE ADD KIYA: Taaki Customer ko OTP dikhe
        ]
        read_only_fields = ["total_amount", "status", "created_at", "partner_order_number"]

    def create(self, validated_data):
        items_data = validated_data.pop('order_items')
        user = self.context['request'].user
        address_id = validated_data.pop('address_id')
        address = Address.objects.get(id=address_id, user=user)
        
        order_phone = validated_data.get('phone') or user.phone
        pickup_datetime = validated_data.get("pickup_datetime")

        # 👇 FRONTEND SE AAYA HUA DELIVERY DATA GET KARNA (Default values ke sath)
        delivery_mode = validated_data.get("delivery_mode", "Normal")
        delivery_charge = validated_data.get("delivery_charge", Decimal("0.00"))

        # Payment Method
        payment_mode = validated_data.get("payment_mode", "COD")

        # FIX 1: Yaha order create karte waqt phone save karna zaruri hai
        amount = validated_data.get('amount', 0)
        order = Order.objects.create(
            amount=amount,  # ✅ Ye field ab Order model me hai, toh yahan bhi save karna hoga
            user=user,
            address=address,
            phone=order_phone, # 👈 Yahan ab sahi number save hoga
            pickup_datetime=pickup_datetime,  
            delivery_mode=delivery_mode,  # 👈 Yahan save ho gaya
            delivery_charge=delivery_charge,
            payment_mode=payment_mode
        )

        total = Decimal("0")

        for item_data in items_data:
            item = item_data['item']
            quantity = item_data['quantity']
            price = item.price

            OrderItem.objects.create(
                order=order,
                item=item,
                quantity=quantity,
                price=price
            )
            total += price * quantity

        # 👇 MAIN FIX: Total calculation me delivery_charge ko add karna hai
        order.total_amount = total + Decimal(str(delivery_charge))
        order.save(update_fields=["total_amount"])

        return order
    
class PartnerOrderSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.username", read_only=True)
    
    # FIX 2: Agar order me phone na ho, toh direct user profile se phone fetch kar lo
    phone = serializers.CharField(source="user.phone", read_only=True) 
    
    # FIX 3: address_text ke liye StringRelatedField use karo, taaki Address model ka poora address aa jaye
    address_text = serializers.StringRelatedField(source="address", read_only=True)
    order_items = OrderItemSerializer(many=True, read_only=True)
    
    user_profile_image = serializers.ImageField(source='user.profile_image', read_only=True)
    pickup_datetime = serializers.DateTimeField(format="%Y-%m-%dT%H:%M:%S", default_timezone=None)

    class Meta:
        model = Order
        fields = [
            "id",
            "partner_order_number", # 🔥 YEH HAI MAIN FIX: Partner ko uska apna sequence dikhega
            "user_name",
            "phone",
            "total_amount",
            "status",
            "address_text",
            "delivery_mode",    # 👈 Partner ko dikhega ki Premium delivery hai
            "delivery_charge",
            "payment_mode",
            'order_items',
            'user_profile_image',
             "pickup_datetime",
             "accepted_at",
            "deadline",

            
        ]
