import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

# Load environment before anything else
load_dotenv()

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from data import db
from gateway import gateway
from agents.supervisor import supervisor
from tools.registry import log_audit_entry

# Setup structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
)
logger = logging.getLogger("agentbank.api")

app = FastAPI(
    title="AgentBank API",
    description="Multi-Agent Banking Simulation Platform",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static folder
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# In-memory storage for pending Human-in-the-Loop approvals
# action_id -> action_data
PENDING_APPROVALS: Dict[str, Dict[str, Any]] = {}


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User prompt or question")
    customer_id: str = Field(default="CUST_001", description="Active logged-in demo customer ID")
    session_id: Optional[str] = Field(default=None, description="Optional persistent session ID")


class ApprovalRequest(BaseModel):
    action_id: str = Field(..., description="Unique ID of the pending HITL action")
    approved: bool = Field(..., description="True if approved by user, False if rejected")
    customer_id: str = Field(default="CUST_001", description="Active logged-in demo customer ID")


@app.get("/")
def serve_index():
    """Serve the single-page chat UI."""
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="UI index.html not found.")
    return FileResponse(str(index_file))


class GenerateCustomerRequest(BaseModel):
    seed: Optional[int] = Field(default=None, description="Optional deterministic seed integer")


@app.get("/api/customers")
def get_customers():
    """Retrieve list of switchable demo and generated customers with overview info."""
    customers = db.get_all_customers()
    summary = []
    for c in customers:
        summary.append({
            "customer_id": c["customer_id"],
            "name": c["name"],
            "kyc_status": c.get("kyc_status", "VERIFIED"),
            "credit_score": c.get("credit_score"),
            "monthly_income": c.get("monthly_income"),
            "accounts_count": len(c.get("accounts", [])),
            "anomaly_injected": c.get("anomaly_injected", False),
            "anomaly_type": c.get("anomaly_type")
        })
    return {"customers": summary}


@app.post("/api/customers/generate")
def create_generated_customer(req: Optional[GenerateCustomerRequest] = None):
    """
    Generates a realistic synthetic customer with ~30 transactions,
    accounts, devices, and potential risk anomaly.
    Returns the created customer profile and registers it in-memory.
    """
    seed_val = req.seed if req else None
    new_customer = db.generate_customer(seed=seed_val)
    logger.info(f"Generated new synthetic customer: {new_customer['customer_id']} ({new_customer['name']})")
    return {"customer": new_customer}


@app.post("/api/chat")
def handle_chat(req: ChatRequest):
    """
    Main conversational endpoint:
    1. Attaches correlation Trace ID.
    2. Runs AI Gateway guardrails (injection, cross-customer, domain check).
    3. Supervisor analyzes intent, coordinates specialist agents, executes deterministic tools.
    4. Applies PII masking to output.
    5. Returns unified response, agent trace, and any pending HITL actions.
    """
    trace_id = f"trc_{uuid.uuid4().hex[:8]}"
    browser_session = req.session_id or "default"
    # Session key = customer ID plus browser session ID
    session_id = f"{req.customer_id}_{browser_session}"

    logger.info(f"[{trace_id}] Received user message for customer {req.customer_id} (session {session_id}): '{req.message}'")

    # 1. AI Gateway & Guardrails check
    guardrail_result = gateway.inspect_request(
        user_message=req.message,
        session_customer_id=req.customer_id,
        session_id=session_id
    )

    if not guardrail_result.is_safe:
        if guardrail_result.is_prompt_injection:
            logger.warning(f"[{trace_id}] Prompt injection detected! Triggering Fraud Investigation via risk_agent.")
            fraud_result = supervisor.plan_and_execute_prompt_injection_fraud(
                user_message=req.message,
                session_customer_id=req.customer_id,
                trace_id=trace_id,
                session_id=session_id
            )
            raw_response = fraud_result["response"]
            masked_response = gateway.mask_pii(raw_response)
            return {
                "trace_id": trace_id,
                "response": masked_response,
                "guardrail": {
                    "passed": False,
                    "refusal_reason": guardrail_result.refusal_reason,
                    "applied_rules": guardrail_result.applied_rules
                },
                "trace": fraud_result["trace"],
                "pending_actions": fraud_result.get("pending_actions", [])
            }

        logger.warning(f"[{trace_id}] Blocked by guardrail: {guardrail_result.refusal_reason}")
        return {
            "trace_id": trace_id,
            "response": guardrail_result.refusal_reason,
            "guardrail": {
                "passed": False,
                "refusal_reason": guardrail_result.refusal_reason,
                "applied_rules": guardrail_result.applied_rules
            },
            "trace": {
                "trace_id": trace_id,
                "route": "general (no agent)",
                "intent": "GUARDRAIL_BLOCKED",
                "reasoning": f"Blocked by guardrail rules: {', '.join(guardrail_result.applied_rules)}",
                "plan": [],
                "needs_human": False,
                "agents_executed": [],
                "tool_calls": [],
                "iterations_total": 0,
                "duration_ms": 1.5,
                "aggregation_summary": "Route: general (no agent) - Request terminated early at AI Gateway safety layer."
            },
            "pending_actions": []
        }

    # 2. Supervisor / Orchestrator Execution
    result = supervisor.plan_and_execute(
        user_message=req.message,
        session_customer_id=req.customer_id,
        trace_id=trace_id,
        session_id=session_id
    )

    raw_response = result["response"]
    # 3. PII Masking on outgoing message
    masked_response = gateway.mask_pii(raw_response)

    # 4. Register any pending HITL actions
    client_pending = []
    for action in result.get("pending_actions", []):
        act_id = f"act_{uuid.uuid4().hex[:6]}"
        action["action_id"] = act_id
        action["customer_id"] = req.customer_id
        action["trace_id"] = trace_id
        PENDING_APPROVALS[act_id] = action
        client_pending.append(action)

    return {
        "trace_id": trace_id,
        "response": masked_response,
        "guardrail": {
            "passed": True,
            "refusal_reason": None,
            "applied_rules": guardrail_result.applied_rules
        },
        "trace": result["trace"],
        "pending_actions": client_pending
    }


