"""
Banking Knowledge Base & Domain Scope Classifier:
Provides comprehensive explanations for all general banking and financial questions,
strict domain boundaries (refusing non-banking topics with standard refusal phrasing),
and prompt injection detection signatures.
"""

import re
from typing import Dict, Optional, Tuple

# Comprehensive Dictionary of Banking System Concepts
# Each concept contains an authoritative, plain-text explanation with an intuitive example.
# Strictly NO LaTeX formatting and NO $...$ formulas.
BANKING_KNOWLEDGE_BASE: Dict[str, Dict[str, str]] = {
    # 1. Account Types & Operations
    "savings_account": {
        "title": "Savings Account",
        "description": "A savings account is an interest-bearing deposit account maintained at a retail bank that provides capital safety and liquidity for everyday individuals. Funds can be deposited and withdrawn at any time via debit cards, UPI, or online transfers, while earning nominal interest (typically 3% to 4% p.a.).",
        "example": "For example, if you keep Rs. 50,000 in your AgentBank savings account at 3.5% annual interest, you earn approximately Rs. 1,750 in interest over one year while retaining instant access to your funds."
    },
    "current_account": {
        "title": "Current / Checking Account",
        "description": "A current (or checking) account is a non-interest-bearing bank account designed for businesses, entrepreneurs, and traders who conduct frequent, high-volume transactions. Unlike savings accounts, current accounts have no restriction on daily deposits or withdrawals and frequently include overdraft facilities.",
        "example": "For example, a retail business uses a current account to receive hundreds of daily customer payments and pay supplier invoices seamlessly without hitting monthly transaction limits."
    },
    "fixed_deposit": {
        "title": "Fixed Deposit (FD)",
        "description": "A Fixed Deposit (FD) is a financial instrument where a customer deposits a lump sum with a bank for a fixed tenure (ranging from 7 days to 10 years) at a guaranteed, higher interest rate than regular savings. Premature withdrawals may incur a nominal penalty.",
        "example": "For example, depositing Rs. 1,00,000 in a 1-year Fixed Deposit at 7.0% per annum yields Rs. 7,185 in compounded interest at maturity."
    },
    "recurring_deposit": {
        "title": "Recurring Deposit (RD)",
        "description": "A Recurring Deposit (RD) is a disciplined monthly savings vehicle where an investor deposits a fixed sum every month for a pre-determined duration (e.g. 12 to 60 months) earning interest comparable to fixed deposits.",
        "example": "For example, depositing Rs. 5,000 every month into a 12-month RD at 6.8% annual interest accumulates Rs. 60,000 in principal plus approximately Rs. 2,240 in accrued interest."
    },
    "certificate_of_deposit": {
        "title": "Certificate of Deposit (CD)",
        "description": "A Certificate of Deposit (CD) is a bank-issued, time-bound promissory note acknowledging a deposit for a set term with fixed maturity and interest. CDs are typically purchased by institutional investors or high-net-worth depositors.",
        "example": "For example, purchasing a 6-month Certificate of Deposit of Rs. 10,00,000 locks in a guaranteed payout upon completion of the 180-day term."
    },
    "overdraft": {
        "title": "Bank Overdraft",
        "description": "An overdraft is a credit extension facility linked to a bank account that permits the account holder to continue withdrawing funds or making payments even when the balance drops below zero, up to an agreed credit limit. Interest is charged strictly on the amount overdrawn and the days utilized.",
        "example": "For example, with a pre-approved overdraft limit of Rs. 50,000, you can pay a vendor bill of Rs. 30,000 even if your bank balance is only Rs. 10,000, incurring interest only on the Rs. 20,000 borrowed until repaid."
    },
    "demat_account": {
        "title": "Demat Account",
        "description": "A Demat (Dematerialized) account converts physical share certificates into electronic format to facilitate trading and investing in stocks, bonds, government securities, and mutual funds via depositories.",
        "example": "For example, buying shares of a listed company automatically credits the electronic shares into your linked Demat account while debiting funds from your bank account."
    },
    "escrow_account": {
        "title": "Escrow Account",
        "description": "An escrow account is an impartial third-party account where funds or financial assets are held during a transaction until specific legal or contractual obligations are fulfilled by both the buyer and seller.",
        "example": "For example, during a real estate purchase of Rs. 50,00,000, the buyer deposits the funds into an escrow account, which releases payment to the seller only after clear property title deeds are verified."
    },
    "joint_account": {
        "title": "Joint Account",
        "description": "A joint bank account is an account owned and managed simultaneously by two or more individuals (such as spouses, family members, or business partners), operating under mandates such as 'Either or Survivor' or 'Jointly Operated'.",
        "example": "For example, two partners maintain a joint savings account where both have linked debit cards and can deposit or withdraw money for shared household expenses."
    },
    "dormant_account": {
        "title": "Dormant / Inactive Account",
        "description": "A bank account is classified as inoperative or dormant when no customer-induced transactions (deposits, withdrawals, transfers) occur for more than 24 consecutive months. To reactivate it, the customer must submit fresh KYC documentation.",
        "example": "For example, if an account has zero transactions between 2024 and 2026, the bank restricts outgoing transactions until the customer visits a branch or completes video KYC verification."
    },
    "minimum_balance": {
        "title": "Minimum Balance Requirement",
        "description": "The minimum balance (or Average Monthly Balance - AMB) is the threshold of funds a bank requires customers to maintain in their account to avoid non-maintenance penalty charges.",
        "example": "For example, a premier savings account may mandate maintaining an average monthly balance of Rs. 10,000, while basic zero-balance savings accounts waive this requirement."
    },

    # 2. Interest Rates, Financial Math & Metrics
    "emi": {
        "title": "Equated Monthly Installment (EMI)",
        "description": "An Equated Monthly Installment (EMI) is a fixed monthly payment made by a borrower to a lender to repay a loan over an agreed tenure. Each payment covers both principal and interest, calculated using the reducing balance formula: EMI = P x r x (1+r)^n / ((1+r)^n - 1), where P is principal, r is the monthly interest rate, and n is tenure in months.",
        "example": "For example, a loan of Rs. 1,00,000 at 12% annual interest (1% monthly) for 12 months results in an EMI of Rs. 8,885 per month."
    },
    "percentage": {
        "title": "Percentage Calculation",
        "description": "A percentage represents a proportion or fraction out of 100, written using the % symbol. In banking, percentages express interest rates, tax deductions, and fees using the formula: Value = (Percentage / 100) x Total.",
        "example": "For example, a 15% down payment on a Rs. 2,00,000 purchase is calculated as (15 / 100) x 2,00,000 = Rs. 30,000."
    },
    "compound_interest": {
        "title": "Compound Interest",
        "description": "Compound interest is interest calculated on both the initial principal amount and the accumulated interest from previous periods (interest on interest), allowing deposits to grow exponentially over time.",
        "example": "For example, investing Rs. 10,000 at 10% annual interest compounded yearly yields Rs. 11,000 after year 1, and Rs. 12,100 after year 2 (earning Rs. 1,100 in the second year instead of Rs. 1,000)."
    },
    "simple_interest": {
        "title": "Simple Interest",
        "description": "Simple interest is calculated solely on the principal loan amount, without compounding prior interest periods. Formula: SI = (Principal x Rate x Time) / 100.",
        "example": "For example, borrowing Rs. 50,000 at 8% simple interest for 3 years incurs total interest of (50,000 x 8 x 3) / 100 = Rs. 12,000."
    },
    "apr": {
        "title": "Annual Percentage Rate (APR)",
        "description": "The Annual Percentage Rate (APR) reflects the true annualized cost of borrowing, incorporating both the nominal interest rate and any mandatory upfront fees, processing charges, or loan origination costs.",
        "example": "For example, a loan with a nominal 10% interest rate and a 2% processing fee may reflect an effective APR of 11.2%, giving borrowers a transparent measure of total borrowing expense."
    },
    "apy": {
        "title": "Annual Percentage Yield (APY)",
        "description": "Annual Percentage Yield (APY) is the real rate of return earned on a deposit or investment when taking the compounding frequency (daily, monthly, quarterly) into account over one year.",
        "example": "For example, a savings certificate offering 6% nominal interest compounded monthly delivers an effective APY of approximately 6.17% per year."
    },
    "dti": {
        "title": "Debt-to-Income (DTI) Ratio",
        "description": "The Debt-to-Income (DTI) ratio is a key underwriting metric comparing total monthly debt payments to gross monthly income: DTI = (Total Monthly EMIs / Gross Monthly Income) x 100. Banks require DTI to remain below 50% to ensure sustainable debt service.",
        "example": "For example, if an applicant earns Rs. 1,00,000 monthly and pays Rs. 25,000 in existing loan EMIs, their current DTI is 25%, qualifying them comfortably for new credit."
    },
    "credit_score": {
        "title": "Credit Score / CIBIL Score",
        "description": "A credit score is a 3-digit numerical score (typically ranging from 300 to 900) summarizing your credit history, repayment track record, credit utilization, and debt stability. Lenders use it to determine loan approval and interest rates.",
        "example": "For example, a score of 780 qualifies a borrower for prime interest rates (such as 10.5%), while a score below 650 indicates high credit risk and may result in loan rejection."
    },

    # 3. Loans, Mortgages & Credit
    "personal_loan": {
        "title": "Personal Loan",
        "description": "A personal loan is an unsecured retail loan provided by banks for personal expenditures (such as medical emergencies, home renovation, or weddings). Because it requires no collateral, approval depends heavily on credit score, income stability, and debt obligations.",
        "example": "For example, an employed individual with a 750+ credit score can borrow Rs. 5,00,000 for 36 months without pledging assets, repaying through fixed monthly installments."
    },
    "mortgage": {
        "title": "Mortgage / Home Loan",
        "description": "A mortgage (home loan) is a secured loan used to purchase or construct residential property. The property serves as collateral until the loan principal and interest are paid in full over tenures up to 20 or 30 years.",
        "example": "For example, borrowing Rs. 40,00,000 for a 20-year home loan at 8.5% interest allows purchasing a house while making regular monthly mortgage payments."
    },
    "collateral": {
        "title": "Loan Collateral",
        "description": "Collateral is an asset (such as real estate, fixed deposits, gold, or vehicles) that a borrower pledges to a lender as security. If the borrower defaults on repayments, the lender possesses the legal right to liquidate the collateral to recover outstanding dues.",
        "example": "For example, in a loan against property of Rs. 25,00,000, the borrower pledges their residential property title deeds as collateral."
    },
    "amortization": {
        "title": "Loan Amortization",
        "description": "Amortization is the process of spreading loan repayments into equal installments over time according to an amortization schedule. In earlier installments, a larger portion covers interest, while later installments pay down the principal balance.",
        "example": "For example, in month 1 of an EMI schedule, Rs. 10,000 goes toward interest and Rs. 6,250 toward principal, but by month 36, Rs. 15,800 reduces principal and only Rs. 450 covers interest."
    },
    "foreclosure": {
        "title": "Loan Foreclosure / Prepayment",
        "description": "Loan foreclosure occurs when a borrower repays the entire remaining loan principal ahead of the scheduled tenure, concluding the debt early and saving on future interest outlays.",
        "example": "For example, paying off a remaining balance of Rs. 2,00,000 on a 5-year loan at month 24 saves 36 months of subsequent interest payments."
    },

    # 4. Cards & Payment Instruments
    "debit_card": {
        "title": "Debit Card",
        "description": "A debit card is an electronic payment card linked directly to your savings or current bank account. When you make a purchase or ATM withdrawal, funds are deducted immediately in real time from your available account balance.",
        "example": "For example, swiping your debit card for Rs. 1,500 at a grocery store immediately debits Rs. 1,500 from your linked savings balance."
    },
    "credit_card": {
        "title": "Credit Card",
        "description": "A credit card is a revolving credit facility issued by banks allowing customers to borrow funds up to an approved credit limit for purchases. Cardholders receive a monthly bill and an interest-free grace period (20 to 50 days) to repay the balance.",
        "example": "For example, with a credit limit of Rs. 1,50,000, you can charge Rs. 12,000 during the billing cycle and pay no interest if the full statement balance is paid by the due date."
    },
    "debit_vs_credit": {
        "title": "Debit Card vs Credit Card",
        "description": "The primary difference lies in the source of money: a debit card spends your own deposited money directly from your bank account, whereas a credit card spends the bank's money up to an approved limit, which you repay later. Credit cards also build credit history and offer fraud chargeback rights.",
        "example": "For example, a Rs. 5,000 purchase with a debit card immediately reduces your bank balance by Rs. 5,000; with a credit card, your balance remains untouched until you pay your monthly statement."
    },
    "cvv": {
        "title": "CVV / CVC (Card Verification Value)",
        "description": "A CVV (Card Verification Value) is a 3-digit security code printed on the reverse side of Visa/Mastercard (or 4 digits on the front of Amex) used to verify that the customer physically possesses the card during online card-not-present transactions.",
        "example": "For example, when shopping online, entering the 3-digit CVV ensures that someone who merely stole a stored card number without the physical card cannot complete the payment."
    },
    "pin": {
        "title": "Personal Identification Number (PIN)",
        "description": "A PIN is a confidential 4- or 6-digit numeric password used by cardholders to authenticate transactions at ATMs and Point-of-Sale (PoS) merchant chip-and-PIN terminals.",
        "example": "For example, withdrawing Rs. 5,000 at an ATM requires inserting your debit card and typing your secret 4-digit PIN."
    },
    "otp": {
        "title": "One-Time Password (OTP) / 2FA",
        "description": "An OTP (One-Time Password) is a dynamic, time-sensitive numeric code sent via SMS or authenticator app to provide two-factor authentication (2FA) for validating digital banking transactions and logins.",
        "example": "For example, authorizing an online card payment triggers an SMS with a 6-digit OTP valid for 5 minutes that must be entered to finalize the transaction."
    },
    "chargeback": {
        "title": "Chargeback / Payment Dispute",
        "description": "A chargeback is a reversal of a payment transaction initiated by the issuing bank to refund the cardholder when an unauthorized charge occurs, merchant fraud takes place, or paid goods are not delivered.",
        "example": "For example, if you notice a fraudulent charge of Rs. 8,500 from a merchant you never visited, you file a dispute and the bank credits the funds back following a fraud investigation."
    },

    # 5. Electronic Transfers & Routing Codes
    "wire_transfer": {
        "title": "Wire Transfer",
        "description": "A wire transfer is an electronic transfer of funds between financial institutions domestically or internationally, providing fast, secure settlement for high-value payments.",
        "example": "For example, transferring funds from a branch in Mumbai to a university abroad uses an international wire transfer to deliver settled funds within 24 to 48 hours."
    },
    "swift_code": {
        "title": "SWIFT / BIC Code",
        "description": "A SWIFT code (Society for Worldwide Interbank Financial Telecommunication) is an 8- or 11-character international bank identifier code (BIC) used to route payments and messages accurately between banks worldwide.",
        "example": "For example, receiving an international wire transfer requires providing your bank's SWIFT code (such as AGNTINBBXXX) alongside your account number."
    },
    "iban": {
        "title": "International Bank Account Number (IBAN)",
        "description": "An IBAN is an internationally agreed system of identifying bank accounts across national borders (up to 34 alphanumeric characters), reducing transcription errors and facilitating automated cross-border settlement.",
        "example": "For example, a customer sending funds to Europe inputs the beneficiary's IBAN starting with country code and checksum digits (e.g., DE89...)."
    },
    "routing_number": {
        "title": "Bank Routing Number / ABA",
        "description": "A bank routing transit number is a 9-digit code used primarily in the United States to identify specific financial institutions during electronic fund transfers, check clearing, and Automated Clearing House (ACH) direct deposits.",
        "example": "For example, setting up direct payroll deposit requires providing your bank's 9-digit routing number alongside your account number."
    },
    "ifsc_code": {
        "title": "IFSC Code (Indian Financial System Code)",
        "description": "An IFSC code is an 11-character alphanumeric code used to identify individual bank branches participating in electronic fund transfers (NEFT, RTGS, and IMPS) across India.",
        "example": "For example, an IFSC code like AGNT0001234 identifies AgentBank's specific branch for routing electronic transfers."
    },
    "neft": {
        "title": "National Electronic Funds Transfer (NEFT)",
        "description": "NEFT is a nationwide electronic payment system in India that facilitates one-to-one funds transfers. Settlements operate on a round-the-clock basis in half-hourly batches 24x7 with no minimum amount restriction.",
        "example": "For example, transferring Rs. 15,000 via NEFT to a friend's account settles in the next half-hourly batch."
    },
    "rtgs": {
        "title": "Real Time Gross Settlement (RTGS)",
        "description": "RTGS is a real-time, order-by-order gross settlement system designed for high-value funds transfers (minimum Rs. 2,00,000 in India). Settlement happens immediately without waiting for netting batches.",
        "example": "For example, a commercial payment of Rs. 10,00,000 sent via RTGS is credited to the beneficiary's bank account instantly."
    },
    "imps": {
        "title": "Immediate Payment Service (IMPS)",
        "description": "IMPS is an instant 24x7 interbank electronic fund transfer service accessible through mobile banking, internet banking, and ATMs for immediate credit up to prescribed limits (typically Rs. 5 Lakhs).",
        "example": "For example, sending Rs. 2,500 via IMPS on a Sunday evening credits the recipient's bank account in under 5 seconds."
    },
    "upi": {
        "title": "Unified Payments Interface (UPI)",
        "description": "UPI is an advanced real-time payment system that powers multiple bank accounts into a single mobile application, merging seamless fund routing and merchant payments using a virtual identifier (UPI ID or QR code) without sharing bank account numbers.",
        "example": "For example, scanning a merchant QR code and authenticating with your 6-digit UPI PIN transfers Rs. 350 instantly from your bank account."
    },
    "cheque_bounce": {
        "title": "Cheque / Check Clearance & Dishonour (Bounce)",
        "description": "A cheque is a negotiable instrument directing a bank to pay a specific sum from the drawer's account. A cheque bounces (is dishonoured) if the account lacks sufficient funds, has a signature mismatch, or has expired (over 3 months old), which carries financial penalties and legal liability.",
        "example": "For example, presenting a cheque for Rs. 50,000 against an account holding only Rs. 10,000 causes the cheque to bounce for insufficient funds, incurring return fees."
    },
    "demand_draft": {
        "title": "Demand Draft (DD) / Cashier's Check",
        "description": "A Demand Draft is a prepaid financial instrument issued by a bank guaranteeing payment to a specified beneficiary. Because funds are debited up front before issuance, a demand draft cannot bounce due to insufficient funds.",
        "example": "For example, paying university entrance fees of Rs. 25,000 using a bank Demand Draft provides the university with guaranteed, non-bouncing payment."
    },

    # 6. Banking Security, Fraud & Regulations
    "kyc": {
        "title": "Know Your Customer (KYC)",
        "description": "Know Your Customer (KYC) is a mandatory identity verification process used by banks to confirm customer identities and prevent financial fraud. It protects accounts from unauthorized use and identity theft.",
        "example": "For example, completing KYC requires submitting government-issued identity documents such as PAN and Aadhaar along with valid address proof."
    },
    "aml": {
        "title": "Anti-Money Laundering (AML)",
        "description": "Anti-Money Laundering (AML) refers to financial laws, regulations, and bank surveillance systems designed to prevent criminals from disguising illicit or criminal proceeds as legitimate income.",
        "example": "For example, banks automatically flag and report cash deposits exceeding statutory thresholds (e.g. Rs. 10 Lakhs) to regulatory intelligence units."
    },
    "fraud_detection": {
        "title": "Fraud Detection & Prevention",
        "description": "Fraud detection is an automated monitoring system that analyzes account transactions in real time to spot suspicious or unauthorized activity. It evaluates transaction amounts, merchant locations, timestamps, and device fingerprints against your typical spending patterns.",
        "example": "For example, if a transaction of Rs. 1,99,200 is initiated from an unrecognized device in a foreign location, the system flags it as high risk and requests verification."
    },
    "phishing": {
        "title": "Phishing in Banking",
        "description": "Phishing is a fraudulent cyberattack where bad actors impersonate banks via deceptive emails, SMS messages (smishing), or spoofed websites to trick victims into disclosing passwords, card numbers, or OTPs.",
        "example": "For example, a scam message claiming 'Your bank account is blocked, click this link to update KYC' is a phishing attempt designed to steal online banking passwords."
    },
    "skimming": {
        "title": "Card Skimming",
        "description": "Card skimming is a technique where criminals affix illegal scanning devices to ATM card slots or PoS terminals to copy magnetic stripe data while using hidden pinhole cameras to record PIN entries.",
        "example": "For example, modern EMV chip cards and dual-factor tokenization protect against skimming because chip transactions generate unique dynamic cryptograms."
    },
    "deposit_insurance": {
        "title": "Deposit Insurance (DICGC / FDIC)",
        "description": "Deposit insurance is a statutory government safety net that guarantees depositors' savings in commercial banks up to a legal limit (e.g. up to Rs. 5,00,000 per depositor per bank in India via DICGC, or $250,000 in the US via FDIC) if a bank undergoes liquidation.",
        "example": "For example, if an insured bank experiences financial insolvency, all eligible deposits up to Rs. 5,00,000 are reimbursed by the deposit insurance authority."
    },
    "bank_guarantee": {
        "title": "Bank Guarantee (BG)",
        "description": "A Bank Guarantee is an irrevocable promise issued by a bank on behalf of a customer assuring a beneficiary that liabilities will be honored if the customer defaults on contract terms.",
        "example": "For example, a construction contractor submits a bank guarantee of Rs. 10,00,000 to a government agency ensuring the completion of civic road work according to contract specifications."
    },
    "letter_of_credit": {
        "title": "Letter of Credit (LC)",
        "description": "A Letter of Credit (LC) is a financial document issued by a buyer's bank guaranteeing that payment will be delivered to a seller upon presentation of verified shipping and commercial documentation.",
        "example": "For example, an exporter in Germany ships machinery to an importer in Mumbai, confident that AgentBank will release payment once verified bill of lading documents are presented."
    },

    # 7. Central Banking, Macroeconomics & Operations
    "central_bank": {
        "title": "Central Bank (RBI / Federal Reserve)",
        "description": "A central bank is the apex monetary authority of a country (such as the Reserve Bank of India or US Federal Reserve). It manages currency issuance, regulates commercial banks, controls monetary policy, and maintains financial stability.",
        "example": "For example, the central bank adjusts policy repo rates to manage inflation and oversee commercial banking capital adequacy ratios."
    },
    "repo_rate": {
        "title": "Repo Rate & Reverse Repo Rate",
        "description": "The Repo Rate is the benchmark interest rate at which the central bank lends short-term money to commercial banks against government securities. The Reverse Repo Rate is the rate at which the central bank absorbs excess liquidity from commercial banks.",
        "example": "For example, when the central bank lowers the repo rate by 25 basis points, commercial banks lower home loan and personal loan interest rates for borrowers."
    },
    "liquidity": {
        "title": "Liquidity in Banking",
        "description": "Liquidity refers to how quickly an asset can be converted into ready cash without loss of value. For a bank, liquidity represents having sufficient cash reserves and liquid securities to honor customer withdrawal demands.",
        "example": "For example, cash and government bonds are highly liquid assets, whereas long-term mortgages are illiquid assets."
    },
    "inflation": {
        "title": "Inflation & Purchasing Power",
        "description": "Inflation is the sustained increase in the general price level of goods and services over time, eroding the purchasing power of money. Banks offer interest on savings and fixed deposits to help depositors offset inflation.",
        "example": "For example, if inflation is 5% annually, a basket of goods costing Rs. 10,000 today will cost Rs. 10,500 next year."
    },
    "how_banks_make_money": {
        "title": "How Banks Operate & Generate Income",
        "description": "Banks operate primarily on the financial intermediation model: they accept deposits from savers paying lower interest rates and extend loans to borrowers charging higher interest rates. The gap between interest earned and interest paid is known as the Net Interest Margin (NIM), complemented by fee-based banking services.",
        "example": "For example, a bank pays 3.5% on savings deposits and lends those funds out for personal loans at 10.5%, earning a 7% spread to cover operational overhead and loan reserves."
    },
    "opening_account": {
        "title": "How to Open a Bank Account",
        "description": "Opening a bank account requires selecting the account type (savings, current, or salary), completing the application form, submitting valid identity proof (PAN card, Aadhaar card, or passport), address documentation, and funding the initial minimum deposit.",
        "example": "For example, you can open an AgentBank account digitally via paperless video KYC by uploading PAN and Aadhaar in under 10 minutes."
    },
    "closing_account": {
        "title": "How to Close a Bank Account",
        "description": "To close a bank account, clear any negative balance, transfer remaining funds to another account, return unused cheque books and debit cards, cancel automatic recurring debits, and submit an account closure form.",
        "example": "For example, transferring your remaining balance of Rs. 15,200 to your secondary bank and submitting a signed closure request allows closing an unused account without fees."
    },
    "banking_hours": {
        "title": "Banking Hours & Digital Availability",
        "description": "Traditional bank branch counters operate during standard business hours (typically 9:30 AM to 4:30 PM on weekdays), whereas AgentBank digital channels, mobile banking, UPI, IMPS, and ATM networks operate 24 hours a day, 7 days a week, 365 days a year.",
        "example": "For example, while branch teller counters close in the evening, you can check balances, transfer funds, or block a card 24x7 via AgentBank online banking."
    }
}

