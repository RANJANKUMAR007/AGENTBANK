import math
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from data import db
from tools.registry import ToolDefinition, registry

# ----------------- Customer Agent Tools -----------------

class GetCustomerProfileArgs(BaseModel):
    pass

def get_customer_profile(session_customer_id: str, trace_id: str) -> Dict[str, Any]:
    """Retrieve the logged-in customer's profile."""
    cust = db.get_customer_by_id(session_customer_id)
    if not cust:
        return {"error": "Customer not found."}
    return {
        "customer_id": cust["customer_id"],
        "name": cust["name"],
        "email": cust["email"],
        "phone": cust["phone"],
        "address": cust["address"],
        "kyc_status": cust.get("kyc_status", "PENDING"),
        "accounts_count": len(cust.get("accounts", []))
    }

class GetAccountBalanceArgs(BaseModel):
    account_number: Optional[str] = Field(None, description="Optional specific account number. If not provided, returns all accounts.")

def get_account_balance(session_customer_id: str, trace_id: str, account_number: Optional[str] = None) -> Dict[str, Any]:
    """Get balance for one or all accounts of the logged-in customer."""
    cust = db.get_customer_by_id(session_customer_id)
    if not cust:
        return {"error": "Customer not found."}
    
    accounts = cust.get("accounts", [])
    if account_number:
        target = next((a for a in accounts if a["account_number"] == account_number), None)
        if not target:
            return {"error": f"Account {account_number} not found or does not belong to your profile."}
        return {"account": target}
    
    total_balance = sum(a.get("balance", 0.0) for a in accounts)
    return {
        "accounts": accounts,
        "total_balance": round(total_balance, 2),
        "currency": "INR"
    }

class GetTransactionsArgs(BaseModel):
    limit: Optional[int] = Field(5, description="Number of recent transactions to retrieve, default 5")
    category: Optional[str] = Field(None, description="Optional filter by category e.g. Food, Fuel, Electronics")

def get_transactions(session_customer_id: str, trace_id: str, limit: Optional[int] = 5, category: Optional[str] = None) -> Dict[str, Any]:
    """Get recent transactions for the logged-in customer."""
    txs = db.get_transactions_by_customer(session_customer_id)
    if category:
        txs = [t for t in txs if t.get("category", "").lower() == category.lower()]
    
    # Sort reverse chronological by timestamp
    txs = sorted(txs, key=lambda x: x.get("timestamp", ""), reverse=True)
    limit = limit or 5
    sliced = txs[:limit]
    return {
        "count": len(sliced),
        "total_available": len(txs),
        "transactions": sliced
    }

class GetCustomer360Args(BaseModel):
    pass

def get_customer_360(session_customer_id: str, trace_id: str) -> Dict[str, Any]:
    """Consolidated 360-degree view of customer accounts, credit, active loans, and recent activity."""
    cust = db.get_customer_by_id(session_customer_id)
    if not cust:
        return {"error": "Customer not found."}
    
    txs = db.get_transactions_by_customer(session_customer_id)
    txs_sorted = sorted(txs, key=lambda x: x.get("timestamp", ""), reverse=True)
    loans = db.get_loans_by_customer(session_customer_id)
    devices = db.get_devices_by_customer(session_customer_id)
    
    total_balance = sum(a.get("balance", 0.0) for a in cust.get("accounts", []))
    total_loan_outstanding = sum(l.get("outstanding_balance", 0) for l in loans)

    return {
        "customer_id": cust["customer_id"],
        "name": cust["name"],
        "credit_score": cust.get("credit_score"),
        "monthly_income": cust.get("monthly_income"),
        "total_balance": round(total_balance, 2),
        "accounts": cust.get("accounts", []),
        "cards": cust.get("cards", []),
        "active_loans_count": len(loans),
        "total_loan_debt": total_loan_outstanding,
        "trusted_devices_count": len([d for d in devices if d.get("trusted")]),
        "recent_transactions_count": len(txs),
        "last_transaction": txs_sorted[0] if txs_sorted else None
    }


