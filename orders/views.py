from decimal import Decimal
import threading
import requests
from rest_framework.response import Response 
from rest_framework import generics, permissions
from rest_framework.decorators import api_view, permission_classes
from notification.models import Notification
from notification.utils import create_notification
from orders.tasks import send_deadline_push
from services.models import Complaint
from .serializers import OrderSerializer, PartnerOrderSerializer, DeliveryConfigSerializer
from math import radians, cos, sin, asin, sqrt
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from datetime import timedelta
import razorpay
from django.conf import settings
# orders/views.py ke sabse upar ye line add karein
from services.models import Category, Complaint # Category import karna zaroori hai
from vastrafix.core.firebase import send_push # Ye bhi import karna zaruri hai notification bhejne ke liye
from vastrafix.core.firebase import send_broadcast_push # Broadcast push ke liye naya import
from accounts.models import User # Partner tokens ke liye User model import karna zaruri hai
from payments.models import PayoutRequest
from payments.models import PartnerWallet
from .models import Order, DeliveryConfig, UserFCMToken
import random

# delivery config 

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_delivery_configs(request):
    configs = DeliveryConfig.objects.filter(is_active=True)
    serializer = DeliveryConfigSerializer(configs, many=True)
    return Response(serializer.data)


class CreateOrderView(generics.CreateAPIView):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def perform_create(self, serializer):
        # 🔥 FIX: serializer.save() ko 'order' variable mein store karein
        order = serializer.save(user=self.request.user)
        
        
        #payment id logic
        
        payment_id = self.request.data.get('paymentId') 
        
        if payment_id:
            try:
                # Purani payment entry ko dhoondho jo verify_razorpay_payment ne banayi thi
                from payments.models import Payment
                payment = Payment.objects.filter(razorpay_payment_id=payment_id, order__isnull=True).first() # Ye line thodi risky hai, ideally payment_id unique hona chahiye
                
                if not payment:
                    payment = Payment.objects.filter(razorpay_payment_id=payment_id).first() # Agar above se nahi mila toh thoda loose search karte hain
                
                if payment:
                    # 🔴 CRITICAL FIX: Order model ki fields ko manually update karein
                    # Taaki aapke Admin Screenshot mein details dikhne lagein
                    order.razorpay_payment_id = payment.razorpay_payment_id
                    order.razorpay_order_id = payment.razorpay_order_id
                    order.is_paid = True
                    # Agar total_amount 0.00 aa raha hai toh yahan calculate karke save karein
                    order.total_amount = Decimal(payment.amount) / 100  # Kyunki payment amount paise mein hota hai
                    order.save()
                    
                    payment.order = order
                    payment.save()
                    # Payment entry ko bhi order se link kardo permanent
                    
                    print(f"✅ Success: Payment {payment_id} linked to Order {order.id}")
                else:
                    print(f"⚠️ Warning: Payment ID {payment_id} database mein toh hai par link nahi ho pa rahi.")

            except Exception as e:
                 print(f"❌ Linking Error: {str(e)}")
        
        # Ab niche wala code sahi chalega kyunki 'order' define ho gaya hai
       # --- SIRF YE RADIUS LOGIC ADD KAREIN (Baaki sab upar ka waisa hi rahega) ---
        from accounts.models import User, Address
        from vastrafix.core.firebase import send_broadcast_push
        
        # 1. Customer ki location order ke address se lo
        c_lat = order.address.latitude if order.address else None
        c_lng = order.address.longitude if order.address else None
        
        nearby_partner_tokens = []

        if c_lat and c_lng:
            # 2. Sirf un partners ko filter karo jo Online hain
            partners = User.objects.filter(role='partner', is_online=True).exclude(fcm_token__isnull=True)
            
            for partner in partners:
                # 3. Partner ka address DB se nikalo
                p_addr = Address.objects.filter(user=partner).first()
                
                if p_addr and p_addr.latitude:
                    # 4. Radius Check (Aapka calculate_distance function call ho raha hai)
                    dist = calculate_distance(p_addr.latitude, p_addr.longitude, c_lat, c_lng)
                    
                    # 🔥 SIRF 5 KM CONDITION
                    if dist is not None and dist <= 5.0:
                        # Database mein notification entry
                        create_notification(
                            user=partner,
                            title="New Order Available!🧺",
                            message=f"Order #{order.id}",
                            icon_type="order"
                        )
                        # Token collect karein push ke liye
                        nearby_partner_tokens.append(partner.fcm_token)

        # 5. Ab sirf nearby partners ko hi push notification bhejo
        if nearby_partner_tokens:
            # 1. Sirf wahi tokens lo jo khali nahi hain
            valid_tokens = [t for t in nearby_partner_tokens if t and len(t) > 10]
            # 2. Duplicate hatane ke liye SET ka use
            unique_tokens = list(set(valid_tokens))
            
            print(f"🚨 FINAL PUSH TO {len(unique_tokens)} UNIQUE PARTNERS")

            if unique_tokens:
                send_broadcast_push(
                    tokens=unique_tokens,
                    title="New Order Available! 🧺",
                    body=f"Order #{order.id}",
                    channel='partner_orders'
                )
        # --- RADIUS LOGIC END ---
    
