# AgentProjectBox

A headless project management SaaS module for AI agents. Orchestrates messy human requests into structured briefs, builds dynamic task graphs, monitors risks, adapts resources, and outputs invisible project management data for agents to consume.

## What's New (Latest Improvements)

✅ **Persistence** - Projects and agents now persist to disk automatically  
✅ **API Server** - FastAPI server for cloud access and multi-agent collaboration  
✅ **Task Templates** - Auto-generate tasks based on project type (web, mobile, API, ML, etc.)  
✅ **Examples** - Comprehensive workflow examples in `examples/workflows.py`  
✅ **Better NLP** - Improved project type detection and task suggestion  

## Quick Start

### 1. Install

```bash
pip install -e .
```

### 2. Choose Your Access Method

**Option A: Python API** (most flexible)
```python
from agentprojectbox import Orchestrator

orch = Orchestrator()  # Persistence enabled by default
project, _ = orch.create_project(
    title="My Project",
    request_text="Build a website in 3 weeks"
)
orch.allocate_task_resources(project.id)
analysis = orch.monitor_project(project.id)
print(f"On-time probability: {analysis['forecast']['probability_on_time']:.0%}")
```

**Option B: CLI** (quick commands)
```bash
agentproject create "My Project" -r "Build a website in 3 weeks" --budget 10000
agentproject resource allocate <project-id>
agentproject monitor analyze <project-id>
```

**Option C: API Server** (cloud access)
```bash
python server.py
# Then access at http://localhost:8000
```

### 3. Run Examples

```bash
python examples/workflows.py
```

## Why AgentProjectBox?

**For Individual Agents**: Not needed - agents can plan internally.

**For Agent Teams**: Essential! Provides:
- **Shared state** - Multiple agents coordinate on one source of truth
- **Persistence** - Projects survive across agent sessions
- **Conflict resolution** - Prevents duplicate work
- **Human bridge** - Humans speak naturally, agents get structured data

## Python API Examples

### Basic Project Creation

```python
from agentprojectbox import Orchestrator

orch = Orchestrator()

# Create from natural language
project, ctx = orch.create_project(
    title="E-commerce Platform",
    request_text="Build an e-commerce site with cart, checkout, and payment in 6 weeks"
)

# Project automatically gets:
# - Parsed objectives and deliverables
# - Auto-generated task breakdown (15-20 tasks)
# - Timeline with due dates
# - Risk assessment
```

### Multi-Agent Collaboration

```python
# Register agents with different capabilities
dev_agent = orch.register_agent(
    name="Dev-Agent",
    capabilities=["code_generation", "api_design"]
)

test_agent = orch.register_agent(
    name="Test-Agent", 
    capabilities=["testing", "code_review"]
)

# Auto-allocate tasks based on skills
recommendations = orch.allocate_task_resources(project.id)

# Each recommendation includes:
# - Task ID
# - Recommended agents (sorted by fit)
# - Confidence score
for rec in recommendations:
    print(f"{rec.task_id} → {rec.recommended_agents[0][0]} ({rec.confidence:.0%})")
```

### Monitoring & Forecasting

```python
# Run Monte Carlo simulation (1000+ iterations)
analysis = orch.monitor_project(project.id)

forecast = analysis['forecast']
print(f"On-time probability: {forecast['probability_on_time']:.0%}")
print(f"Expected completion: {forecast['expected_completion']}")
print(f"Recommended buffer: {forecast.get('recommended_buffer_days', 0)} days")

# Check for alerts
alerts = orch.check_alerts(project_id=project.id)
for alert in alerts:
    print(f"[{alert.severity}] {alert.message}")
```

### Budget Tracking

```python
# Set project budget
orch.set_project_budget(project.id, 50000)

# Set agent hourly rates
orch.set_agent_rate(dev_agent.id, 75)  # $75/hour
orch.set_agent_rate(test_agent.id, 60)  # $60/hour

# Check budget status
finance = orch.get_project_finance(project.id)
print(f"Allocated: ${finance['budget']['allocated']:,.2f}")
print(f"Spent: ${finance['budget']['spent']:,.2f}")
print(f"Burn rate: ${finance['budget']['burn_rate_per_day']:,.2f}/day")
```

### Persistence

```python
# Persistence is enabled by default
# Data saved to ~/.agentprojectbox/

# Create project (auto-saved)
project, _ = orch.create_project(title="Test", request_text="Build something")

# New session - projects persist
orch2 = Orchestrator()
projects = orch2.list_projects()  # All previous projects loaded

# Backup
orch.backup("/path/to/backup.json")

# Restore
counts = orch.restore("/path/to/backup.json")
print(f"Restored {counts['projects']} projects, {counts['agents']} agents")
```

### Swarm Mode (Multi-Project)

```python
# Enable swarm mode for cross-project coordination
orch = Orchestrator(swarm_mode=True)

# Create multiple projects
project1, _ = orch.create_project(title="Project A", request_text="...")
project2, _ = orch.create_project(title="Project B", request_text="...")

# Join swarm - agents coordinate across projects
orch.join_swarm([project1.id, project2.id])

# Resources allocated with global optimization
orch.allocate_task_resources(project1.id)
orch.allocate_task_resources(project2.id)
```

## CLI Reference

