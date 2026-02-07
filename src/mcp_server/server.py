"""
MCP (Model Context Protocol) Server

This FastAPI server exposes cloud infrastructure tools to the AI agent
while enforcing security policies through the Policy Engine.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
import sys
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.guardrails.policy_engine import PolicyEngine, PolicyViolationError
from src.mcp_server.tools import (
    cloud_infra,
    get_service_status,
    list_services,
    read_logs,
    restart_service,
    scale_fleet,
    delete_database
)


# Initialize FastAPI app
app = FastAPI(
    title="Proxi MCP Server",
    description="Context-Aware Cloud Guardian - Policy-Enforced Tool Server",
    version="1.0.0"
)


# Initialize Policy Engine
policy_path = Path(__file__).parent.parent.parent / "policies" / "ops_policy.json"
policy_engine = PolicyEngine(str(policy_path))


# Request/Response Models
class ToolRequest(BaseModel):
    """Request model for tool execution."""
    tool_name: str = Field(..., description="Name of the tool to execute")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Tool arguments")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Execution context")


class ToolResponse(BaseModel):
    """Response model for tool execution."""
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    policy_violation: bool = False
    blocked_reason: Optional[str] = None


class ModeChangeRequest(BaseModel):
    """Request model for changing operational mode."""
    mode: str = Field(..., description="Mode to switch to (NORMAL or EMERGENCY)")


# API Endpoints
@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "Proxi MCP Server",
        "status": "operational",
        "current_mode": policy_engine.get_current_mode(),
        "policy_engine": "active"
    }


@app.get("/policy/status")
async def get_policy_status():
    """Get current policy configuration and status."""
    return {
        "current_mode": policy_engine.get_current_mode(),
        "allowed_tools": policy_engine.get_allowed_tools(),
        "blocked_tools": policy_engine.get_blocked_tools(),
        "summary": policy_engine.get_policy_summary()
    }


@app.post("/policy/set-mode")
async def set_mode(request: ModeChangeRequest):
    """Change the operational mode (NORMAL or EMERGENCY)."""
    try:
        policy_engine.set_mode(request.mode)
        return {
            "success": True,
            "new_mode": request.mode,
            "allowed_tools": policy_engine.get_allowed_tools()
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/tools/execute", response_model=ToolResponse)
async def execute_tool(request: ToolRequest):
    """
    Execute a tool with policy enforcement.
    
    This is the critical endpoint that enforces security policies.
    Every tool execution MUST pass through policy validation first.
    """
    tool_name = request.tool_name
    arguments = request.arguments
    context = request.context
    
    print(f"\n🔧 Tool execution request: {tool_name}")
    print(f"   Arguments: {arguments}")
    print(f"   Current mode: {policy_engine.get_current_mode()}")
    
    # CRITICAL: Validate against policy BEFORE execution
    try:
        policy_engine.validate(tool_name, arguments, context)
    except PolicyViolationError as e:
        print(f"   ❌ BLOCKED by policy: {e.reason}")
        return ToolResponse(
            success=False,
            policy_violation=True,
            blocked_reason=str(e),
            error=f"Policy violation: {e.reason}"
        )
    
    # Policy check passed - execute the tool
    try:
        result = _execute_tool_function(tool_name, arguments)
        print(f"   ✓ Execution completed successfully")
        return ToolResponse(
            success=True,
            result=result
        )
    except Exception as e:
        print(f"   ❌ Execution error: {str(e)}")
        return ToolResponse(
            success=False,
            error=f"Execution error: {str(e)}"
        )


def _execute_tool_function(tool_name: str, arguments: Dict[str, Any]) -> Any:
    """
    Route tool execution to the appropriate function.
    
    This internal function maps tool names to their implementations.
    """
    tool_map = {
        "get_service_status": get_service_status,
        "read_logs": read_logs,
        "restart_service": restart_service,
        "scale_fleet": scale_fleet,
        "delete_database": delete_database,
        "list_services": list_services
    }
    
    if tool_name not in tool_map:
        raise ValueError(f"Unknown tool: {tool_name}")
    
    tool_function = tool_map[tool_name]
    
    # Execute the tool with its arguments
    try:
        result = tool_function(**arguments)
        return result
    except TypeError as e:
        raise ValueError(f"Invalid arguments for {tool_name}: {str(e)}")


@app.get("/infrastructure/status")
async def get_infrastructure_status():
    """Get current infrastructure status (diagnostic endpoint)."""
    return {
        "services": cloud_infra.services,
        "fleet_size": cloud_infra.fleet_size,
        "recent_actions": cloud_infra.execution_log[-10:]
    }


@app.post("/infrastructure/simulate-incident")
async def simulate_incident(service: str, status: str = "critical"):
    """Simulate a service incident for demo purposes."""
    cloud_infra.set_service_health(service, status)
    return {
        "success": True,
        "message": f"Simulated incident: {service} set to {status}"
    }


# Tool catalog for agent discovery
@app.get("/tools/catalog")
async def get_tool_catalog():
    """Get catalog of available tools with descriptions."""
    return {
        "tools": [
            {
                "name": "list_services",
                "description": "List all available cloud services",
                "parameters": {},
                "category": "read-only"
            },
            {
                "name": "get_service_status",
                "description": "Get the current health status of cloud services",
                "parameters": {
                    "service_name": {
                        "type": "string",
                        "description": "Specific service to check (optional)",
                        "required": False
                    }
                },
                "category": "read-only"
            },
            {
                "name": "read_logs",
                "description": "Read recent system logs",
                "parameters": {
                    "lines": {
                        "type": "integer",
                        "description": "Number of log lines to retrieve",
                        "default": 10
                    }
                },
                "category": "read-only"
            },
            {
                "name": "restart_service",
                "description": "Restart a cloud service (EMERGENCY mode only)",
                "parameters": {
                    "service_name": {
                        "type": "string",
                        "description": "Name of the service to restart",
                        "required": True
                    }
                },
                "category": "active"
            },
            {
                "name": "scale_fleet",
                "description": "Scale the number of service instances (EMERGENCY mode only)",
                "parameters": {
                    "count": {
                        "type": "integer",
                        "description": "Target number of instances",
                        "required": True
                    }
                },
                "category": "active"
            },
            {
                "name": "delete_database",
                "description": "Delete a database (ALWAYS BLOCKED)",
                "parameters": {
                    "db_name": {
                        "type": "string",
                        "description": "Name of the database",
                        "required": True
                    }
                },
                "category": "destructive"
            }
        ],
        "current_mode": policy_engine.get_current_mode(),
        "allowed_in_current_mode": policy_engine.get_allowed_tools()
    }


if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*70)
    print("  PROXI MCP SERVER - Context-Aware Cloud Guardian")
    print("="*70)
    print(policy_engine.get_policy_summary())
    print("\nStarting server on http://localhost:8000")
    print("API docs available at http://localhost:8000/docs")
    print("="*70 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)