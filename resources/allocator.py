"""Adaptive Resource Allocation: Auto-assign tasks with swarm mode support."""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from shared.models import (
    Task, TaskStatus, Agent, Project, ResourceAllocation, 
    AgentCapability, Priority, ProjectStatus
)
from shared.utils import timestamp_now, generate_id


@dataclass
class WorkloadSnapshot:
    """Snapshot of current agent workloads."""
    agent_id: str
    current_tasks: int
    capacity_used: float  # 0-1
    current_utilization: float  # hours per day currently committed
    availability_score: float  # 0-1, higher is more available


@dataclass
class AssignmentRecommendation:
    """Recommendation for task assignment."""
    task_id: str
    recommended_agents: list[tuple[str, float]]  # (agent_id, score)
    reason: str
    confidence: float
    alternatives: list[str]
    estimated_completion: datetime | None = None


@dataclass
class SwarmCoordination:
    """Cross-project coordination data."""
    swarm_id: str
    participating_projects: list[str]
    shared_agents: list[str]
    coordination_rules: dict[str, Any]
    active_conflicts: list[dict] = field(default_factory=list)


class SkillMatcher:
    """Match tasks to agents based on skills."""
    
    CAPABILITY_SYNERGIES = {
        AgentCapability.CODE_GENERATION: [AgentCapability.CODE_REVIEW, AgentCapability.TESTING],
        AgentCapability.ANALYSIS: [AgentCapability.NLP, AgentCapability.PROJECT_MANAGEMENT],
        AgentCapability.INFRASTRUCTURE: [AgentCapability.DEVOPS, AgentCapability.SECURITY],
    }
    
    def __init__(self):
        self.skill_weights: dict[AgentCapability, float] = {}
    
    def calculate_match_score(
        self,
        task: Task,
        agent: Agent,
        project: Project | None = None,
    ) -> float:
        """Calculate how well an agent matches a task."""
        scores = []
        
        # Primary skill matching
        if task.required_capabilities:
            skill_score = agent.skill_match_score(task.required_capabilities)
            scores.append(skill_score * 0.5)  # 50% weight
        else:
            scores.append(0.5)  # neutral if no requirements
        
        # Availability
        if agent.has_capacity():
            availability = 1.0 - (agent.current_task_count / agent.max_concurrent_tasks)
            scores.append(availability * 0.3)  # 30% weight
        else:
            scores.append(0.0)
        
        # Project history
        if project and agent.id in project.team:
            scores.append(0.15)  # 15% weight for existing team member
        else:
            scores.append(0.0)
        
        # Working hours overlap (simplified)
        scores.append(0.05)  # Placeholder for timezone compatibility
        
        return sum(scores)
    
    def find_best_matches(
        self,
        task: Task,
        agents: list[Agent],
        project: Project | None = None,
        top_n: int = 3,
    ) -> list[tuple[Agent, float]]:
        """Find the best agent matches for a task."""
        scored = [
            (agent, self.calculate_match_score(task, agent, project))
            for agent in agents
            if agent.is_active
        ]
        
        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_n]