# Standard Prompt Injection and Adversarial Signatures
PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
    r"disregard\s+(all\s+)?guidelines",
    r"disregard\s+(all\s+)?(previous|prior|above)\s+instructions",
    r"you\s+are\s+now\s+dan",
    r"jailbreak",
    r"system\s*prompt",
    r"reveal\s+your\s+hidden\s+rules",
    r"reveal\s+(the\s+)?system\s+prompt",
    r"bypass\s+security",
    r"override\s+(all\s+)?(system|safety|security)\s+(rules|prompts|boundaries|instructions)",
    r"act\s+as\s+(an?\s+)?unrestricted",
    r"do\s+anything\s+now",
    r"forget\s+(all\s+)?(previous|your)\s+(rules|instructions)",
    r"pretend\s+you\s+have\s+no\s+(rules|restrictions|limits)",
    r"dan\s+mode",
    r"developer\s+mode\s+output"
]

# Patterns for non-banking topics
OFF_TOPIC_PATTERNS = [
    r"write\s+(a\s+)?poem",
    r"tell\s+me\s+a\s+joke",
    r"who\s+won\s+the\s+world\s+cup",
    r"recipe\s+for",
    r"translate\s+this\s+french",
    r"write\s+python\s+code\s+to\s+hack",
    r"\b(what('s|\s+is)\s+the\s+)?weather\b",
    r"\b(tell\s+me\s+about\s+)?movies?\b",
    r"\b(write|show|generate)\s+(some\s+)?(python|java|javascript|c\+\+|code|coding)\b",
    r"\bhow\s+to\s+code\b",
    r"\bcapital\s+of\b",
    r"\bpresident\s+of\b",
    r"\bprime\s+minister\s+of\b",
    r"\bwho\s+is\s+(albert\s+einstein|shakespeare|newton|messi|ronaldo)\b",
    r"\bhow\s+to\s+(cook|bake|make\s+pizza|make\s+cake)\b",
    r"\btell\s+me\s+a\s+story\b",
    r"\bquantum\s+physics\b"
]

