import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

DATA_DIR = Path(__file__).parent

# ----------------- In-Memory Customer & Data Registry -----------------
# We load default curated demo customers and data into memory, and allow dynamic addition up to 50 customers.
_INITIALIZED = False
_CUSTOMERS_REGISTRY: Dict[str, Dict[str, Any]] = {}
_TRANSACTIONS_REGISTRY: List[Dict[str, Any]] = []
_DEVICES_REGISTRY: List[Dict[str, Any]] = []
_LOANS_REGISTRY: List[Dict[str, Any]] = []

def _load_initial_json(filename: str) -> Any:
    filepath = DATA_DIR / filename
    if not filepath.exists():
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

def init_registry() -> None:
    global _INITIALIZED, _CUSTOMERS_REGISTRY, _TRANSACTIONS_REGISTRY, _DEVICES_REGISTRY, _LOANS_REGISTRY
    if _INITIALIZED:
        return
    customers = _load_initial_json("customers.json")
    for c in customers:
        _CUSTOMERS_REGISTRY[c["customer_id"]] = c
    _TRANSACTIONS_REGISTRY = _load_initial_json("transactions.json")
    _DEVICES_REGISTRY = _load_initial_json("devices.json")
    _LOANS_REGISTRY = _load_initial_json("loans.json")
    _INITIALIZED = True

init_registry()

def get_customer_by_id(customer_id: str) -> Optional[Dict[str, Any]]:
    return _CUSTOMERS_REGISTRY.get(customer_id)

def get_all_customers() -> List[Dict[str, Any]]:
    return list(_CUSTOMERS_REGISTRY.values())

def get_account_by_number(account_number: str) -> Optional[Dict[str, Any]]:
    for c in _CUSTOMERS_REGISTRY.values():
        for acc in c.get("accounts", []):
            if acc.get("account_number") == account_number:
                acc_copy = dict(acc)
                acc_copy["customer_id"] = c.get("customer_id")
                return acc_copy
    return None

def get_transactions_by_customer(customer_id: str) -> List[Dict[str, Any]]:
    return [t for t in _TRANSACTIONS_REGISTRY if t.get("customer_id") == customer_id]

def get_transaction_by_id(tx_id: str) -> Optional[Dict[str, Any]]:
    for t in _TRANSACTIONS_REGISTRY:
        if t.get("transaction_id") == tx_id:
            return t
    return None

def update_transaction(tx_id: str, updates: Dict[str, Any]) -> bool:
    for t in _TRANSACTIONS_REGISTRY:
        if t.get("transaction_id") == tx_id:
            t.update(updates)
            return True
    return False

def update_card_status(customer_id: str, card_number_last4: str, new_status: str) -> bool:
    cust = _CUSTOMERS_REGISTRY.get(customer_id)
    if not cust:
        return False
    updated = False
    for card in cust.get("cards", []):
        if card.get("card_number", "").endswith(card_number_last4) or card_number_last4 in card.get("card_number", ""):
            card["status"] = new_status
            updated = True
    return updated

def get_devices_by_customer(customer_id: str) -> List[Dict[str, Any]]:
    return [d for d in _DEVICES_REGISTRY if d.get("customer_id") == customer_id]

def get_loans_by_customer(customer_id: str) -> List[Dict[str, Any]]:
    return [l for l in _LOANS_REGISTRY if l.get("customer_id") == customer_id]

def get_policy_content() -> str:
    policy_path = DATA_DIR / "policies.md"
    if not policy_path.exists():
        return ""
    with open(policy_path, "r", encoding="utf-8") as f:
        return f.read()

# ----------------- Synthetic Dynamic Customer Generator -----------------

FIRST_NAMES = [
    "Aarav", "Aditi", "Ananya", "Dev", "Ishaan", "Kavya", "Manish", "Neha",
    "Pooja", "Rahul", "Rohan", "Sanya", "Tanvi", "Varun", "Vikram", "Zara",
    "Siddharth", "Rhea", "Kiran", "Aditya"
]

LAST_NAMES = [
    "Kapoor", "Verma", "Reddy", "Menon", "Bose", "Choudhury", "Nair", "Deshmukh",
    "Banerjee", "Mehta", "Bhat", "Singhania", "Chatterjee", "Kulkarni", "Malhotra"
]

CITIES = [
    ("Mumbai", "Maharashtra"),
    ("Bengaluru", "Karnataka"),
    ("Delhi", "Delhi"),
    ("Hyderabad", "Telangana"),
    ("Pune", "Maharashtra"),
    ("Chennai", "Tamil Nadu"),
    ("Kolkata", "West Bengal"),
    ("Jaipur", "Rajasthan")
]

MERCHANTS = [
    ("Amazon India", "Shopping"),
    ("Swiggy", "Food"),
    ("Zomato", "Food"),
    ("Starbucks Coffee", "Dining"),
    ("Shell Petrol", "Fuel"),
    ("Nature's Basket", "Groceries"),
    ("BigBasket", "Groceries"),
    ("Uber India", "Travel"),
    ("Apollo Pharmacy", "Medical"),
    ("Croma Electronics", "Electronics"),
    ("Cult.Fit", "Fitness"),
    ("Netflix India", "Entertainment")
]