@app.post("/api/approve")
def handle_approval(req: ApprovalRequest):
    """
    Handles Human-in-the-Loop approval/rejection of sensitive operations
    (e.g., block_card, flag_transaction).
    """
    action = PENDING_APPROVALS.get(req.action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Pending approval action not found or expired.")

    action_type = action.get("action_type")
    trace_id = action.get("trace_id", "trc_hitl")

    if not req.approved:
        # User cancelled action
        del PENDING_APPROVALS[req.action_id]
        log_audit_entry("human_supervisor", action_type, {"action_id": req.action_id}, "User rejected action", trace_id, status="REJECTED")
        return {
            "status": "cancelled",
            "message": f"Action {action_type} was cancelled by user request. No changes were made."
        }

    # Execute approved action
    if action_type == "BLOCK_CARD":
        card_last4 = action.get("card_last4")
        success = db.update_card_status(req.customer_id, card_last4, "BLOCKED")
        del PENDING_APPROVALS[req.action_id]
        log_audit_entry("human_supervisor", "block_card_confirmed", {"card_last4": card_last4}, f"Card ending in {card_last4} blocked", trace_id, status="SUCCESS")
        return {
            "status": "completed",
            "message": f"Card ending in {card_last4} has been frozen and blocked. A replacement card has been queued."
        }

    elif action_type == "FLAG_TRANSACTION":
        tx_id = action.get("transaction_id")
        reason = action.get("reason", "Unauthorized charge reported by customer")
        success = db.update_transaction(tx_id, {"status": "FLAGGED_FRAUD", "fraud_flagged_reason": reason})
        del PENDING_APPROVALS[req.action_id]
        log_audit_entry("human_supervisor", "flag_transaction_confirmed", {"transaction_id": tx_id}, f"Transaction {tx_id} marked as FLAGGED_FRAUD", trace_id, status="SUCCESS")
        return {
            "status": "completed",
            "message": f"Transaction {tx_id} has been flagged as fraudulent and submitted to the disputes department."
        }

    return {"status": "error", "message": f"Unknown action type: {action_type}"}
 
 
class ClearChatRequest(BaseModel):
    customer_id: str = Field(..., description="Customer ID whose conversation memory to clear")
    session_id: Optional[str] = Field(default=None, description="Optional browser session ID")
 
 
@app.post("/api/chat/clear")
def clear_chat(req: ClearChatRequest):
    """Clear conversational memory for the active customer's session."""
    browser_session = req.session_id or "default"
    session_id = f"{req.customer_id}_{browser_session}"
    supervisor.clear_history(session_id)
    logger.info(f"Cleared session history for {session_id}")
    return {"status": "cleared", "customer_id": req.customer_id, "session_id": session_id}

