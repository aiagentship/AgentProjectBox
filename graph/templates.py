"""Task templates for auto-generation based on project type."""

from __future__ import annotations

from typing import Any


# Task templates organized by project type
TASK_TEMPLATES: dict[str, list[dict[str, Any]]] = {
    "web_application": [
        {
            "title": "Project Setup",
            "description": "Initialize repository, configure build tools, set up CI/CD",
            "estimated_hours": 4,
            "priority": "HIGH",
            "tags": ["setup", "infrastructure"],
        },
        {
            "title": "Database Schema Design",
            "description": "Design and implement database schema",
            "estimated_hours": 8,
            "priority": "HIGH",
            "depends_on": ["setup"],
            "tags": ["database", "design"],
        },
        {
            "title": "Authentication System",
            "description": "Implement user authentication and authorization",
            "estimated_hours": 16,
            "priority": "CRITICAL",
            "depends_on": ["setup", "database"],
            "tags": ["security", "auth"],
        },
        {
            "title": "API Development",
            "description": "Build REST/GraphQL API endpoints",
            "estimated_hours": 24,
            "priority": "HIGH",
            "depends_on": ["database", "auth"],
            "tags": ["api", "backend"],
        },
        {
            "title": "Frontend Implementation",
            "description": "Build UI components and pages",
            "estimated_hours": 32,
            "priority": "HIGH",
            "depends_on": ["api"],
            "tags": ["frontend", "ui"],
        },
        {
            "title": "Testing",
            "description": "Write unit, integration, and E2E tests",
            "estimated_hours": 16,
            "priority": "HIGH",
            "depends_on": ["api", "frontend"],
            "tags": ["testing", "quality"],
        },
        {
            "title": "Documentation",
            "description": "Write API docs, user guides, and README",
            "estimated_hours": 8,
            "priority": "MEDIUM",
            "depends_on": ["api", "frontend"],
            "tags": ["docs"],
        },
        {
            "title": "Deployment Setup",
            "description": "Configure production environment and deploy",
            "estimated_hours": 8,
            "priority": "HIGH",
            "depends_on": ["testing"],
            "tags": ["deployment", "devops"],
        },
    ],
    "mobile_app": [
        {
            "title": "Project Setup",
            "description": "Initialize mobile project (React Native/Flutter/Swift/Kotlin)",
            "estimated_hours": 4,
            "priority": "HIGH",
            "tags": ["setup"],
        },
        {
            "title": "UI/UX Design",
            "description": "Design app screens and user flows",
            "estimated_hours": 16,
            "priority": "HIGH",
            "tags": ["design", "ui"],
        },
        {
            "title": "Backend API",
            "description": "Build or integrate backend services",
            "estimated_hours": 24,
            "priority": "HIGH",
            "tags": ["api", "backend"],
        },
        {
            "title": "Core Features",
            "description": "Implement main app functionality",
            "estimated_hours": 40,
            "priority": "CRITICAL",
            "depends_on": ["ui_design", "backend"],
            "tags": ["features"],
        },
        {
            "title": "Authentication",
            "description": "Implement user login and registration",
            "estimated_hours": 12,
            "priority": "CRITICAL",
            "depends_on": ["backend"],
            "tags": ["auth", "security"],
        },
        {
            "title": "Testing",
            "description": "Write tests and perform device testing",
            "estimated_hours": 16,
            "priority": "HIGH",
            "depends_on": ["core_features"],
            "tags": ["testing"],
        },
        {
            "title": "App Store Submission",
            "description": "Prepare and submit to iOS/Android app stores",
            "estimated_hours": 8,
            "priority": "HIGH",
            "depends_on": ["testing"],
            "tags": ["deployment"],
        },
    ],
    "api_service": [
        {
            "title": "API Design",
            "description": "Design API endpoints and data models",
            "estimated_hours": 8,
            "priority": "HIGH",
            "tags": ["design", "api"],
        },
        {
            "title": "Database Setup",
            "description": "Set up database and migrations",
            "estimated_hours": 4,
            "priority": "HIGH",
            "depends_on": ["api_design"],
            "tags": ["database"],
        },
        {
            "title": "Core Endpoints",
            "description": "Implement main API endpoints",
            "estimated_hours": 24,
            "priority": "CRITICAL",
            "depends_on": ["database"],
            "tags": ["api", "backend"],
        },
        {
            "title": "Authentication & Authorization",
            "description": "Implement API auth (JWT, OAuth, etc.)",
            "estimated_hours": 12,
            "priority": "CRITICAL",
            "depends_on": ["core_endpoints"],
            "tags": ["security", "auth"],
        },
        {
            "title": "Error Handling",
            "description": "Implement comprehensive error handling",
            "estimated_hours": 6,
            "priority": "HIGH",
            "depends_on": ["core_endpoints"],
            "tags": ["quality"],
        },
        {
            "title": "API Documentation",
            "description": "Generate OpenAPI/Swagger docs",
            "estimated_hours": 4,
            "priority": "MEDIUM",
            "depends_on": ["core_endpoints"],
            "tags": ["docs"],
        },
        {
            "title": "Testing",
            "description": "Write unit and integration tests",
            "estimated_hours": 12,
            "priority": "HIGH",
            "depends_on": ["core_endpoints"],
            "tags": ["testing"],
        },
        {
            "title": "Deployment",
            "description": "Deploy to production",
            "estimated_hours": 4,
            "priority": "HIGH",
            "depends_on": ["testing"],
            "tags": ["deployment"],
        },
    ],
    "data_pipeline": [
        {
            "title": "Requirements Analysis",
            "description": "Understand data sources and requirements",
            "estimated_hours": 8,
            "priority": "HIGH",
            "tags": ["analysis"],
        },
        {
            "title": "Architecture Design",
            "description": "Design data pipeline architecture",
            "estimated_hours": 8,
            "priority": "HIGH",
            "depends_on": ["requirements"],
            "tags": ["design"],
        },
        {
            "title": "Data Source Integration",
            "description": "Connect to data sources",
            "estimated_hours": 16,
            "priority": "HIGH",
            "depends_on": ["architecture"],
            "tags": ["integration"],
        },
        {
            "title": "ETL Development",
            "description": "Build extract, transform, load processes",
            "estimated_hours": 24,
            "priority": "CRITICAL",
            "depends_on": ["data_sources"],
            "tags": ["etl", "data"],
        },
        {
            "title": "Data Validation",
            "description": "Implement data quality checks",
            "estimated_hours": 8,
            "priority": "HIGH",
            "depends_on": ["etl"],
            "tags": ["quality"],
        },
        {
            "title": "Monitoring & Alerting",
            "description": "Set up pipeline monitoring",
            "estimated_hours": 8,
            "priority": "MEDIUM",
            "depends_on": ["etl"],
            "tags": ["monitoring"],
        },
        {
            "title": "Documentation",
            "description": "Document pipeline and data flows",
            "estimated_hours": 4,
            "priority": "MEDIUM",
            "depends_on": ["etl"],
            "tags": ["docs"],
        },
    ],
    "ml_project": [
        {
            "title": "Data Collection",
            "description": "Gather and understand training data",
            "estimated_hours": 16,
            "priority": "HIGH",
            "tags": ["data"],
        },
        {
            "title": "Data Preprocessing",
            "description": "Clean and prepare data for training",
            "estimated_hours": 16,
            "priority": "HIGH",
            "depends_on": ["data_collection"],
            "tags": ["data", "preprocessing"],
        },
        {
            "title": "Feature Engineering",
            "description": "Create and select features",
            "estimated_hours": 12,
            "priority": "HIGH",
            "depends_on": ["data_preprocessing"],
            "tags": ["features"],
        },
        {
            "title": "Model Development",
            "description": "Build and train ML models",
            "estimated_hours": 24,
            "priority": "CRITICAL",
            "depends_on": ["feature_engineering"],
            "tags": ["model", "training"],
        },
        {
            "title": "Model Evaluation",
            "description": "Evaluate model performance",
            "estimated_hours": 8,
            "priority": "HIGH",
            "depends_on": ["model_development"],
            "tags": ["evaluation"],
        },
        {
            "title": "Model Deployment",
            "description": "Deploy model as API/service",
            "estimated_hours": 12,
            "priority": "HIGH",
            "depends_on": ["model_evaluation"],
            "tags": ["deployment"],
        },
        {
            "title": "Monitoring",
            "description": "Set up model performance monitoring",
            "estimated_hours": 8,
            "priority": "MEDIUM",
            "depends_on": ["model_deployment"],
            "tags": ["monitoring"],
        },
    ],
}

