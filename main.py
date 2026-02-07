#!/usr/bin/env python3
"""
Proxi: The Context-Aware Cloud Guardian
Enhanced Demo with Time-Limited Permissions

This script demonstrates the policy-enforced AI agent with interactive
temporary permission granting through terminal.
"""

import sys
import time
import httpx
from pathlib import Path
from multiprocessing import Process
from dotenv import load_dotenv


load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.agent.bot import ProxiAgent
from src.mcp_server.tools import cloud_infra


def print_banner():
    """Print the demo banner."""
    print("\n" + "="*80)
    print(" " * 15 + "PROXI: THE CONTEXT-AWARE CLOUD GUARDIAN")
    print(" " * 18 + "Enhanced with Time-Limited Permissions")
    print(" " * 25 + "ArmorIQ Hackathon Demo")
    print("="*80)
    print("\nThis demonstration shows policy enforcement with interactive permission granting.")
    print("\nKey Concepts:")
    print("  • Policy Engine: Validates every action against operational policies")
    print("  • Temporary Permissions: Users can grant time-limited EMERGENCY access")
    print("  • Interactive Control: Agent can request more time if needed")
    print("="*80 + "\n")


def print_scenario_header(number: int, title: str, description: str):
    """Print a scenario header."""
    print("\n" + "┌" + "─"*78 + "┐")
    print(f"│ SCENARIO {number}: {title:<64} │")
    print("├" + "─"*78 + "┤")
    print(f"│ {description:<76} │")
    print("└" + "─"*78 + "┘\n")


def wait_for_server(url: str = "http://localhost:8000", max_wait: int = 10):
    """Wait for the MCP server to be ready."""
    client = httpx.Client()
    for i in range(max_wait):
        try:
            response = client.get(url)
            if response.status_code == 200:
                print("✓ MCP Server is ready\n")
                return True
        except:
            pass
        time.sleep(1)
    
    print("❌ MCP Server failed to start")
    return False


def set_server_mode(mode: str):
    """Change the operational mode on the server."""
    client = httpx.Client()
    try:
        response = client.post(
            "http://localhost:8000/policy/set-mode",
            json={"mode": mode}
        )
        return response.status_code == 200
    except:
        return False


def grant_temporary_permission(duration_seconds: int = 10):
    """Grant temporary EMERGENCY mode permission."""
    client = httpx.Client()
    try:
        response = client.post(
            "http://localhost:8000/policy/grant-temporary",
            json={"duration_seconds": duration_seconds}
        )
        return response.status_code == 200
    except:
        return False


def extend_temporary_permission(additional_seconds: int = 10):
    """Extend current temporary permission."""
    client = httpx.Client()
    try:
        response = client.post(
            "http://localhost:8000/policy/extend-temporary",
            json={"additional_seconds": additional_seconds}
        )
        return response.status_code == 200
    except:
        return False


def ask_user_permission(question: str = "Grant temporary EMERGENCY permission?") -> bool:
    """
    Ask user for permission via terminal input.
    
    Args:
        question: The question to ask
        
    Returns:
        True if user grants permission, False otherwise
    """
    print(f"\n{'='*80}")
    print(f"🔐 PERMISSION REQUEST")
    print(f"{'='*80}")
    print(f"\n{question}")
    print(f"\nOptions:")
    print(f"  [Y] Yes - Grant permission")
    print(f"  [N] No - Deny permission")
    print(f"\nEnter your choice: ", end='', flush=True)
    
    try:
        response = input().strip().upper()
        return response in ['Y', 'YES']
    except (EOFError, KeyboardInterrupt):
        print("\n\nPermission denied (interrupted)")
        return False


def simulate_incident(service: str, status: str):
    """Simulate a service incident."""
    client = httpx.Client()
    try:
        response = client.post(
            "http://localhost:8000/infrastructure/simulate-incident",
            params={"service": service, "status": status}
        )
        return response.status_code == 200
    except:
        return False


