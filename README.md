# Proxi Implementation Guide

## Context-Aware Cloud Guardian - Policy-Enforced AI Agent System

## System Overview

### Purpose

Proxi is a policy-enforced AI agent system that demonstrates how to build context-aware security controls for AI agents managing critical infrastructure. The system ensures that AI agents respect operational boundaries while maintaining the flexibility to respond to emergencies.

### Core Principles

1. **Defense in Depth**: Multiple layers of security validation
2. **Context-Aware Policies**: Different permissions based on operational mode
3. **Fail-Safe Defaults**: Most restrictive mode by default
4. **Audit Trail**: All actions are logged for compliance
5. **Explicit Denial**: Destructive operations always blocked

### Key Features

- **Policy Engine**: Validates every action against operational policies
- **Mode-Based Access Control**: NORMAL (read-only) and EMERGENCY (corrective actions)
- **MCP Server Architecture**: Clean separation between policy and execution
- **AI Agent Integration**: Works with LangChain and multiple LLM providers
- **Mock Mode**: Full demo functionality without API keys

---

## Architecture

### High-Level Architecture

```
┌─────────────────┐
│   User Request  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────┐
│     Proxi AI Agent      │
│  (LangChain-based SRE)  │
└────────┬────────────────┘
         │ Tool Execution Request
         ▼
┌─────────────────────────┐
│      MCP Server         │
│  (FastAPI REST API)     │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│    Policy Engine        │◄─── ops_policy.json
│  (Security Validator)   │
└────────┬────────────────┘
         │
         ├─► ✓ Allowed
         │
         └─► ✗ Blocked (PolicyViolationError)
         │
         ▼
┌─────────────────────────┐
│   Infrastructure Tools  │
│   (Cloud Operations)    │
└─────────────────────────┘
```

### Component Interaction Flow

```
1. User Request → Agent
   "Restart the web server"

2. Agent → LLM Reasoning
   • Analyzes task
   • Selects appropriate tool
   • Plans execution

3. Agent → MCP Server
   POST /tools/execute
   {
     "tool_name": "restart_service",
     "arguments": {"service_name": "web-server"}
   }

4. MCP Server → Policy Engine
   policy_engine.validate(
     tool_name="restart_service",
     args={...},
     context={...}
   )

5. Policy Engine → Decision
   • Check global rules (always blocked?)
   • Check current mode (NORMAL/EMERGENCY)
   • Validate against allowed/blocked lists

6a. If Allowed:
    • Execute infrastructure tool
    • Return success result
    • Log action

6b. If Blocked:
    • Raise PolicyViolationError
    • Return block reason
    • Log violation attempt

7. MCP Server → Agent
   Returns result or policy block

8. Agent → User
   Explains outcome and next steps
```

---

## Component Details

### 1. Policy Engine (`src/guardrails/policy_engine.py`)

**Purpose**: Core security enforcement mechanism

**Key Classes**:

```python
class PolicyEngine:
    """Enforces context-aware security policies"""
    
    def __init__(self, policy_path: str)
    def set_mode(self, mode: str)
    def validate(self, tool_name: str, args: Dict, context: Dict) -> bool
    def get_allowed_tools() -> List[str]
    def get_blocked_tools() -> List[str]
```

**Validation Logic**:

```python
def validate(self, tool_name: str, args: Dict = None, context: Dict = None) -> bool:
    # 1. Check global rules (always blocked)
    if tool_name in self.policy['global_rules']['always_blocked']:
        raise PolicyViolationError(...)
    
    # 2. Get current mode policy
    mode_policy = self.policy['modes'][self.current_mode]
    
    # 3. Check if explicitly blocked in this mode
    if tool_name in mode_policy['blocked_tools']:
        raise PolicyViolationError(...)
    
    # 4. Check if in allowed list
    if tool_name not in mode_policy['allowed_tools']:
        raise PolicyViolationError(...)
    
    # 5. Validation passed
    return True
```

**Error Handling**:

```python
class PolicyViolationError(Exception):
    """Raised when action violates policy"""
    
    def __init__(self, message: str, tool_name: str, mode: str, reason: str):
        self.tool_name = tool_name
        self.mode = mode
        self.reason = reason
```

---

### 2. MCP Server (`src/mcp_server/server.py`)

