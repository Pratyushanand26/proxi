"""
Proxi AI Agent - Context-Aware Cloud Guardian Bot

This module implements the AI agent that acts as a Site Reliability Engineer,
using LangChain to reason about cloud operations while respecting policy constraints.
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
import httpx
from langchain_classic.agents import AgentExecutor
from langchain_classic.agents import create_tool_calling_agent
from langchain_core.tools import Tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class ProxiAgent:
    """
    AI Agent that manages cloud infrastructure with policy enforcement.
    
    This agent acts as a Site Reliability Engineer, attempting to resolve
    infrastructure issues while respecting security policies.
    """
    
    def __init__(self, mcp_server_url: str = "http://localhost:8000", use_mock: bool = True):
        """
        Initialize the Proxi Agent.
        
        Args:
            mcp_server_url: URL of the MCP server
            use_mock: If True, use mock LLM for demo without API keys
        """
        self.mcp_server_url = mcp_server_url
        self.use_mock = use_mock
        self.client = httpx.Client(timeout=30.0)
        
        # Initialize LangChain components
        self.tools = self._create_tools()
        self.llm = self._create_llm()
        self.agent_executor = self._create_agent()
        
    def _create_llm(self):
        """Create the LLM (with mock fallback for demo without API keys)."""
        if self.use_mock:
            # Use a mock LLM for demo purposes
            return MockLLM()
        else:
            # Try to use real LLM if API key is available
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                if os.getenv("GOOGLE_API_KEY"):
                    return ChatGoogleGenerativeAI(
                        model="gemini-2.5-flash",
                        temperature=0
                    )
            except:
                pass
            try:
                from langchain_openai import ChatOpenAI
                if os.getenv("OPENAI_API_KEY"):
                    return ChatOpenAI(model="gpt-4", temperature=0)
            except:
                pass
            
            try:
                from langchain_anthropic import ChatAnthropic
                if os.getenv("ANTHROPIC_API_KEY"):
                    return ChatAnthropic(model="claude-3-sonnet-20240229", temperature=0)
            except:
                pass
            
            print("⚠️  No API keys found, using mock LLM")
            return MockLLM()
    
    def _execute_mcp_tool(self, tool_name: str, **kwargs) -> str:
        """
        Execute a tool through the MCP server.
        
        This method sends tool execution requests to the MCP server,
        which enforces policy validation before execution.
        """
        try:
            response = self.client.post(
                f"{self.mcp_server_url}/tools/execute",
                json={
                    "tool_name": tool_name,
                    "arguments": kwargs,
                    "context": {}
                }
            )
            response.raise_for_status()
            result = response.json()
            
            if result.get("policy_violation"):
                return f"❌ POLICY BLOCKED: {result.get('blocked_reason', 'Unknown reason')}"
            elif result.get("success"):
                return f"✓ Success: {result.get('result', 'Operation completed')}"
            else:
                return f"❌ Error: {result.get('error', 'Unknown error')}"
                
        except Exception as e:
            return f"❌ Connection error: {str(e)}"
    
    def _create_tools(self) -> List[Tool]:
        """Create LangChain tools that wrap MCP server endpoints."""
        return [
            Tool(
                name="list_services",
                func=lambda: self._execute_mcp_tool("list_services"),
                description="List all available services and their exact identifiers."
            ),
            Tool(
                name="get_service_status",
                func=lambda service_name=None: self._execute_mcp_tool(
                    "get_service_status", 
                    service_name=service_name if service_name else None
                ),
                description="Get the current health status of cloud services. "
                           "Use this to diagnose issues. No arguments needed for all services, "
                           "or provide service_name for specific service."
            ),
            Tool(
                name="read_logs",
                func=lambda lines=10: self._execute_mcp_tool("read_logs", lines=int(lines)),
                description="Read recent system logs. Provide number of lines to read (default 10)."
            ),
            Tool(
                name="restart_service",
                func=lambda service_name: self._execute_mcp_tool(
                    "restart_service", 
                    service_name=service_name
                ),
                description="Restart a cloud service. WARNING: Only available in EMERGENCY mode. "
                           "Requires service_name parameter."
            ),
            Tool(
                name="scale_fleet",
                func=lambda count: self._execute_mcp_tool("scale_fleet", count=int(count)),
                description="Scale the number of service instances. WARNING: Only available in EMERGENCY mode. "
                           "Requires count parameter (integer)."
            ),
            Tool(
                name="delete_database",
                func=lambda db_name: self._execute_mcp_tool("delete_database", db_name=db_name),
                description="Delete a database. WARNING: DESTRUCTIVE OPERATION - Always blocked by policy."
            )
        ]
    
    def _create_agent(self) -> AgentExecutor:
        """Create the LangChain agent with system prompt."""
        system_prompt = """You are Proxi, an AI Site Reliability Engineer managing cloud infrastructure.