class UserOrderListView(generics.ListAPIView):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).order_by('-id')
    
# Change address

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_order_address(request, order_id):
    if request.user.role != "customer":
         return Response({"error": "Only customers can update address"}, status=403)

    try:
        # Pata karo ki kya ye order is user ka hai
        order = Order.objects.get(id=order_id, user=request.user)
        
        # Delivered ya cancelled order ka address change nahi ho sakta
        if order.status in ["delivered", "cancelled"]:
            return Response({"error": f"Cannot update address for {order.status} order"}, status=400)
            
        address_id = request.data.get('address_id')
        if not address_id:
            return Response({"error": "Address ID is required"}, status=400)
            
        # Pata karo ki naya address isi user ka hai ya nahi
        new_address = Address.objects.get(id=address_id, user=request.user)
        
        # Order mein naya address save kardo
        order.address = new_address
        order.save()
        
        return Response({"message": "Order address updated successfully"}, status=200)
        
    except Order.DoesNotExist:
        return Response({"error": "Order not found"}, status=404)
    except Address.DoesNotExist:
        return Response({"error": "Address not found or does not belong to user"}, status=404)
    except Exception as e:
        return Response({"error": str(e)}, status=500)
    
  


#partner views


from rest_framework.decorators import APIView, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from accounts.models import User

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def partner_new_orders(request):
    
    # 🔥 NAYA: Check agar partner offline hai toh empty list bhejo
    if not request.user.is_online:
        return Response([]) # Kuch nahi dikhayega

    if request.user.role != "partner":
        return Response({"error": "Only partner allowed"}, status=403)

    orders = Order.objects.filter(
        status="pending",
        partner__isnull=True
    ).select_related("user", "address").order_by("-id")
    
    # ✅ FIX: Ye line add karein (partner_address ko define karne ke liye)
    from accounts.models import Address
    partner_address = Address.objects.filter(user=request.user).first()
    
    nearby_orders = []
    
    # 🔥 CHANGE: Distance check karke list mein add karo
    if partner_address and partner_address.latitude:
        for order in orders:
            if order.address and order.address.latitude:
                dist = calculate_distance(
                    partner_address.latitude, partner_address.longitude,
                    order.address.latitude, order.address.longitude
                )
                if dist is not None and dist <= 5.0:
                    nearby_orders.append(order)

    serializer = PartnerOrderSerializer(nearby_orders, many=True)
    return Response(serializer.data)

# Agar Address model kisi aur file me hai toh import kar lena, jaise:
from accounts.models import Address 

from accounts.models import Address # Upar import check kar lena
from accounts.models import Address # Ise file ke upar import kar lena agar nahi hai

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def partner_pending_orders(request):
    
    # 🔥 NAYA: Check agar partner offline hai toh empty list bhejo
    if not request.user.is_online:
        return Response([], status=200) # Kuch nahi dikhayega
    
    
    if request.user.role != "partner":
        return Response({"error": "Only partner allowed"}, status=403)

    # 1. 🔥 Partner ka saved address Database se nikalo
    partner_address = Address.objects.filter(user=request.user).first()

    orders = Order.objects.filter(
        status="pending",
        partner__isnull=True
    ).select_related("user", "address").order_by("-created_at")
       

    serializer = PartnerOrderSerializer(orders, many=True)
    
    # Serializer data ko read-only se hata kar mutable dictionary banaya
    mutable_data = [dict(item) for item in serializer.data]


import requests

def calculate_distance(lat1, lon1, lat2, lon2):
    try:
        # 🔥 ORS ki free API key yahan dalo
        API_KEY = "Tumhari_ORS_Api_Key_Yahan_Aayegi"
        
        # ORS bhi pehle longitude fir latitude leta hai
        url = f"https://api.openrouteservice.org/v2/directions/driving-car?api_key={API_KEY}&start={lon1},{lat1}&end={lon2},{lat2}"
        
        response = requests.get(url, timeout=5)
        data = response.json()

        if 'features' in data:
            distance_in_meters = data['features'][0]['properties']['segments'][0]['distance']
            distance_in_km = distance_in_meters / 1000
            print(f"✅ ORS ROAD DISTANCE: {round(distance_in_km, 2)} KM")
            return round(distance_in_km, 2)
        else:
            print("❌ ORS ERROR:", data)
            return None
            
    except Exception as e:
        print(f"❌ CODE CRASH: {e}")
        return None
