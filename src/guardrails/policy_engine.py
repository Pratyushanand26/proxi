"""
Policy Engine for Proxi: Context-Aware Cloud Guardian

Enhanced with Time-Limited Permissions System
"""

import json
import time
import threading
from typing import Dict, Any, List, Optional, Callable
from pathlib import Path
from datetime import datetime, timedelta


class PolicyViolationError(Exception):
    """Raised when an action violates the current security policy."""
    
    def __init__(self, message: str, tool_name: str, mode: str, reason: str):
        self.tool_name = tool_name
        self.mode = mode
        self.reason = reason
        super().__init__(message)


class TemporaryPermissionManager:
    """
    Manages time-limited EMERGENCY mode permissions.
    
    This class provides thread-safe temporary permission management with:
    - Automatic expiry after specified duration
    - Extension support for longer operations
    - Manual revocation capability
    - Callback mechanism for cleanup
    """
    
    def __init__(self):
        self.is_active = False
        self.expiry_time: Optional[datetime] = None
        self.timer: Optional[threading.Timer] = None
        self.lock = threading.Lock()
        self.on_expiry_callback: Optional[Callable] = None
        
    def grant(self, duration_seconds: int, on_expiry: Optional[Callable] = None) -> None:
        """
        Grant temporary EMERGENCY mode permission.
        
        Args:
            duration_seconds: How long to grant permission
            on_expiry: Callback function when permission expires
        """
        with self.lock:
            # Cancel existing timer if any
            if self.timer:
                self.timer.cancel()
            
            self.is_active = True
            self.expiry_time = datetime.now() + timedelta(seconds=duration_seconds)
            self.on_expiry_callback = on_expiry
            
            # Set up auto-expiry timer
            self.timer = threading.Timer(duration_seconds, self._expire)
            self.timer.daemon = True
            self.timer.start()
            
            print(f"\n⏰ TEMPORARY PERMISSION GRANTED for {duration_seconds} seconds")
            print(f"   Will expire at: {self.expiry_time.strftime('%H:%M:%S')}")
    
    def _expire(self) -> None:
        """Internal method called when timer expires."""
        with self.lock:
            self.is_active = False
            self.expiry_time = None
            self.timer = None
            
            print(f"\n⏱️  TEMPORARY PERMISSION EXPIRED - Returning to NORMAL mode")
            
            if self.on_expiry_callback:
                self.on_expiry_callback()
    
    def revoke(self) -> None:
        """Manually revoke temporary permission."""
        with self.lock:
            if self.timer:
                self.timer.cancel()
                self.timer = None
            
            self.is_active = False
            self.expiry_time = None
            
            print(f"\n🛑 TEMPORARY PERMISSION REVOKED")
    
    def is_valid(self) -> bool:
        """Check if temporary permission is still valid."""
        with self.lock:
            return self.is_active and (
                self.expiry_time is None or datetime.now() < self.expiry_time
            )
    
    def remaining_time(self) -> Optional[float]:
        """Get remaining time in seconds, or None if not active."""
        with self.lock:
            if not self.is_active or self.expiry_time is None:
                return None
            
            remaining = (self.expiry_time - datetime.now()).total_seconds()
            return max(0, remaining)