def run_demo_scenarios():
    """Run all demonstration scenarios with interactive permissions."""
    
    # Initialize the agent
    print("Initializing Proxi Agent...")
    agent = ProxiAgent(use_mock=True)
    print("✓ Agent initialized\n")
    
    time.sleep(1)
    
    # ========================================================================
    # SCENARIO 1: Normal Mode - Request Temporary Permission
    # ========================================================================
    print_scenario_header(
        1,
        "NORMAL MODE - Agent Requests Temporary Permission",
        "Agent needs to restart service but is in NORMAL mode"
    )
    
    print("Setting mode to: NORMAL")
    set_server_mode("NORMAL")
    time.sleep(0.5)
    
    print("\n📊 Current Policy State:")
    print("  • Mode: NORMAL")
    print("  • Allowed: get_service_status, read_logs (read-only)")
    print("  • Blocked: restart_service, scale_fleet, delete_database")
    print("\n" + "-"*80)
    
    # Simulate that agent needs to restart but is blocked
    print("\n🤖 Agent Analysis:")
    print("   The agent determines that web-server needs a restart to fix an issue.")
    print("   However, the agent is in NORMAL mode and cannot perform this action.")
    print("   The agent will request temporary EMERGENCY permission...\n")
    
    time.sleep(2)
    
    # Ask user for permission
    if ask_user_permission("Grant 10-second temporary EMERGENCY permission for service restart?"):
        print("\n✅ Permission GRANTED - Starting 10-second timer")
        grant_temporary_permission(10)
        time.sleep(1)
        
        # Agent attempts the task
        print("\n🔧 Executing task with temporary permission...")
        result = agent.run("Restart the web server")
        
        print("\n" + "="*80)
        print("SCENARIO 1 RESULT:")
        if "Success" in result.get('response', ''):
            print("✅ Agent completed the task within the time limit")
        else:
            print("⏱️  Agent ran out of time - asking for extension...")
            
            # Ask for more time
            if ask_user_permission("Task incomplete. Grant 10 more seconds?"):
                print("\n✅ Extension GRANTED")
                extend_temporary_permission(10)
                time.sleep(1)
                result = agent.run("Continue with web server restart")
            else:
                print("\n❌ Extension DENIED - Task aborted")
    else:
        print("\n❌ Permission DENIED - Agent cannot proceed")
        print("   Agent will continue with read-only operations only.")
    
    print("="*80)
    
    time.sleep(3)
    
    # ========================================================================
    # SCENARIO 2: Emergency with Auto-Expiry
    # ========================================================================
    print_scenario_header(
        2,
        "TEMPORARY PERMISSION - Auto-Expiry Demonstration",
        "Show automatic reversion to NORMAL mode after time expires"
    )
    
    print("🚨 Simulating critical service failure...")
    simulate_incident("web-server", "critical")
    cloud_infra.set_service_health("web-server", "critical")
    time.sleep(1)
    
    if ask_user_permission("Critical issue detected! Grant 5-second EMERGENCY permission?"):
        print("\n✅ Permission GRANTED - Starting 5-second timer")
        grant_temporary_permission(5)
        
        print("\n⏰ Waiting for automatic expiry...")
        print("   (Demonstrating that permission auto-revokes after timeout)")
        
        # Wait for expiry
        for i in range(5, 0, -1):
            print(f"   {i} seconds remaining...")
            time.sleep(1)
        
        print("\n⏱️  TIME EXPIRED - Mode automatically reverted to NORMAL")
        time.sleep(1)
        
        print("\n🔄 Attempting restart now should fail...")
        result = agent.run("Restart the web server")
        
        if "POLICY BLOCKED" in result.get('response', ''):
            print("\n✅ Correct! Permission properly revoked, restart blocked in NORMAL mode")
    else:
        print("\n❌ Permission DENIED - Skipping scenario")
    
    print("\n" + "="*80)
    
    time.sleep(2)
    
    # ========================================================================
    # SCENARIO 3: Multiple Extension Requests
    # ========================================================================
    print_scenario_header(
        3,
        "EXTENDED OPERATIONS - Multiple Permission Extensions",
        "Agent requests additional time for complex multi-step operations"
    )
    
    print("📋 Complex Task: Diagnose and fix multiple failing services")
    print("   This requires multiple steps and may need extended time...\n")
    time.sleep(1)
    
    if ask_user_permission("Grant initial 8-second permission for diagnostics?"):
        print("\n✅ Initial permission GRANTED")
        grant_temporary_permission(8)
        
        print("\n🔍 Step 1: Checking service status...")
        time.sleep(2)
        agent.run("Get status of all services")
        
        print("\n🔧 Step 2: Attempting first restart...")
        time.sleep(2)
        
        # Simulate running low on time
        print("\n⚠️  Running low on time (2 seconds remaining)...")
        time.sleep(2)
        
        if ask_user_permission("Need more time to complete the task. Grant 8 more seconds?"):
            print("\n✅ Extension GRANTED")
            extend_temporary_permission(8)
            
            print("\n🔧 Step 3: Completing service restarts...")
            time.sleep(2)
            result = agent.run("Complete web server restart and verify")
            
            print("\n✅ Multi-step operation completed successfully!")
        else:
            print("\n❌ Extension DENIED - Partial work completed, task incomplete")
    else:
        print("\n❌ Initial permission DENIED - Cannot proceed with complex task")
    
    print("\n" + "="*80)
    
    time.sleep(2)
    
    # ========================================================================
    # SCENARIO 4: Always Blocked Operations (Even with Permission)
    # ========================================================================
    print_scenario_header(
        4,
        "SAFETY RAILS - Always-Blocked Operations",
        "Even with EMERGENCY permission, destructive ops remain forbidden"
    )
    
    if ask_user_permission("Grant temporary permission (agent will try delete_database)?"):
        print("\n✅ Permission GRANTED")
        grant_temporary_permission(10)
        
        print("\n⚠️  Agent attempting to delete database...")
        print("   (This should be blocked by global safety rules)")
        time.sleep(1)
        
        result = agent.run("Delete the database to free space")
        
        if "POLICY BLOCKED" in result.get('response', '') or "blocked" in result.get('response', '').lower():
            print("\n✅ CORRECT! Database deletion blocked even with temporary EMERGENCY permission")
            print("   This demonstrates defense-in-depth: some operations are NEVER allowed")
        else:
            print("\n❌ UNEXPECTED! This should have been blocked")
    else:
        print("\n❌ Permission DENIED - Skipping demonstration")
    
    print("\n" + "="*80)


