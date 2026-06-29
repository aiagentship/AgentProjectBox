"""
AgentProjectBox Example Workflows

This file demonstrates various ways to use AgentProjectBox.
Run with: python examples/workflows.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def example_1_basic_usage():
    """Basic usage: Create a project and monitor it."""
    print("\n" + "="*60)
    print("EXAMPLE 1: Basic Usage")
    print("="*60)
    
    from agentprojectbox import Orchestrator
    
    # Initialize orchestrator
    orch = Orchestrator()
    
    # Create a project from natural language
    print("\n1. Creating project from natural language...")
    project, context = orch.create_project(
        title="AI Agent SaaS Launch",
        request_text="Build a SaaS platform for AI agents in 2 months. Objectives: MVP build, Beta release. Deliverables: Core modules, Documentation, Launch campaign.",
    )
    
    if project:
        print(f"   ✓ Created project: {project.title}")
        print(f"   ✓ Generated {len(project.tasks)} tasks automatically")
        print(f"   ✓ Objectives: {len(project.objectives)}")
        print(f"   ✓ Deliverables: {len(project.deliverables)}")
    else:
        print("   ✗ Project needs clarification:")
        for q in context.get('questions', []):
            print(f"      - {q}")
        return
    
    # Monitor the project
    print("\n2. Monitoring project...")
    analysis = orch.monitor_project(project.id)
    
    if 'forecast' in analysis:
        forecast = analysis['forecast']
        prob = forecast.get('probability_on_time', 0)
        print(f"   ✓ On-time probability: {prob:.0%}")
        if 'expected_completion' in forecast:
            print(f"   ✓ Expected completion: {forecast['expected_completion']}")
    
    # Export report
    print("\n3. Exporting full report...")
    report = orch.export_full_report(project.id)
    print(f"   ✓ Report exported with {len(report.get('tasks', []))} tasks")
    
    print("\n✅ Example 1 complete!")


def example_2_multi_agent_collaboration():
    """Multi-agent collaboration: Register agents and allocate tasks."""
    print("\n" + "="*60)
    print("EXAMPLE 2: Multi-Agent Collaboration")
    print("="*60)
    
    from agentprojectbox import Orchestrator
    from shared.models import AgentCapability
    
    # Initialize
    orch = Orchestrator()
    
    # Create project
    print("\n1. Creating project...")
    project, _ = orch.create_project(
        title="E-commerce Platform",
        request_text="Build an e-commerce platform with product catalog, shopping cart, and payment integration in 6 weeks. Objectives: MVP launch. Deliverables: Product catalog, Shopping cart, Payment system.",
    )
    
    if not project:
        print("   ✗ Failed to create project")
        return
    
    print(f"   ✓ Created project with {len(project.tasks)} tasks")
    
    # Register agents
    print("\n2. Registering agents...")
    agents = [
        orch.register_agent(
            name="Dev-Agent-1",
            capabilities=["code_generation", "api_design"],
        ),
        orch.register_agent(
            name="Dev-Agent-2",
            capabilities=["frontend_development", "ui_design"],
        ),
        orch.register_agent(
            name="Test-Agent",
            capabilities=["testing", "code_review"],
        ),
        orch.register_agent(
            name="DevOps-Agent",
            capabilities=["infrastructure", "devops"],
        ),
    ]
    
    for agent in agents:
        print(f"   ✓ Registered: {agent.name} ({agent.type})")
    
    # Allocate tasks
    print("\n3. Allocating tasks to agents...")
    recommendations = orch.allocate_task_resources(project.id)
    
    for rec in recommendations[:5]:  # Show first 5
        task_title = rec.task_id[:8]  # Truncate for display
        if rec.recommended_agents:
            agent_id = rec.recommended_agents[0][0]
            confidence = rec.confidence
            print(f"   ✓ {task_title} → {agent_id} (confidence: {confidence:.0%})")
    
    if len(recommendations) > 5:
        print(f"   ... and {len(recommendations) - 5} more")
    
    # Check alerts
    print("\n4. Checking for alerts...")
    alerts = orch.check_alerts(project_id=project.id)
    
    if alerts:
        for alert in alerts[:3]:
            print(f"   ⚠ {alert.severity}: {alert.message[:60]}")
    else:
        print("   ✓ No alerts")
    
    print("\n✅ Example 2 complete!")


def example_3_swarm_mode():
    """Swarm mode: Coordinate multiple projects."""
    print("\n" + "="*60)
    print("EXAMPLE 3: Swarm Mode (Multi-Project Coordination)")
    print("="*60)
    
    from agentprojectbox import Orchestrator
    
    # Initialize with swarm mode
    orch = Orchestrator(swarm_mode=True)
    
    # Create multiple projects
    print("\n1. Creating multiple projects...")
    projects = []
    
    for i, (title, request) in enumerate([
        ("Project Alpha", "Build API backend in 3 weeks"),
        ("Project Beta", "Create frontend dashboard in 4 weeks"),
        ("Project Gamma", "Implement data pipeline in 2 weeks"),
    ]):
        project, _ = orch.create_project(title=title, request_text=request)
        if project:
            projects.append(project)
            print(f"   ✓ Created: {project.title}")
    
    # Register shared agents
    print("\n2. Registering shared agents...")
    for name in ["Shared-Dev-Agent", "Shared-Test-Agent"]:
        orch.register_agent(name, capabilities=["code_generation", "testing"])
        print(f"   ✓ Registered: {name}")
    
    # Join swarm
    print("\n3. Activating swarm mode...")
    swarm_result = orch.join_swarm([p.id for p in projects])
    print(f"   ✓ Swarm activated for {swarm_result.get('agents')} agents")
    
    # Allocate across projects
    print("\n4. Allocating resources across projects...")
    for project in projects:
        recs = orch.allocate_task_resources(project.id)
        print(f"   ✓ {project.title[:20]}: {len(recs)} tasks allocated")
    
    # Monitor all
    print("\n5. Monitoring all projects...")
    for project in projects:
        analysis = orch.monitor_project(project.id)
        prob = analysis.get('forecast', {}).get('probability_on_time', 0)
        print(f"   ✓ {project.title[:20]}: {prob:.0%} on-time")
    
    print("\n✅ Example 3 complete!")


def example_4_budget_tracking():
    """Budget tracking and cost analysis."""
    print("\n" + "="*60)
    print("EXAMPLE 4: Budget Tracking")
    print("="*60)
    
    from agentprojectbox import Orchestrator
    
    orch = Orchestrator()
    
    # Create project with budget
    print("\n1. Creating project with budget...")
    project, _ = orch.create_project(
        title="Marketing Campaign",
        request_text="Run a marketing campaign with ads, content, and analytics in 1 month.",
        budget=50000,
    )
    
    if not project:
        print("   ✗ Failed to create project")
        return
    
    print(f"   ✓ Created project")
    
    # Set agent rates
    print("\n2. Setting agent rates...")
    agent1 = orch.register_agent("Content-Agent", capabilities=["writing"])
    agent2 = orch.register_agent("Ads-Agent", capabilities=["analysis"])
    
    orch.set_agent_rate(agent1.id, 50)  # $50/hour
    orch.set_agent_rate(agent2.id, 75)  # $75/hour
    
    print(f"   ✓ Content-Agent: $50/hour")
    print(f"   ✓ Ads-Agent: $75/hour")
    
    # Allocate tasks
    print("\n3. Allocating tasks...")
    orch.allocate_task_resources(project.id)
    
    # Check budget
    print("\n4. Checking budget...")
    finance = orch.get_project_finance(project.id)
    
    if finance:
        budget = finance.get('budget', {})
        print(f"   ✓ Allocated: ${budget.get('allocated', 0):,.2f}")
        print(f"   ✓ Spent: ${budget.get('spent', 0):,.2f}")
        print(f"   ✓ Remaining: ${budget.get('remaining', 0):,.2f}")
        print(f"   ✓ Burn rate: ${budget.get('burn_rate_per_day', 0):,.2f}/day")
    
    print("\n✅ Example 4 complete!")


def example_5_persistence():
    """Persistence: Save and load projects."""
    print("\n" + "="*60)
    print("EXAMPLE 5: Persistence")
    print("="*60)
    
    from agentprojectbox import Orchestrator
    
    # Create new orchestrator with persistence
    print("\n1. Creating orchestrator with persistence...")
    orch1 = Orchestrator(persist=True, data_dir="/tmp/apb_test")
    
    # Create project
    print("\n2. Creating project...")
    project, _ = orch1.create_project(
        title="Persistent Project",
        request_text="Build a simple task manager in 2 weeks.",
    )
    
    if project:
        print(f"   ✓ Created project: {project.id[:8]}")
        print(f"   ✓ Data saved to ~/.agentprojectbox/")
    
    # Simulate new session
    print("\n3. Simulating new session (new orchestrator)...")
    orch2 = Orchestrator(persist=True, data_dir="/tmp/apb_test")
    
    # Load project
    print("\n4. Loading projects...")
    projects = orch2.list_projects()
    print(f"   ✓ Found {len(projects)} persisted project(s)")
    
    for p in projects:
        print(f"   - {p.title} (ID: {p.id[:8]})")
    
    # Backup
    print("\n5. Creating backup...")
    backup_path = "/tmp/apb_backup.json"
    orch2.backup(backup_path)
    print(f"   ✓ Backup saved to: {backup_path}")
    
    print("\n✅ Example 5 complete!")


def example_6_cli_usage():
    """CLI usage examples."""
    print("\n" + "="*60)
    print("EXAMPLE 6: CLI Usage")
    print("="*60)
    
    print("""
