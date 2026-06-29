"""Collaboration Layer: Agent APIs, negotiation, and arbitration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable

from shared.models import Task, Project, Agent, TaskStatus
from shared.utils import timestamp_now, generate_id


class CollaborationMessageType(str, Enum):
    """Types of collaboration messages."""
    TASK_PROPOSAL = "task_proposal"  # Suggest taking a task
    TASK_CLAIM = "task_claim"  # Claim responsibility for a task
    TASK_DELEGATE = "task_delegate"  # Delegate task to another agent
    TASK_HANDOFF = "task_handoff"  # Hand off partial work
    DEADLINE_NEGOTIATION = "deadline_negotiation"  # Negotiate timeline
    RESOURCE_REQUEST = "resource_request"  # Request resources
    CONFLICT_NOTICE = "conflict_notice"  # Alert about conflict
    ARBITRATION_REQUEST = "arbitration_request"  # Request arbitration
    ARBITRATION_DECISION = "arbitration_decision"  # Arbitration result


class NegotiationStatus(str, Enum):
    """Status of a negotiation."""
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    COUNTERED = "countered"
    EXPIRED = "expired"


@dataclass
class CollaborationMessage:
    """Message between agents."""
    id: str = field(default_factory=generate_id)
    msg_type: CollaborationMessageType = CollaborationMessageType.TASK_PROPOSAL
    
    # Sender/receiver
    from_agent: str = ""
    to_agent: str | None = None  # None = broadcast
    
    # Content
    subject_id: str = ""  # Task, resource, or project ID
    subject_type: str = "task"
    content: dict[str, Any] = field(default_factory=dict)
    
    # Negotiation
    proposal: dict[str, Any] = field(default_factory=dict)
    deadline: datetime | None = None
    
    # Metadata
    sent_at: datetime = field(default_factory=timestamp_now)
    expires_at: datetime | None = None
    priority: int = 5  # 1-10, lower is higher priority
    thread_id: str | None = None
    
    # Response tracking
    response_to: str | None = None  # ID of message this responds to
    status: NegotiationStatus = NegotiationStatus.PENDING


@dataclass
class NegotiationSession:
    """A negotiation between agents."""
    id: str = field(default_factory=generate_id)
    session_type: str = ""  # task_ownership, deadline, resource
    
    # Participants
    initiator: str = ""  # Agent ID
    participants: list[str] = field(default_factory=list)
    
    # Subject
    subject_id: str = ""
    subject_type: str = ""
    
    # Negotiation state
    current_proposal: dict[str, Any] = field(default_factory=dict)
    proposal_history: list[dict[str, Any]] = field(default_factory=list)
    status: NegotiationStatus = NegotiationStatus.PENDING
    
    # Timeline
    created_at: datetime = field(default_factory=timestamp_now)
    expires_at: datetime | None = None
    resolved_at: datetime | None = None
    
    # Outcome
    winner: str | None = None
    terms: dict[str, Any] = field(default_factory=dict)
    
    def add_proposal(self, proposal: dict[str, Any], from_agent: str) -> None:
        """Add a proposal to the negotiation."""
        self.proposal_history.append({
            "agent": from_agent,
            "proposal": proposal,
            "timestamp": timestamp_now().isoformat(),
        })
        self.current_proposal = proposal


class AgentNegotiator:
    """Facilitate negotiations between agents."""
    
    def __init__(self):
        self.active_negotiations: dict[str, NegotiationSession] = {}
        self.message_history: list[CollaborationMessage] = []
        self.callbacks: dict[str, list[Callable]] = {}
    
    def propose_task_ownership(
        self,
        proposing_agent: Agent,
        task: Task,
        rationale: str,
        estimated_completion: datetime,
        confidence: float = 0.8,
    ) -> CollaborationMessage:
        """Propose taking ownership of a task."""
        message = CollaborationMessage(
            msg_type=CollaborationMessageType.TASK_CLAIM,
            from_agent=proposing_agent.id,
            subject_id=task.id,
            subject_type="task",
            content={
                "rationale": rationale,
                "agent_name": proposing_agent.name,
                "capabilities": [c.value for c in proposing_agent.capabilities],
            },
            proposal={
                "estimated_completion": estimated_completion.isoformat(),
                "confidence": confidence,
                "current_workload": proposing_agent.current_task_count,
            },
            priority=task.priority.value if isinstance(task.priority.value, int) else 3,
        )
        
        self.message_history.append(message)
        return message
    
    def negotiate_deadline(
        self,
        requesting_agent: Agent,
        task: Task,
        requested_deadline: datetime,
        reason: str,
        proposals: list[tuple[datetime, float]] | None = None,  # (date, confidence)
    ) -> NegotiationSession:
        """Initiate deadline negotiation for a task."""
        proposal = {
            "task_id": task.id,
            "task_title": task.title,
            "original_deadline": task.scheduled_end.isoformat() if task.scheduled_end else None,
            "requested_deadline": requested_deadline.isoformat(),
            "reason": reason,
            "options": proposals or [],
        }
        
        session = NegotiationSession(
            session_type="deadline",
            initiator=requesting_agent.id,
            subject_id=task.id,
            subject_type="task",
            current_proposal=proposal,
        )
        
        self.active_negotiations[session.id] = session
        
        # Create message
        message = CollaborationMessage(
            msg_type=CollaborationMessageType.DEADLINE_NEGOTIATION,
            from_agent=requesting_agent.id,
            subject_id=task.id,
            subject_type="task",
            content={"session_id": session.id},
            proposal=proposal,
        )
        self.message_history.append(message)
        
        return session
    
    def respond_to_negotiation(
        self,
        session_id: str,
        responding_agent: Agent,
        accept: bool,
        counter_proposal: dict[str, Any] | None = None,
    ) -> NegotiationSession | None:
        """Respond to a negotiation."""
        session = self.active_negotiations.get(session_id)
        if not session:
            return None
        
        if accept:
            session.status = NegotiationStatus.ACCEPTED
            session.resolved_at = timestamp_now()
            session.winner = session.initiator
        elif counter_proposal:
            session.status = NegotiationStatus.COUNTERED
            session.add_proposal(counter_proposal, responding_agent.id)
        else:
            session.status = NegotiationStatus.REJECTED
            session.resolved_at = timestamp_now()
        
        return session
    
    def request_task_handoff(
        self,
        from_agent: Agent,
        to_agent: Agent,
        task: Task,
        handoff_notes: str,
        completion_percent: float = 0.0,
    ) -> CollaborationMessage:
        """Request to hand off a task to another agent."""
        message = CollaborationMessage(
            msg_type=CollaborationMessageType.TASK_HANDOFF,
            from_agent=from_agent.id,
            to_agent=to_agent.id,
            subject_id=task.id,
            subject_type="task",
            content={
                "handoff_notes": handoff_notes,
                "completion_percent": completion_percent,
                "work_in_progress": task.status.value == "in-progress",
            },
            proposal={
                "accept_required": True,
            },
        )
        
        self.message_history.append(message)
        return message
    
    def get_pending_negotiations(
        self,
        agent_id: str | None = None,
    ) -> list[NegotiationSession]:
        """Get pending negotiations, optionally filtered by agent."""
        pending = [
            s for s in self.active_negotiations.values()
            if s.status == NegotiationStatus.PENDING
        ]
        
        if agent_id:
            pending = [
                s for s in pending
                if agent_id in s.participants or s.initiator == agent_id
            ]
        
        return sorted(pending, key=lambda x: x.created_at, reverse=True)


class ArbitrationEngine:
    """Arbitrate conflicts between agents."""
    
    CONFLICT_STRATEGIES = {
        "priority_highest": "Agent with highest priority claims wins",
        "earliest_claim": "First agent to claim gets the task",
        "skill_match": "Agent with best skill match wins",
        "workload_balance": "Agent with lower workload wins",
        "random": "Random selection among claimants",
    }
    
    def __init__(self):
        self.pending_arbitrations: dict[str, dict] = {}
    
    def register_conflict(
        self,
        conflict_type: str,
        subject_id: str,
        claimant_agents: list[Agent],
        context: dict[str, Any],
    ) -> str:
        """Register a conflict for arbitration."""
        arb_id = generate_id()
        
        self.pending_arbitrations[arb_id] = {
            "id": arb_id,
            "type": conflict_type,
            "subject_id": subject_id,
            "claimants": [a.id for a in claimant_agents],
            "context": context,
            "created_at": timestamp_now().isoformat(),
            "status": "pending",
        }
        
        return arb_id
    
    def arbitrate_task_ownership(
        self,
        task: Task,
        claimants: list[Agent],
        strategy: str = "skill_match",
    ) -> dict[str, Any]:
        """
        Arbitrate task ownership between competing agents.
        
        Returns:
            Decision with reasoning
        """
        if not claimants:
            return {"winner": None, "reason": "No claimants"}
        
        if strategy == "skill_match":
            # Score by skill match
            scored = [
                (agent, agent.skill_match_score(task.required_capabilities))
                for agent in claimants
            ]
            scored.sort(key=lambda x: x[1], reverse=True)
            winner = scored[0][0]
            reason = f"Best skill match: {scored[0][1]:.2f}"
        
        elif strategy == "workload_balance":
            # Agent with lowest current task count
            winner = min(claimants, key=lambda a: a.current_task_count)
            reason = f"Lowest workload: {winner.current_task_count} tasks"
        
        elif strategy == "earliest_claim":
            # First claimant (context should have claim timestamps)
            winner = claimants[0]
            reason = "First to claim"
        
        elif strategy == "random":
            import random
            winner = random.choice(claimants)
            reason = "Random selection"
        
        else:
            # Default to skill match
            winner = claimants[0]
            reason = "Default assignment"
        
        return {
            "winner_id": winner.id,
            "winner_name": winner.name,
            "reason": reason,
            "strategy": strategy,
            "alternatives_considered": [a.id for a in claimants if a.id != winner.id],
        }
    
    def arbitrate_resource_conflict(
        self,
        resource_type: str,
        resource_id: str,
        competing_projects: list[tuple[str, Priority]],  # (project_id, priority)
    ) -> dict[str, Any]:
        """Arbitrate resource conflicts between projects."""
        if not competing_projects:
            return {"winner": None, "reason": "No competing projects"}
        
        # Priority-based arbitration
        sorted_projects = sorted(competing_projects, key=lambda x: x[1].value)
        winner = sorted_projects[0]
        
        return {
            "winner_project_id": winner[0],
            "priority": winner[1].value,
            "reason": f"Highest priority: {winner[1].name}",
            "projects_considered": len(competing_projects),
        }
    
    def arbitrate_deadline_conflict(
        self,
        task: Task,
        proposed_deadline: datetime,
        project_constraints: dict[str, Any],
    ) -> dict[str, Any]:
        """Arbitrate deadline negotiation."""
        # Simple logic: accept if within buffer, reject if beyond
        if project_constraints.get("hard_deadline"):
            hard = project_constraints["hard_deadline"]
            if proposed_deadline > hard:
                return {
                    "approved": False,
                    "reason": f"Proposed deadline {proposed_deadline} exceeds hard deadline {hard}",
                    "counter_offer": hard.isoformat() if isinstance(hard, datetime) else hard,
                }
        
        return {
            "approved": True,
            "reason": "Deadline within acceptable parameters",
            "original_deadline": task.scheduled_end,
            "approved_deadline": proposed_deadline,
        }


class AgentAPI:
    """API for agents to join/leave projects and interact."""
    
    def __init__(self):
        self.registered_agents: dict[str, Agent] = {}
        self.project_memberships: dict[str, set[str]] = {}  # project_id -> set(agent_ids)
        self.negotiator = AgentNegotiator()
        self.arbitrator = ArbitrationEngine()
        self.event_handlers: list[Callable] = []
    
    def register_agent(self, agent: Agent) -> None:
        """Register an agent with the collaboration system."""
        self.registered_agents[agent.id] = agent
    
    def join_project(
        self,
        agent: Agent,
        project: Project,
        role: str = "contributor",
    ) -> dict[str, Any]:
        """Register an agent as joining a project."""
        if project.id not in self.project_memberships:
            self.project_memberships[project.id] = set()
        
        self.project_memberships[project.id].add(agent.id)
        project.team.append(agent.id)
        agent.current_projects.append(project.id)
        
        return {
            "agent_id": agent.id,
            "project_id": project.id,
            "role": role,
            "joined_at": timestamp_now().isoformat(),
        }
    
    def leave_project(
        self,
        agent: Agent,
        project: Project,
        handoff_tasks: list[Task] | None = None,
    ) -> dict[str, Any]:
        """Handle agent leaving a project."""
        if project.id in self.project_memberships:
            self.project_memberships[project.id].discard(agent.id)
        
        if agent.id in project.team:
            project.team.remove(agent.id)
        
        if project.id in agent.current_projects:
            agent.current_projects.remove(project.id)
        
        return {
            "agent_id": agent.id,
            "project_id": project.id,
            "handoff_tasks": len(handoff_tasks) if handoff_tasks else 0,
            "left_at": timestamp_now().isoformat(),
        }
    
    def claim_task(
        self,
        agent: Agent,
        task: Task,
        confidence: float = 0.8,
    ) -> dict[str, Any]:
        """Agent claims a task. May trigger negotiation if contested."""
        # Check if already claimed
        if task.assigned_to and agent.id not in task.assigned_to:
            # Conflict! Need arbitration
            current_owners = [self.registered_agents.get(aid) for aid in task.assigned_to]
            current_owners = [a for a in current_owners if a]
            
            decision = self.arbitrator.arbitrate_task_ownership(
                task,
                current_owners + [agent],
                strategy="skill_match",
            )
            
            if decision["winner_id"] == agent.id:
                # Agent wins
                task.assigned_to = [agent.id]
                agent.assigned_tasks.append(task.id)
                return {
                    "success": True,
                    "method": "arbitration",
                    "decision": decision,
                }
            else:
                # Agent loses
                return {
                    "success": False,
                    "method": "arbitration",
                    "decision": decision,
                }
        
        # No conflict, direct assignment
        if agent.id not in task.assigned_to:
            task.assigned_to.append(agent.id)
            agent.assigned_tasks.append(task.id)
        
        return {
            "success": True,
            "method": "direct",
            "task_id": task.id,
        }
    
    def request_collaboration(
        self,
        from_agent: Agent,
        to_agents: list[Agent],
        msg_type: CollaborationMessageType,
        subject: Any,
        content: dict[str, Any],
    ) -> list[CollaborationMessage]:
        """Send collaboration request to agents."""
        messages = []
        
        for to_agent in to_agents:
            message = CollaborationMessage(
                msg_type=msg_type,
                from_agent=from_agent.id,
                to_agent=to_agent.id,
                subject_id=subject.id if hasattr(subject, 'id') else str(subject),
                subject_type=subject.__class__.__name__.lower(),
                content=content,
            )
            messages.append(message)
            self.negotiator.message_history.append(message)
        
        return messages
    
    def get_project_agents(self, project_id: str) -> list[Agent]:
        """Get all agents participating in a project."""
        agent_ids = self.project_memberships.get(project_id, set())
        return [self.registered_agents.get(aid) for aid in agent_ids if aid in self.registered_agents]
    
    def export_collaboration_log(
        self,
        project_id: str | None = None,
        since: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Export collaboration activity log."""
        messages = self.negotiator.message_history
        
        if project_id:
            messages = [m for m in messages if m.content.get("project_id") == project_id]
        
        if since:
            messages = [m for m in messages if m.sent_at >= since]
        
        return [
            {
                "id": m.id,
                "type": m.msg_type.value,
                "from_agent": m.from_agent,
                "to_agent": m.to_agent,
                "subject": f"{m.subject_type}:{m.subject_id}",
                "sent_at": m.sent_at.isoformat(),
                "status": m.status.value,
            }
            for m in messages
        ]


class CollaborationLayer:
    """Main entry point for collaboration operations."""
    
    def __init__(self):
        self.api = AgentAPI()
        self.negotiator = self.api.negotiator
        self.arbitrator = self.api.arbitrator
    
    def connect_agent(self, agent: Agent) -> None:
        """Connect an agent to the collaboration system."""
        self.api.register_agent(agent)
    
    def disconnect_agent(self, agent: Agent) -> None:
        """Disconnect an agent gracefully."""
        # Handle any open handoffs
        pass
    
    def get_agent_status(self, agent_id: str) -> dict[str, Any]:
        """Get agent's collaboration status."""
        agent = self.api.registered_agents.get(agent_id)
        if not agent:
            return {"error": "Agent not found"}
        
        return {
            "agent_id": agent.id,
            "projects": agent.current_projects,
            "assigned_tasks": agent.assigned_tasks,
            "current_load": f"{agent.current_task_count}/{agent.max_concurrent_tasks}",
            "available": agent.has_capacity(),
        }