# ----------------- Risk & Fraud Agent Tools -----------------

class GetTransactionDetailsArgs(BaseModel):
    transaction_id: str = Field(..., description="ID of transaction to investigate e.g. TX_PRIYA_029")

def get_transaction_details(session_customer_id: str, trace_id: str, transaction_id: str) -> Dict[str, Any]:
    """Retrieve in-depth details of a specific transaction with customer security verification."""
    tx = db.get_transaction_by_id(transaction_id)
    if not tx:
        return {"error": f"Transaction '{transaction_id}' not found."}
    if tx.get("customer_id") != session_customer_id:
        return {"error": "Security Boundary Violation: Cannot inspect transactions belonging to another customer."}
    return {"transaction": tx}

class ScoreFraudRiskArgs(BaseModel):
    transaction_id: str = Field(..., description="ID of transaction to evaluate for fraud")

def score_fraud_risk(session_customer_id: str, trace_id: str, transaction_id: str) -> Dict[str, Any]:
    """
    Deterministic rule-based fraud scoring algorithm.
    Calculates numerical risk score (0-100) and factors:
    - Amount ratio vs historical average
    - Geo / foreign location
    - Device trust status
    - Velocity
    """
    tx = db.get_transaction_by_id(transaction_id)
    if not tx:
        return {"error": f"Transaction '{transaction_id}' not found."}
    if tx.get("customer_id") != session_customer_id:
        return {"error": "Security Violation: Cross-customer access forbidden."}

    all_txs = db.get_transactions_by_customer(session_customer_id)
    devices = db.get_devices_by_customer(session_customer_id)
    
    # Calculate historical average (excluding this transaction)
    other_txs = [t for t in all_txs if t["transaction_id"] != transaction_id]
    avg_amount = (sum(t["amount"] for t in other_txs) / len(other_txs)) if other_txs else 3000.0
    
    score = 10
    reasons = []

    # 1. Amount Outlier Rule
    amount = tx.get("amount", 0.0)
    if amount > 5 * avg_amount:
        score += 35
        reasons.append(f"Transaction amount ({amount:,.2f} INR) is {amount/avg_amount:.1f}x higher than your average historical spend ({avg_amount:,.2f} INR)")
    elif amount > 2.5 * avg_amount:
        score += 20
        reasons.append(f"Transaction amount is significantly above your regular spending pattern ({avg_amount:,.2f} INR)")

    # 2. Foreign / Unknown Geo Rule
    location = tx.get("location", "")
    customer = db.get_customer_by_id(session_customer_id)
    home_city = "India"
    if "India" not in location and location != "":
        score += 35
        reasons.append(f"Foreign transaction origin detected ({location}) without an international travel notice")

    # 3. Device Trust Rule
    device_id = tx.get("device_id")
    device_obj = next((d for d in devices if d["device_id"] == device_id), None)
    if not device_obj:
        score += 25
        reasons.append(f"Initiated from an unrecognized device ({device_id or 'Unknown'})")
    elif not device_obj.get("trusted", True):
        score += 25
        reasons.append(f"Initiated from an untrusted device ({device_obj.get('device_name')}) located in {device_obj.get('location')}")

    # 4. Rapid Velocity Rule (checking transactions within 1 hour)
    recent_same_day = [
        t for t in all_txs
        if t["transaction_id"] != transaction_id and t.get("merchant") == tx.get("merchant")
    ]
    if len(recent_same_day) >= 1:
        score += 15
        reasons.append(f"Repeated transactions detected with identical merchant '{tx.get('merchant')}' in short timeframe")

    score = min(100, max(0, score))
    
    risk_level = "LOW"
    if score >= 70:
        risk_level = "HIGH"
    elif score >= 35:
        risk_level = "MEDIUM"

    recommended_action = "MONITOR"
    if risk_level == "HIGH":
        recommended_action = "FREEZE_CARD_AND_DISPUTE"
    elif risk_level == "MEDIUM":
        recommended_action = "NOTIFY_CUSTOMER_OTP_STEPUP"

    return {
        "transaction_id": transaction_id,
        "risk_score": score,
        "risk_level": risk_level,
        "risk_factors": reasons,
        "recommended_action": recommended_action,
        "requires_human_approval": risk_level == "HIGH",
        "timestamp": tx.get("timestamp")
    }

