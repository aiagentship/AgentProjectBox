"""Task Graph Engine: DAG builder and Knowledge Graph for projects."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterator

import networkx as nx

from shared.models import Task, TaskStatus, Project, AgentCapability
from shared.utils import generate_id, timestamp_now


@dataclass
class DependencyEdge:
    """Represents a dependency between two tasks."""
    from_task_id: str
    to_task_id: str
    dependency_type: str = "hard"  # hard, soft, optional
    weight: float = 1.0  # 0-1, strength of dependency


@dataclass
class TaskNode:
    """Enhanced task representation for the graph."""
    task: Task
    depth: int = 0  # Distance from root (no dependencies)
    critical_path_weight: float = 0.0  # Sum of durations on critical path
    earliest_start: float = 0.0  # Earliest start time (hours from project start)
    latest_start: float = float('inf')  # Latest start without delaying project
    slack: float = 0.0  # Float time


class DAGBuilder:
    """Build and manage Directed Acyclic Graphs of tasks."""
    
    def __init__(self):
        self.graph: nx.DiGraph = nx.DiGraph()
        self.task_nodes: dict[str, TaskNode] = {}
    
    def add_task(self, task: Task) -> None:
        """Add a task to the graph."""
        self.graph.add_node(task.id, task=task)
        self.task_nodes[task.id] = TaskNode(task=task)
        
        # Add dependency edges
        for dep_id in task.depends_on:
            self.graph.add_edge(dep_id, task.id, type="dependency")
    
    def add_dependency(self, from_task_id: str, to_task_id: str, hard: bool = True) -> None:
        """Add a dependency edge between tasks."""
        weight = 1.0 if hard else 0.5
        self.graph.add_edge(from_task_id, to_task_id, type="dependency", weight=weight)
        
        # Update task's depends_on
        to_task = self.graph.nodes[to_task_id].get("task")
        if to_task and from_task_id not in to_task.depends_on:
            to_task.depends_on.append(from_task_id)
    
    def remove_dependency(self, from_task_id: str, to_task_id: str) -> None:
        """Remove a dependency edge."""
        if self.graph.has_edge(from_task_id, to_task_id):
            self.graph.remove_edge(from_task_id, to_task_id)
        
        # Update task's depends_on
        to_task = self.graph.nodes[to_task_id].get("task")
        if to_task and from_task_id in to_task.depends_on:
            to_task.depends_on.remove(from_task_id)
    
    def is_dag(self) -> bool:
        """Check if graph is still a DAG (no cycles)."""
        return nx.is_directed_acyclic_graph(self.graph)
    
    def detect_cycles(self) -> list[list[str]]:
        """Detect all cycles in the graph."""
        try:
            cycles = list(nx.simple_cycles(self.graph))
            return cycles
        except:
            return []
    
    def topological_sort(self) -> list[str]:
        """Return tasks in topological order (dependency order)."""
        if not self.is_dag():
            raise ValueError("Graph contains cycles")
        return list(nx.topological_sort(self.graph))
    
    def get_ready_tasks(self) -> list[Task]:
        """Get tasks with all dependencies satisfied (can start now)."""
        ready = []
        task_map = {node_id: data["task"] for node_id, data in self.graph.nodes(data=True) if "task" in data}
        
        for node_id, data in self.graph.nodes(data=True):
            task = data.get("task")
            if not task:
                continue
            
            # Task is ready if:
            # 1. Status is PENDING
            # 2. All dependencies are COMPLETED
            if task.status == TaskStatus.PENDING:
                deps = [task_map.get(dep_id) for dep_id in task.depends_on]
                if all(d and d.status == TaskStatus.COMPLETED for d in deps):
                    ready.append(task)
        
        return ready
    
    def get_blocked_tasks(self) -> list[Task]:
        """Get tasks that are blocked by incomplete dependencies."""
        blocked = []
        task_map = {node_id: data["task"] for node_id, data in self.graph.nodes(data=True) if "task" in data}
        
        for node_id, data in self.graph.nodes(data=True):
            task = data.get("task")
            if not task or task.status != TaskStatus.PENDING:
                continue
            
            deps = [task_map.get(dep_id) for dep_id in task.depends_on]
            if any(d and d.status != TaskStatus.COMPLETED for d in deps):
                blocked.append(task)
        
        return blocked
    
    def calculate_critical_path(self) -> tuple[float, list[str]]:
        """
        Calculate the critical path using longest path algorithm.
        Returns (duration, list of task IDs on critical path).
        """
        if not self.is_dag():
            raise ValueError("Cannot calculate critical path with cycles")
        
        # Use weighted edges based on task duration
        for u, v in self.graph.edges():
            task_u = self.graph.nodes[u].get("task")
            if task_u:
                self.graph[u][v]["weight"] = -task_u.estimated_hours  # Negative for longest path
        
        # Find longest path (critical path)
        critical_path = nx.dag_longest_path(self.graph, weight="weight")
        duration = sum(
            self.graph.nodes[n].get("task", Task(title="", estimated_hours=0)).estimated_hours
            for n in critical_path
        )
        
        return duration, critical_path
    
    def calculate_parallel_groups(self) -> list[list[str]]:
        """Group tasks that can be executed in parallel."""
        if not self.is_dag():
            raise ValueError("Cannot parallelize with cycles")
        
        # Calculate depth (longest path from root)
        depths = {}
        for node in nx.topological_sort(self.graph):
            preds = list(self.graph.predecessors(node))
            if not preds:
                depths[node] = 0
            else:
                depths[node] = max(depths.get(p, 0) + 1 for p in preds)
        
        # Group by depth
        groups: dict[int, list[str]] = defaultdict(list)
        for node_id, depth in depths.items():
            groups[depth].append(node_id)
        
        return [groups[d] for d in sorted(groups.keys())]
    
    def get_dependents(self, task_id: str) -> list[str]:
        """Get all tasks that depend on this task."""
        return list(nx.descendants(self.graph, task_id))
    
    def get_dependencies(self, task_id: str) -> list[str]:
        """Get all tasks this task depends on (transitive)."""
        return list(nx.ancestors(self.graph, task_id))
    
    def find_parallelizable_pairs(self) -> list[tuple[str, str]]:
        """Find pairs of tasks that can run in parallel."""
        parallel_pairs = []
        tasks = list(self.graph.nodes())
        
        for i, task_a in enumerate(tasks):
            for task_b in tasks[i+1:]:
                # Check if neither depends on the other
                if not nx.has_path(self.graph, task_a, task_b) and \
                   not nx.has_path(self.graph, task_b, task_a):
                    parallel_pairs.append((task_a, task_b))
        
        return parallel_pairs
    
    def calculate_slack_times(self) -> dict[str, float]:
        """Calculate slack (float) time for each task."""
        if not self.is_dag():
            return {}
        
        _, critical_path = self.calculate_critical_path()
        critical_set = set(critical_path)
        
        slack_times = {}
        for node_id, node_data in self.graph.nodes(data=True):
            task = node_data.get("task")
            if not task:
                continue
            
            if node_id in critical_set:
                slack_times[node_id] = 0.0
            else:
                # Calculate how much this task can be delayed
                # This is a simplified calculation
                slack_times[node_id] = task.estimated_hours * 0.5  # Placeholder
        
        return slack_times
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize graph to dictionary."""
        return {
            "nodes": [
                {
                    "id": node_id,
                    "task": self.graph.nodes[node_id].get("task"),
                }
                for node_id in self.graph.nodes()
            ],
            "edges": [
                {
                    "from": u,
                    "to": v,
                    "data": data,
                }
                for u, v, data in self.graph.edges(data=True)
            ],
        }