# ===============================
# ACCEPT ORDER
# ===============================
from django.utils import timezone # Ye upar import karo
from django.db.models import Max # 🔥 File ke upar check kar lena agar import na ho toh

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def accept_order(request, order_id):

    if request.user.role != "partner":
        return Response({"error": "Only partner allowed"}, status=403)

    try:
        # Check karo ki order pending hai aur kisi ne accept nahi kiya hai
        order = Order.objects.get(id=order_id, status="pending", partner__isnull=True)
    except Order.DoesNotExist:
        return Response({"error": "Order not available"}, status=404)

    # 🔥 MAIN FIX: Partner Wise Counting Logic
    # Hum check karenge ki is partner ke paas pehle se kitne orders hain
    max_num = Order.objects.filter(partner=request.user).aggregate(Max('partner_order_number'))['partner_order_number__max']
    
    if max_num is None:
        order.partner_order_number = 1 # Pehla naya partner = #1
    else:
        order.partner_order_number = max_num + 1 # Purana partner = Pichla + 1

    # Partner assign karo aur status update karo
    order.partner = request.user
    order.status = "accepted"
    now = timezone.now()
    order.accepted_at = now

    # Delivery deadline logic (Aapka purana logic waisa hi hai)
    if order.delivery_mode.lower() == "premium":
        order.deadline = now + timedelta(hours=6)
    elif order.delivery_mode.lower() == "1_day":
        order.deadline = now + timedelta(hours=24)
    else:
        order.deadline = now + timedelta(days=3)

    order.save()
    
    # Baaki notifications aur threading logic same rahega...
    threading.Thread(
        target=send_deadline_push,
        args=(order.id,)
    ).start()

    create_notification(
        user=order.user,
        title="Order Accepted",
        message=f"Your order #{order.id} has been accepted by partner",
        icon_type="check"
    )

    token = getattr(order.user, "fcm_token", None)
    if token:
        try:
            send_push(
                token,
                "Order Accepted",
                f"Your order #{order.id} has been accepted by partner"
            )
        except Exception as e:
            print("Push notification failed:", e)        

    return Response({
        "message": "Order accepted",
        "partner_order_number": order.partner_order_number # Flutter ke liye return kar diya
    })

# Customer Order History
class CustomerOrderListView(generics.ListAPIView):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(
            user=self.request.user
        ).order_by("-created_at")
        
# Partner Pending Orders
# Partner Pending Orders (Asli wali Class jahan API hit ho rahi hai)
# Partner Pending Orders (Asli wali Class jahan API hit ho rahi hai)
class PartnerPendingOrdersView(generics.ListAPIView):
    serializer_class = PartnerOrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        # 1. Orders nikalo
        
          # 🔴 STEP 1: Agar partner OFFLINE hai
        if not request.user.is_online:
            return Response([])

        # 🔴 STEP 2: Role check
        if request.user.role != "partner":
            return Response({"error": "Only partner allowed"}, status=403)
        
        orders = Order.objects.filter(
            status="pending", 
            partner__isnull=True
        ).select_related("address").order_by("-created_at")

        # 2. Partner ka address nikalo
        from accounts.models import Address
        partner_address = Address.objects.filter(user=request.user).first()

        serializer = PartnerOrderSerializer(orders, many=True)
        mutable_data = [dict(item) for item in serializer.data]
        filtered_nearby_data = []

        # 3. Asli Distance calculate karo (Sirf DB values se)
        for index, order in enumerate(orders):
            # Customer ki DB Location
            c_lat = getattr(order.address, 'latitude', None) if order.address else None
            c_lng = getattr(order.address, 'longitude', None) if order.address else None

            # Partner ki DB Location
            p_lat = getattr(partner_address, 'latitude', None) if partner_address else None
            p_lng = getattr(partner_address, 'longitude', None) if partner_address else None

            # 🔥 ASLI LOGIC: Agar dono ke DB mein real location hai, tabhi calculate karo
            if p_lat and p_lng and c_lat and c_lng:
                dist = calculate_distance(p_lat, p_lng, c_lat, c_lng)
                # 🔥 ASLI CHANGE: Agar distance 5km ke barabar ya kam hai tabhi add karo
                if dist is not None and dist <= 5.0:
                    order_data = PartnerOrderSerializer(order).data
                    order_data['distance'] = dist
                    filtered_nearby_data.append(order_data)
                mutable_data[index]['distance'] = dist
            else:
                mutable_data[index]['distance'] = None

        # 4. Sort (Kam distance wale upar)
        mutable_data = sorted(mutable_data, key=lambda x: x.get('distance') if x.get('distance') is not None else 9999)
        filtered_nearby_data = sorted(filtered_nearby_data, key=lambda x: x.get('distance', 9999))

        return Response(filtered_nearby_data)


    
class PartnerAssignedOrdersView(generics.ListAPIView):
    serializer_class = PartnerOrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(
            partner=self.request.user
        ).order_by("-created_at")                