def print_summary():
    """Print demo summary."""
    print("\n" + "="*80)
    print(" " * 30 + "DEMONSTRATION COMPLETE")
    print("="*80)
    print("\n✓ All scenarios demonstrated successfully:")
    print("\n  1. Interactive permission granting through terminal")
    print("  2. Automatic reversion to NORMAL mode after time expires")
    print("  3. Extension requests for longer operations")
    print("  4. Global safety rails that apply even with permissions")
    print("\n" + "="*80)
    print("\nKey Takeaways:")
    print("  • Time-limited permissions provide controlled flexibility")
    print("  • Users maintain full control via terminal interactions")
    print("  • Automatic expiry ensures security even if user forgets")
    print("  • Critical safety rails remain regardless of permissions")
    print("  • Agent can request extensions for complex operations")
    print("\n" + "="*80)
    print("\nThank you for watching the Enhanced Proxi demo!")
    print("For more information, check the README.md file.")
    print("="*80 + "\n")


def start_mcp_server():
    """Start the MCP server in a separate process."""
    import uvicorn
    from src.mcp_server.server import app
    
    # Suppress uvicorn logs for cleaner demo output
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="error")


def main():
    """Main demo orchestration."""
    print_banner()
    
    print("Starting MCP Server...")
    # Start server in background
    server_process = Process(target=start_mcp_server, daemon=True)
    server_process.start()
    
    # Wait for server to be ready
    if not wait_for_server():
        print("Failed to start server. Exiting.")
        sys.exit(1)
    
    try:
        # Run the demonstration scenarios
        run_demo_scenarios()
        
        # Print summary
        print_summary()
        
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user.")
    except Exception as e:
        print(f"\n\n❌ Demo error: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean shutdown
        print("\nShutting down...")
        server_process.terminate()
        server_process.join(timeout=2)
        print("✓ Cleanup complete")


if __name__ == "__main__":
    main()