class KnowledgeGraph:
    """
    Persistent knowledge graph for projects, tasks, and outcomes.
    Enables querying past projects for reusable workflows.
    """
    
    def __init__(self):
        # Multi-graph for complex relationships
        self.graph: nx.MultiDiGraph = nx.MultiDiGraph()
        self.project_patterns: dict[str, dict] = {}  # Reusable workflow patterns
    
    def index_project(self, project: Project) -> None:
        """Index a completed project into the knowledge graph."""
        # Add project node
        self.graph.add_node(
            project.id,
            type="project",
            title=project.title,
            data=project.model_dump(),
        )
        
        # Add task nodes
        for task in project.tasks:
            self.graph.add_node(
                task.id,
                type="task",
                title=task.title,
                status=task.status.value,
            )
            self.graph.add_edge(project.id, task.id, relation="contains")
        
        # Add dependency edges
        for task in project.tasks:
            for dep_id in task.depends_on:
                self.graph.add_edge(dep_id, task.id, relation="depends_on")
        
        # Extract and store pattern if successful
        if project.status.value in ["completed", "active"]:
            self._extract_pattern(project)
    
    def _extract_pattern(self, project: Project) -> None:
        """Extract a reusable workflow pattern from a project."""
        pattern = {
            "domain": self._extract_domain(project),
            "task_ontology": self._categorize_tasks(project.tasks),
            "dependency_structure": self._capture_dependency_structure(project),
            "resource_patterns": self._capture_resource_patterns(project),
            "timeline_pattern": self._capture_timeline_pattern(project),
            "metadata": {
                "source_project_id": project.id,
                "success_indicators": project.calculate_progress(),
            }
        }
        
        pattern_id = generate_id()
        self.project_patterns[pattern_id] = pattern
        
        # Link pattern to project
        self.graph.add_node(pattern_id, type="pattern", **pattern)
        self.graph.add_edge(project.id, pattern_id, relation="exhibits_pattern")
    
    def _extract_domain(self, project: Project) -> str:
        """Extract project domain from title and tasks."""
        text = f"{project.title} {' '.join(t.title for t in project.tasks)}".lower()
        
        domains = {
            "software": ["api", "app", "backend", "frontend", "service", "database", "microservice", "saas"],
            "ai_ml": ["ai", "ml", "model", "training", "inference", "llm", "neural"],
            "devops": ["deploy", "ci/cd", "infrastructure", "kubernetes", "docker", "pipeline"],
            "data": ["data", "etl", "warehouse", "lake", "analytics", "pipeline"],
            "web": ["website", "webapp", "landing page", "e-commerce", "cms"],
        }
        
        scores = {domain: sum(1 for kw in keywords if kw in text) 
                  for domain, keywords in domains.items()}
        
        return max(scores, key=scores.get) if max(scores.values()) > 0 else "general"
    
    def _categorize_tasks(self, tasks: list[Task]) -> dict[str, list[str]]:
        """Categorize tasks by type/phase."""
        categories = defaultdict(list)
        
        for task in tasks:
            task_lower = task.title.lower()
            
            if any(kw in task_lower for kw in ["setup", "config", "init", "bootstrap"]):
                categories["setup"].append(task.title)
            elif any(kw in task_lower for kw in ["design", "architect", "plan", "spec"]):
                categories["design"].append(task.title)
            elif any(kw in task_lower for kw in ["build", "implement", "code", "develop", "create", "add"]):
                categories["implementation"].append(task.title)
            elif any(kw in task_lower for kw in ["test", "quality", "verify", "validate", "qa"]):
                categories["testing"].append(task.title)
            elif any(kw in task_lower for kw in ["deploy", "release", "launch", "ship", "publish"]):
                categories["deployment"].append(task.title)
            elif any(kw in task_lower for kw in ["doc", "document", "readme", "guide", "wiki"]):
                categories["documentation"].append(task.title)
            else:
                categories["other"].append(task.title)
        
        return dict(categories)
    
    def _capture_dependency_structure(self, project: Project) -> dict:
        """Capture the dependency structure as a pattern."""
        builder = DAGBuilder()
        for task in project.tasks:
            builder.add_task(task)
        
        return {
            "is_dag": builder.is_dag(),
            "num_levels": len(builder.calculate_parallel_groups()),
            "parallelization_ratio": len(project.tasks) / max(len(builder.calculate_parallel_groups()), 1),
        }
    
    def _capture_resource_patterns(self, project: Project) -> dict:
        """Capture resource allocation patterns."""
        return {
            "avg_task_duration": sum(t.estimated_hours for t in project.tasks) / max(len(project.tasks), 1),
            "total_estimated_hours": sum(t.estimated_hours for t in project.tasks),
        }
    
    def _capture_timeline_pattern(self, project: Project) -> dict:
        """Capture timeline and scheduling patterns."""
        if not project.timeline:
            return {"pattern": "unknown"}
        
        duration = (project.timeline.due_date - project.timeline.start_date).days
        return {
            "duration_days": duration,
            "buffer_ratio": project.timeline.buffer_days / max(duration, 1),
        }
    
    def query_similar_projects(
        self, 
        domain: str | None = None,
        min_tasks: int = 0,
        max_tasks: int = 1000,
        status: str | None = None,
    ) -> list[dict]:
        """Query past projects for similar instances."""
        results = []
        
        for node_id, data in self.graph.nodes(data=True):
            if data.get("type") != "project":
                continue
            
            project_data = data.get("data", {})
            tasks = project_data.get("tasks", [])
            
            # Apply filters
            if len(tasks) < min_tasks or len(tasks) > max_tasks:
                continue
            
            if status and project_data.get("status") != status:
                continue
            
            if domain:
                title = project_data.get("title", "").lower()
                # Simple domain matching
                if domain not in title:
                    continue
            
            results.append(project_data)
        
        return results
    
    def suggest_task_breakdown(self, objective: str, deliverable: str) -> list[dict]:
        """Suggest task breakdown based on similar past projects."""
        # Find patterns from same domain
        relevant_patterns = [
            p for p in self.project_patterns.values()
            if objective.lower() in p.get("domain", "")
        ]
        
        if not relevant_patterns:
            # Return generic breakdown
            return [
                {"title": f"Design {deliverable}", "phase": "design"},
                {"title": f"Implement {deliverable}", "phase": "implementation"},
                {"title": f"Test {deliverable}", "phase": "testing"},
                {"title": f"Document {deliverable}", "phase": "documentation"},
            ]
        
        # Aggregate patterns
        suggested_tasks = []
        for pattern in relevant_patterns[:3]:  # Top 3 patterns
            ontology = pattern.get("task_ontology", {})
            for phase, tasks in ontology.items():
                for task in tasks[:2]:  # Top 2 tasks per phase
                    suggested_tasks.append({
                        "title": task,
                        "phase": phase,
                        "confidence": 0.7,  # baseline confidence
                    })
        
        return suggested_tasks
    
    def estimate_duration(
        self, 
        domain: str, 
        num_deliverables: int,
        complexity: str = "medium"
    ) -> dict:
        """Estimate project duration based on similar projects."""
        # Find similar completed projects
        similar = self.query_similar_projects(domain=domain, status="completed")
        
        if not similar:
            # Default estimates
            multipliers = {"low": 0.7, "medium": 1.0, "high": 1.5, "critical": 2.5}
            base_days = 14 * num_deliverables
            return {
                "estimated_days": base_days * multipliers.get(complexity, 1.0),
                "confidence": 0.3,
                "based_on": 0,
            }
        
        # Calculate statistics
        durations = []
        for proj in similar:
            timeline = proj.get("timeline", {})
            if timeline:
                start = timeline.get("start_date")
                end = timeline.get("due_date")
                if start and end:
                    duration = (end - start).days
                    durations.append(duration)
        
        if durations:
            avg_duration = sum(durations) / len(durations)
            confidence = min(0.9, 0.3 + (len(durations) * 0.1))
            
            return {
                "estimated_days": avg_duration,
                "confidence": confidence,
                "based_on": len(durations),
                "range": (min(durations), max(durations)),
            }
        
        return {"estimated_days": 14 * num_deliverables, "confidence": 0.3, "based_on": 0}
    
    def export_graph(self, format: str = "json") -> str:
        """Export knowledge graph in various formats."""
        if format == "json":
            data = {
                "nodes": [
                    {"id": n, **self.graph.nodes[n]}
                    for n in self.graph.nodes()
                ],
                "edges": [
                    {"from": u, "to": v, **d}
                    for u, v, d in self.graph.edges(data=True)
                ],
                "patterns": list(self.project_patterns.values()),
            }
            return json.dumps(data, indent=2, default=str)
        elif format == "cypher":
            # Neo4j Cypher format
            lines = []
            for node_id, data in self.graph.nodes(data=True):
                props = ", ".join(f'{k}: "{v}"' for k, v in data.items() if isinstance(v, str))
                lines.append(f'CREATE (n:{data.get("type", "Node")} {{id: "{node_id}", {props}}})')
            return "\n".join(lines)
        else:
            raise ValueError(f"Unsupported format: {format}")


