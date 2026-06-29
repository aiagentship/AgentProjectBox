"""Pydantic models for AgentProjectBox data structures."""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict

from uuid6 import uuid7


def generate_id() -> str:
    """Generate a new UUID7 as a string."""
    return str(uuid7())


def timestamp_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.utcnow()


class ProjectStatus(str, Enum):
    """Project life-cycle states."""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskStatus(str, Enum):
    """Task life-cycle states."""
    PENDING = "pending"
    BLOCKED = "blocked"
    IN_PROGRESS = "in-progress"
    REVIEW = "review"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Priority(int, Enum):
    """Task/Project priority levels."""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4
    TRIVIAL = 5


class AgentCapability(str, Enum):
    """Agent skill types for matching."""
    NLP = "nlp"
    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    TESTING = "testing"
    INFRASTRUCTURE = "infrastructure"
    DESIGN = "design"
    WRITING = "writing"
    ANALYSIS = "analysis"
    PROJECT_MANAGEMENT = "project_management"
    SECURITY = "security"
    COMPLIANCE = "compliance"


class ValidationResult(BaseModel):
    """Result of validation checks."""
    model_config = ConfigDict(frozen=True)
    
    is_valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    
    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0


class Timeline(BaseModel):
    """Timeline constraints and forecasts."""
    model_config = ConfigDict(json_encoders={timedelta: lambda v: v.total_seconds() / 86400})
    
    start_date: datetime
    due_date: datetime
    estimated_duration: timedelta = Field(default_factory=lambda: timedelta(days=14))
    buffer_days: int = 3
    
    # Forecast fields (populated by Monte Carlo)
    on_time_probability: float = Field(ge=0.0, le=1.0, default=0.5)
    expected_completion: datetime | None = None
    risk_factors: list[str] = Field(default_factory=list)


class Risk(BaseModel):
    """Risk assessment and tracking."""
    model_config = ConfigDict(frozen=True)
    
    id: str = Field(default_factory=generate_id)
    category: str  # e.g., "technical", "resource", "timeline", "financial"
    description: str
    probability: float = Field(ge=0.0, le=1.0)
    impact: float = Field(ge=0.0, le=1.0)  # 0-1 severity
    mitigation: str = ""
    owner: str = ""  # Agent or human responsible
    status: str = "open"  # open, mitigated, accepted, closed
    detected_at: datetime = Field(default_factory=timestamp_now)
    resolved_at: datetime | None = None
    
    @property
    def risk_score(self) -> float:
        return self.probability * self.impact


class Task(BaseModel):
    """A unit of work in the project."""
    model_config = ConfigDict(frozen=False)
    
    id: str = Field(default_factory=generate_id)
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    priority: Priority = Priority.MEDIUM
    
    # Dependencies
    depends_on: list[str] = Field(default_factory=list)
    blocks: list[str] = Field(default_factory=list)
    
    # Assignment
    assigned_to: list[str] = Field(default_factory=list)  # Agent IDs
    required_capabilities: list[AgentCapability] = Field(default_factory=list)
    
    # Estimation
    estimated_hours: float = Field(ge=0.0, default=8.0)
    actual_hours: float = Field(ge=0.0, default=0.0)
    
    # Timeline
    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None
    actual_start: datetime | None = None
    actual_end: datetime | None = None
    
    # Metadata
    created_at: datetime = Field(default_factory=timestamp_now)
    updated_at: datetime = Field(default_factory=timestamp_now)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    
    def is_blocked(self, task_map: dict[str, Task]) -> bool:
        """Check if task is blocked by incomplete dependencies."""
        return any(
            task_map[dep_id].status != TaskStatus.COMPLETED
            for dep_id in self.depends_on
            if dep_id in task_map
        )
    
    def can_parallelize_with(self, other: Task) -> bool:
        """Check if this task can run parallel to another."""
        return (
            self.id not in other.depends_on
            and other.id not in self.depends_on
            and self.id not in other.blocks
            and other.id not in self.blocks
        )


class Agent(BaseModel):
    """An agent that can be assigned work."""
    model_config = ConfigDict(frozen=False)
    
    id: str = Field(default_factory=generate_id)
    name: str
    type: str = "ai"  # ai, human, hybrid
    capabilities: list[AgentCapability] = Field(default_factory=list)
    
    # Availability
    max_concurrent_tasks: int = Field(ge=1, default=5)
    current_task_count: int = Field(ge=0, default=0)
    available_hours_per_day: float = Field(ge=0.0, default=8.0)
    timezone: str = "UTC"
    working_hours: tuple[int, int] = (9, 17)  # Start and end hour
    
    # Load tracking
    assigned_tasks: list[str] = Field(default_factory=list)
    current_projects: list[str] = Field(default_factory=list)
    
    # Skills proficiency (capability -> 0-1 score)
    skill_levels: dict[AgentCapability, float] = Field(default_factory=dict)
    
    # Metadata
    created_at: datetime = Field(default_factory=timestamp_now)
    is_active: bool = True
    
    def has_capacity(self) -> bool:
        return self.current_task_count < self.max_concurrent_tasks
    
    def skill_match_score(self, required: list[AgentCapability]) -> float:
        """Calculate how well this agent matches required capabilities."""
        if not required:
            return 1.0
        
        matches = sum(
            self.skill_levels.get(cap, 0.5) if cap in self.capabilities else 0.0
            for cap in required
        )
        return matches / len(required)


