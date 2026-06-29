"""Risk & SLA Monitor: Timeline tracking, predictive simulation, and alerts."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from statistics import mean, stdev
from typing import Any, Callable

import numpy as np

from shared.models import Project, Task, TaskStatus, Timeline, Risk, Alert, Priority
from shared.utils import timestamp_now, generate_id


@dataclass
class SLAConstraint:
    """Service Level Agreement constraint."""
    metric: str  # e.g., "completion_date", "daily_progress", "budget"
    target: float
    threshold: float  # Warning threshold
    deadline: float  # Critical threshold
    unit: str = "days"  # or "hours", "percent", "dollars"


@dataclass
class DriftIndicator:
    """Project drift metrics."""
    schedule_drift_days: float = 0.0
    budget_drift_percent: float = 0.0
    scope_creep_count: int = 0
    velocity_trend: float = 1.0  # 1.0 = on track, <1 = behind, >1 = ahead
    quality_degradation: float = 0.0  # 0-1


@dataclass
class SimulationResult:
    """Result from Monte Carlo simulation."""
    iterations: int
    success_count: int
    mean_completion_time: float
    std_dev: float
    percentiles: dict[int, float]  # e.g., {5: 10.5, 50: 15.0, 95: 25.0}
    probability_on_time: float
    risk_contributions: dict[str, float]
    histogram: list[tuple[float, int]]  # (completion_time, frequency)


class MonteCarloSimulator:
    """Monte Carlo simulation for timeline forecasting."""
    
    def __init__(self, iterations: int = 10000):
        self.iterations = iterations
        self.rng = random.Random()
    
    def run_simulation(
        self,
        tasks: list[Task],
        start_date: datetime,
        target_date: datetime,
        risks: list[Risk | None] = None,
    ) -> SimulationResult:
        """
        Run Monte Carlo simulation to predict completion probability.
        
        Args:
            tasks: List of tasks with estimates
            start_date: Project start date
            target_date: Target completion date
            risks: Optional list of risks that could affect timeline
        """
        target_duration_days = (target_date - start_date).days
        completion_times = []
        success_count = 0
        risk_impacts: dict[str, list[float]] = field.default_factory(lambda: defaultdict(list))
        
        for _ in range(self.iterations):
            result = self._simulate_once(tasks, risks, target_duration_days, risk_impacts)
            completion_times.append(result)
            if result <= target_duration_days:
                success_count += 1
        
        # Calculate statistics
        mean_time = mean(completion_times)
        stddev = stdev(completion_times) if len(completion_times) > 1 else 0
        
        sorted_times = sorted(completion_times)
        percentiles = {
            5: np.percentile(sorted_times, 5),
            10: np.percentile(sorted_times, 10),
            25: np.percentile(sorted_times, 25),
            50: np.percentile(sorted_times, 50),
            75: np.percentile(sorted_times, 75),
            90: np.percentile(sorted_times, 90),
            95: np.percentile(sorted_times, 95),
        }
        
        # Build histogram
        hist, bins = np.histogram(completion_times, bins=20)
        histogram = list(zip(bins[:-1], hist))
        
        # Calculate risk contributions
        risk_contributions = {}
        for risk_id, impacts in risk_impacts.items():
            risk_contributions[risk_id] = mean(impacts)
        
        return SimulationResult(
            iterations=self.iterations,
            success_count=success_count,
            mean_completion_time=mean_time,
            std_dev=stddev,
            percentiles=percentiles,
            probability_on_time=success_count / self.iterations,
            risk_contributions=risk_contributions,
            histogram=histogram,
        )
    
    def _simulate_once(
        self,
        tasks: list[Task],
        risks: list[Risk] | None,
        target_duration: float,
        risk_impacts: dict[str, list[float]],
    ) -> float:
        """Run a single simulation iteration."""
        total_time = 0.0
        completed_tasks: set[str] = set()
        
        # Sort tasks by dependencies
        pending = sorted(tasks, key=lambda t: len(t.depends_on))
        
        while pending:
            # Find tasks that can start
            ready = [
                t for t in pending
                if all(dep in completed_tasks for dep in t.depends_on)
            ]
            
            if not ready:
                break  # Can't proceed (cycle or bug)
            
            # Simulate each ready task
            for task in ready:
                # Add variance to estimate (triangular distribution)
                min_hours = task.estimated_hours * 0.6
                max_hours = task.estimated_hours * 2.5
                actual_hours = self.rng.triangular(min_hours, task.estimated_hours, max_hours)
                
                # Apply risk impacts
                if risks:
                    for risk in risks:
                        if random.random() < risk.probability:
                            impact_hours = actual_hours * risk.impact
                            actual_hours += impact_hours
                            # Track risk impact
                            if hasattr(risk, 'id'):
                                risk_impacts.setdefault(risk.id, []).append(impact_hours)
                
                total_time += actual_hours / 8  # Convert to days (assuming 8h workday)
                completed_tasks.add(task.id)
                pending.remove(task)
        
        return total_time
    
    def estimate_buffer(
        self,
        tasks: list[Task],
        confidence_level: float = 0.8,
    ) -> float:
        """Estimate recommended buffer time based on variance."""
        durations = []
        for _ in range(1000):
            total = sum(
                self.rng.triangular(t.estimated_hours * 0.7, t.estimated_hours, t.estimated_hours * 2.0)
                for t in tasks
            ) / 8  # days
            durations.append(total)
        
        sorted_durations = sorted(durations)
        mean_dur = mean(sorted_durations)
        
        # Find duration at confidence level
        idx = int(len(sorted_durations) * confidence_level)
        confidence_duration = sorted_durations[idx]
        
        # Buffer is the difference between confidence duration and mean
        return confidence_duration - mean_dur


class RiskAssessor:
    """Risk assessment and tracking."""
    
    RISK_CATEGORIES = {
        "technical": ["code complexity", "integration", "new technology", "performance"],
        "resource": ["availability", "skill gap", "turnover", "overallocation"],
        "timeline": ["dependency delay", "scope creep", "unrealistic estimate", "external blocker"],
        "external": ["vendor dependency", "regulatory", "market change", "competitor"],
        "financial": ["budget overrun", "cost escalation", "funding"],
    }
    
    def __init__(self):
        self.risk_rules: list[Callable[[Project], list[Risk]]] = []
        self._load_default_rules()
    
    def _load_default_rules(self) -> None:
        """Load default risk detection rules."""
        self.risk_rules = [
            self._detect_resource_risk,
            self._detect_dependency_risk,
            self._detect_estimate_risk,
            self._detect_quality_risk,
        ]
    
    def assess_project(self, project: Project) -> list[Risk]:
        """Run full risk assessment on a project."""
        risks = []
        
        # Run rule-based detection
        for rule in self.risk_rules:
            risks.extend(rule(project))
        
        # Assess existing risks
        for risk in project.risks:
            self._update_risk_probability(risk, project)
        
        risks.extend(project.risks)
        
        # Deduplicate
        seen = set()
        unique_risks = []
        for risk in risks:
            key = (risk.category, risk.description.lower())
            if key not in seen:
                seen.add(key)
                unique_risks.append(risk)
        
        return sorted(unique_risks, key=lambda r: r.risk_score, reverse=True)
    
    def _detect_resource_risk(self, project: Project) -> list[Risk]:
        """Detect resource-related risks."""
        risks = []
        
        # Check team capacity
        if len(project.team) == 0:
            risks.append(Risk(
                category="resource",
                description="No team assigned to project",
                probability=0.9,
                impact=0.9,
            ))
        
        # Check for overloaded tasks
        for task in project.tasks:
            if task.estimated_hours > 80:  # > 2 week task
                risks.append(Risk(
                    category="resource",
                    description=f"Task '{task.title}' is large ({task.estimated_hours}h), risk of underestimation",
                    probability=0.6,
                    impact=0.5,
                ))
        
        return risks
    
    def _detect_dependency_risk(self, project: Project) -> list[Risk]:
        """Detect dependency-related risks."""
        risks = []
        task_map = {t.id: t for t in project.tasks}
        
        for task in project.tasks:
            if len(task.depends_on) > 3:
                risks.append(Risk(
                    category="timeline",
                    description=f"Task '{task.title}' has many dependencies ({len(task.depends_on)}), increasing delay risk",
                    probability=0.5,
                    impact=0.6,
                ))
            
            # Check if dependencies exist
            for dep_id in task.depends_on:
                if dep_id not in task_map:
                    risks.append(Risk(
                        category="timeline",
                        description=f"Task '{task.title}' depends on unknown task '{dep_id}'",
                        probability=0.8,
                        impact=0.7,
                    ))
        
        return risks
    
    def _detect_estimate_risk(self, project: Project) -> list[Risk]:
        """Detect estimation-related risks."""
        risks = []
        
        total_hours = sum(t.estimated_hours for t in project.tasks)
        if project.timeline and total_hours > 0:
            available_hours = (project.timeline.due_date - project.timeline.start_date).days * 8
            if total_hours > available_hours * 1.5:
                risks.append(Risk(
                    category="timeline",
                    description=f"Estimated work ({total_hours}h) exceeds available time ({available_hours}h) by 50%+",
                    probability=0.75,
                    impact=0.8,
                ))
        
        return risks
    
    def _detect_quality_risk(self, project: Project) -> list[Risk]:
        """Detect quality-related risks."""
        risks = []
        
        # Check if testing is mentioned
        has_testing = any(
            "test" in t.title.lower() or "qa" in t.title.lower() or "quality" in t.title.lower()
            for t in project.tasks
        )
        
        if not has_testing and len(project.tasks) > 5:
            risks.append(Risk(
                category="technical",
                description="No explicit testing tasks defined",
                probability=0.5,
                impact=0.6,
            ))
        
        return risks
    
    def _update_risk_probability(self, risk: Risk, project: Project) -> None:
        """Update risk probability based on current project state."""
        # Increase probability as deadline approaches
        if project.timeline:
            days_remaining = (project.timeline.due_date - timestamp_now()).days
            total_days = (project.timeline.due_date - project.timeline.start_date).days
            
            if days_remaining < total_days * 0.3:  # Less than 30% time remaining
                risk.probability = min(risk.probability * 1.3, 1.0)
    
    def calculate_velocity_trend(self, project: Project, window: int = 7) -> float:
        """Calculate recent velocity trend."""
        now = timestamp_now()
        recent_tasks = [
            t for t in project.tasks
            if t.actual_start and (now - t.actual_start).days <= window
        ]
        
        if not recent_tasks:
            return 1.0
        
        total_estimated = sum(t.estimated_hours for t in recent_tasks)
        total_actual = sum(t.actual_hours for t in recent_tasks)
        
        if total_estimated == 0:
            return 1.0
        
        return total_estimated / max(total_actual, 1)  # >1 means faster than estimate


class SLAMonitor:
    """Monitor SLA compliance and project health."""
    
    def __init__(self):
        self.constraints: dict[str, SLAConstraint] = {}
        self.alerts: list[Alert] = []
        self.monte_carlo = MonteCarloSimulator()
        self.risk_assessor = RiskAssessor()
    
    def add_constraint(self, project_id: str, constraint: SLAConstraint) -> None:
        """Add an SLA constraint for a project."""
        self.constraints[f"{project_id}:{constraint.metric}"] = constraint
    
    def check_compliance(self, project: Project) -> dict[str, Any]:
        """Check project compliance against all constraints."""
        results = {}
        
        for key, constraint in self.constraints.items():
            if not key.startswith(f"{project.id}:"):
                continue
            
            current_value = self._get_metric_value(project, constraint.metric)
            status = "compliant"
            
            if current_value >= constraint.deadline:
                status = "breached"
            elif current_value >= constraint.threshold:
                status = "at_risk"
            
            results[constraint.metric] = {
                "current": current_value,
                "target": constraint.target,
                "threshold": constraint.threshold,
                "deadline": constraint.deadline,
                "status": status,
            }
        
        return results
    
    def _get_metric_value(self, project: Project, metric: str) -> float:
        """Get current value for a metric."""
        if metric == "completion_date":
            if not project.tasks:
                return 0.0
            completed = sum(1 for t in project.tasks if t.status == TaskStatus.COMPLETED)
            return len(project.tasks) - completed
        
        elif metric == "daily_progress":
            # Calculate tasks per day
            if project.timeline:
                days_elapsed = max(1, (timestamp_now() - project.timeline.start_date).days)
                completed = sum(1 for t in project.tasks if t.status == TaskStatus.COMPLETED)
                return completed / days_elapsed
            return 0.0
        
        elif metric == "budget":
            return project.budget.spent if project.budget else 0.0
        
        return 0.0
    
    def forecast_timeline(self, project: Project) -> dict[str, Any]:
        """Generate timeline forecast with Monte Carlo simulation."""
        if not project.timeline or not project.tasks:
            return {
                "error": "Insufficient data for forecasting",
            }
        
        # Run simulation
        simulation = self.monte_carlo.run_simulation(
            tasks=project.tasks,
            start_date=project.timeline.start_date,
            target_date=project.timeline.due_date,
            risks=project.risks,
        )
        
        # Update timeline with forecast
        project.timeline.on_time_probability = simulation.probability_on_time
        project.timeline.expected_completion = project.timeline.start_date + timedelta(
            days=int(simulation.percentiles.get(50, simulation.mean_completion_time))
        )
        project.timeline.risk_factors = [
            r.description for r in self.risk_assessor.assess_project(project)
            if r.probability > 0.5
        ][:5]  # Top 5 risks
        
        return {
            "probability_on_time": simulation.probability_on_time,
            "expected_completion": project.timeline.expected_completion.isoformat(),
            "percentiles": simulation.percentiles,
            "mean_duration_days": simulation.mean_completion_time,
            "std_dev_days": simulation.std_dev,
            "recommended_buffer_days": self.monte_carlo.estimate_buffer(project.tasks),
            "risk_factors": project.timeline.risk_factors,
        }
    
    def calculate_drift(self, project: Project) -> DriftIndicator:
        """Calculate drift metrics for a project."""
        drift = DriftIndicator()
        
        if not project.timeline:
            return drift
        
        # Schedule drift
        if project.timeline.expected_completion:
            expected = project.timeline.expected_completion
            target = project.timeline.due_date
            drift.schedule_drift_days = (expected - target).days
        
        # Budget drift
        if project.budget and project.budget.allocated > 0:
            drift.budget_drift_percent = (project.budget.spent / project.budget.allocated - 1) * 100
        
        # Velocity trend
        drift.velocity_trend = self.risk_assessor.calculate_velocity_trend(project)
        
        # Scope creep - compare initial task count to current
        # (simplified - would use actual baseline in production)
        drift.scope_creep_count = max(0, len(project.tasks) - len(project.objectives) * 3)
        
        return drift
    
    def generate_alerts(self, project: Project) -> list[Alert]:
        """Generate alerts based on project state."""
        alerts = []
        drift = self.calculate_drift(project)
        
        # Schedule alerts
        if drift.schedule_drift_days > 7:
            alerts.append(Alert(
                severity="critical",
                category="timeline",
                message=f"Project '{project.title}' at risk: {drift.schedule_drift_days} days behind schedule",
                project_id=project.id,
            ))
        elif drift.schedule_drift_days > 3:
            alerts.append(Alert(
                severity="warning",
                category="timeline",
                message=f"Project '{project.title}' showing schedule drift: {drift.schedule_drift_days} days",
                project_id=project.id,
            ))
        
        # Budget alerts
        if drift.budget_drift_percent > 20:
            alerts.append(Alert(
                severity="critical",
                category="budget",
                message=f"Project '{project.title}' over budget by {drift.budget_drift_percent:.1f}%",
                project_id=project.id,
            ))
        elif drift.budget_drift_percent > 10:
            alerts.append(Alert(
                severity="warning",
                category="budget",
                message=f"Project '{project.title}' approaching budget limit",
                project_id=project.id,
            ))
        
        # Velocity alerts
        if drift.velocity_trend < 0.7:
            alerts.append(Alert(
                severity="warning",
                category="timeline",
                message=f"Project velocity declining: {drift.velocity_trend:.2f}x estimate",
                project_id=project.id,
            ))
        
        # Risk alerts
        high_risks = [r for r in project.risks if r.probability > 0.6 and r.impact > 0.6]
        for risk in high_risks[:3]:  # Top 3 risks
            alerts.append(Alert(
                severity="warning",
                category="risk",
                message=f"High risk: {risk.description}",
                project_id=project.id,
            ))
        
        self.alerts.extend(alerts)
        return alerts
    
    def export_audit_log(self, format: str = "json") -> list[dict]:
        """Export monitoring data for audit trail."""
        log_entries = []
        
        for alert in self.alerts:
            log_entries.append({
                "type": "alert",
                "timestamp": alert.created_at.isoformat(),
                "severity": alert.severity,
                "category": alert.category,
                "message": alert.message,
                "project_id": alert.project_id,
            })
        
        if format == "json":
            return log_entries
        else:
            # CSV format headers would be handled separately
            return log_entries


class RiskSLAMonitor:
    """Main entry point for risk and SLA monitoring."""
    
    def __init__(self):
        self.monitor = SLAMonitor()
        self.assessor = RiskAssessor()
    
    def analyze_project(self, project: Project) -> dict[str, Any]:
        """Run full analysis on a project."""
        # Risk assessment
        risks = self.assessor.assess_project(project)
        project.risks = risks
        
        # Timeline forecast
        forecast = self.monitor.forecast_timeline(project)
        
        # Drift calculation
        drift = self.monitor.calculate_drift(project)
        
        # Generate alerts
        alerts = self.monitor.generate_alerts(project)
        
        return {
            "forecast": forecast,
            "drift": {
                "schedule_drift_days": drift.schedule_drift_days,
                "budget_drift_percent": drift.budget_drift_percent,
                "velocity_trend": drift.velocity_trend,
                "scope_creep_count": drift.scope_creep_count,
            },
            "risks": [r.model_dump() for r in risks],
            "alerts": [a.model_dump() for a in alerts],
            "compliance_status": self.monitor.check_compliance(project),
        }


from collections import defaultdict
from dataclasses import field
