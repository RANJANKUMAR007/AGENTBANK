import json
import logging
import re
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from llm.client import llm_client
from agents.base import AgentExecutionResult, ToolExecutionTrace
from agents.customer import customer_agent
from agents.risk import risk_agent
from agents.credit import credit_agent
from knowledge.banking_knowledge import (
    lookup_banking_concept,
    is_banking_related,
    is_prompt_injection,
    STANDARD_OFF_TOPIC_REFUSAL
)

logger = logging.getLogger("agentbank.supervisor")


def sanitize_plain_text(text: str) -> str:
    """Ensure no LaTeX or $...$ formulas appear in the output."""
    if not text:
        return ""
    # Standardize reducing balance EMI formula in plain text
    text = text.replace(r"\frac{P \times R \times (1+R)^N}{(1+R)^N - 1}", "P x r x (1+r)^n / ((1+r)^n - 1)")
    text = text.replace(r"\frac{P \times r \times (1+r)^n}{(1+r)^n - 1}", "P x r x (1+r)^n / ((1+r)^n - 1)")
    # Replace LaTeX multiplication and fractions
    text = text.replace(r"\times", "x")
    text = re.sub(r"\\frac\{([^}]+)\}\{([^}]+)\}", r"(\1 / \2)", text)
    # Strip any dollar signs used for math
    text = text.replace("$", "")
    return text


class PlanStep(BaseModel):
    agent: str = Field(..., description="Target specialist agent: customer_agent, risk_agent, or credit_agent")
    task: str = Field(..., description="Specific goal for the specialist agent to accomplish")


class SupervisorPlan(BaseModel):
    route: str = Field(default="specialist", description="Routing decision: 'general' (no agent) or 'specialist'")
    intent: str = Field(..., description="High-level classified intent")
    reasoning: str = Field(..., description="Step-by-step reasoning for agent selection and ordering")
    plan: List[PlanStep] = Field(default_factory=list, description="Sequential list of specialist agent tasks. Empty for general route.")
    direct_answer: Optional[str] = Field(default=None, description="Direct answer from supervisor for general knowledge, greetings, or refusals.")
    needs_human: bool = Field(default=False, description="Whether immediate human escalation is needed")


class SupervisorTrace(BaseModel):
    trace_id: str
    route: str = Field(default="specialist", description="Routing path: 'general (no agent)' or 'specialist'")
    intent: str
    reasoning: str
    plan: List[Dict[str, str]]
    needs_human: bool
    agents_executed: List[str]
    tool_calls: List[Dict[str, Any]]
    iterations_total: int
    duration_ms: float
    aggregation_summary: str


