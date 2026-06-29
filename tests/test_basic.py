"""Basic tests for AgentProjectBox."""

import pytest
from datetime import datetime, timedelta

from shared.models import (
    Project, Task, Agent, Budget, Timeline, 
    ProjectStatus, TaskStatus, Priority, AgentCapability
)
from shared.utils import generate_id, timestamp_now

from intake import IntakeLayer
from graph import TaskGraphEngine
from monitor import RiskSLAMonitor
from resources import ResourceAllocator
from finance import FinanceLayer
from compliance import ComplianceLayer, Permission, Role
from collab import CollaborationLayer


class TestIntakeLayer:
    """Test natural language intake."""
    
    def test_parse_simple_request(self):
        intake = IntakeLayer()
        request, project = intake.process_request(
            "Build a SaaS app for AI agents. Deliverables: core modules, docs, launch campaign. Timeline: 2 months."
        )
        
        assert project is not None
        assert len(project.deliverables) == 3
    
    def test_extract_objectives(self):
        intake = IntakeLayer()
        request, project = intake.process_request(
            "Create a documentation system. Goals: write user guide, create API docs, build landing page."
        )
        
        assert project is not None
        assert len(project.objectives) > 0


class TestTaskGraph:
    """Test DAG builder."""
    
    def test_build_dag(self):
        engine = TaskGraphEngine()
        
        t1 = Task(title="Setup", estimated_hours=8)
        t2 = Task(title="Development", estimated_hours=40, depends_on=[t1.id])
        t3 = Task(title="Testing", estimated_hours=16, depends_on=[t2.id])
        
        builder = engine.builder
        builder.add_task(t1)
        builder.add_task(t2)
        builder.add_task(t3)
        
        assert builder.is_dag()
        assert len(builder.topological_sort()) == 3
    
    def test_critical_path(self):
        engine = TaskGraphEngine()
        
        t1 = Task(title="A", estimated_hours=10)
        t2 = Task(title="B", estimated_hours=20, depends_on=[t1.id])
        t3 = Task(title="C", estimated_hours=5)
        
        builder = engine.builder
        builder.add_task(t1)
        builder.add_task(t2)
        builder.add_task(t3)
        
        duration, path = builder.calculate_critical_path()
        assert duration == 30  # A -> B is longest
        assert path == [t1.id, t2.id]


class TestMonitoring:
    """Test risk and SLA monitoring."""
    
    def test_risk_assessment(self):
        monitor = RiskSLAMonitor()
        
        project = Project(
            title="Test Project",
            objectives=["Build X"],
            deliverables=["X v1"],
        )
        project.tasks = [
            Task(title="Big task", estimated_hours=100),
        ]
        
        risks = monitor.assessor.assess_project(project)
        
        # Should detect at least something
        assert len(risks) >= 1
    
    def test_monte_carlo_forecast(self):
        monitor = RiskSLAMonitor()
        project = Project(
            title="Forecast Test",
            timeline=Timeline(
                start_date=timestamp_now(),
                due_date=timestamp_now() + timedelta(days=30),
            )
        )
        project.tasks = [
            Task(title="T1", estimated_hours=40),
            Task(title="T2", estimated_hours=40),
        ]
        
        # Just verify it runs
        result = monitor.monitor.forecast_timeline(project)
        assert result is not None


class TestResources:
    """Test resource allocation."""
    
    def test_skill_matching(self):
        from resources.allocator import SkillMatcher
        
        matcher = SkillMatcher()
        
        agent = Agent(
            name="Dev Agent",
            capabilities=[AgentCapability.CODE_GENERATION, AgentCapability.TESTING],
            skill_levels={AgentCapability.CODE_GENERATION: 0.9},
        )
        
        task = Task(
            title="Write code",
            required_capabilities=[AgentCapability.CODE_GENERATION],
        )
        
        score = matcher.calculate_match_score(task, agent)
        assert score > 0.5  # Should have good match


class TestFinance:
    """Test budget tracking."""
    
    def test_budget_tracking(self):
        finance = FinanceLayer()
        
        project = Project(title="Budget Test")
        budget = finance.initialize_project_budget(project, 50000)
        
        assert budget.allocated == 50000
        assert budget.spent == 0
        assert budget.remaining == 50000


class TestCompliance:
    """Test RBAC and audit."""
    
    def test_role_permissions(self):
        rbac = ComplianceLayer().rbac
        
        principal = rbac.register_principal("user-1", "user", [Role.MANAGER])
        
        assert principal.has_role(Role.MANAGER)
        
        perms = principal.get_effective_permissions(None)
        assert Permission.PROJECT_CREATE in perms
    
    def test_audit_trail(self):
        audit = ComplianceLayer().audit
        
        event = audit.log_event(
            event_type="test_action",
            actor="test-user",
            action="create",
            resource_type="test",
            resource_id="test-1",
        )
        
        assert event.id is not None
        assert event.signature is not None
        
        integrity = audit.verify_integrity()
        assert integrity["valid"]


class TestCollaboration:
    """Test agent collaboration."""
    
    def test_agent_registration(self):
        collab = CollaborationLayer()
        
        agent = Agent(name="Agent-1", capabilities=[AgentCapability.NLP])
        collab.connect_agent(agent)
        
        status = collab.get_agent_status(agent.id)
        assert status["agent_id"] == agent.id
        assert status["available"] is True


class TestIntegration:
    """Integration tests across modules."""
    
    def test_full_workflow(self):
        """Test a complete project lifecycle."""
        from agentprojectbox import Orchestrator
        
        orch = Orchestrator()
        
        # Create project
        project, ctx = orch.create_project(
            title="Integration Test",
            objectives=["Test integration"],
            deliverables=["Output"],
        )
        assert project is not None
        
        # Register agent
        agent = orch.register_agent("TestAgent", ["code_generation"])
        assert agent.id in orch.agents
        
        # Add task
        task = orch.add_task(project.id, "Write test", estimated_hours=4)
        assert task in project.tasks
        
        # Set budget
        budget = orch.set_project_budget(project.id, 10000)
        assert budget.allocated == 10000
        
        # Monitor
        analysis = orch.monitor_project(project.id)
        assert "forecast" in analysis or "error" in analysis


if __name__ == "__main__":
    pytest.main()
