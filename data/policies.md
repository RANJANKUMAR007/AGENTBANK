# Banking Policies & Guidelines

## 1. Personal Loan Eligibility Policy
- **Minimum Credit Score**: 700 is required for standard unsecured personal loans. Applications with credit score below 650 are strictly rejected. Scores between 650-699 require manual underwriting or collateral.
- **Maximum Debt-to-Income (DTI) Ratio**: Total monthly debt obligations (including the new loan's proposed EMI) cannot exceed 50% of verified net monthly income.
- **Minimum Monthly Income**: Minimum net monthly income must be INR 25,000.
- **Maximum Loan Quantum**: Up to 15x net monthly income, capped at INR 20,00,000 for standard retail customers.
- **Standard Interest Rates**:
  - Credit Score 750+: 10.5% p.a.
  - Credit Score 700 - 749: 12.0% p.a.
  - Credit Score 650 - 699: 14.5% p.a.
- **Loan Tenures**: Available from 12 to 60 months.

## 2. EMI Calculation Guidelines
- Equated Monthly Installment (EMI) follows standard reducing balance amortization:
  EMI = [P x R x (1+R)^N] / [(1+R)^N - 1]
  where P = Principal, R = Monthly interest rate (Annual % / 12 / 100), N = Tenure in months.

## 3. Fraud Detection & Risk Scoring Policy
- **Risk Score Scale**: 0 to 100.
  - 0 - 30: Low Risk. Normal transaction activity.
  - 31 - 69: Medium Risk. Additional monitoring / step-up OTP authentication advised.
  - 70 - 100: High Risk. Potential fraud. Recommend immediate card freeze and transaction hold.
- **Risk Indicators & Weights**:
  - Large Outlier Amount: Transaction > 3x average customer transaction (+30 pts).
  - Foreign / High-Risk IP / Geo: Transaction initiated from outside the customer's registered country without travel notice (+35 pts).
  - Unrecognized / New Device: Unregistered or suspicious device (+25 pts).
  - High Velocity: Multiple transactions within minutes (+20 pts).
  - Round high amounts or crypto/gambling merchant codes (+15 pts).
- **Human-in-the-Loop Protocol**:
  - Freezing a debit/credit card (`block_card`) or formally flagging a transaction as fraud (`flag_transaction`) MUST have explicit customer/officer confirmation.
