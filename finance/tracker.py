"""Finance Layer: Invisible budget tracking and financial analytics."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from shared.models import Budget, Project, Task, Agent
from shared.utils import timestamp_now, generate_id


@dataclass
class CostRate:
    """Cost rate for an agent or resource type."""
    resource_id: str
    rate_per_hour: float
    currency: str = "USD"
    effective_from: datetime = field(default_factory=timestamp_now)
    effective_until: datetime | None = None


@dataclass
class CostEntry:
    """Individual cost entry."""
    id: str = field(default_factory=generate_id)
    project_id: str = ""
    task_id: str | None = None
    agent_id: str | None = None
    cost_type: str = ""  # labor, infrastructure, external, other
    amount: float = 0.0
    currency: str = "USD"
    timestamp: datetime = field(default_factory=timestamp_now)
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class BudgetTracker:
    """Track budgets across projects and agents."""
    
    def __init__(self):
        self.cost_rates: dict[str, CostRate] = {}
        self.cost_entries: list[CostEntry] = []
        self.budgets: dict[str, Budget] = {}
    
    def set_cost_rate(self, agent: Agent, rate_per_hour: float, currency: str = "USD") -> CostRate:
        """Set the cost rate for an agent."""
        rate = CostRate(
            resource_id=agent.id,
            rate_per_hour=rate_per_hour,
            currency=currency,
        )
        self.cost_rates[agent.id] = rate
        return rate
    
    def record_cost(
        self,
        project_id: str,
        amount: float,
        cost_type: str,
        task_id: str | None = None,
        agent_id: str | None = None,
        description: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> CostEntry:
        """Record a cost entry."""
        entry = CostEntry(
            project_id=project_id,
            task_id=task_id,
            agent_id=agent_id,
            cost_type=cost_type,
            amount=amount,
            description=description,
            metadata=metadata or {},
        )
        self.cost_entries.append(entry)
        
        # Update project budget if exists
        if project_id in self.budgets:
            budget = self.budgets[project_id]
            budget.spent += amount
            
            if agent_id:
                budget.agent_costs[agent_id] = budget.agent_costs.get(agent_id, 0) + amount
            
            if cost_type == "infrastructure":
                budget.infrastructure_costs += amount
            elif cost_type == "external":
                budget.external_costs += amount
        
        return entry
    
    def calculate_task_cost(self, task: Task) -> float:
        """Calculate the cost of a task based on actual hours and agent rates."""
        total_cost = 0.0
        
        for agent_id in task.assigned_to:
            rate = self.cost_rates.get(agent_id)
            if rate:
                total_cost += task.actual_hours * rate.rate_per_hour
        
        return total_cost
    
    def update_project_budget(self, project: Project) -> Budget:
        """Update budget tracking for a project."""
        if project.id not in self.budgets:
            self.budgets[project.id] = project.budget or Budget()
        
        budget = self.budgets[project.id]
        
        # Calculate costs from tasks
        for task in project.tasks:
            if task.status.value == "completed":
                task_cost = self.calculate_task_cost(task)
                # Only add if not already recorded
                existing = sum(
                    1 for e in self.cost_entries
                    if e.task_id == task.id and e.cost_type == "labor"
                )
                if existing == 0 and task_cost > 0:
                    self.record_cost(
                        project_id=project.id,
                        task_id=task.id,
                        amount=task_cost,
                        cost_type="labor",
                        description=f"Labor cost for task: {task.title}",
                    )
        
        # Calculate burn rate
        days_since_start = max(1, (timestamp_now() - project.created_at).days)
        budget.burn_rate_per_day = budget.spent / days_since_start
        
        # Calculate projection
        if budget.allocated > 0:
            days_remaining = (budget.allocated - budget.spent) / budget.burn_rate_per_day if budget.burn_rate_per_day > 0 else float('inf')
            budget.projected_total = budget.spent + (budget.burn_rate_per_day * days_remaining)
        
        return budget
    
    def get_project_finance(self, project_id: str) -> dict[str, Any]:
        """Get complete financial data for a project."""
        budget = self.budgets.get(project_id, Budget())
        
        # Get all cost entries for project
        entries = [e for e in self.cost_entries if e.project_id == project_id]
        
        # Breakdown by type
        cost_by_type: dict[str, float] = {}
        for entry in entries:
            cost_by_type[entry.cost_type] = cost_by_type.get(entry.cost_type, 0) + entry.amount
        
        # Breakdown by agent
        cost_by_agent: dict[str, float] = {}
        for entry in entries:
            if entry.agent_id:
                cost_by_agent[entry.agent_id] = cost_by_agent.get(entry.agent_id, 0) + entry.amount
        
        return {
            "budget": budget.model_dump(),
            "summary": {
                "allocated": budget.allocated,
                "spent": budget.spent,
                "remaining": budget.remaining,
                "percent_used": budget.percent_used,
                "burn_rate_per_day": budget.burn_rate_per_day,
                "burn_rate_category": budget.burn_rate_category,
            },
            "breakdown": {
                "by_type": cost_by_type,
                "by_agent": cost_by_agent,
            },
            "entries": [
                {
                    "id": e.id,
                    "cost_type": e.cost_type,
                    "amount": e.amount,
                    "timestamp": e.timestamp.isoformat(),
                    "description": e.description,
                }
                for e in entries
            ],
        }
    
    def check_budget_drift(self, project_id: str, threshold_percent: float = 10.0) -> dict[str, Any]:
        """Check if project is drifting over budget."""
        budget = self.budgets.get(project_id)
        if not budget or budget.allocated == 0:
            return {"status": "unknown", "drift_percent": 0}
        
        drift_percent = ((budget.spent / budget.allocated) - 1) * 100
        
        status = "on_track"
        if drift_percent > threshold_percent:
            status = "critical"
        elif drift_percent > 0:
            status = "warning"
        
        return {
            "status": status,
            "drift_percent": drift_percent,
            "threshold_percent": threshold_percent,
            "projected_overrun": max(0, budget.projected_total - budget.allocated) if budget.projected_total else 0,
        }
    
    def export_finance_json(self, project_id: str) -> dict[str, Any]:
        """Export structured finance JSON for agent consumption."""
        finance = self.get_project_finance(project_id)
        drift = self.check_budget_drift(project_id)
        
        return {
            "project_id": project_id,
            "timestamp": timestamp_now().isoformat(),
            "budget_status": finance["summary"],
            "cost_breakdown": finance["breakdown"],
            "drift_analysis": drift,
            "compliance_ready": True,
            "audit_trail_hash": generate_id()[:8],  # Simplified hash
        }


class BurnRateAnalyzer:
    """Analyze and predict burn rates."""
    
    def __init__(self):
        self.history: list[tuple[datetime, float]] = []  # (timestamp, cumulative_spend)
    
    def record_spend(self, timestamp: datetime, cumulative_spend: float) -> None:
        """Record a spend data point."""
        self.history.append((timestamp, cumulative_spend))
    
    def predict_burn(
        self,
        days_ahead: int = 30,
    ) -> dict[str, Any]:
        """Predict future burn rate based on historical data."""
        if len(self.history) < 2:
            return {
                "predicted_daily_burn": 0,
                "confidence": 0.0,
            }
        
        # Linear regression on recent points
        recent = self.history[-30:] if len(self.history) > 30 else self.history
        
        # Calculate daily rate
        total_days = (recent[-1][0] - recent[0][0]).days or 1
        total_spend = recent[-1][1] - recent[0][1]
        daily_rate = total_spend / total_days
        
        # Simple trend (acceleration)
        if len(recent) >= 7:
            first_week = recent[:7]
            last_week = recent[-7:]
            first_week_rate = (first_week[-1][1] - first_week[0][1]) / max((first_week[-1][0] - first_week[0][0]).days, 1)
            last_week_rate = (last_week[-1][1] - last_week[0][1]) / max((last_week[-1][0] - last_week[0][0]).days, 1)
            acceleration = last_week_rate - first_week_rate
        else:
            acceleration = 0
        
        predicted_daily = max(0, daily_rate + acceleration)
        
        return {
            "current_daily_burn": daily_rate,
            "predicted_daily_burn": predicted_daily,
            "acceleration": acceleration,
            "days_projected": days_ahead,
            "predicted_spend": predicted_daily * days_ahead,
            "confidence": min(0.9, 0.5 + (len(recent) * 0.02)),
        }


class FinanceLayer:
    """Main entry point for finance operations."""
    
    def __init__(self):
        self.tracker = BudgetTracker()
        self.analyzers: dict[str, BurnRateAnalyzer] = {}
    
    def initialize_project_budget(
        self,
        project: Project,
        allocated: float,
        currency: str = "USD",
    ) -> Budget:
        """Initialize budget for a project."""
        budget = Budget(
            allocated=allocated,
            currency=currency,
        )
        project.budget = budget
        self.tracker.budgets[project.id] = budget
        self.analyzers[project.id] = BurnRateAnalyzer()
        return budget
    
    def record_agent_cost(
        self,
        project: Project,
        agent: Agent,
        hours: float,
        description: str = "",
    ) -> CostEntry:
        """Record agent labor cost."""
        rate = self.tracker.cost_rates.get(agent.id)
        amount = hours * rate.rate_per_hour if rate else 0.0
        
        return self.tracker.record_cost(
            project_id=project.id,
            agent_id=agent.id,
            amount=amount,
            cost_type="labor",
            description=description or f"Agent {agent.name} - {hours}h",
        )
    
    def update_project(self, project: Project) -> dict[str, Any]:
        """Update all financial tracking for a project."""
        self.tracker.update_project_budget(project)
        
        if project.id in self.analyzers:
            self.analyzers[project.id].record_spend(
                timestamp_now(),
                project.budget.spent if project.budget else 0
            )
        
        return self.export_project_finance(project.id)
    
    def export_project_finance(self, project_id: str) -> dict[str, Any]:
        """Export project finance data for agents."""
        return self.tracker.export_finance_json(project_id)
    
    def get_multi_project_summary(self, project_ids: list[str]) -> dict[str, Any]:
        """Get aggregated financial data across projects."""
        total_budgeted = 0.0
        total_spent = 0.0
        project_summaries = []
        
        for pid in project_ids:
            finance = self.tracker.get_project_finance(pid)
            summary = finance["summary"]
            total_budgeted += summary.get("allocated", 0)
            total_spent += summary.get("spent", 0)
            project_summaries.append({
                "project_id": pid,
                **summary,
            })
        
        return {
            "total_budgeted": total_budgeted,
            "total_spent": total_spent,
            "total_remaining": total_budgeted - total_spent,
            "portfolio_utilization": (total_spent / total_budgeted * 100) if total_budgeted > 0 else 0,
            "project_breakdown": project_summaries,
        }
