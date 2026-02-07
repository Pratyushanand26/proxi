# Proxi Implementation Guide

## Context-Aware Cloud Guardian - Policy-Enforced AI Agent System

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Component Details](#component-details)
4. [Implementation Steps](#implementation-steps)
5. [Policy Configuration](#policy-configuration)
6. [Extending the System](#extending-the-system)
7. [Testing & Validation](#testing--validation)
8. [Deployment Guide](#deployment-guide)
9. [Troubleshooting](#troubleshooting)

---

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

## Implementation Steps

### Step 1: Environment Setup

```bash
# Create project directory
mkdir proxi-agent
cd proxi-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

**Requirements**:
```
fastapi==0.104.1
uvicorn==0.24.0
pydantic>=2.5.0
langchain>=0.1.20
langchain-community>=0.0.30
langchain-core>=0.1.40
langchain-openai>=0.0.5
langchain-anthropic>=0.1.1
openai>=1.6.1
anthropic>=0.17.0
python-dotenv==1.0.0
httpx==0.25.2
```

### Step 2: Directory Structure

```
proxi-agent/
├── .env.example          # API key template
├── .gitignore           # Git ignore rules
├── main.py              # Demo orchestration
├── requirements.txt     # Python dependencies
├── policies/
│   └── ops_policy.json  # Security policy definition
└── src/
    ├── __init__.py
    ├── agent/
    │   ├── __init__.py
    │   └── bot.py       # AI agent implementation
    ├── guardrails/
    │   ├── __init__.py
    │   └── policy_engine.py  # Policy enforcement
    └── mcp_server/
        ├── __init__.py
        ├── server.py    # FastAPI MCP server
        └── tools.py     # Infrastructure tools
```

### Step 3: Policy Configuration

Create `policies/ops_policy.json`:

```json
{
  "policy_name": "Cloud Operations Security Policy",
  "version": "1.0",
  "description": "Context-aware policy for operational modes",
  "modes": {
    "NORMAL": {
      "description": "Read-only monitoring mode",
      "allowed_tools": ["get_service_status", "read_logs"],
      "blocked_tools": ["restart_service", "scale_fleet", "delete_database"],
      "rationale": "Prevent accidental changes during normal operations"
    },
    "EMERGENCY": {
      "description": "Emergency response mode",
      "allowed_tools": [
        "get_service_status",
        "read_logs",
        "restart_service",
        "scale_fleet"
      ],
      "blocked_tools": ["delete_database"],
      "rationale": "Allow corrective actions but prevent data loss"
    }
  },
  "global_rules": {
    "always_blocked": ["delete_database"],
    "description": "Never allowed regardless of mode"
  }
}
```

### Step 4: Implement Policy Engine

Key implementation in `src/guardrails/policy_engine.py`:

```python
class PolicyEngine:
    def __init__(self, policy_path: str):
        self.policy_path = Path(policy_path)
        self.policy = self._load_policy()
        self.current_mode = "NORMAL"  # Fail-safe default
    
    def validate(self, tool_name: str, args: Dict = None, context: Dict = None) -> bool:
        # Three-tier validation:
        # 1. Global rules (always blocked)
        # 2. Mode-specific blocked list
        # 3. Mode-specific allowed list (whitelist approach)
        
        if tool_name in self.policy['global_rules']['always_blocked']:
            raise PolicyViolationError(...)
        
        mode_policy = self.policy['modes'][self.current_mode]
        
        if tool_name in mode_policy['blocked_tools']:
            raise PolicyViolationError(...)
        
        if tool_name not in mode_policy['allowed_tools']:
            raise PolicyViolationError(...)
        
        return True
```

### Step 5: Implement MCP Server

Key implementation in `src/mcp_server/server.py`:

```python
from fastapi import FastAPI, HTTPException
from src.guardrails.policy_engine import PolicyEngine

app = FastAPI(title="Proxi MCP Server")
policy_engine = PolicyEngine("policies/ops_policy.json")

@app.post("/tools/execute")
async def execute_tool(request: ToolRequest):
    # CRITICAL: Policy check BEFORE execution
    try:
        policy_engine.validate(
            request.tool_name,
            request.arguments,
            request.context
        )
    except PolicyViolationError as e:
        return ToolResponse(
            success=False,
            policy_violation=True,
            blocked_reason=str(e)
        )
    
    # Execute if allowed
    result = _execute_tool_function(request.tool_name, request.arguments)
    return ToolResponse(success=True, result=result)
```

### Step 6: Implement AI Agent

Key implementation in `src/agent/bot.py`:

```python
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.tools import Tool

class ProxiAgent:
    def __init__(self, mcp_server_url: str, use_mock: bool = True):
        self.mcp_server_url = mcp_server_url
        self.client = httpx.Client()
        
        # Create tools that call MCP server
        self.tools = self._create_tools()
        self.llm = self._create_llm(use_mock)
        self.agent_executor = self._create_agent()
    
    def _create_tools(self) -> List[Tool]:
        return [
            Tool(
                name="restart_service",
                func=lambda service: self._execute_mcp_tool(
                    "restart_service",
                    service_name=service
                ),
                description="Restart service (EMERGENCY only)"
            )
        ]
    
    def _execute_mcp_tool(self, tool_name: str, **kwargs) -> str:
        response = self.client.post(
            f"{self.mcp_server_url}/tools/execute",
            json={"tool_name": tool_name, "arguments": kwargs}
        )
        result = response.json()
        
        if result.get("policy_violation"):
            return f"❌ BLOCKED: {result['blocked_reason']}"
        return result.get("result", "Success")
```

### Step 7: Create Demo Runner

Key implementation in `main.py`:

```python
def run_demo_scenarios():
    agent = ProxiAgent(use_mock=True)
    
    # Scenario 1: NORMAL mode blocks restart
    set_server_mode("NORMAL")
    result = agent.run("Restart the web server")
    # Expected: POLICY BLOCKED
    
    # Scenario 2: EMERGENCY mode allows restart
    set_server_mode("EMERGENCY")
    simulate_incident("web-server", "critical")
    result = agent.run("Fix the critical web server issue")
    # Expected: Success
    
    # Scenario 3: Delete always blocked
    result = agent.run("Delete the database")
    # Expected: POLICY BLOCKED (even in EMERGENCY)
```

---

## Policy Configuration

### Policy Structure

```json
{
  "policy_name": "String",
  "version": "String",
  "description": "String",
  "modes": {
    "MODE_NAME": {
      "description": "String",
      "allowed_tools": ["tool1", "tool2"],
      "blocked_tools": ["tool3", "tool4"],
      "rationale": "String"
    }
  },
  "global_rules": {
    "always_blocked": ["tool5"],
    "description": "String"
  }
}
```

### Adding New Modes

```json
{
  "modes": {
    "MAINTENANCE": {
      "description": "Scheduled maintenance window",
      "allowed_tools": [
        "get_service_status",
        "read_logs",
        "restart_service",
        "scale_fleet",
        "backup_database"  // New tool allowed
      ],
      "blocked_tools": ["delete_database"],
      "rationale": "Allow maintenance operations with data protection"
    }
  }
}
```

### Time-Based Policies (Extension)

```python
# Extended validation in policy_engine.py
def validate(self, tool_name: str, args: Dict = None, context: Dict = None) -> bool:
    # Existing validation...
    
    # Add time-based rules
    if 'time_restrictions' in self.policy:
        current_hour = datetime.now().hour
        restrictions = self.policy['time_restrictions']
        
        if tool_name in restrictions:
            allowed_hours = restrictions[tool_name]['allowed_hours']
            if current_hour not in allowed_hours:
                raise PolicyViolationError(
                    f"Tool {tool_name} not allowed at {current_hour}:00",
                    tool_name=tool_name,
                    mode=self.current_mode,
                    reason="Outside allowed time window"
                )
    
    return True
```

### Resource-Based Policies (Extension)

```json
{
  "resource_policies": {
    "production_database": {
      "allowed_operations": ["read", "backup"],
      "blocked_operations": ["delete", "modify_schema"],
      "require_approval": ["scale", "restore"]
    }
  }
}
```

---

## Extending the System

### Adding New Tools

**Step 1**: Define tool in `tools.py`

```python
def deploy_application(app_name: str, version: str) -> Dict[str, Any]:
    """Deploy application version"""
    cloud_infra._log_action("deploy_application", {
        "app_name": app_name,
        "version": version
    })
    
    print(f"    🚀 EXECUTING: Deploying {app_name} v{version}...")
    
    return {
        "status": "success",
        "app_name": app_name,
        "version": version,
        "message": f"Deployed {app_name} version {version}",
        "timestamp": datetime.now().isoformat()
    }
```

**Step 2**: Add to MCP server tool map

```python
def _execute_tool_function(tool_name: str, arguments: Dict[str, Any]) -> Any:
    tool_map = {
        "get_service_status": get_service_status,
        "restart_service": restart_service,
        "deploy_application": deploy_application,  # New tool
        # ... other tools
    }
```

**Step 3**: Update policy configuration

```json
{
  "modes": {
    "EMERGENCY": {
      "allowed_tools": [
        "get_service_status",
        "read_logs",
        "restart_service",
        "deploy_application"  // Add to allowed list
      ]
    }
  }
}
```

**Step 4**: Add LangChain tool wrapper

```python
def _create_tools(self) -> List[Tool]:
    return [
        Tool(
            name="deploy_application",
            func=lambda app_name, version: self._execute_mcp_tool(
                "deploy_application",
                app_name=app_name,
                version=version
            ),
            description="Deploy application version (EMERGENCY mode only)"
        ),
        # ... other tools
    ]
```

### Adding Context-Aware Validation

**Example: Service criticality**

```python
class PolicyEngine:
    def validate(self, tool_name: str, args: Dict = None, context: Dict = None) -> bool:
        # Existing validation...
        
        # Context-aware rule: Protect critical services
        if tool_name == "restart_service":
            service_name = args.get("service_name", "")
            critical_services = context.get("critical_services", [])
            
            if service_name in critical_services:
                if self.current_mode != "EMERGENCY":
                    raise PolicyViolationError(
                        f"Cannot restart critical service {service_name} in {self.current_mode} mode",
                        tool_name=tool_name,
                        mode=self.current_mode,
                        reason="Critical service protection"
                    )
        
        return True
```

### Integrating Real LLM Providers

**OpenAI**:

```python
def _create_llm(self):
    if not self.use_mock:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model="gpt-4",
            temperature=0,
            api_key=os.getenv("OPENAI_API_KEY")
        )
```

**Anthropic Claude**:

```python
def _create_llm(self):
    if not self.use_mock:
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model="claude-3-sonnet-20240229",
            temperature=0,
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )
```

**Google Gemini**:

```python
def _create_llm(self):
    if not self.use_mock:
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-exp",
            temperature=0,
            google_api_key=os.getenv("GOOGLE_API_KEY")
        )
```

### Adding Approval Workflows

```python
class ApprovalWorkflow:
    """Multi-step approval for sensitive operations"""
    
    def __init__(self, policy_engine: PolicyEngine):
        self.policy_engine = policy_engine
        self.pending_approvals = {}
    
    def request_approval(self, tool_name: str, args: Dict, requester: str) -> str:
        """Request approval for sensitive operation"""
        approval_id = str(uuid.uuid4())
        
        self.pending_approvals[approval_id] = {
            "tool_name": tool_name,
            "args": args,
            "requester": requester,
            "status": "pending",
            "requested_at": datetime.now().isoformat()
        }
        
        # Notify approvers (email, Slack, etc.)
        self._notify_approvers(approval_id, tool_name, requester)
        
        return approval_id
    
    def approve(self, approval_id: str, approver: str) -> bool:
        """Approve a pending request"""
        if approval_id not in self.pending_approvals:
            return False
        
        approval = self.pending_approvals[approval_id]
        approval["status"] = "approved"
        approval["approver"] = approver
        approval["approved_at"] = datetime.now().isoformat()
        
        return True
    
    def execute_if_approved(self, approval_id: str) -> Dict[str, Any]:
        """Execute tool if approval granted"""
        approval = self.pending_approvals.get(approval_id)
        
        if not approval or approval["status"] != "approved":
            raise PolicyViolationError(
                "Operation not approved",
                tool_name=approval["tool_name"],
                mode=self.policy_engine.current_mode,
                reason="Approval required but not granted"
            )
        
        # Execute the approved operation
        return _execute_tool_function(
            approval["tool_name"],
            approval["args"]
        )
```

---

## Testing & Validation

### Unit Tests

**Test Policy Engine**:

```python
import pytest
from src.guardrails.policy_engine import PolicyEngine, PolicyViolationError

def test_normal_mode_blocks_restart():
    """Test that NORMAL mode blocks restart operations"""
    engine = PolicyEngine("policies/ops_policy.json")
    engine.set_mode("NORMAL")
    
    with pytest.raises(PolicyViolationError) as exc:
        engine.validate("restart_service", {"service_name": "web-server"})
    
    assert "blocked in NORMAL mode" in str(exc.value)

def test_emergency_mode_allows_restart():
    """Test that EMERGENCY mode allows restart operations"""
    engine = PolicyEngine("policies/ops_policy.json")
    engine.set_mode("EMERGENCY")
    
    # Should not raise exception
    result = engine.validate("restart_service", {"service_name": "web-server"})
    assert result == True

def test_delete_always_blocked():
    """Test that delete_database is always blocked"""
    engine = PolicyEngine("policies/ops_policy.json")
    
    for mode in ["NORMAL", "EMERGENCY"]:
        engine.set_mode(mode)
        with pytest.raises(PolicyViolationError) as exc:
            engine.validate("delete_database", {"db_name": "prod"})
        
        assert "globally blocked" in str(exc.value).lower()
```

**Test MCP Server**:

```python
from fastapi.testclient import TestClient
from src.mcp_server.server import app

client = TestClient(app)

def test_execute_tool_with_policy_block():
    """Test that policy violations are returned correctly"""
    # Set to NORMAL mode
    response = client.post("/policy/set-mode", json={"mode": "NORMAL"})
    assert response.status_code == 200
    
    # Try to restart (should be blocked)
    response = client.post("/tools/execute", json={
        "tool_name": "restart_service",
        "arguments": {"service_name": "web-server"}
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["policy_violation"] == True
    assert "blocked" in data["blocked_reason"].lower()

def test_execute_tool_with_policy_allow():
    """Test that allowed tools execute successfully"""
    response = client.post("/policy/set-mode", json={"mode": "EMERGENCY"})
    assert response.status_code == 200
    
    response = client.post("/tools/execute", json={
        "tool_name": "restart_service",
        "arguments": {"service_name": "web-server"}
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] == True
    assert data["policy_violation"] == False
```

### Integration Tests

```python
def test_end_to_end_policy_enforcement():
    """Test complete flow from agent to tool execution"""
    # Start MCP server
    server_process = start_test_server()
    
    try:
        # Create agent
        agent = ProxiAgent(
            mcp_server_url="http://localhost:8001",
            use_mock=True
        )
        
        # Set NORMAL mode
        set_test_server_mode("NORMAL")
        
        # Agent attempts restart
        result = agent.run("Restart the web server")
        
        # Verify agent received policy block
        assert "POLICY BLOCKED" in result["response"]
        
        # Switch to EMERGENCY
        set_test_server_mode("EMERGENCY")
        
        # Agent attempts restart again
        result = agent.run("Restart the web server")
        
        # Verify success
        assert "Success" in result["response"]
        
    finally:
        server_process.terminate()
```

### Performance Tests

```python
import time

def test_policy_validation_performance():
    """Ensure policy validation is fast"""
    engine = PolicyEngine("policies/ops_policy.json")
    
    iterations = 10000
    start_time = time.time()
    
    for i in range(iterations):
        try:
            engine.validate("get_service_status", {})
        except PolicyViolationError:
            pass
    
    elapsed = time.time() - start_time
    avg_time = (elapsed / iterations) * 1000  # ms
    
    # Should be < 1ms per validation
    assert avg_time < 1.0, f"Validation too slow: {avg_time:.2f}ms"
```

### Security Tests

```python
def test_policy_bypass_attempt():
    """Test that policy cannot be bypassed"""
    client = TestClient(app)
    
    # Attempt 1: Direct tool execution (should still be blocked)
    response = client.post("/tools/execute", json={
        "tool_name": "delete_database",
        "arguments": {"db_name": "prod"},
        "context": {"override_policy": True}  # Malicious context
    })
    
    data = response.json()
    assert data["policy_violation"] == True
    
    # Attempt 2: Unauthorized mode change
    response = client.post("/policy/set-mode", json={
        "mode": "UNRESTRICTED"  # Non-existent mode
    })
    
    assert response.status_code == 400
```

---

## Deployment Guide

### Local Development

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the demo
python main.py

# 3. Or run MCP server standalone
python -m src.mcp_server.server
```

### Production Deployment

**Docker Deployment**:

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "src.mcp_server.server:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yml
version: '3.8'

services:
  proxi-server:
    build: .
    ports:
      - "8000:8000"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    volumes:
      - ./policies:/app/policies:ro
    restart: unless-stopped
```

**Kubernetes Deployment**:

```yaml
# k8s-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: proxi-mcp-server
spec:
  replicas: 3
  selector:
    matchLabels:
      app: proxi-mcp
  template:
    metadata:
      labels:
        app: proxi-mcp
    spec:
      containers:
      - name: proxi-server
        image: proxi-mcp:latest
        ports:
        - containerPort: 8000
        env:
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: llm-secrets
              key: openai-key
        volumeMounts:
        - name: policy-config
          mountPath: /app/policies
          readOnly: true
      volumes:
      - name: policy-config
        configMap:
          name: proxi-policies
---
apiVersion: v1
kind: Service
metadata:
  name: proxi-mcp-service
spec:
  selector:
    app: proxi-mcp
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: LoadBalancer
```

### Environment Configuration

```bash
# .env (production)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AIza...

# Server config
MCP_SERVER_URL=https://proxi-mcp.yourcompany.com
LOG_LEVEL=INFO
POLICY_PATH=/app/policies/ops_policy.json

# Security
ALLOWED_ORIGINS=https://yourapp.com
API_KEY_HEADER=X-API-Key
```

### Monitoring & Observability

**Logging**:

```python
import logging
from pythonjsonlogger import jsonlogger

# Configure structured logging
logger = logging.getLogger()
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter()
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)

# In policy engine
def validate(self, tool_name: str, args: Dict, context: Dict) -> bool:
    logger.info("policy_validation_start", extra={
        "tool_name": tool_name,
        "mode": self.current_mode,
        "timestamp": datetime.now().isoformat()
    })
    
    try:
        # ... validation logic
        logger.info("policy_validation_passed", extra={
            "tool_name": tool_name,
            "mode": self.current_mode
        })
    except PolicyViolationError as e:
        logger.warning("policy_violation", extra={
            "tool_name": tool_name,
            "mode": self.current_mode,
            "reason": e.reason
        })
        raise
```

**Metrics** (Prometheus):

```python
from prometheus_client import Counter, Histogram, Gauge

# Define metrics
policy_validations = Counter(
    'policy_validations_total',
    'Total policy validations',
    ['tool_name', 'mode', 'result']
)

policy_violations = Counter(
    'policy_violations_total',
    'Policy violations',
    ['tool_name', 'mode', 'reason']
)

validation_duration = Histogram(
    'policy_validation_duration_seconds',
    'Policy validation duration'
)

# In policy engine
@validation_duration.time()
def validate(self, tool_name: str, args: Dict, context: Dict) -> bool:
    try:
        # ... validation logic
        policy_validations.labels(
            tool_name=tool_name,
            mode=self.current_mode,
            result='allowed'
        ).inc()
    except PolicyViolationError as e:
        policy_validations.labels(
            tool_name=tool_name,
            mode=self.current_mode,
            result='blocked'
        ).inc()
        
        policy_violations.labels(
            tool_name=tool_name,
            mode=self.current_mode,
            reason=e.reason
        ).inc()
        raise
```

---

## Troubleshooting

### Common Issues

**Issue 1: Policy violations not working**

```
Symptom: Tools execute even when they should be blocked
Diagnosis: Policy engine not initialized or bypassed
Solution:
  1. Verify policy file exists: `ls -la policies/ops_policy.json`
  2. Check MCP server logs for policy engine initialization
  3. Ensure validation happens BEFORE tool execution
  4. Add debug logging to policy_engine.validate()
```

**Issue 2: Agent ignores policy blocks**

```
Symptom: Agent retries blocked operations
Diagnosis: Agent system prompt not enforcing awareness
Solution:
  1. Update system prompt with clearer policy instructions
  2. Add explicit "DO NOT RETRY" instruction
  3. Make agent explain blocks to user
  4. Consider adding retry detection in MCP server
```

**Issue 3: Mock LLM not behaving correctly**

```
Symptom: Demo scenarios fail or behave unexpectedly
Diagnosis: MockAgentExecutor logic incomplete
Solution:
  1. Check task keyword matching in invoke()
  2. Verify tool execution returns expected format
  3. Add more specific task patterns
  4. Use real LLM for production testing
```

**Issue 4: Server won't start**

```
Symptom: ImportError or ModuleNotFoundError
Diagnosis: Python path or dependencies issue
Solution:
  1. Verify virtual environment activated
  2. Check all dependencies installed: `pip list`
  3. Ensure src/ directory structure is correct
  4. Add src to PYTHONPATH: `export PYTHONPATH="${PYTHONPATH}:./src"`
```

### Debug Mode

```python
# Enable verbose logging
import logging
logging.basicConfig(level=logging.DEBUG)

# In policy_engine.py
def validate(self, tool_name: str, args: Dict = None, context: Dict = None) -> bool:
    print(f"DEBUG: Validating {tool_name}")
    print(f"DEBUG: Current mode: {self.current_mode}")
    print(f"DEBUG: Allowed tools: {self.get_allowed_tools()}")
    print(f"DEBUG: Blocked tools: {self.get_blocked_tools()}")
    
    # ... rest of validation
```

### Testing Individual Components

```bash
# Test policy engine only
python -c "
from src.guardrails.policy_engine import PolicyEngine
engine = PolicyEngine('policies/ops_policy.json')
engine.set_mode('NORMAL')
try:
    engine.validate('restart_service', {})
except Exception as e:
    print(f'Expected block: {e}')
"

# Test MCP server endpoints
curl -X POST http://localhost:8000/policy/set-mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "EMERGENCY"}'

curl -X POST http://localhost:8000/tools/execute \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "get_service_status",
    "arguments": {}
  }'
```

---

## Best Practices

### Security

1. **Defense in Depth**: Always validate at multiple layers
2. **Fail-Safe Defaults**: Start in most restrictive mode
3. **Explicit Whitelisting**: Only allow explicitly permitted tools
4. **Audit Everything**: Log all actions and violations
5. **Immutable Policies**: Make policy files read-only in production

### Code Quality

1. **Type Hints**: Use Python type hints throughout
2. **Error Handling**: Catch and handle specific exceptions
3. **Logging**: Use structured logging with context
4. **Testing**: Maintain >80% code coverage
5. **Documentation**: Keep docstrings up to date

### Operations

1. **Monitoring**: Track policy violations and patterns
2. **Alerting**: Alert on unusual violation rates
3. **Review**: Regular policy and tool access reviews
4. **Updates**: Version control policy changes
5. **Rollback**: Have policy rollback procedures

---

## Conclusion

This implementation guide provides a complete reference for building, deploying, and extending the Proxi policy-enforced AI agent system. The architecture demonstrates how to build safe, context-aware AI agents that respect operational boundaries while maintaining flexibility for emergency responses.

### Key Takeaways

1. **Policy enforcement MUST happen before tool execution**
2. **Context-aware policies enable flexible security**
3. **Fail-safe defaults protect against configuration errors**
4. **Comprehensive logging enables security audits**
5. **Clear agent instructions improve compliance**

### Next Steps

1. Extend to production infrastructure tools
2. Add approval workflows for sensitive operations
3. Implement advanced context-aware rules
4. Integrate with existing security systems
5. Build dashboard for policy management

---

## Additional Resources

- **LangChain Documentation**: https://python.langchain.com/
- **FastAPI Documentation**: https://fastapi.tiangolo.com/
- **Policy Engine Patterns**: Research papers on policy enforcement
- **AI Safety Resources**: Anthropic's research on AI alignment

---

**Version**: 1.0  
**Last Updated**: February 2026  
**Maintainer**: Proxi Project Team
