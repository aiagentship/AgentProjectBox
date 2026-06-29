"""Task Graph Engine: DAG builder and Knowledge Graph for projects."""

from .builder import (
    DAGBuilder,
    KnowledgeGraph,
    TaskGraphEngine,
    DependencyEdge,
    TaskNode,
)
from .templates import (
    detect_project_type,
    get_templates_for_type,
    generate_tasks_from_template,
    suggest_tasks_from_description,
    TASK_TEMPLATES,
    PROJECT_TYPE_KEYWORDS,
)

__all__ = [
    "DAGBuilder",
    "KnowledgeGraph",
    "TaskGraphEngine",
    "DependencyEdge",
    "TaskNode",
    "detect_project_type",
    "get_templates_for_type",
    "generate_tasks_from_template",
    "suggest_tasks_from_description",
    "TASK_TEMPLATES",
    "PROJECT_TYPE_KEYWORDS",
]
