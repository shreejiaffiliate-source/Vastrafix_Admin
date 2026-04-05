# auto_payout_logic.py
from datetime import timezone
from decimal import Decimal

from dashboard.utils import razorpayx_payout
from payments.models import PartnerBankDetail, PartnerWallet, PayoutRequest


def process_monthly_auto_payouts():
    today = timezone.now()
    # Check ki kya aaj 5 tarikh hai (Agar cron job use kar rahe ho toh ye zaroori nahi)
    if today.day != 5:
        return "Aaj 5 tarikh nahi hai, payout skip kiya gaya."

    # 1. Wo saare wallets dhoondo jinka balance 1000 se upar hai
    eligible_wallets = PartnerWallet.objects.filter(balance__gte=1000)
    
    success_count = 0
    for wallet in eligible_wallets:
        partner = wallet.partner
        total_balance = wallet.balance
        
        # 2. 🔥 SAHI CALCULATION (1% Platform Fee)
        # Example: 1000 balance -> 10 Rs Commission -> 990 Transfer
        commission = (total_balance * Decimal('1.00')) / 100
        net_to_transfer = total_balance - commission
        
        # 3. Bank Detail Check
        bank = PartnerBankDetail.objects.filter(partner=partner, status='verified').first()
        
        if bank:
            try:
                # 4. RazorpayX Call (Jo aapne pehle banaya tha)
                # Note: 'amount' humesha Paise mein bhejna hota hai API ko (* 100)
                rx_res = razorpayx_payout(
                    partner_name=bank.account_holder_name,
                    account_number=bank.account_number,
                    ifsc=bank.ifsc_code,
                    amount=float(net_to_transfer),
                    email=partner.email
                )

                if rx_res.get('status') in ['processed', 'processing', 'created']:
                    # 5. Payout Record banana
                    PayoutRequest.objects.create(
                        partner=partner,
                        amount=total_balance,
                        # Maan lete hain aapke model mein ye fields hain:
                        # commission=commission,
                        # net_amount=net_to_transfer,
                        status='processed'
                    )
                    
                    # 6. Wallet Zero karna
                    wallet.balance = 0
                    wallet.save()
                    success_count += 1
                    
            except Exception as e:
                print(f"Error for {partner.username}: {str(e)}")
                
    return f"Processed {success_count} auto-payouts successfully."