class GetDeviceHistoryArgs(BaseModel):
    pass

def get_device_history(session_customer_id: str, trace_id: str) -> Dict[str, Any]:
    """Retrieve logged-in customer's recognized and recent login devices."""
    devices = db.get_devices_by_customer(session_customer_id)
    return {"devices": devices}

class FlagTransactionArgs(BaseModel):
    transaction_id: str = Field(..., description="ID of transaction to flag as fraudulent")
    reason: str = Field(..., description="Reason for flagging the transaction")

def flag_transaction(session_customer_id: str, trace_id: str, transaction_id: str, reason: str) -> Dict[str, Any]:
    """
    Flag a transaction. Requires Human-in-the-Loop approval for completion.
    """
    tx = db.get_transaction_by_id(transaction_id)
    if not tx or tx.get("customer_id") != session_customer_id:
        return {"error": "Invalid transaction ID or cross-customer access violation."}

    return {
        "status": "pending_approval",
        "action_type": "FLAG_TRANSACTION",
        "transaction_id": transaction_id,
        "reason": reason,
        "message": f"Action required: Confirm flagging transaction {transaction_id} as unauthorized fraud."
    }

class BlockCardArgs(BaseModel):
    card_last4: str = Field(..., description="Last 4 digits of the card to freeze/block")
    reason: str = Field(..., description="Reason for blocking card")

def block_card(session_customer_id: str, trace_id: str, card_last4: str, reason: str) -> Dict[str, Any]:
    """
    Freeze/block payment card to prevent unauthorized charges.
    Requires Human-in-the-Loop approval.
    """
    cust = db.get_customer_by_id(session_customer_id)
    cards = cust.get("cards", []) if cust else []
    matched = any(c.get("card_number", "").endswith(card_last4) for c in cards)
    if not matched:
        return {"error": f"Card ending in {card_last4} not found on your profile."}

    return {
        "status": "pending_approval",
        "action_type": "BLOCK_CARD",
        "card_last4": card_last4,
        "reason": reason,
        "message": f"Action required: Confirm blocking your card ending in {card_last4} immediately for security protection."
    }


# ----------------- Credit & Loan Agent Tools -----------------

class GetCreditProfileArgs(BaseModel):
    pass

def get_credit_profile(session_customer_id: str, trace_id: str) -> Dict[str, Any]:
    """Retrieve customer credit score, monthly income, existing EMIs, and debt obligations."""
    cust = db.get_customer_by_id(session_customer_id)
    if not cust:
        return {"error": "Customer not found."}
    
    loans = db.get_loans_by_customer(session_customer_id)
    monthly_income = cust.get("monthly_income", 0)
    existing_emi = cust.get("existing_emi", 0)
    dti_percent = (existing_emi / monthly_income * 100) if monthly_income > 0 else 0

    return {
        "customer_id": cust["customer_id"],
        "credit_score": cust.get("credit_score"),
        "monthly_income": monthly_income,
        "existing_monthly_emi": existing_emi,
        "current_dti_percentage": round(dti_percent, 1),
        "active_loans": loans
    }

class CalculateEmiArgs(BaseModel):
    principal: float = Field(..., description="Loan principal amount in INR")
    tenure_months: int = Field(..., description="Loan tenure in months (e.g. 12, 24, 36, 60)")
    annual_interest_rate: float = Field(..., description="Annual interest rate percentage (e.g. 10.5)")