class PartnerAcceptedOrders(APIView):
    permission_classes = [IsAuthenticated]
    

    def get(self, request):

        if request.user.role != "partner":
            return Response(
                {"error": "Only partner allowed"},
                status=403
            )

        orders = Order.objects.filter(
            partner=request.user,
            status="accepted"
        ).select_related("user", "address").order_by("-created_at")

        serializer = PartnerOrderSerializer(orders, many=True)
        return Response(serializer.data)    

#cancel order by customer
# orders/views.py
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_order(request, pk):
    try:
        order = Order.objects.get(id=pk, user=request.user)

        # 1. Check karo delivered toh nahi hai
        if order.status == "delivered":
            return Response({"error": "Delivered order cannot be cancelled"}, status=400)

        # 🔥 IMPORTANT: Status change se pehle check karein ki partner assigned hai ya nahi
        partner_to_notify = order.partner
        # Agar status 'accepted' tha aur partner assigned tha, tabhi notification bhejni hai
        was_accepted = order.status == "accepted" and partner_to_notify is not None

        # 2. Status update aur save
        order.status = "cancelled"
        order.save()
        
        # 3. 🔥 TARGETED LOGIC: Sirf usi partner ko notification jaye jisne accept kiya tha
        if was_accepted:
            from notification.models import Notification as AppNotification
            
            # A. Database Notification (Sirf assigned partner ke liye)
            AppNotification.objects.create(
                user=partner_to_notify,
                title="Order Cancelled ❌",
                message=f"Order #{order.id} jo aapne accept kiya tha, wo customer ne cancel kar diya hai.",
                icon_type="cancel"
            )

            # B. Targeted Push (Sirf assigned partner ke phone par)
            if partner_to_notify.fcm_token:
                try:
                    # 'notification' object add karna zaroori hai bahar dikhane ke liye
                    notification_payload = {
                        "title": "Order Cancelled ❌",
                        "body": f"Afsos! Order #{order.id} cancel ho gaya hai."
                    }
                    send_push(
                        token=partner_to_notify.fcm_token,
                        title="Order Cancelled ❌",
                        body=f"Afsos! Order #{order.id} cancel ho gaya hai.",
                        data={
                            "type": "order_cancelled",
                            "order_id": str(order.id),
                            "title": notification_payload["title"],
                            "body": notification_payload["body"],
                        }
                    )
                except Exception as e:
                    print(f"Push failed: {e}")
        
        # NOTE: Humne yahan se 'partners = User.objects.filter...' wala 
        # broadcast logic hata diya hai taaki sabko faltu notifications na jayein.

        return Response({"message": "Order cancelled successfully"}, status=200)

    except Order.DoesNotExist:
        return Response({"error": "Order not found"}, status=404)

# ===============================
# COMPLETE ORDER
# ===============================
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def complete_order(request, order_id):

    if request.user.role != "partner":
        return Response({"error": "Only partner allowed"}, status=403)

    try:
        order = Order.objects.get(
            id=order_id,
            partner=request.user,
            status="accepted"
        )
    except Order.DoesNotExist:
        return Response({"error": "Order not found"}, status=404)

    order.status = "delivered"
    order.save()
    
    create_notification(
    user=order.user,
    title="Order Delivered",
    message="Your laundry order has been delivered",
    icon_type="delivery"
    )
    
    # 🔥 PUSH ADD KARO
    token = getattr(order.user, "fcm_token", None)

    if token:
        try:
            send_push(
                token,
                "Order Delivered 🎉",
                "Your laundry order has been delivered"
            )
        except Exception as e:
            print("Push failed:", e)
    

    return Response({"message": "Order completed"}, status=200)
# ===============================
# PARTNER ACTIVE ORDERS
# ===============================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def partner_accepted_orders(request):

    if request.user.role != "partner":
        return Response({"error": "Only partner allowed"}, status=403)

    orders = Order.objects.filter(
        partner=request.user,
        status__in=["accepted", "pickup", "processing", "shipping"]
    ).select_related("user", "address").order_by("-created_at")

    serializer = PartnerOrderSerializer(orders, many=True)
    return Response(serializer.data)

# ===============================
# PARTNER ORDER HISTORY (DELIVERED)
# ===============================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def partner_order_history(request):
    if request.user.role != "partner":
        return Response({"error": "Only partner allowed"}, status=403)

    # Sirf wahi orders nikalo jo delivered ho chuke hain
    orders = Order.objects.filter(
        partner=request.user,
        status="delivered" 
    ).select_related("user", "address").order_by("-created_at")

    serializer = PartnerOrderSerializer(orders, many=True)
    return Response(serializer.data)