class AdaptiveAllocator:
    """Adaptive resource allocation engine."""
    
    def __init__(self):
        self.matcher = SkillMatcher()
        self.allocations: dict[str, ResourceAllocation] = {}
        self.workload_history: list[WorkloadSnapshot] = []
    
    def allocate_task(
        self,
        task: Task,
        available_agents: list[Agent],
        project: Project,
        force: bool = False,
    ) -> AssignmentRecommendation | None:
        """
        Allocate a task to the best available agent.
        
        Args:
            task: Task to allocate
            available_agents: Pool of available agents
            project: Parent project
            force: If True, allocate even if no perfect match
        
        Returns:
            Assignment recommendation or None if allocation failed
        """
        # Check if task already assigned
        existing = self._get_allocation_for_task(task.id)
        if existing:
            return AssignmentRecommendation(
                task_id=task.id,
                recommended_agents=[(existing.agent_id, 1.0)],
                reason="Task already allocated",
                confidence=1.0,
                alternatives=[],
            )
        
        # Find matches
        matches = self.matcher.find_best_matches(task, available_agents, project, top_n=5)
        
        # Filter to only available agents
        available_matches = [(agent, score) for agent, score in matches if agent.has_capacity()]
        
        if not available_matches and not force:
            # No available agents
            return AssignmentRecommendation(
                task_id=task.id,
                recommended_agents=[],
                reason="No agents with available capacity",
                confidence=0.0,
                alternatives=[agent.id for agent, _ in matches],
            )
        
        # Use best available, or best overall if forced
        selected = available_matches[0] if available_matches else matches[0]
        agent, score = selected
        
        # Create allocation
        allocation = ResourceAllocation(
            task_id=task.id,
            agent_id=agent.id,
            allocated_by="adaptive_allocator",
            confidence=score,
            reason=f"Best skill match with {score:.2f} confidence",
        )
        
        self.allocations[allocation.id] = allocation
        
        # Update agent state
        agent.current_task_count += 1
        agent.assigned_tasks.append(task.id)
        
        # Update task
        task.assigned_to.append(agent.id)
        task.scheduled_start = timestamp_now()
        task.status = TaskStatus.PENDING
        
        # Calculate estimated completion
        estimated_completion = timestamp_now() + timedelta(hours=task.estimated_hours / 8)
        
        return AssignmentRecommendation(
            task_id=task.id,
            recommended_agents=[(agent.id, score)],
            reason=f"Matched {agent.name} based on skills",
            confidence=score,
            alternatives=[a.id for a, _ in available_matches[1:3]],
            estimated_completion=estimated_completion,
        )
    
    def reallocate_task(
        self,
        task: Task,
        reason: str,
        available_agents: list[Agent],
    ) -> AssignmentRecommendation | None:
        """
        Reallocate a task when there's a deadline slip or change.
        
        Args:
            task: Task to reallocate
            reason: Reason for reallocation
            available_agents: Pool of available agents
        
        Returns:
            New assignment recommendation or None
        """
        # Remove current allocation
        current_allocation = self._get_allocation_for_task(task.id)
        if current_allocation:
            del self.allocations[current_allocation.id]
            
            # Update previous agent
            for agent in available_agents:
                if agent.id == current_allocation.agent_id:
                    agent.current_task_count -= 1
                    if task.id in agent.assigned_tasks:
                        agent.assigned_tasks.remove(task.id)
        
        # Clear current assignment
        task.assigned_to = []
        task.status = TaskStatus.PENDING
        
        # Find best agent (prioritize speed over cost due to deadline slip)
        matches = self.matcher.find_best_matches(task, available_agents, top_n=5)
        
        # Prioritize agents with most availability
        def speed_priority(agent_score):
            agent, score = agent_score
            return (
                agent.max_concurrent_tasks - agent.current_task_count,
                score
            )
        
        matches.sort(key=speed_priority, reverse=True)
        
        if not matches:
            return None
        
        agent, score = matches[0]
        
        # Create new allocation
        allocation = ResourceAllocation(
            task_id=task.id,
            agent_id=agent.id,
            allocated_by="adaptive_allocator_reallocation",
            confidence=score * 0.9,  # Slightly lower confidence due to reallocation
            reason=f"Reallocated: {reason}",
        )
        
        self.allocations[allocation.id] = allocation
        
        # Update state
        agent.current_task_count += 1
        agent.assigned_tasks.append(task.id)
        task.assigned_to.append(agent.id)
        
        return AssignmentRecommendation(
            task_id=task.id,
            recommended_agents=[(agent.id, score)],
            reason=f"Reallocated: {reason}",
            confidence=score * 0.9,
            alternatives=[a.id for a, _ in matches[1:3]],
        )
    
    def check_for_deadline_slippage(
        self,
        project: Project,
        agents: list[Agent],
        threshold_hours: float = 24.0,
    ) -> list[AssignmentRecommendation]:
        """Check for tasks at risk of missing deadlines and reallocate if needed."""
        at_risk_tasks = []
        now = timestamp_now()
        
        for task in project.tasks:
            if task.status != TaskStatus.IN_PROGRESS:
                continue
            
            if task.scheduled_end:
                hours_remaining = (task.scheduled_end - now).total_seconds() / 3600
                hours_needed = task.estimated_hours - task.actual_hours
                
                if hours_needed > hours_remaining + threshold_hours:
                    # Task is at risk
                    rec = self.reallocate_task(
                        task,
                        reason=f"Deadline slippage detected: {hours_needed}h needed, {hours_remaining}h remaining",
                        available_agents=agents,
                    )
                    if rec:
                        at_risk_tasks.append(rec)
        
        return at_risk_tasks
    
    def get_workload_distribution(self, agents: list[Agent]) -> dict[str, Any]:
        """Get current workload distribution across agents."""
        distribution = {
            "agents": [],
            "total_tasks": 0,
            "avg_utilization": 0.0,
            "bottlenecks": [],
            "underutilized": [],
        }
        
        total_util = 0.0
        
        for agent in agents:
            util = agent.current_task_count / agent.max_concurrent_tasks
            total_util += util
            
            agent_data = {
                "id": agent.id,
                "name": agent.name,
                "utilization": util,
                "tasks": len(agent.assigned_tasks),
                "capacity": agent.max_concurrent_tasks,
            }
            distribution["agents"].append(agent_data)
            
            if util >= 1.0:
                distribution["bottlenecks"].append(agent.id)
            elif util < 0.3:
                distribution["underutilized"].append(agent.id)
        
        distribution["total_tasks"] = sum(len(a.assigned_tasks) for a in agents)
        distribution["avg_utilization"] = total_util / len(agents) if agents else 0.0
        
        return distribution
    
    def balance_workload(
        self,
        agents: list[Agent],
        threshold: float = 0.3,
    ) -> list[AssignmentRecommendation]:
        """Redistribute work to balance agent workloads."""
        recommendations = []
        
        distribution = self.get_workload_distribution(agents)
        
        while distribution["bottlenecks"] and distribution["underutilized"]:
            # Find most overloaded agent
            bottleneck_id = distribution["bottlenecks"][0]
            bottleneck_agent = next((a for a in agents if a.id == bottleneck_id), None)
            
            if not bottleneck_agent or not bottleneck_agent.assigned_tasks:
                break
            
            # Find a task to move
            task_id = bottleneck_agent.assigned_tasks[-1]  # Simple: take last task
            
            # Find underutilized agent who can take it
            for under_id in distribution["underutilized"]:
                under_agent = next((a for a in agents if a.id == under_id), None)
                if under_agent and under_agent.has_capacity():
                    # Find task object (would look up in real implementation)
                    task = Task(title="Pending task", estimated_hours=8)  # Placeholder
                    task.id = task_id
                    
                    rec = self.reallocate_task(
                        task,
                        reason="Workload rebalancing",
                        available_agents=[under_agent],
                    )
                    if rec:
                        recommendations.append(rec)
                    break
            
            # Recalculate distribution
            distribution = self.get_workload_distribution(agents)
        
        return recommendations
    
    def _get_allocation_for_task(self, task_id: str) -> ResourceAllocation | None:
        """Get existing allocation for a task."""
        for allocation in self.allocations.values():
            if allocation.task_id == task_id:
                return allocation
        return None


