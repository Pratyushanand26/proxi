"""
Policy Engine for Proxi: Context-Aware Cloud Guardian

This module implements the core security enforcement mechanism that validates
all agent actions against defined operational policies.
"""

import json
from typing import Dict, Any, List
from pathlib import Path


class PolicyViolationError(Exception):
    """Raised when an action violates the current security policy."""
    
    def __init__(self, message: str, tool_name: str, mode: str, reason: str):
        self.tool_name = tool_name
        self.mode = mode
        self.reason = reason
        super().__init__(message)


class PolicyEngine:
    """
    Enforces context-aware security policies on agent actions.
    
    The Policy Engine loads operational policies from a JSON file and validates
    every tool execution request against the current operational mode.
    """
    
    def __init__(self, policy_path: str):
        """
        Initialize the Policy Engine with a policy file.
        
        Args:
            policy_path: Path to the JSON policy configuration file
        """
        self.policy_path = Path(policy_path)
        self.policy = self._load_policy()
        self.current_mode = "NORMAL"  # Default to most restrictive mode
        
    def _load_policy(self) -> Dict[str, Any]:
        """Load and parse the policy JSON file."""
        if not self.policy_path.exists():
            raise FileNotFoundError(f"Policy file not found: {self.policy_path}")
        
        with open(self.policy_path, 'r') as f:
            policy = json.load(f)
        
        print(f"✓ Loaded policy: {policy.get('policy_name', 'Unknown')}")
        print(f"  Version: {policy.get('version', 'Unknown')}")
        return policy
    
    def set_mode(self, mode: str) -> None:
        """
        Change the operational mode.
        
        Args:
            mode: One of "NORMAL" or "EMERGENCY"
        
        Raises:
            ValueError: If the mode is not defined in the policy
        """
        if mode not in self.policy['modes']:
            raise ValueError(f"Invalid mode: {mode}. Available: {list(self.policy['modes'].keys())}")
        
        self.current_mode = mode
        print(f"\n🔄 Policy mode changed to: {mode}")
        print(f"   {self.policy['modes'][mode]['description']}")
    
    def get_current_mode(self) -> str:
        """Get the current operational mode."""
        return self.current_mode
    
    def get_allowed_tools(self) -> List[str]:
        """Get the list of tools allowed in the current mode."""
        return self.policy['modes'][self.current_mode]['allowed_tools']
    
    def get_blocked_tools(self) -> List[str]:
        """Get the list of tools blocked in the current mode."""
        return self.policy['modes'][self.current_mode]['blocked_tools']
    
    def validate(self, tool_name: str, args: Dict[str, Any] = None, context: Dict[str, Any] = None) -> bool:
        """
        Validate whether a tool execution is allowed under the current policy.
        
        Args:
            tool_name: Name of the tool to execute
            args: Arguments passed to the tool (for future use in advanced policies)
            context: Additional context about the request
        
        Returns:
            True if the action is allowed
        
        Raises:
            PolicyViolationError: If the action violates the current policy
        """
        args = args or {}
        context = context or {}
        
        # Check global rules first (always blocked tools)
        if tool_name in self.policy['global_rules']['always_blocked']:
            raise PolicyViolationError(
                f"Tool '{tool_name}' is globally blocked and can never be executed",
                tool_name=tool_name,
                mode=self.current_mode,
                reason="Globally blocked - destructive operation"
            )
        
        # Get the current mode's policy
        mode_policy = self.policy['modes'][self.current_mode]
        allowed_tools = mode_policy['allowed_tools']
        blocked_tools = mode_policy['blocked_tools']
        
        # Check if tool is explicitly blocked in current mode
        if tool_name in blocked_tools:
            raise PolicyViolationError(
                f"Tool '{tool_name}' is blocked in {self.current_mode} mode. "
                f"Rationale: {mode_policy['rationale']}",
                tool_name=tool_name,
                mode=self.current_mode,
                reason=f"Blocked in {self.current_mode} mode"
            )
        
        # Check if tool is in allowed list
        if tool_name not in allowed_tools:
            raise PolicyViolationError(
                f"Tool '{tool_name}' is not in the allowed list for {self.current_mode} mode",
                tool_name=tool_name,
                mode=self.current_mode,
                reason=f"Not whitelisted for {self.current_mode} mode"
            )
        
        # Validation passed
        print(f"  ✓ Policy check passed: {tool_name} allowed in {self.current_mode} mode")
        return True
    
    def get_policy_summary(self) -> str:
        """Generate a human-readable summary of the current policy state."""
        mode_info = self.policy['modes'][self.current_mode]
        
        summary = f"""
╔════════════════════════════════════════════════════════════════╗
║  POLICY ENGINE STATUS                                          ║
╠════════════════════════════════════════════════════════════════╣
║  Current Mode: {self.current_mode:<47} ║
║  Description:  {mode_info['description']:<47} ║
╠════════════════════════════════════════════════════════════════╣
║  Allowed Tools:                                                ║
{self._format_tool_list(mode_info['allowed_tools'])}
╠════════════════════════════════════════════════════════════════╣
║  Blocked Tools:                                                ║
{self._format_tool_list(mode_info['blocked_tools'])}
╚════════════════════════════════════════════════════════════════╝
"""
        return summary
    
    def _format_tool_list(self, tools: List[str]) -> str:
        """Format a list of tools for the summary display."""
        if not tools:
            return "║    (none)                                                      ║"
        
        lines = []
        for tool in tools:
            lines.append(f"║    • {tool:<56} ║")
        return "\n".join(lines)