class TaskGraphEngine:
    """Main entry point for task graph operations."""
    
    def __init__(self):
        self.builder = DAGBuilder()
        self.knowledge = KnowledgeGraph()
    
    def build_from_project(self, project: Project) -> DAGBuilder:
        """Build task DAG from a project."""
        builder = DAGBuilder()
        
        for task in project.tasks:
            builder.add_task(task)
        
        self.builder = builder
        return builder
    
    def auto_infer_dependencies(self, tasks: list[Task]) -> list[DependencyEdge]:
        """Automatically infer dependencies between tasks based on semantics."""
        edges = []
        
        # Simple heuristic: ordering by phase
        phase_order = ["setup", "design", "implementation", "testing", "deployment", "documentation"]
        task_phases = []
        
        for task in tasks:
            task_lower = task.title.lower()
            for i, phase in enumerate(phase_order):
                if phase in task_lower or any(
                    kw in task_lower for kw in self._get_phase_keywords(phase)
                ):
                    task_phases.append((task, i))
                    break
            else:
                task_phases.append((task, 99))  # Unknown phase
        
        # Create edges between phases
        for i, (task_a, phase_a) in enumerate(task_phases):
            for task_b, phase_b in task_phases[i+1:]:
                if phase_b > phase_a + 1:  # Not adjacent phases
                    break
                if phase_b == phase_a + 1:
                    edges.append(DependencyEdge(
                        from_task_id=task_a.id,
                        to_task_id=task_b.id,
                        dependency_type="inferred",
                        weight=0.7,
                    ))
        
        return edges
    
    def _get_phase_keywords(self, phase: str) -> list[str]:
        """Get keywords for project phases."""
        return {
            "setup": ["setup", "init", "bootstrap", "prepare", "configure"],
            "design": ["design", "architect", "plan", "spec", "prototype"],
            "implementation": ["build", "develop", "implement", "code", "create", "add"],
            "testing": ["test", "quality", "verify", "validate", "check"],
            "deployment": ["deploy", "release", "launch", "ship", "publish", "publish"],
            "documentation": ["doc", "document", "write", "guide", "readme"],
        }.get(phase, [])
    
    def suggest_optimizations(self) -> list[dict]:
        """Suggest optimizations for the task graph."""
        suggestions = []
        
        # Find tasks with no dependencies that could start
        ready = self.builder.get_ready_tasks()
        if len(ready) > 3:
            suggestions.append({
                "type": "parallelization",
                "message": f"{len(ready)} tasks are ready to start in parallel",
                "tasks": [t.title for t in ready],
            })
        
        # Find long chains that could be optimized
        _, critical_path = self.builder.calculate_critical_path()
        if len(critical_path) > 5:
            suggestions.append({
                "type": "critical_path",
                "message": f"Long critical path with {len(critical_path)} tasks - consider parallelizing",
                "tasks": critical_path,
            })
        
        # Detect potential bottlenecks (tasks with many dependents)
        for node_id in self.builder.graph.nodes():
            dependents = self.builder.get_dependents(node_id)
            if len(dependents) > 3:
                task = self.builder.graph.nodes[node_id].get("task")
                if task:
                    suggestions.append({
                        "type": "bottleneck",
                        "message": f"'{task.title}' has {len(dependents)} dependent tasks",
                        "task_id": node_id,
                        "dependent_count": len(dependents),
                    })
        
        return suggestions
    
    def export_for_agents(self) -> dict:
        """Export task graph in agent-consumable format."""
        return {
            "dag": self.builder.to_dict(),
            "is_valid_dag": self.builder.is_dag(),
            "cycles": self.builder.detect_cycles() if not self.builder.is_dag() else [],
            "critical_path": self.builder.calculate_critical_path() if self.builder.is_dag() else None,
            "parallel_groups": self.builder.calculate_parallel_groups() if self.builder.is_dag() else [],
            "ready_tasks": [
                {"id": t.id, "title": t.title, "estimated_hours": t.estimated_hours}
                for t in self.builder.get_ready_tasks()
            ],
            "blocked_tasks": [
                {"id": t.id, "title": t.title, "blocked_by": t.depends_on}
                for t in self.builder.get_blocked_tasks()
            ],
        }


from pydantic import BaseModel, ConfigDict, Field