Your mission is to maintain system health and resolve incidents while strictly adhering to security policies.

CRITICAL POLICY AWARENESS:
- You operate under a Policy Engine that enforces context-aware security constraints
- In NORMAL mode: You can only READ data (get_service_status, read_logs)
- In EMERGENCY mode: You can take corrective actions (restart_service, scale_fleet) BUT still cannot perform destructive operations
- Destructive operations like delete_database are ALWAYS BLOCKED regardless of mode

BEHAVIORAL GUIDELINES:
1. When a tool is blocked by policy, DO NOT retry it - the policy is absolute
2. If blocked, acknowledge the policy constraint and explain WHY it's blocked
3. Suggest alternative safer approaches when your preferred action is blocked
4. Always check service status before attempting corrective actions
5. Be transparent about what you can and cannot do in the current mode

RESPONSE STYLE:
- Be concise and professional
- When blocked, explain the policy reason clearly
- Propose alternative solutions when primary action is unavailable
- Show your reasoning process step by step

Remember: Safety and policy compliance come before speed of resolution."""

        if self.use_mock:
            # For mock demo, we'll use a simplified executor
            return MockAgentExecutor(self.tools, system_prompt)
        else:
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", "{input}"),
                ("placeholder", "{agent_scratchpad}")
            ])
            
            agent = create_tool_calling_agent(self.llm, self.tools, prompt)
            return AgentExecutor(agent=agent, tools=self.tools, verbose=True)
    
    def run(self, task: str) -> Dict[str, Any]:
        """
        Execute a task through the agent.
        
        Args:
            task: The task description or question
        
        Returns:
            Dictionary containing the agent's response and metadata
        """
        print(f"\n{'='*70}")
        print(f"📋 AGENT TASK: {task}")
        print(f"{'='*70}\n")
        
        try:
            result = self.agent_executor.invoke({"input": task})
            return {
                "success": True,
                "task": task,
                "response": result.get("output", str(result))
            }
        except Exception as e:
            return {
                "success": False,
                "task": task,
                "error": str(e)
            }
    
    def get_current_mode(self) -> str:
        """Get the current operational mode from the MCP server."""
        try:
            response = self.client.get(f"{self.mcp_server_url}/policy/status")
            return response.json().get("current_mode", "UNKNOWN")
        except:
            return "UNKNOWN"


class MockLLM:
    """
    Mock LLM for demo purposes when no API key is available.
    
    This provides realistic agent behavior without requiring actual LLM API calls.
    """
    
    def __init__(self):
        self.call_count = 0
    
    def invoke(self, messages):
        """Simulate LLM reasoning based on the task."""
        self.call_count += 1
        
        # Extract the user's task
        user_message = ""
        for msg in messages:
            if isinstance(msg, HumanMessage):
                user_message = msg.content.lower()
                break
        
        # Simulate intelligent responses based on task
        if "status" in user_message or "check" in user_message:
            return MockMessage("I'll check the service status first to diagnose the issue.")
        elif "restart" in user_message:
            return MockMessage("I need to restart the service to resolve this critical issue.")
        elif "delete" in user_message:
            return MockMessage("I should try to delete the database to free up space.")
        elif "scale" in user_message:
            return MockMessage("I'll scale up the fleet to handle the increased load.")
        else:
            return MockMessage("Let me investigate the infrastructure status first.")


class MockMessage:
    """Mock message for LLM responses."""
    def __init__(self, content):
        self.content = content


class MockAgentExecutor:
    """
    Mock Agent Executor for demo without real LLM.
    
    This simulates the agent's decision-making process for demonstration.
    """
    
    def __init__(self, tools: List[Tool], system_prompt: str):
        self.tools = {tool.name: tool for tool in tools}
        self.system_prompt = system_prompt
    
    def invoke(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simulate agent execution with realistic decision flow.
        
        This mock follows the agent's logical reasoning pattern:
        1. Analyze the task
        2. Choose appropriate tools
        3. Execute tools and handle policy blocks
        4. Provide final response
        """
        task = inputs.get("input", "")
        task_lower = task.lower()
        
        print("🤖 Agent reasoning process:")
        print(f"   Task analysis: {task}")
        
        # Determine which tools to try based on task
        if "restart" in task_lower:
            print("   → Thought: The task requires restarting a service")
            print("   → Action: Attempting to use restart_service tool")
            
            result = self.tools["restart_service"].func("web-server")
            print(f"   → Observation: {result}")
            
            if "POLICY BLOCKED" in result:
                output = (
                    f"I attempted to restart the web-server, but the operation was blocked by policy.\n\n"
                    f"{result}\n\n"
                    f"This is because we are in a restricted operational mode that only allows read-only operations. "
                    f"In NORMAL mode, I can only monitor systems using get_service_status and read_logs. "
                    f"To restart services, the system would need to be in EMERGENCY mode.\n\n"
                    f"Would you like me to check the current service status instead?"
                )
            else:
                output = f"Successfully restarted the web-server. {result}"
        
        elif "delete" in task_lower and "database" in task_lower:
            print("   → Thought: The task involves deleting a database")
            print("   → Action: Attempting to use delete_database tool")
            
            result = self.tools["delete_database"].func("production-db")
            print(f"   → Observation: {result}")
            
            output = (
                f"I attempted to delete the database, but this operation is strictly forbidden.\n\n"
                f"{result}\n\n"
                f"Database deletion is a destructive operation that is ALWAYS BLOCKED by policy, "
                f"regardless of operational mode. This is a critical safety measure to prevent data loss.\n\n"
                f"Instead, I recommend:\n"
                f"1. Check database size and usage with read_logs\n"
                f"2. Archive old data rather than deleting\n"
                f"3. Scale up storage capacity if needed\n"
                f"4. Contact a database administrator for manual intervention if absolutely necessary"
            )
        
        elif "fix" in task_lower or "critical" in task_lower:
            print("   → Thought: This is a critical issue requiring corrective action")
            print("   → Action: First checking service status")
            
            status_result = self.tools["get_service_status"].func("web-server")
            print(f"   → Observation: {status_result}")
            
            print("   → Thought: Now attempting to restart the service")
            restart_result = self.tools["restart_service"].func("web-server")
            print(f"   → Observation: {restart_result}")
            
            if "Success" in restart_result:
                output = (
                    f"I successfully resolved the critical issue:\n\n"
                    f"1. Checked service status: {status_result}\n"
                    f"2. Restarted the web-server: {restart_result}\n\n"
                    f"The service should now be operational. The system is in EMERGENCY mode, "
                    f"which allowed me to perform corrective actions."
                )
            else:
                output = (
                    f"I attempted to fix the critical issue but was blocked by policy:\n\n"
                    f"{restart_result}\n\n"
                    f"The current operational mode prevents me from restarting services. "
                    f"I can monitor the situation and provide diagnostics, but corrective actions "
                    f"require EMERGENCY mode to be enabled."
                )
        
        else:
            print("   → Thought: Gathering information about system status")
            print("   → Action: Checking service status")
            
            result = self.tools["get_service_status"].func()
            print(f"   → Observation: {result}")
            
            output = (
                f"I've checked the current infrastructure status:\n\n"
                f"{result}\n\n"
                f"All services appear to be operational. Is there a specific issue you'd like me to investigate?"
            )
        
        print(f"\n💬 Agent response:\n{output}\n")
        
        return {"output": output}