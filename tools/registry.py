import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field

LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)
AUDIT_LOG_FILE = LOGS_DIR / "audit.jsonl"

def log_audit_entry(
    agent_name: str,
    tool_name: str,
    args: Dict[str, Any],
    result_summary: str,
    trace_id: str,
    status: str = "SUCCESS"
) -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trace_id": trace_id,
        "agent": agent_name,
        "tool": tool_name,
        "args": args,
        "result_summary": result_summary,
        "status": status,
    }
    with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

class ToolDefinition(BaseModel):
    name: str
    description: str
    owner_agent: str
    args_schema: Any
    func: Callable[..., Any]

    class Config:
        arbitrary_types_allowed = True

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}

    def register(self, tool_def: ToolDefinition) -> None:
        self._tools[tool_def.name] = tool_def

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        return self._tools.get(name)

    def list_tools_for_agent(self, agent_name: str) -> List[ToolDefinition]:
        return [t for t in self._tools.values() if t.owner_agent == agent_name]

    def get_schemas_for_agent(self, agent_name: str) -> List[Dict[str, Any]]:
        tools = self.list_tools_for_agent(agent_name)
        schemas = []
        for t in tools:
            # Generate OpenAI/Gemini/Anthropic compatible function schema
            json_schema = t.args_schema.model_json_schema() if hasattr(t.args_schema, "model_json_schema") else {}
            schemas.append({
                "name": t.name,
                "description": t.description,
                "parameters": json_schema
            })
        return schemas

    def execute(
        self,
        calling_agent: str,
        tool_name: str,
        args: Dict[str, Any],
        trace_id: str,
        session_customer_id: str
    ) -> Dict[str, Any]:
        """
        Executes a registered tool under strict permission and security boundaries.
        Returns a dict with status and result. Never crashes caller.
        """
        tool = self.get_tool(tool_name)
        if not tool:
            err = f"Security Violation: Tool '{tool_name}' not found."
            log_audit_entry(calling_agent, tool_name, args, err, trace_id, status="FAILED")
            return {"status": "error", "message": err}

        # Permission boundary enforcement
        if tool.owner_agent != calling_agent:
            err = f"Permission Denied: Agent '{calling_agent}' is not authorized to call '{tool_name}' (owned by '{tool.owner_agent}')."
            log_audit_entry(calling_agent, tool_name, args, err, trace_id, status="PERMISSION_DENIED")
            return {"status": "error", "message": err}

        # Schema validation
        try:
            validated_args = tool.args_schema(**args)
        except Exception as e:
            err = f"Schema Validation Error for tool '{tool_name}': {str(e)}"
            log_audit_entry(calling_agent, tool_name, args, err, trace_id, status="VALIDATION_ERROR")
            return {"status": "error", "message": err}

        # Execute business logic
        try:
            # inject session customer id and trace id if accepted
            call_kwargs = validated_args.model_dump()
            result = tool.func(session_customer_id=session_customer_id, trace_id=trace_id, **call_kwargs)
            
            # Format summary for audit log
            summary = str(result)[:200]
            log_audit_entry(calling_agent, tool_name, args, summary, trace_id, status="SUCCESS")
            return {"status": "success", "result": result}
        except Exception as e:
            err = f"Execution Error in '{tool_name}': {str(e)}"
            log_audit_entry(calling_agent, tool_name, args, err, trace_id, status="EXECUTION_ERROR")
            return {"status": "error", "message": err}

registry = ToolRegistry()