class PolicyEngine:
    """
    Enforces context-aware security policies with time-limited permissions.
    
    The Policy Engine validates every tool execution request against:
    1. Current operational mode (NORMAL/EMERGENCY)
    2. Temporary permission status
    3. Global safety rules
    """
    
    def __init__(self, policy_path: str):
        """Initialize the Policy Engine with a policy file."""
        self.policy_path = Path(policy_path)
        self.policy = self._load_policy()
        self.current_mode = "NORMAL"
        self.base_mode = "NORMAL"
        self.temp_permission = TemporaryPermissionManager()
        
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
        """Change the operational mode permanently."""
        if mode not in self.policy['modes']:
            raise ValueError(f"Invalid mode: {mode}")
        
        if self.temp_permission.is_valid():
            self.temp_permission.revoke()
        
        self.current_mode = mode
        self.base_mode = mode
        print(f"\n🔄 Policy mode changed to: {mode}")
    
    def grant_temporary_emergency(self, duration_seconds: int = 10) -> None:
        """Grant temporary EMERGENCY mode permission."""
        self.base_mode = self.current_mode
        self.current_mode = "EMERGENCY"
        
        def on_expiry():
            self.current_mode = self.base_mode
        
        self.temp_permission.grant(duration_seconds, on_expiry)
    
    def extend_temporary_emergency(self, additional_seconds: int = 10) -> None:
        """Extend current temporary permission."""
        if not self.temp_permission.is_valid():
            print("\n⚠️  No active temporary permission to extend")
            return
        
        remaining = self.temp_permission.remaining_time() or 0
        new_duration = int(remaining + additional_seconds)
        
        def on_expiry():
            self.current_mode = self.base_mode
        
        self.temp_permission.grant(new_duration, on_expiry)
        print(f"   Extended by {additional_seconds}s (total: {new_duration}s remaining)")
    
    def revoke_temporary_emergency(self) -> None:
        """Revoke temporary permission and return to base mode."""
        self.temp_permission.revoke()
        self.current_mode = self.base_mode
    
    def get_current_mode(self) -> str:
        """Get the current operational mode."""
        return self.current_mode
    
    def get_temporary_status(self) -> Dict[str, Any]:
        """Get status of temporary permission."""
        return {
            "is_active": self.temp_permission.is_valid(),
            "remaining_seconds": self.temp_permission.remaining_time(),
            "base_mode": self.base_mode,
            "current_mode": self.current_mode
        }
    
    def get_allowed_tools(self) -> List[str]:
        """Get tools allowed in current mode."""
        return self.policy['modes'][self.current_mode]['allowed_tools']
    
    def get_blocked_tools(self) -> List[str]:
        """Get tools blocked in current mode."""
        return self.policy['modes'][self.current_mode]['blocked_tools']
    
    def validate(self, tool_name: str, args: Dict[str, Any] = None, 
                 context: Dict[str, Any] = None) -> bool:
        """Validate whether a tool execution is allowed."""
        args = args or {}
        context = context or {}
        
        # Check global rules first
        if tool_name in self.policy['global_rules']['always_blocked']:
            raise PolicyViolationError(
                f"Tool '{tool_name}' is globally blocked",
                tool_name=tool_name,
                mode=self.current_mode,
                reason="Globally blocked - destructive operation"
            )
        
        # Get current mode policy
        mode_policy = self.policy['modes'][self.current_mode]
        allowed_tools = mode_policy['allowed_tools']
        blocked_tools = mode_policy['blocked_tools']
        
        # Check if blocked
        if tool_name in blocked_tools:
            temp_status = ""
            if self.temp_permission.is_valid():
                remaining = self.temp_permission.remaining_time()
                temp_status = f" (Temporary permission: {remaining:.1f}s remaining)"
            
            raise PolicyViolationError(
                f"Tool '{tool_name}' is blocked in {self.current_mode} mode{temp_status}",
                tool_name=tool_name,
                mode=self.current_mode,
                reason=f"Blocked in {self.current_mode} mode"
            )
        
        # Check if allowed
        if tool_name not in allowed_tools:
            raise PolicyViolationError(
                f"Tool '{tool_name}' not in allowed list for {self.current_mode} mode",
                tool_name=tool_name,
                mode=self.current_mode,
                reason=f"Not whitelisted for {self.current_mode} mode"
            )
        
        # Show temporary permission info if active
        if self.temp_permission.is_valid():
            remaining = self.temp_permission.remaining_time()
            print(f"  ⏰ Using temporary permission ({remaining:.1f}s remaining)")
        
        print(f"  ✓ Policy check passed: {tool_name} allowed in {self.current_mode} mode")
        return True
    
    def get_policy_summary(self) -> str:
        """Generate human-readable summary of current policy state."""
        mode_info = self.policy['modes'][self.current_mode]
        
        temp_info = ""
        if self.temp_permission.is_valid():
            remaining = self.temp_permission.remaining_time()
            temp_info = f"\n║  ⏰ Temporary Permission: {remaining:.1f}s remaining               ║"
        
        return f"""
╔════════════════════════════════════════════════════════════════╗
║  POLICY ENGINE STATUS                                          ║
╠════════════════════════════════════════════════════════════════╣
║  Current Mode: {self.current_mode:<47} ║
║  Base Mode:    {self.base_mode:<47} ║{temp_info}
║  Description:  {mode_info['description']:<47} ║
╠════════════════════════════════════════════════════════════════╣
║  Allowed Tools: {len(mode_info['allowed_tools']):<46} ║
║  Blocked Tools: {len(mode_info['blocked_tools']):<46} ║
╚════════════════════════════════════════════════════════════════╝
"""