def calculate_emi(session_customer_id: str, trace_id: str, principal: float, tenure_months: int, annual_interest_rate: float) -> Dict[str, Any]:
    """
    Deterministic EMI calculator using standard amortization formula.
    EMI = [P x R x (1+R)^N] / [(1+R)^N - 1]
    """
    p = principal
    n = tenure_months
    r = (annual_interest_rate / 12) / 100.0

    if r == 0:
        emi = p / n
    else:
        emi = (p * r * math.pow(1 + r, n)) / (math.pow(1 + r, n) - 1)

    total_payment = emi * n
    total_interest = total_payment - p

    return {
        "principal": p,
        "tenure_months": n,
        "annual_interest_rate": annual_interest_rate,
        "monthly_emi": round(emi, 2),
        "total_interest_payable": round(total_interest, 2),
        "total_amount_payable": round(total_payment, 2)
    }

class CheckLoanEligibilityArgs(BaseModel):
    requested_amount: float = Field(..., description="Requested loan amount in INR")
    tenure_months: Optional[int] = Field(36, description="Desired tenure in months (default: 36)")

def check_loan_eligibility(session_customer_id: str, trace_id: str, requested_amount: float, tenure_months: Optional[int] = 36) -> Dict[str, Any]:
    """
    Deterministic loan underwriting rule engine based on:
    - Credit score threshold (>= 700 standard, < 650 rejected)
    - Debt-to-Income (DTI) ratio max 50%
    - Max loan quantum (<= 15x monthly income, max 20 Lakhs)
    """
    cust = db.get_customer_by_id(session_customer_id)
    if not cust:
        return {"error": "Customer not found."}

    credit_score = cust.get("credit_score", 0)
    monthly_income = cust.get("monthly_income", 0)
    existing_emi = cust.get("existing_emi", 0)
    tenure = tenure_months or 36

    # 1. Determine interest rate tier
    if credit_score >= 750:
        rate = 10.5
    elif credit_score >= 700:
        rate = 12.0
    elif credit_score >= 650:
        rate = 14.5
    else:
        rate = 16.0

    # 2. Compute proposed EMI
    emi_calc = calculate_emi(session_customer_id, trace_id, requested_amount, tenure, rate)
    proposed_emi = emi_calc["monthly_emi"]

    # 3. Compute new DTI
    total_proposed_emi = existing_emi + proposed_emi
    proposed_dti = (total_proposed_emi / monthly_income * 100) if monthly_income > 0 else 100

    max_eligible_amount = min(15 * monthly_income, 2000000.0)

    # 4. Underwriting decision logic
    rejection_reasons = []
    if credit_score < 650:
        rejection_reasons.append(f"Credit score ({credit_score}) is below our minimum threshold of 650.")
    if proposed_dti > 50.0:
        rejection_reasons.append(f"Total Debt-to-Income ratio ({proposed_dti:.1f}%) exceeds maximum permissible 50% limit.")
    if requested_amount > max_eligible_amount:
        rejection_reasons.append(f"Requested amount ({requested_amount:,.2f}) exceeds maximum borrowing capacity ({max_eligible_amount:,.2f}).")

    is_eligible = len(rejection_reasons) == 0

    return {
        "is_eligible": is_eligible,
        "customer_id": session_customer_id,
        "credit_score": credit_score,
        "monthly_income": monthly_income,
        "existing_emi": existing_emi,
        "requested_amount": requested_amount,
        "tenure_months": tenure,
        "interest_rate": rate,
        "proposed_monthly_emi": proposed_emi,
        "proposed_dti_percentage": round(proposed_dti, 1),
        "max_eligible_loan_amount": round(max_eligible_amount, 2),
        "status": "APPROVED" if is_eligible else "REJECTED",
        "reasons": rejection_reasons if not is_eligible else ["Customer fulfills credit score, income, and DTI criteria."]
    }

class RetrieveLoanPolicyArgs(BaseModel):
    query: str = Field(..., description="Keyword or topic to search in banking policies e.g. 'DTI', 'eligibility', 'interest rate'")

