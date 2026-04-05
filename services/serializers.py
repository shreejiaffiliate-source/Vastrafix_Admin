from razorpay import Order
from rest_framework import serializers
from .models import Banner, SubCategory, Category, Item, Complaint
from orders.models import Order  # Order model ko import karna hoga

# 1. Item Serializer: Laundry items (Shirt, Jeans etc.) ki basic details handle karta hai
class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = ['id', 'name', 'price', 'is_active']

# 2. Subcategory Serializer: Category ke andar ki sub-lists (e.g. Men's Wear, Women's Wear)
class SubcategorySerializer(serializers.ModelSerializer):
    # MethodField ka use karke hum related items ko list ke andar hi fetch karte hain
    items = serializers.SerializerMethodField()

    class Meta:
        model = SubCategory
        fields = ['id', 'name', 'items', 'is_active']

    # Function: Sirf wahi items dikhao jo database mein 'is_active=True' hain
    def get_items(self, obj):
        qs = obj.item_set.filter(is_active=True)
        return ItemSerializer(qs, many=True).data

# 3. Category Serializer: Main services (Dry Cleaning, Ironing etc.) aur unki subcategories
class CategorySerializer(serializers.ModelSerializer):
    # Ek category ke andar saari subcategories ko nested structure mein dikhata hai
    subcategories = SubcategorySerializer(many=True, read_only=True)

    class Meta:
        model = Category
        fields = ['id', 'name', 'description', 'icon', 'subcategories']

# 4. Complaint Serializer: Customer complaints (Rahul) aur Partner linking (Het)
class ComplaintSerializer(serializers.ModelSerializer):
    # order_id: Flutter se integer lega par database table mein save nahi hoga (write_only)
    # required=False: Support screen se general complaint bhi allow karega
    order_id = serializers.IntegerField(write_only=True, required=False, allow_null=True) 
    
    order = serializers.PrimaryKeyRelatedField(
        queryset=Order.objects.all(), 
        required=False, 
        allow_null=True
    )

    class Meta:
        model = Complaint
        fields = ['id', 'user','order' ,'issue','message', 'order_id', 'status', 'created_at']
        # User aur Status backend khud set karega, isliye read_only rakha hai
        read_only_fields = ['user', 'status']


# 5. Banner Serializer: Home screen par promotional images dikhane ke liye
class BannerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Banner
        fields = '__all__' # Saari fields (image, title etc.) fetch karega