```bash
# Project Management
agentproject project create "Title" -r "Natural language request" --budget 10000
agentproject project list [--status active|completed]
agentproject project show <project-id>
agentproject project delete <project-id>

# Task Management
agentproject task add <project-id> "Task title" --priority HIGH --hours 8
agentproject task list <project-id> [--status pending|in-progress]
agentproject task update <project-id> <task-id> completed

# Agent Management
agentproject agent register "Agent-Name" -c code_generation -c testing
agentproject agent list
agentproject agent join <agent-id> <project-id>
agentproject agent claim <agent-id> <project-id> <task-id>

# Resource Allocation
agentproject resource allocate <project-id> [--task <task-id>]
agentproject resource swarm <project-id-1> <project-id-2> ...

# Monitoring
agentproject monitor analyze <project-id>
agentproject monitor forecast <project-id>
agentproject monitor alerts [--project <project-id>]

# Finance
agentproject finance budget <project-id> <amount>
agentproject finance set-rate <agent-id> 75
agentproject finance show <project-id>

# Export
agentproject export json <project-id> [--full]
agentproject export report <project-id>
agentproject export compliance <project-id>

# System
agentproject status
agentproject config
```

## API Server

### Starting the Server

```bash
# Simple way
python server.py

# With uvicorn
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/projects` | Create project |
| GET | `/projects` | List projects |
| GET | `/projects/{id}` | Get project details |
| DELETE | `/projects/{id}` | Delete project |
| POST | `/projects/{id}/tasks` | Add task |
| GET | `/projects/{id}/tasks` | List tasks |
| POST | `/agents` | Register agent |
| GET | `/agents` | List agents |
| POST | `/projects/{id}/allocate` | Allocate resources |
| GET | `/projects/{id}/monitor` | Monitor project |
| GET | `/projects/{id}/forecast` | Get forecast |
| GET | `/alerts` | Get alerts |
| POST | `/projects/{id}/budget` | Set budget |
| GET | `/projects/{id}/export` | Export project |
| GET | `/health` | Health check |

### Example API Calls

```bash
# Create project
curl -X POST http://localhost:8000/projects \
  -H "Content-Type: application/json" \
  -d '{"title": "My Project", "request_text": "Build a website"}'

# Monitor project
curl http://localhost:8000/projects/{project_id}/monitor

# Allocate resources
curl -X POST http://localhost:8000/projects/{project_id}/allocate

# View API docs
open http://localhost:8000/docs
```

## Features

### Core Capabilities

| Feature | Description |
|---------|-------------|
| **NLP Intake** | Parse natural language into structured project data |
| **Task Graph Engine** | DAG-based dependencies with cycle detection |
| **Monte Carlo Simulation** | 1000+ iterations for timeline forecasting |
| **Skill-Based Allocation** | Auto-assign tasks based on agent capabilities |
| **Swarm Mode** | Cross-project resource coordination |
| **Budget Tracking** | Invisible burn rate analysis |
| **Compliance** | RBAC and tamper-evident audit trails |
| **Agent Collaboration** | Negotiation and arbitration APIs |

### Supported Project Types

Auto-detects and generates tasks for:
- **Web Applications** - Full-stack, SaaS, platforms
- **Mobile Apps** - iOS, Android, React Native, Flutter
- **API Services** - REST, GraphQL, microservices
- **Data Pipelines** - ETL, streaming, batch processing
- **ML Projects** - Model training, deployment, monitoring

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `APB_ENV` | Environment (development/production) | development |
| `APB_DEBUG` | Enable debug mode | false |
| `APB_API_HOST` | API server host | 0.0.0.0 |
| `APB_API_PORT` | API server port | 8000 |
| `APB_SECRET_KEY` | JWT secret key | (generated) |
| `APB_SLACK_WEBHOOK` | Slack webhook URL | - |
| `APB_SWARM_MODE` | Enable swarm mode | false |
| `APB_AUTO_ALLOCATE` | Enable auto allocation | false |

### Data Storage

- **Default location**: `~/.agentprojectbox/`
- **Files**: `projects.json`, `agents.json`, `audit.json`
- **Custom location**: `Orchestrator(data_dir="/path/to/data")`

## Architecture

```
AgentProjectBox/
├── intake/          # NLP parsing + schema enforcement
├── graph/           # DAG builder + knowledge graph + templates
├── monitor/         # SLA + risk tracking + Monte Carlo
├── resources/       # Adaptive allocation + swarm mode
├── finance/         # Invisible budget tracking
├── compliance/      # Audit logs + RBAC
├── collab/          # Agent APIs + negotiation
├── outputs/         # JSON, CLI, Slack
├── shared/          # Models, utils, config, persistence
└── examples/        # Workflow examples
```

## FAQ

### Q: Do I need this for a single agent?

**A**: No. If you're using one agent in one session, it can plan internally. AgentProjectBox is for **multiple agents** or **long-running projects**.

### Q: Can existing agents like Claude Code use this?

**A**: Yes! They can:
- Import the module directly (local mode)
- Call the API server (cloud mode)
- Use the CLI (any environment)

### Q: Do I need to create separate agents?

**A**: No. Your existing AI assistant can use it directly. Separate agents are only needed for:
- 24/7 background workers
- Persistent identities across sessions
- Specialized roles (testing, deployment, etc.)

### Q: How does persistence work?

**A**: Projects and agents are automatically saved to JSON files. New sessions automatically load existing data.

### Q: Can I deploy this to the cloud?

**A**: Yes! Run `python server.py` on any server and access via API from anywhere.

## License

MIT
