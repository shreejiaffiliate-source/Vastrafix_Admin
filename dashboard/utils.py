import requests
import json
from django.conf import settings

def razorpayx_payout(partner_name, account_number, ifsc, amount, email="test@vastrafix.com"):
    """
    RazorpayX Payout Automation Logic
    """
    BASE_URL = "https://api.razorpay.com/v1/"
    AUTH = (settings.RAZORPAYX_KEY_ID, settings.RAZORPAYX_KEY_SECRET)

    try:
        # STEP 1: Create/Get Contact
        contact_data = {
            "name": partner_name,
            "email": email,
            "type": "vendor",
            "reference_id": f"partner_{partner_name[:10]}"
        }
        contact_res = requests.post(f"{BASE_URL}contacts", json=contact_data, auth=AUTH)
        contact_id = contact_res.json().get('id')

        # STEP 2: Create Fund Account (Bank Details)
        fund_account_data = {
            "contact_id": contact_id,
            "account_type": "bank_account",
            "bank_account": {
                "name": partner_name,
                "ifsc": ifsc,
                "account_number": account_number
            }
        }
        fund_res = requests.post(f"{BASE_URL}fund_accounts", json=fund_account_data, auth=AUTH)
        fund_account_id = fund_res.json().get('id')

        # STEP 3: Create Payout (Asali Paisa Transfer)
        payout_data = {
            "account_number": settings.RAZORPAYX_ACCOUNT_NUMBER,
            "fund_account_id": fund_account_id,
            "amount": int(float(amount) * 100), # Decimal to Paise (e.g. 500.00 -> 50000)
            "currency": "INR",
            "mode": "IMPS",
            "purpose": "payout",
        }
        
        payout_res = requests.post(f"{BASE_URL}payouts", json=payout_data, auth=AUTH)
        return payout_res.json()

    except Exception as e:
        return {"status": "error", "message": str(e)}