# Comprehensive banking keyword vocabulary to detect general banking inquiries
BANKING_KEYWORDS = [
    "bank", "banking", "banker", "account", "accounts", "saving", "savings", "checking", "current",
    "deposit", "deposits", "fixed deposit", "recurring deposit", "certificate of deposit", "cd", "fd", "rd",
    "demat", "escrow", "overdraft", "balance", "balances", "statement", "statements", "passbook", "ledger",
    "loan", "loans", "borrow", "borrowing", "lending", "lender", "mortgage", "emi", "emis", "tenure", "collateral",
    "amortization", "prepayment", "foreclosure", "interest", "apr", "apy", "compound interest",
    "simple interest", "percentage", "rate", "rates", "repo rate", "inflation", "credit", "credit score",
    "cibil", "credit limit", "dti", "debt", "debts", "card", "cards", "debit card", "credit card", "cvv", "pin",
    "otp", "transaction", "transactions", "transfer", "transfers", "wire", "swift", "iban", "ifsc", "neft", "rtgs", "imps",
    "upi", "routing number", "cheque", "cheques", "check", "checks", "bounce", "demand draft", "cashier",
    "kyc", "aml", "fraud", "fraud detection", "phishing", "skimming", "chargeback", "chargebacks", "dispute", "disputes",
    "block card", "freeze", "atm", "pos", "merchant", "merchants", "net banking", "mobile banking",
    "central bank", "rbi", "federal reserve", "fdic", "dicgc", "bank guarantee",
    "letter of credit", "liquidity", "minimum balance", "dormant", "inoperative", "money", "currency",
    "rupee", "rupees", "inr", "funds", "cash", "salary", "expense", "expenses", "spend", "spending", "budget", "finance", "financial",
    "underwriting", "policy", "policies", "nominee", "beneficiary", "pan", "aadhaar", "charge", "charges"
]