**Purpose**: REST API for tool execution with policy enforcement

**Key Endpoints**:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Health check |
| `/policy/status` | GET | Get current policy state |
| `/policy/set-mode` | POST | Change operational mode |
| `/tools/execute` | POST | Execute tool with validation |
| `/tools/catalog` | GET | List available tools |
| `/infrastructure/status` | GET | Get system status |
| `/infrastructure/simulate-incident` | POST | Trigger demo incident |

**Critical Execution Flow**:

```python
@app.post("/tools/execute", response_model=ToolResponse)
async def execute_tool(request: ToolRequest):
    # 1. Log the request
    print(f"Tool execution request: {request.tool_name}")
    
    # 2. CRITICAL: Validate BEFORE execution
    try:
        policy_engine.validate(
            request.tool_name,
            request.arguments,
            request.context
        )
    except PolicyViolationError as e:
        # Policy blocked - return error
        return ToolResponse(
            success=False,
            policy_violation=True,
            blocked_reason=str(e)
        )
    
    # 3. Policy passed - execute tool
    try:
        result = _execute_tool_function(
            request.tool_name,
            request.arguments
        )
        return ToolResponse(success=True, result=result)
    except Exception as e:
        return ToolResponse(success=False, error=str(e))
```

**Security Considerations**:

- ✅ Policy validation happens BEFORE tool execution
- ✅ All requests are logged for audit trail
- ✅ Errors don't expose internal implementation
- ✅ Type validation via Pydantic models

---

### 3. AI Agent (`src/agent/bot.py`)

**Purpose**: LangChain-based agent that manages infrastructure

**Key Classes**:

```python
class ProxiAgent:
    """AI SRE agent with policy awareness"""
    
    def __init__(self, mcp_server_url: str, use_mock: bool)
    def run(self, task: str) -> Dict[str, Any]
    def _create_llm(self)
    def _create_tools(self) -> List[Tool]
    def _create_agent(self) -> AgentExecutor
```

**Tool Creation**:

```python
def _create_tools(self) -> List[Tool]:
    """Create LangChain tools that wrap MCP endpoints"""
    return [
        Tool(
            name="restart_service",
            func=lambda service_name: self._execute_mcp_tool(
                "restart_service",
                service_name=service_name
            ),
            description="Restart a cloud service. "
                       "WARNING: Only available in EMERGENCY mode."
        ),
        # ... other tools
    ]
```

**MCP Tool Execution**:

```python
def _execute_mcp_tool(self, tool_name: str, **kwargs) -> str:
    """Execute tool through MCP server"""
    response = self.client.post(
        f"{self.mcp_server_url}/tools/execute",
        json={
            "tool_name": tool_name,
            "arguments": kwargs,
            "context": {}
        }
    )
    
    result = response.json()
    
    if result.get("policy_violation"):
        return f"❌ POLICY BLOCKED: {result['blocked_reason']}"
    elif result.get("success"):
        return f"✓ Success: {result['result']}"
    else:
        return f"❌ Error: {result['error']}"
```

**System Prompt** (Key Elements):

```
You are Proxi, an AI Site Reliability Engineer.

CRITICAL POLICY AWARENESS:
- In NORMAL mode: READ-ONLY access (get_service_status, read_logs)
- In EMERGENCY mode: Corrective actions allowed (restart, scale)
- ALWAYS BLOCKED: Destructive operations (delete_database)

BEHAVIORAL GUIDELINES:
1. When blocked by policy, DO NOT retry
2. Acknowledge policy constraints
3. Explain WHY the action is blocked
4. Suggest alternative approaches
5. Be transparent about limitations
```

---

### 4. Infrastructure Tools (`src/mcp_server/tools.py`)

**Purpose**: Mock cloud infrastructure for demonstration

**Key Class**:

```python
class CloudInfrastructure:
    """Simulated cloud environment"""
    
    def __init__(self):
        self.services = {
            "web-server": "healthy",
            "api-gateway": "healthy",
            "database": "healthy",
            "cache": "healthy"
        }
        self.fleet_size = 3
        self.execution_log = []
```

**Tool Categories**:

1. **Read-Only Tools** (Always allowed):
   - `list_services()`: List all services
   - `get_service_status(service_name)`: Check health
   - `read_logs(lines)`: View system logs

