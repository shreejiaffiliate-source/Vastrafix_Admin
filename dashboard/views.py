from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Sum, Count, Q
from django.utils import timezone
from decimal import Decimal
from django.contrib import messages

from accounts.models import User 
from services.models import Category, SubCategory, Item, Complaint 
from orders.models import Order, OrderItem # Naya import OrderItem ke liye
from payments.models import PartnerBankDetail, Payment, PartnerWallet, PayoutRequest
from notification.utils import create_notification
from django.core.paginator import Paginator
from django.contrib.auth import authenticate, login

@user_passes_test(lambda u: u.is_authenticated and u.is_superuser, login_url='login')
def admin_dashboard_view(request):
    today = timezone.now().date()

    # --- 1. DAILY PERFORMANCE SUMMARY (Aaj Kya Hua?) ---
    today_orders_pickup = Order.objects.filter(created_at__date=today, status='accepted').count()
    
    # Aaj ki kamai (Online + COD jo deliver ho gaye)
    today_online_revenue = Payment.objects.filter(created_at__date=today, status='Success').aggregate(Sum('amount'))['amount__sum'] or 0
    today_cod_revenue = Order.objects.filter(created_at__date=today, status='delivered', payment_mode='COD').aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    today_total_earnings = (today_online_revenue / 100) + float(today_cod_revenue)
    
    # Active Partners (Duty par kitne hain)
    online_partners_count = User.objects.filter(role='partner', is_online=True).count()


    # --- 2. PARTNER LEADERBOARD & WALLET STATUS ---
    # Top 5 Partners (Delivered orders ke basis par)
    top_partners = User.objects.filter(role='partner').annotate(
        delivered_count=Count('assigned_orders', filter=Q(assigned_orders__status='delivered'))
    ).order_by('-delivered_count')[:5]

    # Wallets checking for negative/low balance (Danger zone)
    low_balance_wallets = PartnerWallet.objects.filter(balance__lt=500).select_related('partner')[:5]


    # --- 3. SERVICE-WISE ANALYTICS (Popular Services) ---
    # Kaunse kapde/service sabse zyada order ho rahi hai
    service_stats = OrderItem.objects.values('item__type__name').annotate(
        total_qty=Sum('quantity')
    ).order_by('-total_qty')[:5]


    # --- 4. EXISTING STATS (Total Details) ---
    total_users = User.objects.filter(is_staff=False).count()
    total_orders = Order.objects.count()
    recent_orders = Order.objects.all().order_by('-id')[:5]
    
    # 🔥 FIXED TOTAL REVENUE LOGIC:
    # Online ho ya COD, agar order 'delivered' hai, toh wo revenue hai.
    total_revenue_val = Order.objects.filter(status='delivered').aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    total_revenue = float(total_revenue_val)

    # Admin Profit (1% of Delivered Orders)
    admin_profit = (total_revenue * 1) / 100 

    total_delivered_val = Order.objects.filter(status='delivered').aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    admin_profit = (float(total_delivered_val) * 1) / 100
    
    pending_payouts_count = PayoutRequest.objects.filter(status='pending').count()
    total_wallet_balance = PartnerWallet.objects.aggregate(Sum('balance'))['balance__sum'] or 0
    pending_complaints = Complaint.objects.filter(status='Pending').count()

    context = {
        # Today's Summary
        'today_orders_pickup': today_orders_pickup,
        'today_total_earnings': round(today_total_earnings, 2),
        'online_partners_count': online_partners_count,
        
        # Leaderboard & Wallets
        'top_partners': top_partners,
        'low_balance_wallets': low_balance_wallets,
        
        # Analytics
        'service_stats': service_stats,
        
        # Totals
        'total_users': total_users,
        'total_orders': total_orders,
        'recent_orders': recent_orders,
        'total_revenue': total_revenue,
        'admin_profit': round(admin_profit, 2),
        'pending_payouts_count': pending_payouts_count,
        'total_wallet_balance': total_wallet_balance,
        'pending_complaints': pending_complaints,
    }
    return render(request, 'dashboard/admin_dashboard.html', context)

# ... Baaki ke functions (inventory, user_list, etc.) wahi rahenge