# Distance nikalne ka formula
def calculate_distance(lat1, lon1, lat2, lon2):
    try:
        lat1, lon1, lat2, lon2 = float(lat1), float(lon1), float(lat2), float(lon2)
        r = 6371 # Earth radius in KM
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
        dlon = lon2 - lon1 
        dlat = lat2 - lat1 
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a)) 
        return round(c * r, 2) # Return in KM
    except:
        return None


from django.db import transaction

@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_order_status(request, order_id):
    if request.user.role != "partner":
        return Response({"error": "Only partners can update status"}, status=403)

    try:
        order = Order.objects.get(id=order_id, partner=request.user)
    except Order.DoesNotExist:
        return Response({"error": "Order not found or not assigned to you"}, status=404)
     
    order = Order.objects.get(id=order_id)  # partner wallet ke liye
    new_status = request.data.get('status')
    
    #partner walltet ke liye
    # orders/views.py mein update_order_status ke andar

    if new_status == "delivered" and order.status != "delivered":
       with transaction.atomic():
        # 1. Pehle Partner ka wallet dhoondo (Taki commission rate mil sake)
        wallet, created = PartnerWallet.objects.get_or_create(partner=order.partner)
        
        # 🔥 FIX 1: Agar naya wallet hai toh balance ko 0.00 set karo (taki None error na aaye)
        current_balance = Decimal(str(wallet.balance)) if wallet.balance else Decimal('0.00')
        # 🔥 FIX: Variable ko sahi se define kiya
        # 🔥 FIX: Commission ko Decimal mein convert kiya
        p_rate = wallet.commission_rate if wallet.commission_rate else 1.00
        commission_percent = Decimal(str(p_rate))        
        # 🔥 FIX 2: Amount ko safely Decimal mein badlo (agar null ho toh 0 lo)
        order_amt = order.total_amount if order.total_amount else 0
        # 2. Calculation (Decimal use karna zaroori hai error se bachne ke liye)
        total_order_amount = Decimal(str(order_amt))
        admin_commission = (total_order_amount * commission_percent) / Decimal('100')
        partner_share = total_order_amount - admin_commission

       # 3. Wallet balance update (Purana balance + Naya share)
        wallet.balance = current_balance + partner_share
        wallet.save()

        # 4. Order status update
        order.status = "delivered"
        order.save()
        
        print(f"✅ Commission Applied: Admin {admin_commission}, Partner {partner_share}")
    
    # 🔥 Yahan 'shipping' add kar diya hai
    valid_statuses = ['accepted', 'pickup', 'processing', 'shipping', 'delivered', 'cancelled']
    
    if new_status not in valid_statuses:
        return Response({"error": "Invalid status"}, status=400)

    order.status = new_status
    order.save()
    
    # --- NOTIFICATION LOGIC (FIXED) ---
    notification_data = {
        'accepted': {"title": "Order Accepted! ✅", "msg": f"Your order #{order.id} has been accepted.", "icon": "check"},
        'pickup': {"title": "Clothes Picked Up 🚚", "msg": f"Our partner has picked up your clothes for order #{order.id}.", "icon": "delivery"},
        'processing': {"title": "Order Processing ⚙️", "msg": f"Your clothes are being cleaned for order #{order.id}.", "icon": "default"},
        'shipping': {"title": "Out for Delivery 🛵", "msg": f"Your clean clothes are on the way for order #{order.id}!", "icon": "delivery"},
        'delivered': {"title": "Order Delivered 🎉", "msg": f"Order #{order.id} is delivered. Enjoy your fresh clothes!", "icon": "check"},
    }

    if new_status in notification_data:
        data = notification_data[new_status]
    
        Notification.objects.create(
            user=order.user,
            title=data['title'],
            message=data['msg'],
            icon_type=data['icon']
        )
    
    token = order.user.fcm_token
    if token:
        try:
            send_push(
    token,
    notification_data[new_status]["title"],
    notification_data[new_status]["msg"]
)
        except Exception as e:
            print("Push failed:", e)
    

    return Response({
        "message": f"Order status updated to {new_status}",
        "status": order.status
    }, status=200)
    
    
    
    
# ===============================
# PAYMENT VIEWS (UPDATED)
# ===============================

# Razorpay Client Setup
client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

@api_view(['POST'])
def create_razorpay_order(request):
    try:
        amount = Decimal(str(request.data.get('amount')))
    except:
        return Response({"error": "Invalid amount"}, status=400)
        
    razorpay_amount = int(amount) * 100

    data = {
        "amount": razorpay_amount,
        "currency": "INR",
        "payment_capture": 1
    }

    try:
        # 1. Sirf Razorpay se order id generate hogi
        razorpay_order = client.order.create(data=data)

        # 🔥 FIX: Yahan se Order.objects.create(...) hata diya gaya hai!
        # Ab database mein ₹0 wala fokat ka order nahi banega.

        return Response({
            "order_id": razorpay_order['id'],
            "amount": razorpay_amount,
            "currency": "INR"
        })

    except Exception as e:
        return Response({"error": str(e)}, status=400)