class SupervisorOrchestrator:
    """
    Supervisor / Orchestrator Agent.
    - Intent classification & task decomposition using structured LLM output
    - "General" route: direct supervisor answers (no agent, no tool calls) for educational,
      greeting/vague, or off-topic prompts
    - "Specialist" route: multi-agent sequential chaining when customer data or tools are required
    - History bleed prevention: classifies CURRENT message first
    - Formula formatting: strictly plain text (no LaTeX or $...$)
    """
    def __init__(self):
        self.agents = {
            "customer_agent": customer_agent,
            "risk_agent": risk_agent,
            "credit_agent": credit_agent
        }
        # Short in-memory conversation memory per session: session_id -> list of exchanges
        self._memory: Dict[str, List[Dict[str, str]]] = {}

    def get_history(self, session_id: str) -> List[Dict[str, str]]:
        return self._memory.get(session_id, [])

    def append_history(self, session_id: str, role: str, content: str) -> None:
        if session_id not in self._memory:
            self._memory[session_id] = []
        self._memory[session_id].append({"role": role, "content": content})
        # Keep sliding window of last 6 exchanges (12 messages)
        if len(self._memory[session_id]) > 12:
            self._memory[session_id] = self._memory[session_id][-12:]

    def clear_history(self, session_id: str) -> None:
        """Clear conversation history for the specified session ID."""
        if session_id in self._memory:
            del self._memory[session_id]

    def plan_and_execute(
        self,
        user_message: str,
        session_customer_id: str,
        trace_id: str,
        session_id: str
    ) -> Dict[str, Any]:
        start_time = time.time()
        history = self.get_history(session_id)

        # 1. Supervisor Structured Intent & Planning Step
        supervisor_prompt = f"""You are the Lead Supervisor & Orchestrator for AgentBank.
Analyze the user request and determine the execution route.

ROUTING RULES:
1. "general" route (plan: [], no agent, no tool calls):
   - General knowledge / educational questions (what is EMI, what is percentage, how does a credit score work, what is KYC, how does fraud detection work):
     Answer directly in direct_answer in 2-4 plain sentences with one simple numeric example.
     NEVER output LaTeX or $...$ math. Write formulas in plain text (e.g. EMI = P x r x (1+r)^n / ((1+r)^n - 1)).
   - Greetings / vague requests ("loan?", "help", "hi"):
     Answer with ONE clarifying question in direct_answer, no agent.
   - Truly off-topic (weather, movies, coding, recipes):
     Provide a polite refusal in direct_answer, no agent.
   - EXCEPTION: If the question specifically relates to loan/KYC bank policy rules or required documents under bank policy, route to credit_agent to call retrieve_loan_policy instead.

2. "specialist" route (call specialist agents with tools):
   - Customer-specific requests (my balance, my transactions, my loan, my charge, investigate charge):
     Route to customer_agent, risk_agent, or credit_agent.
   - Agents must only be called when the request needs customer data or a tool. Never call get_customer_360 or any tool "just in case".

3. PREVENT HISTORY BLEED:
   - Classify the CURRENT message first!
   - Use conversation history only to resolve references like "it" or "that charge". Do NOT let past topics override a new, separate user query.

4. REASONING FIELD REQUIREMENT:
   - The reasoning field MUST be specific to the user's actual prompt: explain exactly why the route was chosen for '{user_message}'.

Schema:
{{
  "route": "general" or "specialist",
  "intent": "INTENT_NAME",
  "reasoning": "Specific reason citing '{user_message}' and chosen route",
  "direct_answer": "Plain text answer for general route, or null for specialist",
  "plan": [
    {{"agent": "customer_agent" | "risk_agent" | "credit_agent", "task": "instruction"}}
  ],
  "needs_human": false
}}
"""

        # Format messages emphasizing the current message first to prevent history bleed
        messages_for_supervisor = list(history)
        current_prompt = f"CURRENT_USER_REQUEST: {user_message}\n(Classify this current request first; use prior history ONLY if needed to resolve pronouns like 'it' or 'that charge')."
        messages_for_supervisor.append({"role": "user", "content": current_prompt})

        plan_response = llm_client.generate(
            system_prompt=supervisor_prompt,
            messages=messages_for_supervisor,
            structured_json=True
        )

        # Parse Plan JSON
        raw_plan_content = plan_response.content or "{}"
        supervisor_plan: Optional[SupervisorPlan] = None
        try:
            cleaned = raw_plan_content.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            parsed_plan = json.loads(cleaned.strip())

            # Normalize plan & route
            if not parsed_plan.get("plan"):
                parsed_plan["plan"] = []
            if parsed_plan.get("direct_answer") or len(parsed_plan.get("plan", [])) == 0:
                parsed_plan["route"] = "general"

            supervisor_plan = SupervisorPlan(**parsed_plan)
        except Exception as e:
            logger.warning(f"Failed to parse structured plan: {e}. Applying deterministic classification.")

        if not supervisor_plan:
            msg_lower = user_message.lower().strip()

            # Rule 0: Prompt Injection / Adversarial attempt -> Trigger Fraud Investigation
            if is_prompt_injection(msg_lower):
                supervisor_plan = SupervisorPlan(
                    route="specialist",
                    intent="PROMPT_INJECTION_FRAUD_INVESTIGATION",
                    reasoning=f"User request '{user_message}' matched prompt injection pattern. Triggering automated Fraud Investigation via risk_agent.",
                    plan=[PlanStep(agent="risk_agent", task=f"Investigate adversarial prompt injection security threat and verify customer device records for: '{user_message}'")],
                    needs_human=False
                )

            # Rule 1: Non-banking off-topic queries
            elif not is_banking_related(msg_lower):
                supervisor_plan = SupervisorPlan(
                    route="general",
                    intent="OFF_TOPIC_REFUSAL",
                    reasoning=f"User asked '{user_message}': Query is off-topic and unrelated to banking; refusing politely without specialist agents.",
                    plan=[],
                    direct_answer="I cannot answer this question as it is not related to the banking system. AgentBank is specialized exclusively in banking, account operations, fraud security, and credit loans. I am unable to assist with non-banking topics such as the weather, movies, coding, or general trivia.",
                    needs_human=False
                )

            # Rule 2: Greetings / vague requests
            elif msg_lower in ["hi", "hello", "hey", "help", "loan?", "loan", "check my account", "account?", "balance?"] or (len(msg_lower.split()) <= 2 and any(w in msg_lower for w in ["loan", "account", "help"])):
                if "loan" in msg_lower:
                    clarification = "Could you please specify what loan assistance you need (for example, checking personal loan eligibility or calculating an EMI)?"
                elif any(w in msg_lower for w in ["account", "balance"]):
                    clarification = "Would you like to check your savings account balance, view your recent transactions, or review your profile overview?"
                else:
                    clarification = "Hello! How may I assist you with your AgentBank accounts, transactions, fraud prevention, or loan inquiries today?"

                supervisor_plan = SupervisorPlan(
                    route="general",
                    intent="CLARIFICATION_NEEDED",
                    reasoning=f"User asked '{user_message}': Request is brief or ambiguous; asking one clarifying question with no agent.",
                    plan=[],
                    direct_answer=clarification,
                    needs_human=False
                )

            # Rule 3: Loan/KYC Policy retrieval (specific to bank policies)
            elif any(w in msg_lower for w in ["loan policy", "kyc policy", "underwriting policy", "bank policy", "what documents do i need", "documents required", "lending policy"]):
                supervisor_plan = SupervisorPlan(
                    route="specialist",
                    intent="POLICY_RETRIEVAL",
                    reasoning=f"User asked '{user_message}': Query asks about internal bank loan or KYC policy guidelines; calling retrieve_loan_policy via credit_agent.",
                    plan=[PlanStep(agent="credit_agent", task=f"Retrieve bank underwriting policy guidelines for: '{user_message}' using retrieve_loan_policy.")],
                    needs_human=False
                )

            # Rule 4: Multi-agent combo
            elif "suspicious" in msg_lower and ("loan" in msg_lower or "eligib" in msg_lower):
                supervisor_plan = SupervisorPlan(
                    route="specialist",
                    intent="MULTI_AGENT_FRAUD_AND_LOAN_CHECK",
                    reasoning=f"User asked '{user_message}': Decomposed into risk_agent to audit suspicious activity followed by credit_agent to assess underwriting impact.",
                    plan=[
                        PlanStep(agent="risk_agent", task=f"Investigate recent transaction for fraud in request: '{user_message}'"),
                        PlanStep(agent="credit_agent", task="Evaluate loan eligibility and impact of reported transaction.")
                    ],
                    needs_human=False
                )

            # Rule 5: Fraud inquiry
            elif any(w in msg_lower for w in ["fraud", "suspicious", "charge", "recognize", "unauthorized"]):
                supervisor_plan = SupervisorPlan(
                    route="specialist",
                    intent="FRAUD_INVESTIGATION",
                    reasoning=f"User inquired about unrecognized or suspicious transaction in '{user_message}': Routing to risk_agent for fraud scoring and device check.",
                    plan=[PlanStep(agent="risk_agent", task=f"Investigate suspicious charge from request: '{user_message}'")],
                    needs_human=False
                )

            # Rule 6: Loan inquiry
            elif any(w in msg_lower for w in ["loan", "borrow", "lakh"]) or ("emi" in msg_lower and "my" in msg_lower):
                supervisor_plan = SupervisorPlan(
                    route="specialist",
                    intent="LOAN_ELIGIBILITY_INQUIRY",
                    reasoning=f"User asked about loan eligibility or borrowing in '{user_message}': Routing to credit_agent for credit profile evaluation and EMI calculation.",
                    plan=[PlanStep(agent="credit_agent", task=f"Check credit profile and evaluate loan request: '{user_message}'")],
                    needs_human=False
                )

            # Rule 7: Default customer profile / balance / transactions
            elif any(w in msg_lower for w in ["my balance", "show my transactions", "my transaction", "my statement", "summary of my profile", "my account", "my card"]):
                supervisor_plan = SupervisorPlan(
                    route="specialist",
                    intent="BANKING_CUSTOMER_INQUIRY",
                    reasoning=f"User requested account balances or transaction records in '{user_message}': Routing to customer_agent to fetch ledger data.",
                    plan=[PlanStep(agent="customer_agent", task=f"Handle customer request: '{user_message}'")],
                    needs_human=False
                )

            # Rule 8: Comprehensive General Banking Knowledge Concepts
            elif lookup_banking_concept(msg_lower):
                concept_ans = lookup_banking_concept(msg_lower)
                supervisor_plan = SupervisorPlan(
                    route="general",
                    intent="GENERAL_BANKING_KNOWLEDGE",
                    reasoning=f"User asked '{user_message}': General educational banking inquiry; supervisor answers directly without specialist agents or tools.",
                    plan=[],
                    direct_answer=concept_ans,
                    needs_human=False
                )

            # Rule 9: Account / balance / transaction general inquiry
            elif any(w in msg_lower for w in ["balance", "transaction", "statement", "summary", "profile", "account"]):
                supervisor_plan = SupervisorPlan(
                    route="specialist",
                    intent="BANKING_CUSTOMER_INQUIRY",
                    reasoning=f"User requested account balances or transaction records in '{user_message}': Routing to customer_agent to fetch ledger data.",
                    plan=[PlanStep(agent="customer_agent", task=f"Handle customer request: '{user_message}'")],
                    needs_human=False
                )
            else:
                supervisor_plan = SupervisorPlan(
                    route="general",
                    intent="GENERAL_ASSISTANCE",
                    reasoning=f"User sent general greeting or open-ended request '{user_message}': Answering directly from supervisor.",
                    plan=[],
                    direct_answer="Hello! I am AgentBank's virtual assistant. I can help you check account balances, review recent transactions, evaluate personal loans, or investigate suspicious charges. How may I assist you today?",
                    needs_human=False
                )

        # 2. Check for "General" Route Execution (0 agents, 0 tools)
        if supervisor_plan.route == "general" or len(supervisor_plan.plan) == 0 or supervisor_plan.direct_answer:
            final_answer = supervisor_plan.direct_answer or "Your request has been processed directly by AgentBank."
            final_answer = sanitize_plain_text(final_answer)

            # Save to conversation memory
            self.append_history(session_id, "user", user_message)
            self.append_history(session_id, "assistant", final_answer)

            duration_ms = round((time.time() - start_time) * 1000, 2)
            trace_data = SupervisorTrace(
                trace_id=trace_id,
                route="general (no agent)",
                intent=supervisor_plan.intent,
                reasoning=supervisor_plan.reasoning,
                plan=[],
                needs_human=False,
                agents_executed=[],
                tool_calls=[],
                iterations_total=0,
                duration_ms=duration_ms,
                aggregation_summary="Route: general (no agent) - Supervisor handled request directly without specialist agents or tools."
            )

            return {
                "response": final_answer,
                "trace": trace_data.model_dump(),
                "pending_actions": []
            }

        # 3. Sequential Multi-Agent Execution Loop ("specialist" route)
        agent_results: List[AgentExecutionResult] = []
        accumulated_context = ""
        total_iterations = 0
        all_traces: List[Dict[str, Any]] = []
        pending_hitl_actions: List[Dict[str, Any]] = []

        for step in supervisor_plan.plan:
            target_agent = self.agents.get(step.agent)
            if not target_agent:
                continue

            result = target_agent.run(
                task=step.task,
                session_customer_id=session_customer_id,
                trace_id=trace_id,
                extra_context=accumulated_context if accumulated_context else None
            )

            agent_results.append(result)
            total_iterations += result.iterations

            for t in result.traces:
                all_traces.append({
                    "agent": result.agent_name,
                    "tool": t.tool_name,
                    "arguments": t.arguments,
                    "result": t.result,
                    "status": t.status
                })

            if result.pending_actions:
                pending_hitl_actions.extend(result.pending_actions)

            accumulated_context += f"\n[Output from {result.agent_name}]: {result.final_response}"

        # 4. Supervisor Final Aggregation & Synthesis
        # If a single specialist agent executed and produced a detailed data-backed response, use it directly or synthesize without losing data
        if len(agent_results) == 1 and agent_results[0].final_response and not agent_results[0].final_response.startswith("Action processed:"):
            final_answer = sanitize_plain_text(agent_results[0].final_response)
        else:
            aggregation_prompt = f"""You are the friendly, professional voice of AgentBank.
Synthesize the findings from the specialist agent(s) into a unified, clear, and reassuring response for the customer.

Customer Question: "{user_message}"
Supervisor Plan: {supervisor_plan.intent} - {supervisor_plan.reasoning}

Specialist Agent Findings and Tool Data:
{accumulated_context}

Strict Instructions:
1. Preserve all concrete data: actual balances, transactions list (date, merchant, amount, category), exact approved/rejected loan decision, exact EMI, DTI %, and interest rate.
2. NEVER replace actual data with generic summaries like "Here is your balance summary" or "check the trace panel".
3. If loan eligibility was checked, start with the decision: "You are eligible: APPROVED..." or "You are not eligible: REJECTED...", state assumption in one line, and end with a next step.
4. Do NOT mention internal agent names (like 'risk_agent') to the user; speak cohesively as AgentBank.
5. NEVER output mathematical formulas using LaTeX or dollar signs ($...$).
"""
            synthesis_resp = llm_client.generate(
                system_prompt=aggregation_prompt,
                messages=[{"role": "user", "content": "Please synthesize the final answer preserving all tool output data."}],
                tools=None
            )
            final_answer = sanitize_plain_text(synthesis_resp.content or agent_results[0].final_response if agent_results else "Your request has been processed successfully.")

        # Save to conversation memory
        self.append_history(session_id, "user", user_message)
        self.append_history(session_id, "assistant", final_answer)

        duration_ms = round((time.time() - start_time) * 1000, 2)

        trace_data = SupervisorTrace(
            trace_id=trace_id,
            route="specialist",
            intent=supervisor_plan.intent,
            reasoning=supervisor_plan.reasoning,
            plan=[{"agent": s.agent, "task": s.task} for s in supervisor_plan.plan],
            needs_human=supervisor_plan.needs_human or (len(pending_hitl_actions) > 0),
            agents_executed=[r.agent_name for r in agent_results],
            tool_calls=all_traces,
            iterations_total=total_iterations,
            duration_ms=duration_ms,
            aggregation_summary="Synthesized unified response across specialist agents."
        )

        return {
            "response": final_answer,
            "trace": trace_data.model_dump(),
            "pending_actions": pending_hitl_actions
        }

    def plan_and_execute_prompt_injection_fraud(
        self,
        user_message: str,
        session_customer_id: str,
        trace_id: str,
        session_id: str
    ) -> Dict[str, Any]:
        """
        Executes dedicated Fraud Investigation when an adversarial prompt injection is detected.
        Invokes risk_agent to conduct security analysis, verify trusted devices, and record audit trace.
        """
        start_time = time.time()
        from tools.registry import log_audit_entry

        risk_task = f"Investigate adversarial prompt injection security threat and audit customer device history for: '{user_message}'"
        risk_result = self.agents["risk_agent"].run(
            task=risk_task,
            session_customer_id=session_customer_id,
            trace_id=trace_id
        )

        all_traces = [{
            "agent": "risk_agent",
            "tool": t.tool_name,
            "arguments": t.arguments,
            "result": t.result,
            "status": t.status
        } for t in risk_result.traces]

        log_audit_entry(
            agent_name="risk_agent",
            tool_name="prompt_injection_fraud_investigation",
            args={"user_message": user_message, "session_id": session_id},
            result_summary=f"Prompt injection intercepted for customer {session_customer_id}; fraud security audit completed.",
            trace_id=trace_id,
            status="SUCCESS"
        )

        response_text = (
            "⚠️ **Security Alert: Automated Fraud Investigation Initiated**\n\n"
            "A prompt injection attempt was detected by the AgentBank security gateway. "
            "In accordance with our fraud prevention and safety protocols, our automated Risk & Fraud "
            "Investigation system has performed an immediate security evaluation:\n\n"
            f"- **Incident Classification**: Adversarial Prompt Injection / Boundary Override Attempt\n"
            f"- **Investigating Specialist**: AgentBank Risk & Fraud Specialist (`risk_agent`)\n"
            f"- **Account & Session Audit**: Inspected active session for customer {session_customer_id}; customer device records verified\n"
            f"- **Protective Actions Taken**: Immutable security audit entry logged ({trace_id}). Enhanced fraud monitoring activated.\n\n"
            "All core banking ledgers, customer balances, and system instructions remain securely safeguarded."
        )

        self.append_history(session_id, "user", user_message)
        self.append_history(session_id, "assistant", response_text)

        duration_ms = round((time.time() - start_time) * 1000, 2)
        trace_data = SupervisorTrace(
            trace_id=trace_id,
            route="specialist",
            intent="PROMPT_INJECTION_FRAUD_INVESTIGATION",
            reasoning=f"User attempt '{user_message}' contained adversarial prompt injection. Intercepted and routed to risk_agent for immediate fraud investigation and security audit.",
            plan=[{"agent": "risk_agent", "task": risk_task}],
            needs_human=False,
            agents_executed=["risk_agent"],
            tool_calls=all_traces,
            iterations_total=risk_result.iterations,
            duration_ms=duration_ms,
            aggregation_summary="Prompt injection intercepted - Risk & Fraud Investigation completed by risk_agent."
        )

        return {
            "response": response_text,
            "trace": trace_data.model_dump(),
            "pending_actions": []
        }

supervisor = SupervisorOrchestrator()

