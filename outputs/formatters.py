"""Output Layer: JSON, CLI, Slack outputs for humans and agents."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from shared.models import Project, Task, TaskStatus, Budget, Timeline, Risk, Alert
from shared.utils import timestamp_now, generate_id


class JSONOutput:
    """Generate structured JSON output for agent consumption."""
    
    @staticmethod
    def export_project(project: Project, include_full_data: bool = True) -> dict[str, Any]:
        """Export complete project data as JSON."""
        base = {
            "project_id": project.id,
            "title": project.title,
            "description": project.description,
            "status": project.status.value,
            "priority": project.priority.name,
            "created_at": project.created_at.isoformat(),
            "updated_at": project.updated_at.isoformat(),
        }
        
        if include_full_data:
            base.update({
                "objectives": project.objectives,
                "deliverables": project.deliverables,
                "constraints": project.constraints,
                "assumptions": project.assumptions,
                "team": project.team,
                "stakeholders": project.stakeholders,
            })
            
            # Timeline
            if project.timeline:
                base["timeline"] = {
                    "start_date": project.timeline.start_date.isoformat(),
                    "due_date": project.timeline.due_date.isoformat(),
                    "on_time_probability": project.timeline.on_time_probability,
                    "expected_completion": project.timeline.expected_completion.isoformat() if project.timeline.expected_completion else None,
                    "risk_factors": project.timeline.risk_factors,
                }
            
            # Budget
            if project.budget:
                base["budget"] = {
                    "allocated": project.budget.allocated,
                    "spent": project.budget.spent,
                    "remaining": project.budget.remaining,
                    "currency": project.budget.currency,
                    "burn_rate": project.budget.burn_rate_category,
                }
            
            # Tasks
            base["task_graph"] = [
                {
                    "task_id": task.id,
                    "title": task.title,
                    "status": task.status.value,
                    "priority": task.priority.name,
                    "assigned_to": task.assigned_to,
                    "depends_on": task.depends_on,
                    "estimated_hours": task.estimated_hours,
                    "actual_hours": task.actual_hours,
                }
                for task in project.tasks
            ]
            
            # Risks
            base["risks"] = [
                {
                    "id": risk.id,
                    "category": risk.category,
                    "description": risk.description,
                    "probability": risk.probability,
                    "impact": risk.impact,
                    "risk_score": risk.risk_score,
                    "status": risk.status,
                }
                for risk in project.risks
            ]
            
            # Progress
            base["progress"] = {
                "completion_percent": project.calculate_progress() * 100,
                "total_tasks": len(project.tasks),
                "completed_tasks": sum(1 for t in project.tasks if t.status == TaskStatus.COMPLETED),
            }
        
        return base
    
    @staticmethod
    def export_dashboard_summary(
        projects: list[Project],
        include_finance: bool = False,
    ) -> dict[str, Any]:
        """Export dashboard-level summary for multiple projects."""
        return {
            "generated_at": timestamp_now().isoformat(),
            "summary": {
                "total_projects": len(projects),
                "active_projects": sum(1 for p in projects if p.status.value == "active"),
                "at_risk_projects": sum(
                    1 for p in projects
                    if p.timeline and p.timeline.on_time_probability < 0.5
                ),
            },
            "projects": [
                JSONOutput.export_project(p, include_full_data=False)
                for p in projects
            ],
            "high_priority_alerts": [],  # Would be populated from monitoring
        }
    
    @staticmethod
    def export_compliance_data(
        audit_logs: list[dict],
        project: Project | None = None,
    ) -> dict[str, Any]:
        """Export compliance-ready data for legal/finance review."""
        return {
            "export_type": "compliance",
            "generated_at": timestamp_now().isoformat(),
            "export_id": generate_id(),
            "project": project.model_dump() if project else None,
            "audit_trail": audit_logs,
            "checksum": generate_id()[:16],  # Simplified
            "retention_until": (datetime.utcnow().replace(year=datetime.utcnow().year + 7)).isoformat(),
        }


class CLIFormatter:
    """Format output for CLI display."""
    
    @staticmethod
    def format_project_summary(project: Project) -> str:
        """Format a project summary for CLI."""
        lines = [
            f"Project: {project.title}",
            f"ID: {project.id}",
            f"Status: {project.status.value.upper()}",
            f"Priority: {project.priority.name}",
            "",
        ]
        
        if project.timeline:
            lines.extend([
                f"Start: {project.timeline.start_date.strftime('%Y-%m-%d')}",
                f"Due: {project.timeline.due_date.strftime('%Y-%m-%d')}",
                f"On-time probability: {project.timeline.on_time_probability:.0%}",
                "",
            ])
        
        if project.tasks:
            completed = sum(1 for t in project.tasks if t.status == TaskStatus.COMPLETED)
            lines.extend([
                f"Tasks: {completed}/{len(project.tasks)} completed",
                f"Progress: {project.calculate_progress():.0%}",
                "",
            ])
        
        if project.risks:
            high_risks = [r for r in project.risks if r.probability > 0.5]
            lines.append(f"Risks: {len(high_risks)} high severity")
        
        return "\n".join(lines)
    
    @staticmethod
    def format_task_list(tasks: list[Task], show_status: bool = True) -> str:
        """Format task list for CLI."""
        lines = []
        
        for task in tasks:
            status_icon = {
                TaskStatus.PENDING: "○",
                TaskStatus.BLOCKED: "⊘",
                TaskStatus.IN_PROGRESS: "◐",
                TaskStatus.COMPLETED: "●",
                TaskStatus.CANCELLED: "✗",
            }.get(task.status, "?")
            
            line = f"  {status_icon} {task.title}"
            if show_status:
                line += f" [{task.status.value}]"
            if task.assigned_to:
                line += f" → {', '.join(task.assigned_to)[:20]}"
            
            lines.append(line)
        
        return "\n".join(lines) if lines else "  (no tasks)"
    
    @staticmethod
    def format_budget_summary(budget: Budget) -> str:
        """Format budget for CLI."""
        if budget.allocated == 0:
            return "Budget: Not set"
        
        percent = budget.percent_used
        progress_bar = CLIFormatter._progress_bar(percent / 100, 20)
        
        lines = [
            f"Budget: ${budget.spent:,.2f} / ${budget.allocated:,.2f} {budget.currency}",
            f"        {progress_bar} {percent:.1f}%",
            f"        Burn rate: {budget.burn_rate_category}",
        ]
        
        return "\n".join(lines)
    
    @staticmethod
    def format_alerts(alerts: list[Alert]) -> str:
        """Format alerts for CLI."""
        if not alerts:
            return "No active alerts"
        
        lines = [f"Alerts ({len(alerts)}):", ""]
        
        for alert in alerts:
            severity_icon = {
                "info": "ℹ",
                "warning": "⚠",
                "critical": "✖",
            }.get(alert.severity, "•")
            
            lines.append(f"  {severity_icon} [{alert.severity.upper()}] {alert.message}")
        
        return "\n".join(lines)
    
    @staticmethod
    def _progress_bar(progress: float, width: int = 20) -> str:
        """Create ASCII progress bar."""
        filled = int(width * progress)
        bar = "█" * filled + "░" * (width - filled)
        return f"[{bar}]"


class SlackFormatter:
    """Format output for Slack webhooks."""
    
    def __init__(self, webhook_url: str | None = None):
        self.webhook_url = webhook_url
    
    def format_project_digest(self, project: Project) -> dict[str, Any]:
        """Format project summary for Slack."""
        # Status emoji
        status_emoji = {
            "draft": ":pencil:",
            "active": ":rocket:",
            "paused": ":pause_button:",
            "completed": ":white_check_mark:",
            "cancelled": ":x:",
        }.get(project.status.value, ":question:")
        
        # Risk indicator
        risk_indicator = ""
        if project.timeline:
            if project.timeline.on_time_probability < 0.3:
                risk_indicator = " :red_circle: High Risk"
            elif project.timeline.on_time_probability < 0.6:
                risk_indicator = " :yellow_circle: At Risk"
            else:
                risk_indicator = " :green_circle: On Track"
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{status_emoji} {project.title}",
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Status:*\n{project.status.value.upper()}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Health:*\n{risk_indicator}"
                    },
                ]
            }
        ]
        
        # Add progress
        if project.tasks:
            completed = sum(1 for t in project.tasks if t.status == TaskStatus.COMPLETED)
            total = len(project.tasks)
            percent = int((completed / total) * 100) if total > 0 else 0
            
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Progress:* {completed}/{total} tasks ({percent}%)"
                }
            })
        
        # Add timeline
        if project.timeline:
            blocks.append({
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Due Date:*\n{project.timeline.due_date.strftime('%Y-%m-%d')}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*On-Time Probability:*\n{project.timeline.on_time_probability:.0%}"
                    },
                ]
            })
        
        return {
            "text": f"Project Update: {project.title}",
            "blocks": blocks,
        }
    
    def format_alert(self, alert: Alert) -> dict[str, Any]:
        """Format an alert for Slack."""
        emoji = {
            "info": ":information_source:",
            "warning": ":warning:",
            "critical": ":rotating_light:",
        }.get(alert.severity, ":bell:")
        
        return {
            "text": f"{emoji} {alert.severity.upper()}: {alert.message}",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"{emoji} {alert.severity.upper()} Alert"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": alert.message
                    }
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"Category: {alert.category} | Project: {alert.project_id or 'N/A'}"
                        }
                    ]
                }
            ]
        }
    
    def format_daily_digest(
        self,
        projects: list[Project],
        alerts: list[Alert],
    ) -> dict[str, Any]:
        """Format daily summary digest."""
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": ":chart_with_upwards_trend: Daily Project Digest"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{len(projects)}* active projects • *{len(alerts)}* alerts"
                }
            },
            {"type": "divider"},
        ]
        
        # At-risk projects
        at_risk = [
            p for p in projects
            if p.timeline and p.timeline.on_time_probability < 0.6
        ]
        
        if at_risk:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":yellow_circle: *{len(at_risk)} Projects At Risk*"
                }
            })
            
            for project in at_risk[:5]:
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"• *{project.title}* - {project.timeline.on_time_probability:.0%} on-time probability"
                    }
                })
        
        # Recent alerts
        if alerts:
            blocks.append({"type": "divider"})
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":bell: *Recent Alerts ({len(alerts)})*"
                }
            })
            
            critical = [a for a in alerts if a.severity == "critical"]
            if critical:
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f":rotating_light: *{len(critical)} Critical*"
                    }
                })
        
        return {
            "text": "Daily Project Digest",
            "blocks": blocks,
        }


class OutputLayer:
    """Main entry point for output operations."""
    
    def __init__(self, slack_webhook_url: str | None = None):
        self.json_output = JSONOutput()
        self.cli_formatter = CLIFormatter()
        self.slack_formatter = SlackFormatter(slack_webhook_url)
    
    def export_project_json(
        self,
        project: Project,
        include_full_data: bool = True,
    ) -> dict[str, Any]:
        """Export project as JSON."""
        return self.json_output.export_project(project, include_full_data)
    
    def export_project_compliance(
        self,
        project: Project,
        audit_logs: list[dict],
    ) -> dict[str, Any]:
        """Export compliance-ready JSON."""
        return self.json_output.export_compliance_data(audit_logs, project)
    
    def format_cli_project(self, project: Project) -> str:
        """Format project for CLI display."""
        return self.cli_formatter.format_project_summary(project)
    
    def format_cli_tasks(self, tasks: list[Task]) -> str:
        """Format tasks for CLI display."""
        return self.cli_formatter.format_task_list(tasks)
    
    def format_cli_alerts(self, alerts: list[Alert]) -> str:
        """Format alerts for CLI display."""
        return self.cli_formatter.format_alerts(alerts)
    
    def format_slack_digest(self, project: Project) -> dict[str, Any]:
        """Format project for Slack webhook."""
        return self.slack_formatter.format_project_digest(project)
    
    def format_slack_alert(self, alert: Alert) -> dict[str, Any]:
        """Format alert for Slack."""
        return self.slack_formatter.format_alert(alert)
    
    def format_slack_daily_digest(
        self,
        projects: list[Project],
        alerts: list[Alert],
    ) -> dict[str, Any]:
        """Format daily digest for Slack."""
        return self.slack_formatter.format_daily_digest(projects, alerts)
    
    def export_full_report(
        self,
        project: Project,
        alerts: list[Alert] | None = None,
    ) -> dict[str, Any]:
        """Export comprehensive report for agent consumption."""
        return {
            "version": "1.0.0",
            "generated_at": timestamp_now().isoformat(),
            "report_type": "full_export",
            "project": self.json_output.export_project(project, include_full_data=True),
            "alerts": [a.model_dump() for a in (alerts or [])],
            "audit_event": {
                "event": "report_generated",
                "actor": "system",
                "timestamp": timestamp_now().isoformat(),
            },
        }