from payments.models import Payment

@api_view(['POST'])
def verify_razorpay_payment(request):
    data = request.data
    razorpay_order_id = request.data.get('razorpay_order_id')
    razorpay_payment_id = request.data.get('razorpay_payment_id')
    razorpay_signature = request.data.get('razorpay_signature')
    amount = data.get('amount') # Flutter se amount bhi bhejna padega

    params_dict = {
        'razorpay_order_id': razorpay_order_id,
        'razorpay_payment_id': razorpay_payment_id,
        'razorpay_signature': razorpay_signature
    }

    try:
        # 🔥 FIX: Sirf Razorpay ke signature ko verify karenge
        client.utility.verify_payment_signature(params_dict)

        # Yahan se order ko dhoondh kar update karne ka logic hata diya hai.
        # Kyunki asli order ab Flutter payment success hone ke baad banayega!
        
        # ✅ YE HAI ASLI KAAM: Database mein save karna
        Payment.objects.create(
            user=request.user, # Login user
            razorpay_order_id=razorpay_order_id,
            razorpay_payment_id=razorpay_payment_id,
            amount= int(amount), # Jo amount Flutter se aaya
            payment_method='online',
            status='success'
        )

        return Response({
            "verified": True,
            "message": "Payment Verified Successfully"
        })

    except Exception as e:
        # 🟢 Terminal mein asli error dekhne ke liye ye print karein
        print(f"🔥 PAYMENT ERROR: {str(e)}")
        return Response({
            "verified": False, 
            "error": f"Verification Failed: {str(e)}" # Asli error message bhejein debugging ke liye
        }, status=400)

# orders/views.py

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def partner_complaints(request):
    if request.user.role != "partner":
        return Response({"error": "Unauthorized"}, status=403)
    
    # Partner ke assigned orders ki complaints nikalen
    complaints = Complaint.objects.filter(
        order__partner=request.user
    ).select_related('user', 'order').order_by('-created_at')
    
    data = []
    for c in complaints:
       data.append({
    "id": c.id,

    "order_id": c.order.id if c.order else "General",

    "customer_name": c.user.username if c.user else "Unknown",

    "customer_phone": c.user.phone if hasattr(c.user, 'phone') else "N/A",

    "subject": c.issue if c.issue else "Order Service Issue",

    "description": c.message if c.message else "No details provided",

    "status": c.status,

    "date": c.created_at.strftime("%d %b %Y")
})
    return Response(data)

# orders/views.py
from django.db.models import Sum

# orders/views.py

# orders/views.py
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def partner_earnings(request):
    if request.user.role != "partner":
        return Response({"error": "Unauthorized"}, status=403)

    try:
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)

        # Base Query: Sirf delivered orders
        orders_query = Order.objects.filter(partner=request.user, status="delivered")

        # 🔥 FIX: 'updated_at' ko 'accepted_at' se badal diya kyunki aapke model me wahi hai
        total_today = orders_query.filter(accepted_at__date=today).aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        total_week = orders_query.filter(accepted_at__date__gte=week_ago).aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        total_month = orders_query.filter(accepted_at__date__gte=month_ago).aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        
        # 🔥 NAYA ADDITION: Wallet Balance (Blue card ke liye)
        wallet, _ = PartnerWallet.objects.get_or_create(partner=request.user)
        wallet_balance = wallet.balance
         
        # Pie Chart Logic (Safe Mode)
        pie_data = []
        category_stats = {}
        
        try:
            # Aapke choices me 'order_items' dikh raha hai, wahi use karenge
            # delivered orders ke saare items ka total category wise
            for order in orders_query:
                for item in order.order_items.all():
                    cat_name = item.item.type.name 
                    category_stats[cat_name] = category_stats.get(cat_name, 0) + (item.price * item.quantity)

            chart_total = sum(category_stats.values())
            colors = ["0xFF3B82F6", "0xFF10B981", "0xFFF59E0B", "0xFFEF4444", "0xFF8B5CF6"]

            for i, (name, val) in enumerate(category_stats.items()):
                perc = round((val / chart_total * 100), 1) if chart_total > 0 else 0
                pie_data.append({
                    "title": name,
                    "value": perc,
                    "color": colors[i % len(colors)]
                })
        except Exception as pie_err:
            print(f"Pie Chart Logic Error (Handled): {pie_err}")

        # Agar chart khali hai toh default data
        if not pie_data:
            pie_data = [{"title": "Service", "value": 100, "color": "0xFF3B82F6"}]

        return Response({
            "today": f"₹{total_today}",
            "week": f"₹{total_week}",
            "month": f"₹{total_month}",
            "wallet_balance": str(wallet_balance), # <--- Ye Flutter ko milega
            "pie_data": pie_data
        })

    except Exception as e:
        print(f"🔥 EARNINGS ERROR: {e}")
        return Response({"error": "Something went wrong on server"}, status=500)
    