class SwarmCoordinator:
    """Coordinate resources across multiple projects (swarm mode)."""
    
    def __init__(self):
        self.active_swarm: SwarmCoordination | None = None
        self.project_allocators: dict[str, AdaptiveAllocator] = {}
        self.swarm_agents: list[Agent] = []
    
    def initialize_swarm(
        self,
        project_ids: list[str],
        shared_agent_pool: list[Agent],
        coordination_rules: dict[str, Any] | None = None,
    ) -> SwarmCoordination:
        """Initialize swarm mode for cross-project coordination."""
        self.active_swarm = SwarmCoordination(
            swarm_id=generate_id(),
            participating_projects=project_ids,
            shared_agents=[a.id for a in shared_agent_pool],
            coordination_rules=coordination_rules or self._default_rules(),
        )
        self.swarm_agents = shared_agent_pool
        
        return self.active_swarm
    
    def _default_rules(self) -> dict[str, Any]:
        """Default swarm coordination rules."""
        return {
            "priority_weights": {
                "critical": 10.0,
                "high": 5.0,
                "medium": 2.0,
                "low": 1.0,
            },
            "max_tasks_per_agent": 5,
            "rebalancing_threshold": 0.3,
            "conflict_resolution": "priority_then_fairness",  # strategy
        }
    
    def optimize_swarm_allocation(
        self,
        projects: list[Project],
    ) -> dict[str, list[AssignmentRecommendation]]:
        """
        Optimize task allocation across all projects in the swarm.
        
        Returns:
            Dict mapping project_id to list of recommendations
        """
        if not self.active_swarm:
            raise ValueError("Swarm not initialized")
        
        # Collect all pending tasks across projects
        all_tasks: list[tuple[Task, Project]] = []
        for project in projects:
            for task in project.tasks:
                if task.status == TaskStatus.PENDING and not task.assigned_to:
                    all_tasks.append((task, project))
        
        # Sort by priority
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        all_tasks.sort(
            key=lambda x: priority_order.get(x[0].priority.name, 99)
        )
        
        # Track agent availability
        agent_capacity = {
            agent.id: agent.max_concurrent_tasks - agent.current_task_count
            for agent in self.swarm_agents
        }
        
        recommendations: dict[str, list[AssignmentRecommendation]] = {
            p.id: [] for p in projects
        }
        
        # Allocate tasks greedily by priority
        allocator = AdaptiveAllocator()
        
        for task, project in all_tasks:
            available = [a for a in self.swarm_agents if agent_capacity.get(a.id, 0) > 0]
            
            if not available:
                # No capacity available
                continue
            
            rec = allocator.allocate_task(task, available, project)
            if rec:
                recommendations[project.id].append(rec)
                # Update capacity tracking
                if rec.recommended_agents:
                    agent_id = rec.recommended_agents[0][0]
                    agent_capacity[agent_id] -= 1
        
        return recommendations
    
    def resolve_conflict(
        self,
        task_a: Task,
        project_a: Project,
        task_b: Task,
        project_b: Project,
        competing_agents: list[Agent],
    ) -> dict[str, Any]:
        """
        Resolve resource conflicts between projects.
        
        Returns:
            Resolution decision with reasoning
        """
        rules = self.active_swarm.coordination_rules if self.active_swarm else {}
        strategy = rules.get("conflict_resolution", "priority_then_fairness")
        
        if strategy == "priority_then_fairness":
            # Compare priorities
            priority_weights = rules.get("priority_weights", {})
            score_a = priority_weights.get(task_a.priority.name.lower(), 1)
            score_b = priority_weights.get(task_b.priority.name.lower(), 1)
            
            # Add fairness factor (projects with fewer allocations get boost)
            allocations_a = sum(1 for t in project_a.tasks if t.assigned_to)
            allocations_b = sum(1 for t in project_b.tasks if t.assigned_to)
            
            score_a *= (1 + 1 / (allocations_a + 1))
            score_b *= (1 + 1 / (allocations_b + 1))
            
            winner = project_a if score_a > score_b else project_b
            winner_task = task_a if winner == project_a else task_b
            
            return {
                "winner_project_id": winner.id,
                "winner_task_id": winner_task.id,
                "reason": f"Priority score: {max(score_a, score_b):.2f} vs {min(score_a, score_b):.2f}",
                "strategy": strategy,
            }
        
        return {
            "winner_project_id": project_a.id,
            "winner_task_id": task_a.id,
            "reason": "Default resolution",
            "strategy": "default",
        }
    
    def get_swarm_status(self) -> dict[str, Any]:
        """Get overall swarm status."""
        if not self.active_swarm:
            return {"status": "inactive"}
        
        return {
            "status": "active",
            "swarm_id": self.active_swarm.swarm_id,
            "projects": len(self.active_swarm.participating_projects),
            "shared_agents": len(self.active_swarm.shared_agents),
            "active_conflicts": len(self.active_swarm.active_conflicts),
            "agent_utilization": self._calculate_swarm_utilization(),
        }
    
    def _calculate_swarm_utilization(self) -> dict[str, Any]:
        """Calculate utilization across swarm."""
        if not self.swarm_agents:
            return {}
        
        total_capacity = sum(a.max_concurrent_tasks for a in self.swarm_agents)
        total_used = sum(a.current_task_count for a in self.swarm_agents)
        
        return {
            "total_agents": len(self.swarm_agents),
            "total_capacity": total_capacity,
            "tasks_allocated": total_used,
            "utilization_rate": total_used / total_capacity if total_capacity > 0 else 0,
            "available_capacity": total_capacity - total_used,
        }


class ResourceAllocator:
    """Main entry point for resource allocation."""
    
    def __init__(self, swarm_mode: bool = False):
        self.allocator = AdaptiveAllocator()
        self.swarm: SwarmCoordinator | None = SwarmCoordinator() if swarm_mode else None
    
    def enable_swarm_mode(
        self,
        project_ids: list[str],
        agent_pool: list[Agent],
    ) -> None:
        """Enable swarm mode for cross-project coordination."""
        self.swarm = SwarmCoordinator()
        self.swarm.initialize_swarm(project_ids, agent_pool)
    
    def allocate_task(
        self,
        task: Task,
        agents: list[Agent],
        project: Project,
    ) -> AssignmentRecommendation | None:
        """Allocate a task to an agent."""
        return self.allocator.allocate_task(task, agents, project)
    
    def allocate_project_tasks(
        self,
        project: Project,
        agents: list[Agent],
    ) -> list[AssignmentRecommendation]:
        """Allocate all pending tasks in a project."""
        recommendations = []
        
        pending_tasks = [t for t in project.tasks if not t.assigned_to]
        
        for task in pending_tasks:
            rec = self.allocator.allocate_task(task, agents, project)
            if rec:
                recommendations.append(rec)
        
        return recommendations