DEVICE_MODELS = [
    ("iPhone 15", "iOS 18.0"),
    ("Samsung Galaxy S24", "Android 14"),
    ("Google Pixel 8", "Android 15"),
    ("OnePlus 12", "Android 14"),
    ("MacBook Pro M3", "macOS 15.0")
]

def generate_customer(seed: Optional[int] = None) -> Dict[str, Any]:
    """
    Creates a realistic synthetic customer with a seeded random generator.
    The same seed always yields the same customer profile.
    Caps in-memory registry at 50 customers (evicts oldest generated customer if needed).
    """
    rng = random.Random(seed)

    # If seed is provided, use it in the customer_id for deterministic reference
    if seed is not None:
        cust_id = f"CUST_GEN_{seed:04d}"
    else:
        # Generate random unique 4-digit ID
        rand_num = rng.randint(1000, 9999)
        cust_id = f"CUST_GEN_{rand_num}"
        # Avoid collision
        while cust_id in _CUSTOMERS_REGISTRY:
            rand_num = rng.randint(1000, 9999)
            cust_id = f"CUST_GEN_{rand_num}"

    first_name = rng.choice(FIRST_NAMES)
    last_name = rng.choice(LAST_NAMES)
    full_name = f"{first_name} {last_name}"
    email = f"{first_name.lower()}.{last_name.lower()}{rng.randint(10, 99)}@example.com"
    phone = f"+91-{rng.randint(91000, 99999)}-{rng.randint(10000, 99999)}"
    city, state = rng.choice(CITIES)
    address = f"{rng.randint(101, 909)} {rng.choice(['Lotus', 'Green', 'Skyline', 'Heritage', 'Sunrise'])} Residency, {city}, {state}"

    # Financial Profile
    monthly_income = float(rng.choice([35000, 48000, 65000, 85000, 110000, 140000, 195000]))
    credit_score = rng.randint(590, 820)
    existing_emi = float(rng.choice([0, 5000, 12000, 18000, 25000])) if monthly_income > 40000 else float(rng.choice([0, 4000, 8000]))
    kyc_status = "VERIFIED" if rng.random() > 0.05 else "PENDING"

    # Accounts
    clean_id = cust_id.replace("CUST_", "").upper()
    acc_num = f"ACC_{clean_id}_01"
    balance = round(rng.uniform(15000.0, 350000.0), 2)
    accounts = [
        {
            "account_number": acc_num,
            "type": "SAVINGS",
            "currency": "INR",
            "balance": balance,
            "status": "ACTIVE"
        }
    ]

    # Card
    card_last4 = f"{rng.randint(1000, 9999)}"
    card_num = f"4520-8800-1122-{card_last4}"
    cards = [
        {
            "card_number": card_num,
            "type": "CREDIT" if credit_score >= 680 else "DEBIT",
            "status": "ACTIVE",
            "daily_limit": 100000 if credit_score >= 700 else 50000
        }
    ]

    # Trusted Device
    dev_model, dev_os = rng.choice(DEVICE_MODELS)
    device_id = f"DEV_{clean_id}_PRIMARY"
    dev_ip = f"103.{rng.randint(20, 250)}.{rng.randint(1, 254)}.{rng.randint(1, 254)}"
    trusted_device = {
        "device_id": device_id,
        "customer_id": cust_id,
        "device_name": dev_model,
        "os": dev_os,
        "ip_address": dev_ip,
        "location": f"{city}, India",
        "trusted": True,
        "first_seen": "2025-01-15T09:00:00Z",
        "last_seen": "2026-10-11T10:00:00Z"
    }

    # Generate 30 Transactions
    now = datetime(2026, 10, 11, 12, 0, 0, tzinfo=timezone.utc)
    customer_txs = []
    avg_ticket = rng.uniform(800.0, 3200.0)

    for i in range(1, 31):
        ts = (now - timedelta(days=35 - i, hours=i % 7, minutes=(i * 13) % 59)).isoformat()
        merchant_name, category = rng.choice(MERCHANTS)
        tx_amt = round(rng.uniform(0.3 * avg_ticket, 2.2 * avg_ticket), 2)
        tx = {
            "transaction_id": f"TX_{clean_id}_{i:03d}",
            "customer_id": cust_id,
            "account_number": acc_num,
            "amount": tx_amt,
            "currency": "INR",
            "type": "DEBIT",
            "merchant": merchant_name,
            "category": category,
            "timestamp": ts,
            "device_id": device_id,
            "location": f"{city}, India",
            "status": "COMPLETED"
        }
        customer_txs.append(tx)

    # Anomaly Injection: ~30% of the time, inject ONE realistic anomaly pattern
    anomaly_choice = rng.random()
    has_anomaly = anomaly_choice < 0.30
    anomaly_type = None

    if has_anomaly:
        # Pick 1 of 3 anomaly patterns
        pattern_id = rng.choice([1, 2, 3])
        if pattern_id == 1:
            # Pattern A: Foreign + new-device large transaction
            anomaly_type = "FOREIGN_NEW_DEVICE"
            untrusted_device_id = f"DEV_{clean_id}_UNKNOWN_INTL"
            foreign_device = {
                "device_id": untrusted_device_id,
                "customer_id": cust_id,
                "device_name": "Unknown Windows/Linux Terminal",
                "os": "Ubuntu Linux",
                "ip_address": f"185.220.{rng.randint(10, 200)}.{rng.randint(1, 250)}",
                "location": "Amsterdam, Netherlands",
                "trusted": False,
                "first_seen": (now - timedelta(days=1, hours=2)).isoformat(),
                "last_seen": (now - timedelta(days=1, hours=2)).isoformat()
            }
            _DEVICES_REGISTRY.append(foreign_device)
            # Inject into 29th transaction
            foreign_amt = round(avg_ticket * rng.uniform(6.0, 10.0), 2)
            customer_txs[28] = {
                "transaction_id": f"TX_{clean_id}_029",
                "customer_id": cust_id,
                "account_number": acc_num,
                "amount": foreign_amt,
                "currency": "INR",
                "type": "DEBIT",
                "merchant": "Global Lux Electronics B.V.",
                "category": "Electronics",
                "timestamp": (now - timedelta(days=1, hours=2)).isoformat(),
                "device_id": untrusted_device_id,
                "location": "Amsterdam, Netherlands",
                "status": "PENDING_REVIEW",
                "description": "High-value foreign purchase on untrusted device"
            }
        elif pattern_id == 2:
            # Pattern B: Rapid repeated micro/high charges
            anomaly_type = "RAPID_VELOCITY"
            rep_merchant = "CoinGate Global Crypto"
            customer_txs[28] = {
                "transaction_id": f"TX_{clean_id}_029",
                "customer_id": cust_id,
                "account_number": acc_num,
                "amount": 9999.0,
                "currency": "INR",
                "type": "DEBIT",
                "merchant": rep_merchant,
                "category": "Crypto/Investment",
                "timestamp": (now - timedelta(hours=5, minutes=10)).isoformat(),
                "device_id": device_id,
                "location": f"{city}, India",
                "status": "PENDING_REVIEW"
            }
            customer_txs[29] = {
                "transaction_id": f"TX_{clean_id}_030",
                "customer_id": cust_id,
                "account_number": acc_num,
                "amount": 9999.0,
                "currency": "INR",
                "type": "DEBIT",
                "merchant": rep_merchant,
                "category": "Crypto/Investment",
                "timestamp": (now - timedelta(hours=5, minutes=2)).isoformat(),
                "device_id": device_id,
                "location": f"{city}, India",
                "status": "PENDING_REVIEW"
            }
        else:
            # Pattern C: Large night-time spend outlier
            anomaly_type = "NIGHT_OUTLIER"
            large_amt = round(avg_ticket * rng.uniform(7.0, 12.0), 2)
            customer_txs[29] = {
                "transaction_id": f"TX_{clean_id}_030",
                "customer_id": cust_id,
                "account_number": acc_num,
                "amount": large_amt,
                "currency": "INR",
                "type": "DEBIT",
                "merchant": "Apex Watch Gallery",
                "category": "Luxury Goods",
                "timestamp": (now - timedelta(days=1, hours=19, minutes=30)).isoformat(),
                "device_id": device_id,
                "location": f"{city}, India",
                "status": "PENDING_REVIEW"
            }

    # Register into memory collections
    # Enforce maximum registry capacity of 50 customers
    if len(_CUSTOMERS_REGISTRY) >= 50:
        # Evict oldest dynamically generated customer (keep the default curated 3)
        evict_candidates = [cid for cid in _CUSTOMERS_REGISTRY.keys() if cid.startswith("CUST_GEN_")]
        if evict_candidates:
            oldest_id = evict_candidates[0]
            del _CUSTOMERS_REGISTRY[oldest_id]
            # Clean up associated txs, devices, loans
            _TRANSACTIONS_REGISTRY[:] = [t for t in _TRANSACTIONS_REGISTRY if t.get("customer_id") != oldest_id]
            _DEVICES_REGISTRY[:] = [d for d in _DEVICES_REGISTRY if d.get("customer_id") != oldest_id]
            _LOANS_REGISTRY[:] = [l for l in _LOANS_REGISTRY if l.get("customer_id") != oldest_id]

    customer_obj = {
        "customer_id": cust_id,
        "name": full_name,
        "email": email,
        "phone": phone,
        "address": address,
        "kyc_status": kyc_status,
        "monthly_income": monthly_income,
        "existing_emi": existing_emi,
        "credit_score": credit_score,
        "accounts": accounts,
        "cards": cards,
        "anomaly_injected": has_anomaly,
        "anomaly_type": anomaly_type
    }

    _CUSTOMERS_REGISTRY[cust_id] = customer_obj
    _DEVICES_REGISTRY.append(trusted_device)
    _TRANSACTIONS_REGISTRY.extend(customer_txs)

    return customer_obj