# Keywords to detect project type from text
PROJECT_TYPE_KEYWORDS: dict[str, list[str]] = {
    "web_application": [
        "website", "web app", "web application", "saas", "platform",
        "frontend", "backend", "full-stack", "react", "vue", "angular",
        "django", "flask", "express", "next.js", "gatsby"
    ],
    "mobile_app": [
        "mobile app", "mobile application", "ios", "android", "iphone",
        "flutter", "react native", "swift", "kotlin", "app store", "play store"
    ],
    "api_service": [
        "api", "rest api", "graphql", "microservice", "backend service",
        "webhook", "endpoint", "swagger", "openapi"
    ],
    "data_pipeline": [
        "data pipeline", "etl", "elt", "data warehouse", "data lake",
        "spark", "airflow", "kafka", "streaming", "batch processing"
    ],
    "ml_project": [
        "machine learning", "ml", "ai", "artificial intelligence",
        "deep learning", "neural network", "model training", "prediction",
        "classification", "nlp", "computer vision"
    ],
}


def detect_project_type(text: str) -> str | None:
    """Detect project type from natural language text."""
    text_lower = text.lower()
    
    best_match = None
    best_score = 0
    
    for project_type, keywords in PROJECT_TYPE_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword in text_lower)
        if score > best_score:
            best_score = score
            best_match = project_type
    
    return best_match


