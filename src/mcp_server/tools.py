"""
Mock Cloud Infrastructure Tools

This module simulates cloud infrastructure management tools that an AI agent
might use to manage services, databases, and fleet scaling.
"""

import random
from typing import Dict, Any
from datetime import datetime


class CloudInfrastructure:
    """
    Mock cloud infrastructure providing simulated services.
    
    This class simulates a cloud environment with services that can be
    in different states (healthy, degraded, critical).
    """
    
    def __init__(self):
        """Initialize the mock cloud infrastructure."""
        self.services = {
            "web-server": "healthy",
            "api-gateway": "healthy",
            "database": "healthy",
            "cache": "healthy"
        }
        self.fleet_size = 3
        self.execution_log = []
    
    def list_services(self) -> Dict[str, Any]:
        self._log_action("list_services", {})
        return {
            "services": list(self.services.keys()),
            "timestamp": datetime.now().isoformat()
    }

    def _log_action(self, action: str, details: Dict[str, Any]) -> None:
        """Log all infrastructure actions for audit trail."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "details": details
        }
        self.execution_log.append(log_entry)
    
    def set_service_health(self, service: str, status: str) -> None:
        """Manually set service health for demo scenarios."""
        if service in self.services:
            self.services[service] = status
    
    def get_service_status(self, service_name: str = None) -> Dict[str, Any]:
        """
        Get the current status of cloud services.
        
        This is a READ-ONLY operation allowed in all modes.
        
        Args:
            service_name: Optional specific service to check. If None, returns all services.
        
        Returns:
            Dictionary containing service status information
        """
        self._log_action("get_service_status", {"service": service_name})
        
        if service_name:
            if service_name not in self.services:
                return {
                    "status": "error",
                    "message": f"Service '{service_name}' not found",
                    "available_services": list(self.services.keys())
                }
            
            return {
                "service": service_name,
                "health": self.services[service_name],
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "services": self.services,
                "fleet_size": self.fleet_size,
                "timestamp": datetime.now().isoformat()
            }
    
    def read_logs(self, lines: int = 10) -> Dict[str, Any]:
        """
        Read system logs.
        
        This is a READ-ONLY operation allowed in all modes.
        
        Args:
            lines: Number of recent log lines to retrieve
        
        Returns:
            Dictionary containing recent log entries
        """
        self._log_action("read_logs", {"lines": lines})
        
        # Simulate log entries
        log_entries = [
            f"[INFO] Web server processing request - 200 OK",
            f"[INFO] Database connection pool: 45/100 active",
            f"[WARN] API response time: 234ms (threshold: 200ms)",
            f"[INFO] Cache hit rate: 87%",
            f"[INFO] Fleet health check: All instances responding"
        ]
        
        return {
            "log_lines": log_entries[:lines],
            "timestamp": datetime.now().isoformat(),
            "total_available": len(log_entries)
        }
    
    def restart_service(self, service_name: str) -> Dict[str, Any]:
        """
        Restart a cloud service.
        
        This is an ACTIVE operation only allowed in EMERGENCY mode.
        
        Args:
            service_name: Name of the service to restart
        
        Returns:
            Dictionary containing restart operation results
        """
        self._log_action("restart_service", {"service": service_name})
        
        if service_name not in self.services:
            return {
                "status": "error",
                "message": f"Service '{service_name}' not found",
                "available_services": list(self.services.keys())
            }
        
        print(f"    🔄 EXECUTING: Restarting service '{service_name}'...")
        print(f"       • Stopping service...")
        print(f"       • Clearing cache...")
        print(f"       • Starting service...")
        
        # Simulate service restart improving health
        self.services[service_name] = "healthy"
        
        return {
            "status": "success",
            "service": service_name,
            "action": "restart",
            "new_health": "healthy",
            "message": f"Service '{service_name}' successfully restarted",
            "timestamp": datetime.now().isoformat()
        }
    
    def scale_fleet(self, count: int) -> Dict[str, Any]:
        """
        Scale the number of service instances.
        
        This is an ACTIVE operation only allowed in EMERGENCY mode.
        
        Args:
            count: Target number of instances
        
        Returns:
            Dictionary containing scaling operation results
        """
        self._log_action("scale_fleet", {"target_count": count})
        
        if count < 1:
            return {
                "status": "error",
                "message": "Fleet size must be at least 1"
            }
        
        if count > 100:
            return {
                "status": "error",
                "message": "Fleet size cannot exceed 100 instances"
            }
        
        old_size = self.fleet_size
        self.fleet_size = count
        
        print(f"    📊 EXECUTING: Scaling fleet from {old_size} to {count} instances...")
        print(f"       • Provisioning new instances...")
        print(f"       • Updating load balancer...")
        print(f"       • Health checking new instances...")
        
        return {
            "status": "success",
            "action": "scale",
            "old_size": old_size,
            "new_size": count,
            "message": f"Fleet scaled from {old_size} to {count} instances",
            "timestamp": datetime.now().isoformat()
        }
    
    def delete_database(self, db_name: str) -> Dict[str, Any]:
        """
        Delete a database.
        
        This is a DESTRUCTIVE operation that is ALWAYS BLOCKED by policy.
        
        Args:
            db_name: Name of the database to delete
        
        Returns:
            Dictionary containing deletion attempt results
        """
        self._log_action("delete_database", {"db_name": db_name})
        
        print(f"    ⚠️  CRITICAL: Attempting to delete database '{db_name}'...")
        print(f"       ❌ THIS OPERATION SHOULD BE BLOCKED BY POLICY ENGINE")
        
        return {
            "status": "error",
            "message": "This operation should never execute - policy violation!",
            "db_name": db_name,
            "timestamp": datetime.now().isoformat()
        }


# Global infrastructure instance
cloud_infra = CloudInfrastructure()


# Tool function wrappers for agent integration
def get_service_status(service_name: str = None) -> str:
    """Get cloud service status - READ ONLY."""
    result = cloud_infra.get_service_status(service_name)
    return str(result)


def read_logs(lines: int = 10) -> str:
    """Read system logs - READ ONLY."""
    result = cloud_infra.read_logs(lines)
    return str(result)


def restart_service(service_name: str) -> str:
    """Restart a service - ACTIVE OPERATION."""
    result = cloud_infra.restart_service(service_name)
    return str(result)


def scale_fleet(count: int) -> str:
    """Scale fleet size - ACTIVE OPERATION."""
    result = cloud_infra.scale_fleet(count)
    return str(result)


def delete_database(db_name: str) -> str:
    """Delete a database - DESTRUCTIVE OPERATION (ALWAYS BLOCKED)."""
    result = cloud_infra.delete_database(db_name)
    return str(result)

def list_services() -> str:
    result = cloud_infra.list_services()
    return str(result)