# orders/views.py mein naya order create hone ke baad
def notify_partners_new_order(order):
    from accounts.models import User
    from vastrafix.core.firebase import send_push
    
    # 1. Sirf un partners ko dhundo jo Online hain aur jinka role 'partner' hai
    active_partners = User.objects.filter(role='partner', is_online=True).exclude(fcm_token__isnull=True)
    
    for partner in active_partners:
        try:
            send_push(
                token=partner.fcm_token,
                title="Naya Order Aaya! 🧺",
                body=f"Order #{order.id} ke liye naya pickup available hai. Jaldi check karein!",
                channel='partner_orders' # 🔥 Partner wala high-priority channel
            )
        except Exception as e:
            print(f"Partner {partner.id} notification failed: {e}")    
            
            
            
            
#customer radius

from math import radians, cos, sin, asin, sqrt

def get_geo_distance(lat1, lon1, lat2, lon2):
    # Latitude/Longitude ko float mein convert karein
    try:
        lat1, lon1, lat2, lon2 = map(float, [lat1, lon1, lat2, lon2])
        r = 6371  # Earth Radius in KM
        # Radians mein convert karein
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        return c * r
    except:
        return 9999 # Agar koi galti ho toh bahut bada distance return karein            
            
            
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def check_service_area(request):
    user_lat = request.data.get('latitude')
    user_lng = request.data.get('longitude')

    if not user_lat or not user_lng:
        return Response({"error": "Location data missing"}, status=400)

    # 1. Sabhi Active aur Online Partners ka address nikalo
    # Partner ka address 'accounts.Address' model mein hona chahiye
    from accounts.models import Address as UserAddress
    
    active_partners_addresses = UserAddress.objects.filter(
        user__role='partner', 
        user__is_online=True
    ).exclude(latitude__isnull=True)

    is_available = False
    min_distance = 9999

    for p_addr in active_partners_addresses:
        distance = get_geo_distance(user_lat, user_lng, p_addr.latitude, p_addr.longitude)
        
        if distance <= 5.0:  # 🔥 Aapka 5 KM wala rule
            is_available = True
            break # Ek bhi partner mil gaya toh kafi hai
            
    if is_available:
        return Response({
            "available": True,
            "message": "Service is available in your area!"
        }, status=200)
    else:
        return Response({
            "available": False,
            "message": "Currently not available in this area. We serve within 5km of our hubs."
        }, status=200) # 200 isliye taaki Flutter message read kar sake            

     
     


# 1. Wallet aur History dikhane ke liye
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_wallet_details(request):
    wallet, _ = PartnerWallet.objects.get_or_create(partner=request.user)    
    # Pichli requests ki history
    # 1. Partner ki bank details nikalo
    bank = PartnerBankDetail.objects.filter(partner=request.user).first()
    
    bank_info = None
    if bank:
        # Sirf tabhi data bhejo jab account verified ho ya kam se kam exist karta ho
        bank_info = {
            "bank_name": bank.bank_name,
            "account_number": bank.account_number,
            "upi_id": bank.upi_id,
            "status": bank.status
        }
    requests = PayoutRequest.objects.filter(partner=request.user).order_by('-created_at')
    request_list = []
    for r in requests:
        request_list.append({
            "id": r.id,
            "amount": str(r.amount),
            "status": r.status,
            "upi_id": r.upi_id,
            "date": r.created_at.strftime("%d %b %Y")
        })
    return Response({
        "balance": str(wallet.balance),
        "bank_details": bank_info, # 🔥 Ye Flutter ko "Please add bank..." se bachayega
        "requests": [
            {
                "amount": str(r.amount),
                "status": r.status,
                "date": r.created_at.strftime("%d %b %Y")
            } for r in requests
        ]
    })

# 2. Payout Request submit karne ke liye
# views.py (Payout Request Logic)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_payout_request(request):
    user = request.user
    try:
        amount = Decimal(str(request.data.get('amount', 0)))
    except:
        return Response({"error": "Invalid amount format"}, status=400)
    
    # 🔥 NAYA CHECK: Minimum 1000 ki limit (Backend Security)
    if amount < 1000:
        return Response({"error": "Minimum payout amount is ₹1000."}, status=400)
    bank = PartnerBankDetail.objects.filter(partner=user, status='verified').first()    
    if not bank:
        return Response({"error": "Verified bank details not found!"}, status=400)
    # 2. Baaki ka purana logic (Balance check etc.)
    
    # 2. Wallet balance check karo
    wallet = PartnerWallet.objects.get(partner=user)
    if amount > wallet.balance:
        return Response({"error": "Insufficient balance"}, status=400)
    
   # 3. Request Create karo (Bank se UPI ID lekar)
    PayoutRequest.objects.create(
        partner=user,
        amount=amount,
        upi_id=bank.upi_id, # 🔥 Ab ye automatic admin panel mein dikhega
        status='pending'
    )
    return Response({"message": "Payout request submitted!"}, status=201)
     
     