def retrieve_loan_policy(session_customer_id: str, trace_id: str, query: str) -> Dict[str, Any]:
    """Mini-RAG keyword search over policies.md."""
    policy_text = db.get_policy_content()
    keywords = [w.lower() for w in query.split() if len(w) > 2]
    
    paragraphs = policy_text.split("\n\n")
    matched = []
    for p in paragraphs:
        p_lower = p.lower()
        if any(k in p_lower for k in keywords):
            matched.append(p.strip())
            
    if not matched:
        # Fallback to returning relevant section
        matched = [paragraphs[0], paragraphs[1]] if len(paragraphs) > 1 else [policy_text]

    return {
        "query": query,
        "matched_sections": matched[:3]
    }


# ----------------- Register All Tools -----------------

def register_all_tools():
    # Customer Agent
    registry.register(ToolDefinition(
        name="get_customer_profile",
        description="Fetch verified profile of the logged-in customer (name, email, phone, KYC).",
        owner_agent="customer_agent",
        args_schema=GetCustomerProfileArgs,
        func=get_customer_profile
    ))
    registry.register(ToolDefinition(
        name="get_account_balance",
        description="Retrieve account balances and status for the logged-in customer.",
        owner_agent="customer_agent",
        args_schema=GetAccountBalanceArgs,
        func=get_account_balance
    ))
    registry.register(ToolDefinition(
        name="get_transactions",
        description="Retrieve recent transactions with optional filters and limits for logged-in customer.",
        owner_agent="customer_agent",
        args_schema=GetTransactionsArgs,
        func=get_transactions
    ))
    registry.register(ToolDefinition(
        name="get_customer_360",
        description="Complete 360-degree financial overview: accounts, cards, loans, devices, recent spend.",
        owner_agent="customer_agent",
        args_schema=GetCustomer360Args,
        func=get_customer_360
    ))

    # Risk Agent
    registry.register(ToolDefinition(
        name="get_transaction_details",
        description="Inspect full details, merchant, location, device ID of a transaction.",
        owner_agent="risk_agent",
        args_schema=GetTransactionDetailsArgs,
        func=get_transaction_details
    ))
    registry.register(ToolDefinition(
        name="score_fraud_risk",
        description="Calculate deterministic fraud risk score (0-100) and risk factors.",
        owner_agent="risk_agent",
        args_schema=ScoreFraudRiskArgs,
        func=score_fraud_risk
    ))
    registry.register(ToolDefinition(
        name="get_device_history",
        description="List registered devices, IP locations, and trust status for customer.",
        owner_agent="risk_agent",
        args_schema=GetDeviceHistoryArgs,
        func=get_device_history
    ))
    registry.register(ToolDefinition(
        name="flag_transaction",
        description="Mark a transaction as unauthorized fraud. Triggers Human-in-the-Loop approval.",
        owner_agent="risk_agent",
        args_schema=FlagTransactionArgs,
        func=flag_transaction
    ))
    registry.register(ToolDefinition(
        name="block_card",
        description="Freeze/block customer debit/credit card. Triggers Human-in-the-Loop approval.",
        owner_agent="risk_agent",
        args_schema=BlockCardArgs,
        func=block_card
    ))

    # Credit Agent
    registry.register(ToolDefinition(
        name="get_credit_profile",
        description="Fetch customer credit score, monthly income, existing EMIs, and active loans.",
        owner_agent="credit_agent",
        args_schema=GetCreditProfileArgs,
        func=get_credit_profile
    ))
    registry.register(ToolDefinition(
        name="calculate_emi",
        description="Deterministic EMI calculation based on principal, tenure, and interest rate.",
        owner_agent="credit_agent",
        args_schema=CalculateEmiArgs,
        func=calculate_emi
    ))
    registry.register(ToolDefinition(
        name="check_loan_eligibility",
        description="Underwrite personal loan eligibility using DTI, credit score, and income limits.",
        owner_agent="credit_agent",
        args_schema=CheckLoanEligibilityArgs,
        func=check_loan_eligibility
    ))
    registry.register(ToolDefinition(
        name="retrieve_loan_policy",
        description="Search banking guidelines and underwriting rules from policies document.",
        owner_agent="credit_agent",
        args_schema=RetrieveLoanPolicyArgs,
        func=retrieve_loan_policy
    ))

# Auto-register on import
register_all_tools()
