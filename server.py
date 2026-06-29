"""FastAPI server for AgentProjectBox - enables cloud access and multi-agent collaboration."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from agentprojectbox import Orchestrator
from shared.models import ProjectStatus, TaskStatus, Priority, AgentCapability


# -----------------------------------------------------------------------------
# Pydantic Models for API
# -----------------------------------------------------------------------------

class ProjectCreateRequest(BaseModel):
    title: str
    request_text: str | None = None
    description: str | None = None
    objectives: list[str] | None = None
    due_date: str | None = None
    budget: float | None = None


class TaskCreateRequest(BaseModel):
    title: str
    depends_on: list[str] = []
    estimated_hours: float = 8.0
    priority: str = "MEDIUM"


class AgentRegisterRequest(BaseModel):
    name: str
    capabilities: list[str] = []
    max_concurrent_tasks: int = 5
    available_hours_per_day: float = 8.0


class TaskUpdateRequest(BaseModel):
    status: str
    actual_hours: float | None = None


class BudgetUpdateRequest(BaseModel):
    amount: float


class AgentRateRequest(BaseModel):
    rate_per_hour: float


# -----------------------------------------------------------------------------
# Application
# -----------------------------------------------------------------------------

orchestrator: Orchestrator | None = None


def get_orchestrator() -> Orchestrator:
    """Get or create the global orchestrator instance."""
    global orchestrator
    if orchestrator is None:
        orchestrator = Orchestrator(swarm_mode=False, persist=True)
    return orchestrator


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    global orchestrator
    orchestrator = Orchestrator(swarm_mode=False, persist=True)
    yield
    # Shutdown
    orchestrator = None


app = FastAPI(
    title="AgentProjectBox API",
    description="Headless project management for AI agents",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for browser access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------------------------------------------------------
# Project Endpoints
# -----------------------------------------------------------------------------

@app.post("/projects", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_project(request: ProjectCreateRequest):
    """Create a new project."""
    orch = get_orchestrator()
    
    kwargs = {}
    if request.due_date:
        try:
            kwargs['due_date'] = datetime.fromisoformat(request.due_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format")
    
    project, context = orch.create_project(
        title=request.title,
        request_text=request.request_text,
        objectives=request.objectives,
        description=request.description,
        **kwargs
    )
    
    if project is None:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "needs_clarification",
                "questions": context.get('questions', []),
            }
        )
    
    if request.budget:
        orch.set_project_budget(project.id, request.budget)
    
    return {
        "status": "created",
        "project": project.model_dump(),
        "context": context,
    }


@app.get("/projects")
async def list_projects(status: str | None = None):
    """List all projects."""
    orch = get_orchestrator()
    projects = orch.list_projects(status=status)
    return {"projects": [p.model_dump() for p in projects]}


@app.get("/projects/{project_id}")
async def get_project(project_id: str):
    """Get project details."""
    orch = get_orchestrator()
    project = orch.get_project(project_id)
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    return {"project": project.model_dump()}


@app.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    """Delete a project."""
    orch = get_orchestrator()
    
    if project_id not in orch.projects:
        raise HTTPException(status_code=404, detail="Project not found")
    
    del orch.projects[project_id]
    if orch.persist:
        orch.persistence.delete_project(project_id)
    
    return {"status": "deleted"}


# -----------------------------------------------------------------------------
# Task Endpoints
# -----------------------------------------------------------------------------

@app.post("/projects/{project_id}/tasks", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_task(project_id: str, request: TaskCreateRequest):
    """Add a task to a project."""
    orch = get_orchestrator()
    
    try:
        task = orch.add_task(
            project_id=project_id,
            title=request.title,
            depends_on=request.depends_on,
            estimated_hours=request.estimated_hours,
            priority=request.priority,
        )
        
        return {"status": "created", "task": task.model_dump()}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/projects/{project_id}/tasks")
async def list_tasks(project_id: str, status: str | None = None):
    """List tasks in a project."""
    orch = get_orchestrator()
    project = orch.get_project(project_id)
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    tasks = project.tasks
    if status:
        tasks = [t for t in tasks if t.status.value == status]
    
    return {"tasks": [t.model_dump() for t in tasks]}


@app.patch("/tasks/{task_id}")
async def update_task(task_id: str, request: TaskUpdateRequest):
    """Update a task."""
    # Note: This requires project_id, simplified for demo
    raise HTTPException(status_code=501, detail="Not implemented - use /projects/{id}/tasks/{task_id}")


# -----------------------------------------------------------------------------
# Agent Endpoints
# -----------------------------------------------------------------------------

@app.post("/agents", response_model=dict, status_code=status.HTTP_201_CREATED)
async def register_agent(request: AgentRegisterRequest):
    """Register a new agent."""
    orch = get_orchestrator()
    
    agent = orch.register_agent(
        name=request.name,
        capabilities=request.capabilities,
        max_concurrent_tasks=request.max_concurrent_tasks,
        available_hours_per_day=request.available_hours_per_day,
    )
    
    return {"status": "registered", "agent": agent.model_dump()}


@app.get("/agents")
async def list_agents():
    """List all agents."""
    orch = get_orchestrator()
    return {"agents": {id: a.model_dump() for id, a in orch.agents.items()}}


@app.post("/agents/{agent_id}/rate")
async def set_agent_rate(agent_id: str, request: AgentRateRequest):
    """Set agent hourly rate."""
    orch = get_orchestrator()
    
    try:
        orch.set_agent_rate(agent_id, request.rate_per_hour)
        return {"status": "updated"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# -----------------------------------------------------------------------------
# Resource Allocation Endpoints
# -----------------------------------------------------------------------------

@app.post("/projects/{project_id}/allocate")
async def allocate_resources(project_id: str, task_id: str | None = None):
    """Allocate resources for a project or specific task."""
    orch = get_orchestrator()
    
    try:
        recommendations = orch.allocate_task_resources(project_id, task_id)
        return {
            "status": "allocated",
            "recommendations": [r.model_dump() if hasattr(r, 'model_dump') else r for r in recommendations]
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# -----------------------------------------------------------------------------
# Monitoring Endpoints
# -----------------------------------------------------------------------------

@app.get("/projects/{project_id}/monitor")
async def monitor_project(project_id: str):
    """Run full monitoring analysis."""
    orch = get_orchestrator()
    
    try:
        analysis = orch.monitor_project(project_id)
        return analysis
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/projects/{project_id}/forecast")
async def get_forecast(project_id: str):
    """Get project forecast."""
    orch = get_orchestrator()
    
    try:
        forecast = orch.forecast(project_id)
        return forecast
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/alerts")
async def get_alerts(project_id: str | None = None):
    """Get active alerts."""
    orch = get_orchestrator()
    alerts = orch.check_alerts(project_id=project_id)
    return {"alerts": [a.model_dump() for a in alerts]}


# -----------------------------------------------------------------------------
# Finance Endpoints
# -----------------------------------------------------------------------------

@app.post("/projects/{project_id}/budget")
async def set_budget(project_id: str, request: BudgetUpdateRequest):
    """Set project budget."""
    orch = get_orchestrator()
    
    try:
        orch.set_project_budget(project_id, request.amount)
        return {"status": "updated"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/projects/{project_id}/finance")
async def get_finance(project_id: str):
    """Get project finance data."""
    orch = get_orchestrator()
    return orch.get_project_finance(project_id)


# -----------------------------------------------------------------------------
# Export Endpoints
# -----------------------------------------------------------------------------

@app.get("/projects/{project_id}/export")
async def export_project(project_id: str, full: bool = False):
    """Export project as JSON."""
    orch = get_orchestrator()
    
    try:
        if full:
            report = orch.export_full_report(project_id)
            return report
        else:
            data = orch.output.export_project_json(
                orch.get_project(project_id),
                include_full_data=False,
            )
            return data
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/projects/{project_id}/compliance")
async def export_compliance(project_id: str):
    """Export compliance report."""
    orch = get_orchestrator()
    report = orch.generate_compliance_report(project_id)
    return report


# -----------------------------------------------------------------------------
# System Endpoints
# -----------------------------------------------------------------------------

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    orch = get_orchestrator()
    return orch.get_health_summary()


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "AgentProjectBox API",
        "version": "1.0.0",
        "docs": "/docs",
    }


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