Run these commands in your terminal:

# Create a project
agentproject create "My Project" -r "Build a website in 3 weeks" --budget 10000

# List projects
agentproject project list

# Add a task
agentproject task add <project-id> "Setup infrastructure" --priority HIGH

# Register an agent
agentproject agent register "Dev-Agent" -c code_generation -c testing

# Allocate resources
agentproject resource allocate <project-id>

# Monitor project
agentproject monitor analyze <project-id>

# View alerts
agentproject monitor alerts

# Export JSON
agentproject export json <project-id> --full

# Show system status
agentproject status
""")
    
    print("\n✅ Example 6 complete!")


def example_7_api_usage():
    """API server usage examples."""
    print("\n" + "="*60)
    print("EXAMPLE 7: API Server")
    print("="*60)
    
    print("""
Start the API server:

    python server.py

Or with uvicorn:

    uvicorn server:app --host 0.0.0.0 --port 8000

Then make API calls:

# Create project
curl -X POST http://localhost:8000/projects \\
  -H "Content-Type: application/json" \\
  -d '{"title": "My Project", "request_text": "Build a website"}'

# List projects
curl http://localhost:8000/projects

# Monitor project
curl http://localhost:8000/projects/{project_id}/monitor

# Allocate resources
curl -X POST http://localhost:8000/projects/{project_id}/allocate

# View API docs
Open http://localhost:8000/docs in your browser
""")
    
    print("\n✅ Example 7 complete!")


def main():
    """Run all examples."""
    print("\n" + "="*60)
    print("AGENTPROJECTBOX EXAMPLE WORKFLOWS")
    print("="*60)
    
    try:
        example_1_basic_usage()
    except Exception as e:
        print(f"\n❌ Example 1 failed: {e}")
    
    try:
        example_2_multi_agent_collaboration()
    except Exception as e:
        print(f"\n❌ Example 2 failed: {e}")
    
    try:
        example_3_swarm_mode()
    except Exception as e:
        print(f"\n❌ Example 3 failed: {e}")
    
    try:
        example_4_budget_tracking()
    except Exception as e:
        print(f"\n❌ Example 4 failed: {e}")
    
    try:
        example_5_persistence()
    except Exception as e:
        print(f"\n❌ Example 5 failed: {e}")
    
    try:
        example_6_cli_usage()
    except Exception as e:
        print(f"\n❌ Example 6 failed: {e}")
    
    try:
        example_7_api_usage()
    except Exception as e:
        print(f"\n❌ Example 7 failed: {e}")
    
    print("\n" + "="*60)
    print("ALL EXAMPLES COMPLETE!")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