GREETING_WORDS = [
    "hi", "hello", "hey", "help", "good morning", "good afternoon", "good evening",
    "greetings", "who are you", "what can you do", "agentbank"
]

STANDARD_OFF_TOPIC_REFUSAL = (
    "I cannot answer this question as it is not related to the banking system. "
    "AgentBank is specialized exclusively in banking, account operations, loans, transactions, "
    "fraud prevention, and financial services. Please let me know if you have questions regarding "
    "your account, loans, transactions, or banking concepts."
)


def is_prompt_injection(message: str) -> bool:
    """Check if message contains adversarial prompt injection signatures."""
    lower = message.lower().strip()
    return any(re.search(pat, lower) for pat in PROMPT_INJECTION_PATTERNS)


def is_banking_related(message: str) -> bool:
    """
    Determines whether a user query is related to the banking system,
    financial concepts, account operations, or conversational greetings.
    """
    lower = message.lower().strip()

    # Empty check
    if not lower:
        return False

    # Check greetings or conversational openers
    if any(lower == g or lower.startswith(f"{g} ") for g in GREETING_WORDS):
        return True

    # Explicit off-topic check
    for pat in OFF_TOPIC_PATTERNS:
        if re.search(pat, lower):
            return False

    # Check presence of any banking keywords or phrases
    for kw in BANKING_KEYWORDS:
        if re.search(rf"\b{re.escape(kw)}\b", lower):
            return True

    return False


