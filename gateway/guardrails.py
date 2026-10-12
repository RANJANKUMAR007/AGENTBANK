import re
import time
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from knowledge.banking_knowledge import (
    is_prompt_injection,
    is_banking_related,
    PROMPT_INJECTION_PATTERNS,
    STANDARD_OFF_TOPIC_REFUSAL
)

class GuardrailCheckResult(BaseModel):
    is_safe: bool
    refusal_reason: Optional[str] = None
    applied_rules: List[str] = Field(default_factory=list)
    masked_text: Optional[str] = None
    is_prompt_injection: bool = False

class SessionRateLimiter:
    """Simple sliding-window rate limiter per session."""
    def __init__(self, max_requests: int = 30, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._history: Dict[str, List[float]] = {}

    def is_allowed(self, session_id: str) -> bool:
        now = time.time()
        timestamps = self._history.get(session_id, [])
        # filter out expired
        timestamps = [t for t in timestamps if now - t < self.window_seconds]
        if len(timestamps) >= self.max_requests:
            return False
        timestamps.append(now)
        self._history[session_id] = timestamps
        return True

class AIGateway:
    """
    AI Gateway & Safety Guardrails Layer.
    - Prompt-injection & jailbreak defense (routes to Fraud Investigation)
    - Off-topic filter (refuses non-banking topics)
    - Cross-customer authorization & boundary checking
    - PII data masking (masking card numbers, account numbers, email, phone)
    - Session budget & rate limiting
    """
    def __init__(self):
        self.rate_limiter = SessionRateLimiter(max_requests=40, window_seconds=60)
        
        # Injection / jailbreak signatures
        self.jailbreak_patterns = PROMPT_INJECTION_PATTERNS

        # Other customer references to block cross-customer access attempts
        # (Demo customers: Priya, Arjun, Meera)
        self.customer_names = {
            "CUST_001": ["arjun", "meera"],
            "CUST_002": ["priya", "meera"],
            "CUST_003": ["priya", "arjun"]
        }

        # Non-banking topic indicators
        self.off_topic_patterns = [
            r"write\s+(a\s+)?poem",
            r"tell\s+me\s+a\s+joke",
            r"who\s+won\s+the\s+world\s+cup",
            r"recipe\s+for",
            r"translate\s+this\s+french",
            r"write\s+python\s+code\s+to\s+hack",
            r"\b(what('s|\s+is)\s+the\s+)?weather\b",
            r"\b(tell\s+me\s+about\s+)?movies?\b",
            r"\b(write|show|generate)\s+(some\s+)?(python|java|javascript|c\+\+|code|coding)\b",
            r"\bhow\s+to\s+code\b"
        ]

    def inspect_request(
        self,
        user_message: str,
        session_customer_id: str,
        session_id: str
    ) -> GuardrailCheckResult:
        rules_applied = []

        # 1. Rate Limit Check
        rules_applied.append("RateLimiter")
        if not self.rate_limiter.is_allowed(session_id):
            return GuardrailCheckResult(
                is_safe=False,
                refusal_reason="Rate limit exceeded for this session. Please wait a moment before sending more requests.",
                applied_rules=rules_applied,
                is_prompt_injection=False
            )

        lower_msg = user_message.lower().strip()

        # 2. Prompt Injection / Jailbreak Filter
        rules_applied.append("PromptInjectionDefense")
        if is_prompt_injection(lower_msg) or any(re.search(pattern, lower_msg) for pattern in self.jailbreak_patterns):
            return GuardrailCheckResult(
                is_safe=False,
                refusal_reason="Security Alert: Your request was blocked because it contains instructions that attempt to alter or override the banking assistant's safety boundaries. Initiating automated Fraud Investigation.",
                applied_rules=rules_applied,
                is_prompt_injection=True
            )

        # 3. Cross-Customer Authorization Check
        rules_applied.append("CrossCustomerAuthorization")

        # Generic unauthorized third-party inquiry phrases
        generic_third_party = [
            r"another\s+customer('s)?",
            r"someone\s+else('s)?",
            r"other\s+people('s)?",
            r"different\s+customer('s)?"
        ]
        if any(re.search(pat, lower_msg) for pat in generic_third_party) and any(kw in lower_msg for kw in ["account", "balance", "transaction", "show", "data", "card", "loan", "details"]):
            return GuardrailCheckResult(
                is_safe=False,
                refusal_reason="Access Denied: You are authenticated as your own profile. You cannot view, inspect, or query financial data belonging to other customers.",
                applied_rules=rules_applied,
                is_prompt_injection=False
            )

        # Check against ALL currently registered customers (except active session customer)
        try:
            from data import db
            all_custs = db.get_all_customers()
        except Exception:
            all_custs = []

        for c in all_custs:
            cid = c.get("customer_id")
            if cid == session_customer_id:
                continue
            
            # Check ID match (e.g. CUST_002, CUST_GEN_0001)
            cid_lower = cid.lower()
            if cid_lower in lower_msg:
                return GuardrailCheckResult(
                    is_safe=False,
                    refusal_reason=f"Access Denied: You are authenticated as your own profile. You cannot view, inspect, or query financial data belonging to other customers.",
                    applied_rules=rules_applied,
                    is_prompt_injection=False
                )

            # Check Name match (first name or full name)
            c_name = c.get("name", "")
            if c_name:
                first_name = c_name.split()[0].lower()
                name_pattern = rf"\b{re.escape(first_name)}('s)?\b"
                if re.search(name_pattern, lower_msg) and any(kw in lower_msg for kw in ["account", "balance", "transaction", "show", "data", "card", "loan", "details"]):
                    return GuardrailCheckResult(
                        is_safe=False,
                        refusal_reason=f"Access Denied: You are authenticated as your own profile. You cannot view, inspect, or query financial data belonging to other customers.",
                        applied_rules=rules_applied,
                        is_prompt_injection=False
                    )

        # 4. Off-Topic / Non-Banking Filter
        rules_applied.append("BankingDomainScopeFilter")
        if not is_banking_related(lower_msg) or any(re.search(pattern, lower_msg) for pattern in self.off_topic_patterns):
            return GuardrailCheckResult(
                is_safe=False,
                refusal_reason="I cannot answer this question as it is not related to the banking system. AgentBank is specialized exclusively in banking, account operations, fraud security, and credit loans. I am unable to assist with non-banking topics such as the weather, movies, coding, or general trivia.",
                applied_rules=rules_applied,
                is_prompt_injection=False
            )

        return GuardrailCheckResult(
            is_safe=True,
            applied_rules=rules_applied,
            is_prompt_injection=False
        )

    def mask_pii(self, text: str) -> str:
        """
        Mask sensitive PII in outputs:
        - Account numbers: ACC_XXX_01 -> ACC_****01
        - Card numbers: 4111-2222-3333-8821 -> ****-****-****-8821
        - Phone numbers: +91-98765-43210 -> +91-*****-43210
        - Emails: priya.sharma@example.com -> p****@example.com
        """
        if not text:
            return text

        # Card numbers (16 digits or groups of 4)
        text = re.sub(r"\b(\d{4})[- ]?(\d{4})[- ]?(\d{4})[- ]?(\d{4})\b", r"****-****-****-\4", text)

        # Account numbers like ACC_PRIYA_01
        text = re.sub(r"\b(ACC_[A-Z]+_)(\d{2})\b", r"ACC_****\2", text)

        # Phone numbers like +91-98765-43210
        text = re.sub(r"(\+91[-\s]?)(\d{5})([-\s]?)(\d{5})", r"\1*****\3\4", text)

        # Email addresses
        def email_replacer(match):
            user = match.group(1)
            domain = match.group(2)
            if len(user) <= 1:
                masked_user = "*"
            else:
                masked_user = user[0] + "****"
            return f"{masked_user}@{domain}"

        text = re.sub(r"\b([a-zA-Z0-9_.+-]+)@([a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)\b", email_replacer, text)

        return text

gateway = AIGateway()
