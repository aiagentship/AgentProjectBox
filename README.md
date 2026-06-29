# AgentProjectBox

A headless project management SaaS module for AI agents. Orchestrates messy human requests into structured briefs, builds dynamic task graphs, monitors risks, adapts resources, and outputs invisible project management data for agents to consume.

## Overview

AgentProjectBox is an API/CLI-first project management system designed specifically for AI agents. It provides:

- **Intake Layer**: NLP-powered parsing of natural language project requests with schema enforcement
- **Task Graph Engine**: DAG-based task dependency management with knowledge graph for reusable workflows
- **Risk & SLA Monitor**: Monte Carlo simulations for timeline forecasting and drift detection
- **Adaptive Resource Allocation**: Auto-assignment to agents based on skills, availability, and workload
- **Finance Layer**: Invisible budget tracking and burn rate analysis
- **Compliance Layer**: Role-based permissions and tamper-evident audit trails
- **Collaboration Layer**: Agent-to-agent negotiation and arbitration
- **Output Layer**: Structured JSON, CLI logs, and Slack digests

## Installation

```bash
pip install -e .
```

## Quick Start

```python
from agentprojectbox import Orchestrator

# Initialize
orch = Orchestrator()

# Create a project
project, context = orch.create_project(
    title="AI Agent SaaS Launch",
    request_text="Build a SaaS platform for AI agents in 2 months. Need core modules, documentation, and launch campaign.",
)

# Register agents
agent1 = orch.register_agent("Agent-Dev", capabilities=["code_generation", "testing"])
agent2 = orch.register_agent("Agent-PM", capabilities=["project_management"])

# Allocate tasks
orch.allocate_task_resources(project.id)

# Monitor
analysis = orch.monitor_project(project.id)
print(f"On-time probability: {analysis['forecast']['probability_on_time']:.0%}")

# Export
report = orch.export_full_report(project.id)
```

## CLI Usage

```bash
# Create a project
agentproject create "AI Agent SaaS Launch" -r "Build a SaaS platform in 2 months with core modules and docs"

# Add tasks
agentproject add-task <project-id> "Core modules" --depends none
agentproject add-task <project-id> "Documentation" --depends <task-id>

# Register agents
agentproject agent register "Agent-Dev" -c code_generation -c testing
agentproject agent register "Agent-PM" -c project_management

# Allocate resources
agentproject resource allocate <project-id>

# Monitor
agentproject monitor analyze <project-id>
agentproject monitor alerts

# Export
agentproject export json <project-id> --full
agentproject export report <project-id>
```

## Architecture

```
AgentProjectBox/
├── intake/          # NLP parsing + schema enforcement
├── graph/           # DAG builder + knowledge graph
├── monitor/         # SLA + risk tracking + Monte Carlo
├── resources/       # Adaptive allocation + swarm mode
├── finance/         # Invisible budget tracking
├── compliance/      # Audit logs + RBAC
├── collab/          # Agent APIs + negotiation
├── outputs/         # JSON, CLI, Slack
└── shared/          # Models, utils, config
```

## Configuration

Environment variables:

- `APB_ENV`: Environment (development/production)
- `APB_DEBUG`: Enable debug mode
- `APB_API_HOST`: API server host
- `APB_API_PORT`: API server port
- `APB_SECRET_KEY`: JWT secret key
- `APB_SLACK_WEBHOOK`: Slack webhook URL for notifications
- `APB_SWARM_MODE`: Enable swarm mode for multi-project coordination
- `APB_AUTO_ALLOCATE`: Enable automatic resource allocation

## API Reference

See examples in `/examples/output_examples/{project_output.json,slack_digest.json,compliance_export.json}`

## License

MIT