# 1. Update Item Price function mein
@user_passes_test(lambda u: u.is_superuser)
def update_item_price(request, item_id):
    if request.method == "POST":
        new_price = request.POST.get('new_price')
        item = get_object_or_404(Item, id=item_id)
        item.price = new_price
        item.save()
        messages.success(request, f"{item.name} ki price update ho gayi!")
    # 🔥 Yahan badlav karein: admin_inventory ki jagah admin_items
    return redirect('admin_items') 

# 2. Add New Category function mein
@user_passes_test(lambda u: u.is_superuser)
def add_new_category(request):
    if request.method == "POST":
        category_name = request.POST.get('category_name')
        if category_name:
            Category.objects.create(name=category_name)
            messages.success(request, "Nayi category add ho gayi!")
    # 🔥 Yahan badlav karein: admin_categories par redirect karein
    return redirect('admin_categories')

# 3. Add New Item function mein
@user_passes_test(lambda u: u.is_superuser)
def add_new_item(request):
    if request.method == "POST":
        # ... aapka purana item create logic ...
        messages.success(request, "Naya item add ho gaya!")
    # 🔥 Yahan bhi admin_items par redirect karein
    return redirect('admin_items')

# --- 1. CATEGORY MANAGEMENT ---
@user_passes_test(lambda u: u.is_superuser)
def admin_categories_view(request):
    categories = Category.objects.all().order_by('-id')
    return render(request, 'dashboard/categories.html', {'categories': categories})

@user_passes_test(lambda u: u.is_superuser)
def toggle_category_status(request, cat_id):
    category = get_object_or_404(Category, id=cat_id)
    # Ensure your model has 'is_active' field
    category.is_active = not category.is_active 
    category.save()
    messages.success(request, f"Category '{category.name}' status updated.")
    return redirect('admin_categories')

@user_passes_test(lambda u: u.is_superuser)
def delete_category(request, cat_id):
    category = get_object_or_404(Category, id=cat_id)
    category.delete()
    messages.warning(request, "Category delete ho gayi hai.")
    return redirect('admin_categories')

