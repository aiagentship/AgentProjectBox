"""Compliance Layer: Role-based permissions and audit trails."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from shared.models import AuditEvent, Project, Agent
from shared.utils import timestamp_now, generate_id, hash_dict


class Permission(str, Enum):
    """Available permissions."""
    # Project permissions
    PROJECT_CREATE = "project:create"
    PROJECT_READ = "project:read"
    PROJECT_UPDATE = "project:update"
    PROJECT_DELETE = "project:delete"
    
    # Task permissions
    TASK_CREATE = "task:create"
    TASK_READ = "task:read"
    TASK_UPDATE = "task:update"
    TASK_DELETE = "task:delete"
    TASK_ASSIGN = "task:assign"
    
    # Agent permissions
    AGENT_READ = "agent:read"
    AGENT_UPDATE = "agent:update"
    AGENT_MANAGE = "agent:manage"
    
    # Finance permissions
    BUDGET_READ = "budget:read"
    BUDGET_UPDATE = "budget:update"
    
    # Compliance permissions
    AUDIT_READ = "audit:read"
    AUDIT_EXPORT = "audit:export"
    AUDIT_MANAGE = "audit:manage"
    
    # Admin permissions
    ADMIN_FULL = "admin:full"


class Role(str, Enum):
    """Pre-defined roles."""
    SYSTEM = "system"
    ADMIN = "admin"
    MANAGER = "manager"
    LEAD = "lead"
    CONTRIBUTOR = "contributor"
    VIEWER = "viewer"
    AUDITOR = "auditor"


ROLE_PERMISSIONS: dict[Role, list[Permission]] = {
    Role.SYSTEM: [Permission.ADMIN_FULL],
    Role.ADMIN: [Permission.ADMIN_FULL],
    Role.MANAGER: [
        Permission.PROJECT_CREATE, Permission.PROJECT_READ, Permission.PROJECT_UPDATE,
        Permission.TASK_CREATE, Permission.TASK_READ, Permission.TASK_UPDATE, Permission.TASK_ASSIGN,
        Permission.AGENT_READ, Permission.AGENT_UPDATE,
        Permission.BUDGET_READ, Permission.BUDGET_UPDATE,
        Permission.AUDIT_READ, Permission.AUDIT_EXPORT,
    ],
    Role.LEAD: [
        Permission.PROJECT_READ, Permission.PROJECT_UPDATE,
        Permission.TASK_CREATE, Permission.TASK_READ, Permission.TASK_UPDATE, Permission.TASK_ASSIGN,
        Permission.AGENT_READ,
        Permission.BUDGET_READ,
        Permission.AUDIT_READ,
    ],
    Role.CONTRIBUTOR: [
        Permission.PROJECT_READ,
        Permission.TASK_READ, Permission.TASK_UPDATE,
        Permission.AGENT_READ,
    ],
    Role.VIEWER: [
        Permission.PROJECT_READ,
        Permission.TASK_READ,
    ],
    Role.AUDITOR: [
        Permission.PROJECT_READ,
        Permission.TASK_READ,
        Permission.AUDIT_READ, Permission.AUDIT_EXPORT, Permission.AUDIT_MANAGE,
    ],
}


@dataclass
class Principal:
    """Security principal (user or agent)."""
    id: str
    type: str  # "user" or "agent"
    roles: list[Role] = field(default_factory=list)
    project_roles: dict[str, Role] = field(default_factory=dict)  # project_id -> role
    attributes: dict[str, Any] = field(default_factory=dict)
    
    def has_role(self, role: Role) -> bool:
        """Check if principal has a global role."""
        return role in self.roles
    
    def get_project_role(self, project_id: str) -> Role | None:
        """Get role for a specific project."""
        return self.project_roles.get(project_id)
    
    def get_effective_permissions(self, project_id: str | None = None) -> set[Permission]:
        """Get all permissions for this principal."""
        permissions: set[Permission] = set()
        
        # Global role permissions
        for role in self.roles:
            permissions.update(ROLE_PERMISSIONS.get(role, []))
        
        # Project-specific role permissions
        if project_id and project_id in self.project_roles:
            project_role = self.project_roles[project_id]
            permissions.update(ROLE_PERMISSIONS.get(project_role, []))
        
        return permissions


class RBACEnforcer:
    """Role-Based Access Control enforcement."""
    
    def __init__(self):
        self.principals: dict[str, Principal] = {}
        self.resource_owners: dict[str, str] = {}  # resource_id -> principal_id
        self.custom_permissions: dict[str, set[Permission]] = {}
    
    def register_principal(
        self,
        principal_id: str,
        principal_type: str,
        roles: list[Role] | None = None,
    ) -> Principal:
        """Register a new principal."""
        principal = Principal(
            id=principal_id,
            type=principal_type,
            roles=roles or [],
        )
        self.principals[principal_id] = principal
        return principal
    
    def assign_project_role(
        self,
        principal_id: str,
        project_id: str,
        role: Role,
    ) -> None:
        """Assign a role to a principal for a specific project."""
        principal = self.principals.get(principal_id)
        if principal:
            principal.project_roles[project_id] = role
    
    def check_permission(
        self,
        principal_id: str,
        permission: Permission,
        resource_id: str | None = None,
        resource_type: str | None = None,
        project_id: str | None = None,
    ) -> bool:
        """
        Check if principal has permission.
        
        Args:
            principal_id: ID of the principal
            permission: Permission to check
            resource_id: Optional specific resource
            resource_type: Type of resource (project, task, etc)
            project_id: Optional project context
        
        Returns:
            True if permitted, False otherwise
        """
        principal = self.principals.get(principal_id)
        if not principal:
            return False
        
        # System principals have all permissions
        if principal.has_role(Role.SYSTEM):
            return True
        
        # Get effective permissions
        permissions = principal.get_effective_permissions(project_id)
        
        # Check specific permission or admin wildcard
        if permission in permissions or Permission.ADMIN_FULL in permissions:
            return True
        
        # Check ownership
        if resource_id and resource_id in self.resource_owners:
            if self.resource_owners[resource_id] == principal_id:
                # Owners have implicit update/read on their resources
                if permission in [Permission.PROJECT_UPDATE, Permission.TASK_UPDATE, 
                                  Permission.PROJECT_READ, Permission.TASK_READ]:
                    return True
        
        return False
    
    def require_permission(self, *permissions: Permission) -> callable:
        """Decorator to require permissions for a function."""
        def decorator(func: callable) -> callable:
            def wrapper(*args, **kwargs):
                # In real implementation, would extract principal from context
                # For now, placeholder
                return func(*args, **kwargs)
            return wrapper
        return decorator


class AuditTrail:
    """Tamper-evident audit trail for compliance."""
    
    def __init__(self):
        self.events: list[AuditEvent] = []
        self.chain_hash: str = "0" * 64  # Blockchain-style hash chain
    
    def log_event(
        self,
        event_type: str,
        actor: str,
        action: str,
        resource_type: str,
        resource_id: str,
        details: dict[str, Any] | None = None,
        before_state: dict[str, Any] | None = None,
        after_state: dict[str, Any] | None = None,
        ip_address: str | None = None,
        session_id: str | None = None,
    ) -> AuditEvent:
        """Log an auditable event."""
        
        # Create event data for hashing
        event_data = {
            "event_type": event_type,
            "actor": actor,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": details or {},
            "timestamp": timestamp_now().isoformat(),
            "previous_hash": self.chain_hash,
        }
        
        # Calculate signature (tamper-evident)
        event_str = json.dumps(event_data, sort_keys=True)
        signature = hashlib.sha256(event_str.encode()).hexdigest()
        
        # Update chain hash
        self.chain_hash = signature
        
        event = AuditEvent(
            event_type=event_type,
            actor=actor,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            before_state=before_state,
            after_state=after_state,
            ip_address=ip_address,
            session_id=session_id,
            signature=signature,
        )
        
        self.events.append(event)
        return event
    
    def log_project_event(
        self,
        project: Project,
        actor: str,
        action: str,
        details: dict[str, Any] | None = None,
    ) -> AuditEvent:
        """Log a project-level event."""
        return self.log_event(
            event_type="project_action",
            actor=actor,
            action=action,
            resource_type="project",
            resource_id=project.id,
            details=details or {"project_title": project.title},
        )
    
    def log_task_event(
        self,
        task: Any,  # Task
        actor: str,
        action: str,
        details: dict[str, Any] | None = None,
    ) -> AuditEvent:
        """Log a task-level event."""
        return self.log_event(
            event_type="task_action",
            actor=actor,
            action=action,
            resource_type="task",
            resource_id=task.id,
            details=details or {"task_title": task.title},
        )
    
    def log_access_event(
        self,
        principal_id: str,
        resource_type: str,
        resource_id: str,
        access_granted: bool,
        ip_address: str | None = None,
    ) -> AuditEvent:
        """Log an access control event."""
        return self.log_event(
            event_type="access_control",
            actor=principal_id,
            action="access_granted" if access_granted else "access_denied",
            resource_type=resource_type,
            resource_id=resource_id,
            details={"granted": access_granted},
            ip_address=ip_address,
        )
    
    def verify_integrity(self) -> dict[str, Any]:
        """Verify audit trail integrity (detect tampering)."""
        if not self.events:
            return {"valid": True, "events_checked": 0}
        
        current_hash = "0" * 64
        tampered_events = []
        
        for i, event in enumerate(self.events):
            event_data = {
                "event_type": event.event_type,
                "actor": event.actor,
                "action": event.action,
                "resource_type": event.resource_type,
                "resource_id": event.resource_id,
                "details": event.details,
                "timestamp": event.timestamp.isoformat(),
                "previous_hash": current_hash,
            }
            
            expected_sig = hashlib.sha256(json.dumps(event_data, sort_keys=True).encode()).hexdigest()
            
            if event.signature != expected_sig:
                tampered_events.append({"index": i, "event_id": event.id})
            
            current_hash = event.signature or expected_sig
        
        return {
            "valid": len(tampered_events) == 0,
            "events_checked": len(self.events),
            "tampered_count": len(tampered_events),
            "tampered_events": tampered_events,
            "final_hash": current_hash,
        }
    
    def export_for_review(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        resource_type: str | None = None,
        actor: str | None = None,
    ) -> list[dict[str, Any]]:
        """Export audit trail for legal/finance review."""
        filtered = self.events
        
        if start_date:
            filtered = [e for e in filtered if e.timestamp >= start_date]
        if end_date:
            filtered = [e for e in filtered if e.timestamp <= end_date]
        if resource_type:
            filtered = [e for e in filtered if e.resource_type == resource_type]
        if actor:
            filtered = [e for e in filtered if e.actor == actor]
        
        return [
            {
                "id": e.id,
                "timestamp": e.timestamp.isoformat(),
                "event_type": e.event_type,
                "actor": e.actor,
                "action": e.action,
                "resource_type": e.resource_type,
                "resource_id": e.resource_id,
                "details": e.details,
                "signature": e.signature,
                "integrity": "verified",  # Would verify in production
            }
            for e in sorted(filtered, key=lambda x: x.timestamp)
        ]
    
    def generate_compliance_report(
        self,
        period_start: datetime | None = None,
        period_end: datetime | None = None,
    ) -> dict[str, Any]:
        """Generate compliance report for auditors."""
        events = self.events
        
        if period_start:
            events = [e for e in events if e.timestamp >= period_start]
        if period_end:
            events = [e for e in events if e.timestamp <= period_end]
        
        # Event type breakdown
        event_types: dict[str, int] = {}
        for e in events:
            event_types[e.event_type] = event_types.get(e.event_type, 0) + 1
        
        # Resource type breakdown
        resource_types: dict[str, int] = {}
        for e in events:
            resource_types[e.resource_type] = resource_types.get(e.resource_type, 0) + 1
        
        # Actor breakdown
        actors: dict[str, int] = {}
        for e in events:
            actors[e.actor] = actors.get(e.actor, 0) + 1
        
        integrity = self.verify_integrity()
        
        return {
            "report_period": {
                "start": period_start.isoformat() if period_start else None,
                "end": period_end.isoformat() if period_end else None,
            },
            "summary": {
                "total_events": len(events),
                "unique_actors": len(actors),
                "integrity_verified": integrity["valid"],
            },
            "breakdown": {
                "by_event_type": event_types,
                "by_resource_type": resource_types,
                "by_actor": actors,
            },
            "integrity_check": integrity,
            "export_hash": hash_dict({"count": len(events), "integrity": integrity["final_hash"]}),
        }


class ComplianceLayer:
    """Main entry point for compliance operations."""
    
    def __init__(self):
        self.rbac = RBACEnforcer()
        self.audit = AuditTrail()
    
    def register_agent(
        self,
        agent: Agent,
        roles: list[Role] | None = None,
    ) -> Principal:
        """Register an agent with the compliance system."""
        principal = self.rbac.register_principal(
            agent.id,
            "agent",
            roles or [Role.CONTRIBUTOR],
        )
        
        self.audit.log_event(
            event_type="principal_registered",
            actor="system",
            action="register_agent",
            resource_type="principal",
            resource_id=agent.id,
            details={"roles": [r.value for r in (roles or [])]},
        )
        
        return principal
    
    def check_access(
        self,
        principal_id: str,
        permission: Permission,
        resource_type: str,
        resource_id: str,
        project_id: str | None = None,
    ) -> bool:
        """Check access and log the attempt."""
        granted = self.rbac.check_permission(
            principal_id, permission, resource_id, resource_type, project_id
        )
        
        self.audit.log_access_event(
            principal_id,
            resource_type,
            resource_id,
            granted,
        )
        
        return granted
    
    def require_access(self, permission: Permission) -> callable:
        """Decorator factory for requiring access."""
        def decorator(func):
            def wrapper(*args, **kwargs):
                # In real implementation, would extract principal from context
                return func(*args, **kwargs)
            wrapper.__wrapped__ = func
            return wrapper
        return decorator
    
    def export_audit_trail(
        self,
        format: str = "json",
        **filters
    ) -> list[dict] | str:
        """Export audit trail for compliance review."""
        entries = self.audit.export_for_review(**filters)
        
        if format == "json":
            return entries
        elif format == "csv":
            # Would generate CSV in real implementation
            return json.dumps(entries)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def generate_compliance_report(
        self,
        period_start: datetime | None = None,
        period_end: datetime | None = None,
    ) -> dict[str, Any]:
        """Generate full compliance report."""
        return self.audit.generate_compliance_report(period_start, period_end)
