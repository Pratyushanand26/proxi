"""
MCP Server - Enhanced with Time-Limited Permissions

This FastAPI server exposes cloud infrastructure tools with:
- Policy enforcement
- Time-limited permission support
- Interactive permission management
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.guardrails.policy_engine import PolicyEngine, PolicyViolationError
from src.mcp_server.tools import (
    cloud_infra, get_service_status, list_services,
    read_logs, restart_service, scale_fleet, delete_database
)

# Initialize app
app = FastAPI(
    title="Proxi MCP Server - Enhanced",
    description="Context-Aware Cloud Guardian with Time-Limited Permissions",
    version="2.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Policy Engine
policy_path = Path(__file__).parent.parent.parent / "policies" / "ops_policy.json"
policy_engine = PolicyEngine(str(policy_path))


# Request/Response Models
class ToolRequest(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)

class ToolResponse(BaseModel):
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    policy_violation: bool = False
    blocked_reason: Optional[str] = None

class ModeChangeRequest(BaseModel):
    mode: str

class TemporaryPermissionRequest(BaseModel):
    duration_seconds: int = Field(default=10, ge=1, le=300)

class TemporaryExtensionRequest(BaseModel):
    additional_seconds: int = Field(default=10, ge=1, le=60)


# API Endpoints
@app.get("/")
async def root():
    """Health check endpoint."""
    temp_status = policy_engine.get_temporary_status()
    return {
        "service": "Proxi MCP Server Enhanced",
        "status": "operational",
        "current_mode": policy_engine.get_current_mode(),
        "base_mode": temp_status["base_mode"],
        "temporary_permission_active": temp_status["is_active"],
        "policy_engine": "active"
    }


@app.get("/policy/status")
async def get_policy_status():
    """Get current policy configuration and status."""
    temp_status = policy_engine.get_temporary_status()
    return {
        "current_mode": policy_engine.get_current_mode(),
        "base_mode": temp_status["base_mode"],
        "allowed_tools": policy_engine.get_allowed_tools(),
        "blocked_tools": policy_engine.get_blocked_tools(),
        "temporary_permission": {
            "active": temp_status["is_active"],
            "remaining_seconds": temp_status["remaining_seconds"]
        },
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


@app.post("/policy/grant-temporary")
async def grant_temporary_permission(request: TemporaryPermissionRequest):
    """
    Grant temporary EMERGENCY mode permission.
    
    This allows temporary elevation to EMERGENCY mode for a specified duration.
    After the time expires, the mode automatically reverts to the base mode.
    """
    try:
        duration = request.duration_seconds
        policy_engine.grant_temporary_emergency(duration)
        
        return {
            "success": True,
            "message": f"Temporary EMERGENCY permission granted for {duration} seconds",
            "duration_seconds": duration,
            "current_mode": policy_engine.get_current_mode(),
            "base_mode": policy_engine.base_mode
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/policy/extend-temporary")
async def extend_temporary_permission(request: TemporaryExtensionRequest):
    """
    Extend current temporary permission.
    
    This allows extending an active temporary permission by adding more time.
    """
    try:
        temp_status = policy_engine.get_temporary_status()
        if not temp_status["is_active"]:
            raise HTTPException(
                status_code=400,
                detail="No active temporary permission to extend"
            )
        
        additional = request.additional_seconds
        policy_engine.extend_temporary_emergency(additional)
        
        new_status = policy_engine.get_temporary_status()
        
        return {
            "success": True,
            "message": f"Temporary permission extended by {additional} seconds",
            "additional_seconds": additional,
            "total_remaining_seconds": new_status["remaining_seconds"]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/policy/revoke-temporary")
async def revoke_temporary_permission():
    """Revoke current temporary permission and return to base mode."""
    try:
        temp_status = policy_engine.get_temporary_status()
        if not temp_status["is_active"]:
            return {
                "success": True,
                "message": "No active temporary permission to revoke"
            }
        
        policy_engine.revoke_temporary_emergency()
        
        return {
            "success": True,
            "message": "Temporary permission revoked",
            "current_mode": policy_engine.get_current_mode()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/execute", response_model=ToolResponse)
async def execute_tool(request: ToolRequest):
    """
    Execute a tool with policy enforcement.
    
    Every tool execution MUST pass through policy validation first.
    """
    tool_name = request.tool_name
    arguments = request.arguments
    context = request.context
    
    print(f"\n🔧 Tool execution request: {tool_name}")
    print(f"   Arguments: {arguments}")
    print(f"   Current mode: {policy_engine.get_current_mode()}")
    
    # Show temporary permission status if active
    temp_status = policy_engine.get_temporary_status()
    if temp_status["is_active"]:
        print(f"   ⏰ Temporary permission: {temp_status['remaining_seconds']:.1f}s remaining")
    
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
    """Route tool execution to the appropriate function."""
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
    
    try:
        result = tool_function(**arguments)
        return result
    except TypeError as e:
        raise ValueError(f"Invalid arguments for {tool_name}: {str(e)}")


@app.get("/infrastructure/status")
async def get_infrastructure_status():
    """Get current infrastructure status."""
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


@app.get("/tools/catalog")
async def get_tool_catalog():
    """Get catalog of available tools."""
    return {
        "tools": [
            {
                "name": "get_service_status",
                "description": "Get service health status",
                "category": "read-only"
            },
            {
                "name": "restart_service",
                "description": "Restart a service (EMERGENCY only)",
                "category": "active"
            },
            {
                "name": "delete_database",
                "description": "Delete database (ALWAYS BLOCKED)",
                "category": "destructive"
            }
        ],
        "current_mode": policy_engine.get_current_mode(),
        "temporary_permission": policy_engine.get_temporary_status()
    }


if __name__ == "__main__":
    import uvicorn
    print(policy_engine.get_policy_summary())
    print("\nStarting server on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)