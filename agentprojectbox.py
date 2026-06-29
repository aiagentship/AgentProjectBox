"""AgentProjectBox - Main orchestration module."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any

from shared.models import (
    Project, Task, Agent, ProjectStatus, TaskStatus, Priority,
    AgentCapability, Timeline, Budget
)
from shared.utils import timestamp_now, generate_id
from shared.config import config

from intake import IntakeLayer
from graph import TaskGraphEngine
from monitor import RiskSLAMonitor
from resources import ResourceAllocator
from finance import FinanceLayer
from compliance import ComplianceLayer, Permission, Role
from collab import CollaborationLayer
from outputs import OutputLayer


class Orchestrator:
    """
    Main orchestrator for AgentProjectBox.
    Coordinates all modules and provides high-level operations.
    """
    
    def __init__(self, swarm_mode: bool = False):
        self.swarm_mode = swarm_mode
        
        # Initialize all layers
        self.intake = IntakeLayer()
        self.graph = TaskGraphEngine()
        self.monitor = RiskSLAMonitor()
        self.resources = ResourceAllocator(swarm_mode=swarm_mode)
        self.finance = FinanceLayer()
        self.compliance = ComplianceLayer()
        self.collab = CollaborationLayer()
        self.output = OutputLayer(config.notifications.slack_webhook_url)
        
        # State
        self.projects: dict[str, Project] = {}
        self.agents: dict[str, Agent] = {}
        self._initialized = True
    
    # -------------------------------------------------------------------------
    # Project Operations
    # -------------------------------------------------------------------------
    
    def create_project(
        self,
        title: str,
        request_text: str | None = None,
        objectives: list[str] | None = None,
        deliverables: list[str] | None = None,
        created_by: str = "system",
        **kwargs
    ) -> tuple[Project, dict[str, Any]]:
        """
        Create a new project from natural language or structured input.
        
        Returns:
            Tuple of (project, creation_context)
        """
        # Try to parse from text if provided
        if request_text:
            parsed_request, project = self.intake.process_request(request_text, created_by)
            
            if project is None:
                # Return the parsed request with questions
                return None, {
                    "status": "needs_clarification",
                    "questions": parsed_request.clarification_questions,
                    "confidence": parsed_request.confidence,
                }
            
            # Use parsed project as base
            project.title = title or project.title
        else:
            # Create project from scratch
            project = Project(
                title=title,
                objectives=objectives or [],
                deliverables=deliverables or [],
                created_by=created_by,
                **kwargs
            )
        
        # Set defaults if not provided
        if not project.timeline:
            project.timeline = Timeline(
                start_date=timestamp_now(),
                due_date=timestamp_now() + timedelta(days=30),
            )
        
        # Store project
        self.projects[project.id] = project
        
        # Build initial task graph
        if project.deliverables:
            self._auto_generate_tasks(project)
        
        # Log creation
        self.compliance.audit.log_project_event(
            project, created_by, "project_created",
            details={"title": project.title}
        )
        
        return project, {
            "status": "created",
            "project_id": project.id,
        }
    
    def add_task(
        self,
        project_id: str,
        title: str,
        depends_on: list[str] | None = None,
        estimated_hours: float = 8.0,
        priority: str = "MEDIUM",
        assigned_to: list[str] | None = None,
        **kwargs
    ) -> Task:
        """Add a task to a project."""
        project = self.projects.get(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")
        
        task = Task(
            title=title,
            depends_on=depends_on or [],
            estimated_hours=estimated_hours,
            priority=Priority[priority.upper()],
            assigned_to=assigned_to or [],
            **kwargs
        )
        
        project.tasks.append(task)
        
        # Update graph
        self.graph.build_from_project(project)
        
        # Log
        self.compliance.audit.log_task_event(task, "system", "task_created")
        
        return task
    
    def update_task_status(
        self,
        project_id: str,
        task_id: str,
        status: str,
        updated_by: str = "system",
    ) -> Task:
        """Update task status."""
        project = self.projects.get(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")
        
        task = next((t for t in project.tasks if t.id == task_id), None)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        old_status = task.status
        task.status = TaskStatus[status.upper()]
        task.updated_at = timestamp_now()
        
        if task.status == TaskStatus.IN_PROGRESS and not task.actual_start:
            task.actual_start = timestamp_now()
        elif task.status == TaskStatus.COMPLETED and not task.actual_end:
            task.actual_end = timestamp_now()
        
        # Log
        self.compliance.audit.log_task_event(
            task, updated_by, "task_status_updated",
            before_state={"status": old_status.value},
            after_state={"status": task.status.value},
        )
        
        return task
    
    def get_project(self, project_id: str) -> Project | None:
        """Get a project by ID."""
        return self.projects.get(project_id)
    
    def list_projects(self, status: str | None = None) -> list[Project]:
        """List all projects, optionally filtered by status."""
        projects = list(self.projects.values())
        if status:
            projects = [p for p in projects if p.status.value == status]
        return projects
    
    # -------------------------------------------------------------------------
    # Task Graph Operations
    # -------------------------------------------------------------------------
    
    def build_task_graph(self, project_id: str) -> dict[str, Any]:
        """Build task graph for project."""
        project = self.projects.get(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")
        
        builder = self.graph.build_from_project(project)
        return self.graph.export_for_agents()
    
    def optimize_tasks(self, project_id: str) -> list[dict]:
        """Get task optimization suggestions."""
        project = self.projects.get(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")
        
        self.graph.build_from_project(project)
        return self.graph.suggest_optimizations()
    
    # -------------------------------------------------------------------------
    # Monitoring
    # -------------------------------------------------------------------------
    
    def monitor_project(self, project_id: str) -> dict[str, Any]:
        """Run full monitoring analysis on a project."""
        project = self.projects.get(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")
        
        return self.monitor.analyze_project(project)
    
    def check_alerts(self, project_id: str | None = None) -> list:
        """Check for alerts."""
        if project_id:
            project = self.projects.get(project_id)
            if project:
                return self.monitor.monitor.generate_alerts(project)
            return []
        
        all_alerts = []
        for project in self.projects.values():
            all_alerts.extend(self.monitor.monitor.generate_alerts(project))
        return all_alerts
    
    def forecast(self, project_id: str) -> dict[str, Any]:
        """Generate forecast for a project."""
        project = self.projects.get(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")
        
        return self.monitor.forecast_timeline(project)
    
    # -------------------------------------------------------------------------
    # Resource Allocation
    # -------------------------------------------------------------------------
    
    def register_agent(
        self,
        name: str,
        capabilities: list[str] | None = None,
        **kwargs
    ) -> Agent:
        """Register a new agent."""
        agent = Agent(
            name=name,
            capabilities=[AgentCapability(c) for c in (capabilities or [])],
            **kwargs
        )
        
        self.agents[agent.id] = agent
        
        # Register with compliance
        self.compliance.register_agent(agent, [Role.CONTRIBUTOR])
        
        # Register with collaboration
        self.collab.connect_agent(agent)
        
        return agent
    
    def allocate_task_resources(
        self,
        project_id: str,
        task_id: str | None = None,
    ) -> list:
        """Allocate resources for tasks."""
        project = self.projects.get(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")
        
        available_agents = list(self.agents.values())
        recommendations = []
        
        if task_id:
            task = next((t for t in project.tasks if t.id == task_id), None)
            if task:
                rec = self.resources.allocate_task(task, available_agents, project)
                if rec:
                    recommendations.append(rec)
        else:
            # Allocate all pending tasks
            recommendations = self.resources.allocate_project_tasks(project, available_agents)
        
        return recommendations
    
    def join_swarm(self, project_ids: list[str]) -> dict[str, Any]:
        """Enable swarm mode for projects."""
        if not self.swarm_mode:
            return {"error": "Swarm mode not enabled"}
        
        agents = list(self.agents.values())
        self.resources.enable_swarm_mode(project_ids, agents)
        
        return {
            "status": "swarm_activated",
            "project_ids": project_ids,
            "agents": len(agents),
        }
    
    # -------------------------------------------------------------------------
    # Finance
    # -------------------------------------------------------------------------
    
    def set_project_budget(
        self,
        project_id: str,
        allocated: float,
        currency: str = "USD",
    ) -> Budget:
        """Set budget for a project."""
        project = self.projects.get(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")
        
        return self.finance.initialize_project_budget(project, allocated, currency)
    
    def set_agent_rate(
        self,
        agent_id: str,
        rate_per_hour: float,
    ) -> None:
        """Set cost rate for an agent."""
        agent = self.agents.get(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")
        
        self.finance.tracker.set_cost_rate(agent, rate_per_hour)
    
    def get_project_finance(self, project_id: str) -> dict[str, Any]:
        """Get finance data for a project."""
        return self.finance.export_project_finance(project_id)
    
    # -------------------------------------------------------------------------
    # Compliance & Audit
    # -------------------------------------------------------------------------
    
    def check_permission(
        self,
        principal_id: str,
        permission: str,
        resource_id: str,
    ) -> bool:
        """Check if principal has permission."""
        perm = Permission(permission)
        return self.compliance.check_access(principal_id, perm, "project", resource_id)
    
    def export_audit_trail(
        self,
        project_id: str | None = None,
        format: str = "json",
    ) -> list | str:
        """Export audit trail."""
        return self.compliance.export_audit_trail(format, project_id=project_id)
    
    def generate_compliance_report(
        self,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        """Generate compliance report."""
        project = self.projects.get(project_id) if project_id else None
        
        audit_logs = self.compliance.audit.export_for_review()
        return self.output.export_project_compliance(project, audit_logs)
    
    # -------------------------------------------------------------------------
    # Collaboration
    # -------------------------------------------------------------------------
    
    def agent_join_project(self, agent_id: str, project_id: str) -> dict[str, Any]:
        """Agent joins a project."""
        agent = self.agents.get(agent_id)
        project = self.projects.get(project_id)
        
        if not agent or not project:
            raise ValueError("Agent or project not found")
        
        return self.collab.api.join_project(agent, project)
    
    def claim_task(
        self,
        agent_id: str,
        project_id: str,
        task_id: str,
    ) -> dict[str, Any]:
        """Agent claims a task."""
        agent = self.agents.get(agent_id)
        project = self.projects.get(project_id)
        
        if not agent or not project:
            raise ValueError("Agent or project not found")
        
        task = next((t for t in project.tasks if t.id == task_id), None)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        return self.collab.api.claim_task(agent, task)
    
    # -------------------------------------------------------------------------
    # Output & Export
    # -------------------------------------------------------------------------
    
    def export_project(
        self,
        project_id: str,
        format: str = "json",
    ) -> dict | str:
        """Export project in specified format."""
        project = self.projects.get(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")
        
        if format.lower() == "json":
            return self.output.export_project_json(project)
        elif format.lower() == "cli":
            return self.output.format_cli_project(project)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def export_full_report(self, project_id: str) -> dict[str, Any]:
        """Export comprehensive project report."""
        project = self.projects.get(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")
        
        alerts = self.monitor.monitor.generate_alerts(project)
        return self.output.export_full_report(project, alerts)
    
    # -------------------------------------------------------------------------
    # Private Helpers
    # -------------------------------------------------------------------------
    
    def _auto_generate_tasks(self, project: Project) -> None:
        """Auto-generate tasks from deliverables."""
        for deliverable in project.deliverables:
            # Suggest tasks using knowledge graph
            suggestions = self.graph.knowledge.suggest_task_breakdown(
                deliverable, deliverable
            )
            
            for suggestion in suggestions:
                task = Task(
                    title=suggestion.get("title", f"Complete {deliverable}"),
                    priority=project.priority,
                    status=TaskStatus.PENDING,
                )
                project.tasks.append(task)
    
    def get_health_summary(self) -> dict[str, Any]:
        """Get system health summary."""
        return {
            "projects": len(self.projects),
            "agents": len(self.agents),
            "swarm_mode": self.swarm_mode,
            "audit_events": len(self.compliance.audit.events),
            "uptime": "active",
        }
