import json
import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from llm.client import llm_client
from tools.registry import registry

logger = logging.getLogger("agentbank.agents")

class ToolExecutionTrace(BaseModel):
    tool_name: str
    arguments: Dict[str, Any]
    result: Any
    status: str

class AgentExecutionResult(BaseModel):
    agent_name: str
    final_response: str
    iterations: int
    traces: List[ToolExecutionTrace] = Field(default_factory=list)
    pending_actions: List[Dict[str, Any]] = Field(default_factory=list)

class BaseAgent:
    """
    Specialist agent with isolated system prompt, restricted toolset,
    and a strictly bounded tool-calling loop (max 5 iterations).
    """
    def __init__(self, name: str, system_prompt: str):
        self.name = name
        self.system_prompt = system_prompt
        self.max_iterations = 5

    def run(
        self,
        task: str,
        session_customer_id: str,
        trace_id: str,
        extra_context: Optional[str] = None
    ) -> AgentExecutionResult:
        tools_schemas = registry.get_schemas_for_agent(self.name)
        
        # Build initial conversation context
        user_message_content = f"TASK: {task}"
        if extra_context:
            user_message_content += f"\n\nCONTEXT FROM PRIOR AGENT/STEP:\n{extra_context}"
        
        messages = [
            {"role": "user", "content": user_message_content}
        ]

        traces: List[ToolExecutionTrace] = []
        pending_actions: List[Dict[str, Any]] = []
        final_response_text = ""
        iteration = 0

        while iteration < self.max_iterations:
            iteration += 1

            # Call LLM wrapper
            response = llm_client.generate(
                system_prompt=self.system_prompt,
                messages=messages,
                tools=tools_schemas,
                structured_json=False
            )

            # If the model requested tool calls
            if response.tool_calls:
                for tc in response.tool_calls:
                    tool_name = tc.get("name", "")
                    tool_args = tc.get("arguments", {})

                    # Execute via central registry with permission checks
                    exec_res = registry.execute(
                        calling_agent=self.name,
                        tool_name=tool_name,
                        args=tool_args,
                        trace_id=trace_id,
                        session_customer_id=session_customer_id
                    )

                    tool_output = exec_res.get("result", exec_res)
                    status = exec_res.get("status", "unknown")

                    traces.append(ToolExecutionTrace(
                        tool_name=tool_name,
                        arguments=tool_args,
                        result=tool_output,
                        status=status
                    ))

                    # Check for Human-in-the-Loop pending approvals
                    if isinstance(tool_output, dict) and tool_output.get("status") == "pending_approval":
                        pending_actions.append(tool_output)

                    # Append tool result into message history for the next iteration
                    messages.append({
                        "role": "assistant",
                        "content": f"[Invoked tool {tool_name} with {json.dumps(tool_args)}]"
                    })
                    messages.append({
                        "role": "user",
                        "content": f"TOOL_OUTPUT for {tool_name}:\n{json.dumps(tool_output, default=str)}"
                    })
            else:
                # LLM finished thinking and provided final text answer
                final_response_text = response.content or "Task completed successfully."
                break

        # Fallback if loop ended due to iteration cap or missing text
        if not final_response_text:
            if traces:
                last_trace = traces[-1]
                final_response_text = f"Action processed: {last_trace.tool_name} returned: {json.dumps(last_trace.result, default=str)}"
            else:
                final_response_text = "I have reviewed your request."

        return AgentExecutionResult(
            agent_name=self.name,
            final_response=final_response_text,
            iterations=iteration,
            traces=traces,
            pending_actions=pending_actions
        )