#bank details 

from payments.models import PartnerBankDetail

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def manage_bank_details(request):
    if request.method == 'GET':
        bank = PartnerBankDetail.objects.filter(partner=request.user).first()
        if bank:
            return Response({
                "exists": True,
                "account_holder_name": bank.account_holder_name,
                "bank_name": bank.bank_name,
                "account_number": bank.account_number,
                "ifsc_code": bank.ifsc_code,
                "upi_id": bank.upi_id,
                "status": bank.status,
                "admin_note": bank.admin_note,
                "passbook_image": bank.passbook_image.url if bank.passbook_image else None
            })
        return Response({"exists": False})

    elif request.method == 'POST':
        data = request.data
        passbook_file = request.FILES.get('passbook_image') # Flutter se ye key aayegi
        
        # 🔥 FIX: Agar user edit kar raha hai, toh status ko 'pending' kar do
        # Taaki Admin ko pata chale ki details change hui hain.
        
        bank_obj, created = PartnerBankDetail.objects.update_or_create(
            partner=request.user,
            defaults={
                "account_holder_name": data.get('account_holder_name'),
                "bank_name": data.get('bank_name'),
                "account_number": data.get('account_number'),
                "ifsc_code": data.get('ifsc_code', '').upper(),
                "upi_id": data.get('upi_id'),
                "status": 'pending'  # 👈 Edit hote hi status 'pending' ho jayega
            }
        )
        
        # 🔥 Agar naye image upload hui hai toh save karo
        if passbook_file:
            bank_obj.passbook_image = passbook_file
            bank_obj.save()
            
        return Response({"message": "Details updated and sent for re-verification", "status": "pending"}, status=201)
# orders/views.py mein ye add karein
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_order_detail(request, order_id):
    try:
        # User apna hi order dekh sake, isliye filter user=request.user
        # Agar partner bhi dekh sake, to logic thoda change karna hoga
        order = Order.objects.get(id=order_id, user=request.user)
        serializer = OrderSerializer(order)
        return Response(serializer.data)
    except Order.DoesNotExist:
        return Response({"error": "Order not found"}, status=404)


# 1. OTP Generate karke bhejne ki API
from .utils import send_push_notification # Agar aapne utils mein notification function banaya hai

@api_view(['POST'])
def send_delivery_otp(request, order_id):
    try:
        order = Order.objects.get(id=order_id)
        otp = str(random.randint(1000, 9999))
        order.delivery_otp = otp
        order.save()

        # 🔥 UPDATE: Direct User model se fcm_token uthao (Jaisa admin mein dikh raha hai)
        token = order.user.fcm_token 

        if token:
            print(f"DEBUG: Found token for {order.user.username}, sending notification...")
            from .utils import send_push_notification
            
            success = send_push_notification(
                token, 
                "Delivery OTP 🔑", 
                f"Your delivery OTP for Order #{order.id} is {otp}. Please share this code with the partner only after receiving your clothes."
            )
            
            if success:
                print("✅ Notification successfully sent to Firebase!")
            else:
                print("❌ Firebase failed to send notification.")
        else:
            # Agar Admin panel mein token khali hota toh ye chalta
            print(f"⚠️ ERROR: No FCM token found for user: {order.user.username}")

        print(f"DEBUG: Delivery OTP for Order {order_id} is: {otp}")
        return Response({"success": True, "message": "OTP sent to customer"})

    except Order.DoesNotExist:
        return Response({"success": False, "error": "Order not found"})
    except Exception as e:
        print(f"❌ View Error: {e}")
        return Response({"success": False, "error": str(e)})
    

# 2. OTP Verify karke Order Delivered karne ki API
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_delivery_otp(request, order_id):
    otp_received = request.data.get('otp')
    try:
        order = Order.objects.get(id=order_id)
        
        if order.delivery_otp == otp_received:
            order.status = 'delivered'
            order.delivery_otp = None  # Verify hone ke baad OTP clear
            order.save()

            # 🔥 SUCCESS NOTIFICATION: Customer ko batao ki delivery ho gayi
            token = order.user.fcm_token
            if token:
                from .utils import send_push_notification
                send_push_notification(
                    token, 
                    "Order Delivered 🎉", 
                    f"Order #{order.id} has been delivered successfully. Enjoy your fresh clothes!"
                )

            return Response({"success": True, "message": "Order delivered successfully!"})
        else:
            return Response({"success": False, "message": "Invalid OTP. Please check again."}, status=400)
          
    except Order.DoesNotExist:
        return Response({"success": False, "message": "Order not found"}, status=404)