def lookup_banking_concept(query: str) -> Optional[str]:
    """
    Matches user query to our rich banking knowledge dictionary
    and returns a structured plain-text answer (no LaTeX, no $).
    """
    lower = query.lower().strip()

    # Never match customer data requests
    if any(p in lower for p in ["my balance", "my transaction", "my account", "my loan", "my card", "show my", "show me", "eligible for", "can i get", "am i eligible", "what's my balance", "whats my balance"]):
        return None

    # Exact topic mapping
    topic_map = [
        # Percentage
        (["percentage", "what is %", "how to calculate percentage"], "percentage"),
        # EMI
        (["what is emi", "explain emi", "how does emi work", "calculate emi", "meaning of emi"], "emi"),
        # Credit Score / CIBIL
        (["credit score", "cibil", "credit rating", "how does credit score work", "what is a credit score", "what is credit score"], "credit_score"),
        # KYC
        (["what is kyc", "how does kyc work", "kyc verification", "know your customer"], "kyc"),
        # Fraud Detection
        (["fraud detection", "how does fraud detection work", "what is fraud detection", "what is fraud prevention"], "fraud_detection"),
        # Phishing
        (["phishing", "what is phishing"], "phishing"),
        # Skimming
        (["skimming", "card skimming"], "skimming"),
        # Overdraft
        (["overdraft", "what is overdraft", "overdraft facility", "overdraw"], "overdraft"),
        # Savings Account
        (["savings account", "what is a savings account", "saving account"], "savings_account"),
        # Current / Checking
        (["current account", "checking account", "what is a current account", "what is checking account"], "current_account"),
        # Fixed Deposit
        (["fixed deposit", "what is fd", "what is a fixed deposit", "term deposit"], "fixed_deposit"),
        # Recurring Deposit
        (["recurring deposit", "what is rd", "what is a recurring deposit"], "recurring_deposit"),
        # Certificate of Deposit
        (["certificate of deposit", "what is cd in banking", "what is a cd"], "certificate_of_deposit"),
        # Demat
        (["demat", "demat account", "dematerialized"], "demat_account"),
        # Escrow
        (["escrow", "what is escrow", "escrow account"], "escrow_account"),
        # Joint Account
        (["joint account", "what is a joint account"], "joint_account"),
        # Dormant
        (["dormant", "inactive account", "inoperative account"], "dormant_account"),
        # Minimum balance
        (["minimum balance", "average monthly balance", "amb"], "minimum_balance"),
        # Compound interest
        (["compound interest", "how does compounding work"], "compound_interest"),
        # Simple interest
        (["simple interest"], "simple_interest"),
        # APR
        (["apr", "annual percentage rate"], "apr"),
        # APY
        (["apy", "annual percentage yield"], "apy"),
        # DTI
        (["dti", "debt to income", "debt-to-income"], "dti"),
        # Personal Loan
        (["what is a personal loan", "what is personal loan", "explain personal loan"], "personal_loan"),
        # Mortgage
        (["mortgage", "home loan", "housing loan", "what is a mortgage"], "mortgage"),
        # Collateral
        (["collateral", "pledged asset", "security for loan", "what is collateral"], "collateral"),
        # Amortization
        (["amortization", "loan amortization", "amortization schedule"], "amortization"),
        # Foreclosure
        (["foreclosure", "prepayment", "preclose loan"], "foreclosure"),
        # Debit vs Credit
        (["debit vs credit", "difference between debit and credit", "debit card or credit card"], "debit_vs_credit"),
        # Debit Card
        (["debit card", "what is a debit card"], "debit_card"),
        # Credit Card
        (["credit card", "what is a credit card"], "credit_card"),
        # CVV
        (["cvv", "cvc", "card verification value"], "cvv"),
        # PIN
        (["what is pin", "pin in banking", "atm pin"], "pin"),
        # OTP
        (["what is otp", "one time password", "2fa"], "otp"),
        # Chargeback
        (["chargeback", "payment dispute", "dispute charge", "what is chargeback"], "chargeback"),
        # Wire Transfer
        (["wire transfer", "what is a wire transfer"], "wire_transfer"),
        # SWIFT
        (["swift", "swift code", "bic code"], "swift_code"),
        # IBAN
        (["iban", "international bank account number"], "iban"),
        # Routing Number
        (["routing number", "aba routing"], "routing_number"),
        # IFSC
        (["ifsc", "ifsc code"], "ifsc_code"),
        # NEFT
        (["neft", "what is neft"], "neft"),
        # RTGS
        (["rtgs", "what is rtgs"], "rtgs"),
        # IMPS
        (["imps", "what is imps"], "imps"),
        # UPI
        (["upi", "what is upi", "unified payments interface"], "upi"),
        # Cheque Bounce
        (["cheque bounce", "check bounce", "dishonour of cheque", "bounced check"], "cheque_bounce"),
        # Demand Draft
        (["demand draft", "what is a dd", "cashier check", "cashier's check"], "demand_draft"),
        # AML
        (["anti money laundering", "what is aml"], "aml"),
        # Deposit Insurance
        (["deposit insurance", "dicgc", "fdic", "if bank fails"], "deposit_insurance"),
        # Bank Guarantee
        (["bank guarantee", "what is a bg"], "bank_guarantee"),
        # Letter of Credit
        (["letter of credit", "what is an lc"], "letter_of_credit"),
        # Central Bank
        (["central bank", "reserve bank", "rbi", "federal reserve"], "central_bank"),
        # Repo Rate
        (["repo rate", "reverse repo"], "repo_rate"),
        # Liquidity
        (["liquidity in banking", "what is liquidity"], "liquidity"),
        # Inflation
        (["inflation in banking", "what is inflation"], "inflation"),
        # How banks make money
        (["how do banks make money", "how banks make money", "fractional reserve banking", "how does a bank work"], "how_banks_make_money"),
        # Opening account
        (["how to open an account", "open bank account", "opening a bank account"], "opening_account"),
        # Closing account
        (["how to close an account", "close bank account", "closing a bank account"], "closing_account"),
        # Banking hours
        (["banking hours", "bank timings", "bank open time"], "banking_hours")
    ]

    for triggers, key in topic_map:
        if any(tr in lower for tr in triggers):
            concept = BANKING_KNOWLEDGE_BASE.get(key)
            if concept:
                return f"{concept['description']} {concept['example']}"

    return None