# --- 2. ITEM MANAGEMENT (With Paging) ---
@user_passes_test(lambda u: u.is_superuser)
def admin_items_view(request):
    search_query = request.GET.get('search', '')
    
    # 🔥 FIXED: Aapke model ke hisaab se 'type' aur 'subcategory' use kiya hai
    items_list = Item.objects.select_related('type', 'subcategory').all().order_by('-id')
    
    if search_query:
        items_list = items_list.filter(name__icontains=search_query)

    paginator = Paginator(items_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Add item modal ke liye dropdowns
    categories = Category.objects.filter(is_active=True)
    subcategories = SubCategory.objects.all()

    return render(request, 'dashboard/items.html', {
        'items': page_obj,
        'categories': categories,
        'subcategories': subcategories,
        'search_query': search_query
    })

@user_passes_test(lambda u: u.is_superuser)
def toggle_item_status(request, item_id):
    item = get_object_or_404(Item, id=item_id)
    item.is_active = not item.is_active
    item.save()
    return redirect('admin_items')


# user show karne ke liye
@user_passes_test(lambda u: u.is_superuser)
def user_list_view(request):
    # 1. Role hamesha pakdo, kuch na mile toh 'customer'
    role_filter = request.GET.get('role', 'customer') 
    status_filter = request.GET.get('status')
    
    # 2. Pehle hi role se filter kar do (Taaki mix na ho)
    users_list = User.objects.filter(role=role_filter).exclude(is_superuser=True).order_by('-id')
    
    # 3. Phir usi role ke andar status check karo
    if status_filter == 'active':
        users_list = users_list.filter(is_active=True)
    elif status_filter == 'inactive':
        users_list = users_list.filter(is_active=False)

    # Paging Logic
    paginator = Paginator(users_list, 10)
    page_number = request.GET.get('page')
    users_obj = paginator.get_page(page_number)

    return render(request, 'dashboard/users.html', {
        'users': users_obj,
        'current_role': role_filter,
        'current_status': status_filter,
        'page_title': "Customers" if role_filter == 'customer' else "Partners"
    })
# 1. User ki detail dekhne ke liye
@user_passes_test(lambda u: u.is_superuser)
def user_detail_view(request, user_id):
    customer = get_object_or_404(User, id=user_id)
    
    # 🔥 FIXED WALLET LOGIC 🔥
    wallet_balance = 0
    if customer.role == 'partner':
        # Hum PartnerWallet ki table mein manually filter maar rahe hain
        # Yahan 'partner=customer' check karo, agar model mein field ka naam 'user' hai toh 'user=customer' kar dena
        wallet_obj = PartnerWallet.objects.filter(partner=customer).first()
        if wallet_obj:
            wallet_balance = wallet_obj.balance
            print(f"DEBUG: Wallet mil gaya! Balance hai: {wallet_balance}") # Console mein check karne ke liye
        else:
            print("DEBUG: Is partner ka wallet database mein mila hi nahi!")

    # Baki activities aur paging wala logic...
    activities_list = Order.objects.filter(partner=customer).order_by('-id') if customer.role == 'partner' else Order.objects.filter(user=customer).order_by('-id')
    
    paginator = Paginator(activities_list, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'dashboard/user_detail.html', {
        'customer': customer,
        'wallet_balance': wallet_balance, # 🔥 Ye variable hum bhej rahe hain
        'activities': page_obj,
    })

# 2. User ko block/unblock karne ke liye
@user_passes_test(lambda u: u.is_superuser)
def toggle_user_status(request, user_id):
    customer = get_object_or_404(User, id=user_id)
    # Toggle status: agar True hai toh False kar do, aur vice versa
    customer.is_active = not customer.is_active
    customer.save()
    return redirect('admin_users')

# Saare orders dikhane ke liye
@user_passes_test(lambda u: u.is_superuser)
def order_list_view(request):
    status_filter = request.GET.get('status')
    search_query = request.GET.get('search')
    
    orders_list = Order.objects.all().order_by('-id')
    
    if status_filter:
        orders_list = orders_list.filter(status=status_filter)
    
    if search_query:
        orders_list = orders_list.filter(
            Q(id__icontains=search_query.replace('#VF-', '')) | 
            Q(user__username__icontains=search_query) |
            Q(user__phone__icontains=search_query) # 🔥 phone_number ki jagah sirf phone
        )

    # 🔥 Paging: 10 orders per page
    paginator = Paginator(orders_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'dashboard/orders.html', {
        'orders': page_obj,
        'current_status': status_filter
    })

# Order ka status change karne ke liye (e.g. Pending -> Picked up)
@user_passes_test(lambda u: u.is_superuser)
def update_order_status(request, order_id):
    if request.method == "POST":
        new_status = request.POST.get('status')
        order = get_object_or_404(Order, id=order_id)
        order.status = new_status
        if new_status == 'delivered' and order.payment_mode.lower() == 'cod':
            order.is_paid = True
        order.save()
    return redirect('admin_orders')

# pending order view 
@user_passes_test(lambda u: u.is_superuser)
def pending_orders_action_view(request):
    # Sirf wo orders jo abhi tak assign nahi huye ya 'accepted' hain
    pending_orders = Order.objects.filter(status='accepted').order_by('-id')
    
    # Saare partners ki list taaki dropdown mein dikha sakein
    partners = User.objects.filter(role='partner', is_active=True)
    
    return render(request, 'dashboard/pending_action.html', {
        'orders': pending_orders,
        'partners': partners
    })

# partner assign in order 
@user_passes_test(lambda u: u.is_superuser)
def assign_partner(request, order_id):
    if request.method == "POST":
        partner_id = request.POST.get('partner_id')
        order = get_object_or_404(Order, id=order_id)
        partner = get_object_or_404(User, id=partner_id)
        
        order.partner = partner # Maan ke chal rahe hain aapke Order model mein partner field hai
        order.status = 'pickup' # Assign hote hi status 'pickup' kar dete hain
        order.save()
        
    return redirect('pending_orders_action')

# complaint view
@user_passes_test(lambda u: u.is_superuser)
def complaint_list_view(request):
    complaint_type = request.GET.get('type') # Filter: 'customer' or 'partner'
    
    # Base Query: Order aur Partner ko select_related se fetch karenge taaki performance bani rahe
    query = Complaint.objects.select_related('user', 'order', 'order__partner').all().order_by('-id')
    
    if complaint_type == 'customer':
        query = query.filter(user__role='customer')
    elif complaint_type == 'partner':
        query = query.filter(user__role='partner')

    pending_count = Complaint.objects.filter(status__iexact='pending').count()
    
    return render(request, 'dashboard/complaints.html', {
        'complaints': query,
        'pending_count': pending_count,
        'current_filter': complaint_type
    })

# compaint solve 
@user_passes_test(lambda u: u.is_superuser)
def resolve_complaint(request, complaint_id):
    if request.method == "POST":
        complaint = get_object_or_404(Complaint, id=complaint_id)
        complaint.status = 'Resolved' # Ya jo bhi aapka status field ho
        complaint.save()
    return redirect('admin_complaints')

#order detail 
@user_passes_test(lambda u: u.is_superuser)
def order_detail_view(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    items = order.order_items.all()
    
    # 1. Sabse pehle Order se linked payment dhoondo
    payment_info = Payment.objects.filter(order=order).first()

    # 2. 🔥 AGAR NA MILE: Toh Razorpay Order ID se dhoondo (Back-up Logic)
    if not payment_info:
        # Hum check kar rahe hain ki kya koi aisi payment padi hai jo is order ki ho sakti hai
        # Razorpay payments mein aksar hum 'amount' aur 'user' se match kar sakte hain
        payment_info = Payment.objects.filter(
            user=order.user, 
            amount=int(order.total_amount * 100), # Paise mein conversion
            status='Success'
        ).first()
        
        # Agar mil gayi toh link kardo taaki agli baar ke liye permanent ho jaye
        if payment_info:
            payment_info.order = order
            payment_info.save()

    # 3. Status Update Logic
    if order.status == 'delivered' and order.payment_mode.lower() == 'cod':
        order.is_paid = True
        order.save()
    elif payment_info and payment_info.status == 'Success':
        order.is_paid = True
        order.save()

    return render(request, 'dashboard/order_detail.html', {
        'order': order, 
        'items': items,
        'payment' : payment_info 
    })

# fine in partner
@user_passes_test(lambda u: u.is_superuser)
def fine_partner_view(request, complaint_id):
    if request.method == "POST":
        complaint = get_object_or_404(Complaint, id=complaint_id)
        amount = request.POST.get('fine_amount', 50) # Default 50 rupaye saja
        
        if complaint.order and complaint.order.partner:
            partner = complaint.order.partner
            # Yahan hum maan rahe hain ki aapne model mein 'fine_balance' rakha hai
            # Agar nahi hai, toh hum 'Penalty' table mein entry kar sakte hain
            
            # Complaint ko resolve mark karein
            complaint.status = 'Resolved'
            complaint.message += f"\n\n[ADMIN ACTION: Fine of ₹{amount} imposed on Partner]"
            complaint.save()
            
            # Message dikhane ke liye (Optional)
            # messages.success(request, f"Fine of ₹{amount} imposed on {partner.username}")

    return redirect('admin_complaints')

# Partner Withdraw request
@user_passes_test(lambda u: u.is_superuser)
def payout_requests_view(request):
    # Sabse pehle saari requests fetch karein
    requests_list = PayoutRequest.objects.select_related('partner', 'partner__bank_details').all().order_by('-created_at')
    
    # 🔥 Paging: 10 requests per page
    paginator = Paginator(requests_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'dashboard/payouts.html', {'requests': page_obj})

@user_passes_test(lambda u: u.is_superuser)
def approve_payout(request, payout_id):
    if request.method == "POST":
        payout = get_object_or_404(PayoutRequest, id=payout_id)
        
        # 1. Bank details check karna abhi bhi zaroori hai
        bank_details = getattr(payout.partner, 'bank_details', None)
        
        if not bank_details or bank_details.status != 'verified':
            messages.error(request, f"❌ {payout.partner.username} ka bank account verified nahi hai!")
            return redirect('admin_payouts')

        try:
            # 2. 🔥 MANUAL APPROVE LOGIC 🔥
            payout.status = 'processed'
            payout.save() # Isse aapke model ka wallet deduction logic apne aap chal jayega
            
            # 3. Partner ko khushkhabri (Notification) bhej do
            create_notification(
                user=payout.partner,
                title="Payout Processed 💸",
                message=f"Hi {payout.partner.username}, your payout request for ₹{payout.amount} has been processed successfully and sent to your bank account."
            )
            
            messages.success(request, f"✅ {payout.partner.username} ka payout successfully approve ho gaya!")

        except ValueError as e:
            # Agar balance kam hone ka error aapke model se aata hai
            messages.error(request, f"❌ Balance Issue: {str(e)}")
        except Exception as e:
            messages.error(request, f"⚠️ Error: {str(e)}")
            
    return redirect('admin_payouts')


@user_passes_test(lambda u: u.is_superuser)
def reject_payout(request, payout_id):
    if request.method == "POST":
        payout = get_object_or_404(PayoutRequest, id=payout_id)
        payout.status = 'rejected'
        payout.save()
        messages.warning(request, f"🚫 Payout request for {payout.partner.username} has been rejected.")
    
    return redirect('admin_payouts')

# all partenr show wallets
@user_passes_test(lambda u: u.is_superuser)
def admin_partner_wallets_view(request):
    # Saare partners ke wallets ko select_related ke saath fetch karein
    wallets = PartnerWallet.objects.select_related('partner').all().order_by('-balance')
    
    total_balance = wallets.aggregate(Sum('balance'))['balance__sum'] or 0
    
    return render(request, 'dashboard/partner_wallets_list.html', {
        'wallets': wallets,
        'total_balance': total_balance
    })
    
    
# bank verify 

# A. Saari pending bank details dekhne ke liye
@user_passes_test(lambda u: u.is_superuser)
def admin_bank_verifications(request):
    # Sirf 'pending' status wali details dikhao
    status_filter = request.GET.get('status', 'pending') 
    
    details_list = PartnerBankDetail.objects.filter(status=status_filter).order_by('-updated_at')
    pending_count = PartnerBankDetail.objects.filter(status='pending').count()

    # 🔥 PAGING LOGIC (10 items per page)
    paginator = Paginator(details_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'dashboard/bank_verifications.html', {
        'details': page_obj,
        'pending_count': pending_count,
        'current_status': status_filter
    })

@user_passes_test(lambda u: u.is_superuser)
def approve_bank_detail(request, detail_id):
    if request.method == "POST":
        detail = get_object_or_404(PartnerBankDetail, id=detail_id)
        detail.status = 'verified' # Status badal diya
        detail.save()
        messages.success(request, f"✅ {detail.partner.username} ka account verify ho gaya!")
    # Redirect hone par ye row apne aap screen se chali jayegi kyunki ab status 'pending' nahi raha
    return redirect('admin_bank_verifications')

@user_passes_test(lambda u: u.is_superuser)
def reject_bank_detail(request, detail_id):
    if request.method == "POST":
        detail = get_object_or_404(PartnerBankDetail, id=detail_id)
        reason = request.POST.get('reason', 'Invalid Details')
        
        detail.status = 'rejected'
        detail.admin_note = reason
        detail.save()
        
        # English Professional Messages
        notification_title = "Bank Verification Failed ❌"
        notification_body = f"Hi {detail.partner.username}, your bank details have been rejected. Reason: {reason}. Please submit the correct details again."
        
        # 🔥 FIX: Humne 'notification_type' hata diya hai kyunki aapka function ise accept nahi kar raha
        create_notification(
            user=detail.partner,
            title=notification_title,
            message=notification_body
        )

        messages.warning(request, f"Bank details for {detail.partner.username} have been rejected, and a notification has been sent.")
        
    return redirect('admin_bank_verifications')

from django.contrib.auth import logout
def custom_logout(request):
    # Django ka in-built logout function session clear kar dega
    logout(request)
    
    # Ek message dikha do taaki user ko pata chale wo bahar aa gaya hai
    messages.info(request, "👋 Logout Successfully.")
    
    # Logout hone ke baad wapas Login page par bhej do
    return redirect('login')  # Dhyan rakhna ki aapke login page ka URL name 'login' hi ho

def custom_login(request):
    # Agar pehle se login hai toh seedha dashboard par bhej do
    if request.user.is_authenticated and request.user.is_superuser:
        return redirect('custom_dashboard')

    if request.method == 'POST':
        u_name = request.POST.get('username')
        p_word = request.POST.get('password')
        
        # Django ka in-built function jo check karega ki username/password sahi hai ya nahi
        user = authenticate(request, username=u_name, password=p_word)
        
        if user is not None:
            # Check karo ki kya wo asali Admin (superuser) hai
            if user.is_superuser:
                login(request, user)
                messages.success(request, f"Welcome back, Admin {user.username}! 👋")
                return redirect('custom_dashboard')
            else:
                messages.error(request, "❌ Access Denied! Aapke paas Admin Panel ka access nahi hai.")
        else:
            messages.error(request, "❌ Invalid Username or Password. Kripya dubara try karein.")
            
    return render(request, 'dashboard/login.html')