def get_templates_for_type(project_type: str) -> list[dict[str, Any]]:
    """Get task templates for a specific project type."""
    return TASK_TEMPLATES.get(project_type, [])


def generate_tasks_from_template(
    project_type: str,
    base_title: str | None = None,
    custom_dependencies: dict[str, list[str]] | None = None,
) -> list[dict[str, Any]]:
    """
    Generate task list from template.
    
    Args:
        project_type: Type of project (e.g., "web_application")
        base_title: Optional title prefix for tasks
        custom_dependencies: Override default dependencies
    
    Returns:
        List of task dictionaries ready for creation
    """
    templates = get_templates_for_type(project_type)
    tasks = []
    
    for template in templates:
        task = template.copy()
        
        # Add custom title prefix if provided
        if base_title:
            task['title'] = f"{base_title}: {task['title']}"
        
        # Override dependencies if provided
        if custom_dependencies:
            template_id = task['title'].split(':')[0].lower().replace(' ', '_')
            if template_id in custom_dependencies:
                task['depends_on'] = custom_dependencies[template_id]
        
        # Convert priority string to Priority enum value
        if 'priority' in task:
            from shared.models import Priority
            priority_str = task['priority'].upper()
            task['priority'] = Priority[priority_str]
        
        tasks.append(task)
    
    return tasks


def suggest_tasks_from_description(text: str) -> list[dict[str, Any]]:
    """
    Suggest tasks based on natural language description.
    
    Args:
        text: Natural language project description
    
    Returns:
        List of suggested tasks
    """
    project_type = detect_project_type(text)
    
    if project_type:
        return generate_tasks_from_template(project_type)
    
    # Fallback: return generic tasks
    return [
        {
            "title": "Requirements Analysis",
            "description": "Understand and document requirements",
            "estimated_hours": 8,
            "priority": "HIGH",
            "tags": ["analysis"],
        },
        {
            "title": "Design & Planning",
            "description": "Create technical design and plan",
            "estimated_hours": 8,
            "priority": "HIGH",
            "depends_on": ["requirements_analysis"],
            "tags": ["design"],
        },
        {
            "title": "Implementation",
            "description": "Build the solution",
            "estimated_hours": 40,
            "priority": "CRITICAL",
            "depends_on": ["design_planning"],
            "tags": ["implementation"],
        },
        {
            "title": "Testing",
            "description": "Test and validate",
            "estimated_hours": 16,
            "priority": "HIGH",
            "depends_on": ["implementation"],
            "tags": ["testing"],
        },
        {
            "title": "Documentation",
            "description": "Write documentation",
            "estimated_hours": 8,
            "priority": "MEDIUM",
            "depends_on": ["implementation"],
            "tags": ["docs"],
        },
        {
            "title": "Deployment",
            "description": "Deploy to production",
            "estimated_hours": 4,
            "priority": "HIGH",
            "depends_on": ["testing"],
            "tags": ["deployment"],
        },
    ]