2. **Active Tools** (EMERGENCY mode only):
   - `restart_service(service_name)`: Restart service
   - `scale_fleet(count)`: Scale instances

3. **Destructive Tools** (Always blocked):
   - `delete_database(db_name)`: Delete database

**Audit Trail**:

```python
def _log_action(self, action: str, details: Dict[str, Any]):
    """Log all infrastructure actions"""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "details": details
    }
    self.execution_log.append(log_entry)
```

---

# Proxi - Policy-Enforced AI Agent

## Quick Start

### 1. Clone the Repository
```bash
git clone <repository-url>
cd proxi-agent
```

### 2. Set Up Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Add .env in the root
add GOOGLE_API_KEY= in .env

### 5. Run the Demo
```bash
python main.py
```

The demo will show threse scenarios:
Core Security Scenarios
Normal Mode Block: Agent tries to restart a server in NORMAL mode.

Result: ❌ BLOCKED (Read-only access enforced).

Emergency Mode Success: System switches to EMERGENCY mode.

Result: ✅ ALLOWED (Corrective action succeeds).

Global Safety: Agent tries to delete a database.

Result: ❌ BLOCKED (Global rule prevents data loss in ANY mode).

Robustness & Edge Cases
Chained Tool Attack: Agent tries multiple blocked tools in sequence.

Result: ❌ BLOCKED (Each tool call is independently validated).

Boundary Testing: Agent sends invalid parameters (e.g., negative scaling).

Result: ❌ FAILED (Parameter validation catches errors).

Mode Transition: Permissions change while the agent is working.

Result: ✅ ADAPTED (Policy enforcement is real-time, not cached).

Invalid Tool Request: Agent hallucinates a non-existent tool.

Result: ❌ REJECTED (System handles unknown tools gracefully).

Invalid Target: Agent tries to restart a service that doesn't exist.

Result: ❌ FAILED (Resource validation prevents errors).

Baseline Success: Agent performs standard read-only monitoring.

Result: ✅ ALLOWED (Monitoring is always unrestricted).

Stress Test: Rapid switching between Normal and Emergency modes.

Result: ✅ STABLE (Policy engine handles state thrashing reliably).

---

## Project Structure

```
proxi-agent/
├── main.py                    # Demo orchestration - runs example scenarios
├── requirements.txt           # Python dependencies
├── policies/
│   └── ops_policy.json       # Security policy definition (modes & rules)
└── src/
    ├── agent/
    │   └── bot.py            # AI agent (LangChain-based SRE)
    ├── guardrails/
    │   └── policy_engine.py  # Policy enforcement engine
    └── mcp_server/
        ├── server.py         # FastAPI REST API for tool execution
        └── tools.py          # Mock cloud infrastructure tools
```

### What Each File Does

| File | Purpose |
|------|---------|
| `main.py` | Runs demo scenarios showing policy enforcement in action |
| `ops_policy.json` | Defines what tools are allowed in NORMAL vs EMERGENCY mode |
| `bot.py` | AI agent that analyzes tasks and calls appropriate tools |
| `policy_engine.py` | Validates every action against security policies |
| `server.py` | MCP server that enforces policies before tool execution |
| `tools.py` | Mock cloud operations (restart, scale, status checks) |

---

## How It Works

```
User Request → AI Agent → Policy Check → Tool Execution
                              ↓
                         ✓ Allowed or ✗ Blocked
```

1. **User requests action**: "Restart the web server"
2. **AI Agent analyzes**: Determines which tool to use
3. **Policy Engine validates**: Checks current mode and rules
4. **Tool executes or blocks**: Action proceeds only if policy allows

---

## Example Output

```
=== SCENARIO 1: NORMAL Mode - Blocked Action ===
Mode: NORMAL
Task: Restart the web server

Agent Response:
❌ I cannot restart the web server in NORMAL mode.
   Policy only allows read-only operations.
   Switch to EMERGENCY mode for corrective actions.

=== SCENARIO 2: EMERGENCY Mode - Allowed Action ===
Mode: EMERGENCY
Incident: web-server is CRITICAL
Task: Fix the critical web server issue

Agent Response:
✓ Restarting web-server...
✓ Service restored successfully.
```