class ResourceAllocation(BaseModel):
    """Resource assignment record."""
    model_config = ConfigDict(frozen=True)
    
    id: str = Field(default_factory=generate_id)
    task_id: str
    agent_id: str
    allocated_at: datetime = Field(default_factory=timestamp_now)
    allocated_by: str = "system"  # system or agent ID
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    reason: str = ""


class Budget(BaseModel):
    """Budget tracking for a project."""
    model_config = ConfigDict(frozen=False)
    
    allocated: float = Field(ge=0.0, default=0.0)
    spent: float = Field(ge=0.0, default=0.0)
    currency: str = "USD"
    
    # Cost tracking
    agent_costs: dict[str, float] = Field(default_factory=dict)  # agent_id -> cost
    infrastructure_costs: float = 0.0
    external_costs: float = 0.0
    
    # Forecast
    projected_total: float | None = None
    burn_rate_per_day: float = 0.0
    
    @property
    def remaining(self) -> float:
        return max(0.0, self.allocated - self.spent)
    
    @property
    def percent_used(self) -> float:
        if self.allocated == 0:
            return 0.0
        return (self.spent / self.allocated) * 100
    
    @property
    def burn_rate_category(self) -> str:
        """Classify burn rate."""
        if self.allocated == 0:
            return "none"
        daily_pct = (self.burn_rate_per_day / self.allocated) * 100
        if daily_pct > 2:
            return "high"
        if daily_pct > 0.5:
            return "moderate"
        return "low"


class AuditEvent(BaseModel):
    """Immutable audit trail entry."""
    model_config = ConfigDict(frozen=True)
    
    id: str = Field(default_factory=generate_id)
    timestamp: datetime = Field(default_factory=timestamp_now)
    event_type: str
    actor: str  # Agent or human ID
    action: str
    resource_type: str  # project, task, agent, etc.
    resource_id: str
    details: dict[str, Any] = Field(default_factory=dict)
    before_state: dict[str, Any] | None = None
    after_state: dict[str, Any] | None = None
    ip_address: str | None = None
    session_id: str | None = None
    signature: str | None = None  # Cryptographic signature for tamper-proofing


class Alert(BaseModel):
    """System alert for human or agent consumption."""
    model_config = ConfigDict(frozen=True)
    
    id: str = Field(default_factory=generate_id)
    severity: str  # info, warning, critical
    category: str  # timeline, budget, risk, resource, compliance
    message: str
    project_id: str | None = None
    task_id: str | None = None
    agent_id: str | None = None
    created_at: datetime = Field(default_factory=timestamp_now)
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None
    auto_resolved: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class Project(BaseModel):
    """Root project object."""
    model_config = ConfigDict(frozen=False)
    
    id: str = Field(default_factory=generate_id)
    title: str
    description: str = ""
    status: ProjectStatus = ProjectStatus.DRAFT
    priority: Priority = Priority.MEDIUM
    
    # Schema fields from intake
    objectives: list[str] = Field(default_factory=list)
    deliverables: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    
    # Nested components
    timeline: Timeline | None = None
    budget: Budget = Field(default_factory=Budget)
    
    # Collections
    tasks: list[Task] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    
    # Agents and resources
    team: list[str] = Field(default_factory=list)  # Agent IDs
    stakeholders: list[str] = Field(default_factory=list)
    
    # Metadata
    created_at: datetime = Field(default_factory=timestamp_now)
    updated_at: datetime = Field(default_factory=timestamp_now)
    created_by: str = "system"
    tags: list[str] = Field(default_factory=list)
    external_refs: dict[str, str] = Field(default_factory=dict)  # CRM, ERP IDs
    
    def get_task_map(self) -> dict[str, Task]:
        """Return a map of task ID to task."""
        return {task.id: task for task in self.tasks}
    
    def get_critical_path(self) -> list[str]:
        """Calculate critical path (placeholder for DAG implementation)."""
        # Returns list of task IDs on the critical path
        return []
    
    def calculate_progress(self) -> float:
        """Calculate overall project completion percentage."""
        if not self.tasks:
            return 0.0
        completed = sum(1 for t in self.tasks if t.status == TaskStatus.COMPLETED)
        return completed / len(self.tasks)
