"""Intake Layer: NLP parsing and schema enforcement for project requests."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

from shared.models import (
    Project, Task, Timeline, Priority, ProjectStatus, TaskStatus, Risk
)
from shared.utils import generate_id, timestamp_now, parse_duration


class ProjectSchema:
    """Schema definition for project requests."""
    
    REQUIRED_FIELDS = {"title", "objectives", "deliverables"}
    OPTIONAL_FIELDS = {"timeline", "risks", "constraints", "budget", "team", "constraints", "assumptions"}
    
    FIELD_HINTS = {
        "title": "A concise project title (e.g., 'AI Agent SaaS Launch')",
        "objectives": "List of measurable goals (e.g., ['MVP build', 'Beta release'])",
        "deliverables": "List of concrete outputs (e.g., ['Core modules', 'Documentation'])",
        "timeline": "Expected duration or due date (e.g., '2 months' or '2026-06-15')",
        "risks": "Potential blockers or concerns",
        "constraints": "Limitations (budget, resources, compliance)",
        "assumptions": "Assumed to be true for planning",
    }


class NLPIntakeParser:
    """Parse natural language project requests into structured data."""
    
    # Keywords for extraction
    TIME_PATTERNS = [
        r"(?:by|before|due)\s+([A-Z][a-z]+ \d{1,2}(?:st|nd|rd|th)?(?:,? \d{4})?)",
        r"(?:in|within) (\d+)\s*(day|week|month|year)s?",
        r"(\d+)-(?:week|month) (?:timeline|sprint|phase)",
        r"(?:duration:?)\s*(\d+)\s*(day|week|month|year)s?",
    ]
    
    PRIORITY_KEYWORDS = {
        Priority.CRITICAL: ["critical", "urgent", "asap", "immediate", "p0", "blocker"],
        Priority.HIGH: ["high", "important", "priority", "p1"],
        Priority.MEDIUM: ["medium", "normal", "standard", "p2"],
        Priority.LOW: ["low", "nice to have", "backlog", "p3"],
        Priority.TRIVIAL: ["trivial", "minor", "whenever", "p4"],
    }
    
    RISK_KEYWORDS = [
        "risk", "challenge", "blocker", "concern", "issue", "bottleneck",
        "dependency", "uncertain", "untested", "unproven", "complex",
    ]
    
    DELIVERABLE_PATTERNS = [
        r"(?:deliverable|output|artifact|result):?\s*([^;.]+)",
        r"(?:create|build|develop|implement|deploy)\s+([^,.;]+(?:module|system|app|feature|api|ui|docs?|test|report|dashboard)",
    ]
    
    OBJECTIVE_PATTERNS = [
        r"(?:goal|objective|aim|target):?\s*([^;.]+)",
        r"(?:to|in order to)\s+([^,.;]+)",
    ]

    def parse(self, text: str, agent_id: str = "system") -> ProjectRequest:
        """Parse natural language into a structured project request."""
        text_lower = text.lower()
        
        extracted = {
            "title": self._extract_title(text),
            "objectives": self._extract_objectives(text),
            "deliverables": self._extract_deliverables(text),
            "timeline": self._extract_timeline(text),
            "risks": self._extract_risks(text),
            "priority": self._extract_priority(text_lower),
            "constraints": self._extract_constraints(text),
            "raw_text": text,
        }
        
        return ProjectRequest(
            extracted_data=extracted,
            confidence=self._calculate_confidence(extracted),
            missing_fields=self._identify_missing(extracted),
            clarification_questions=self._generate_questions(extracted),
            parsed_by=agent_id,
        )
    
    def _extract_title(self, text: str) -> str:
        """Extract project title from text."""
        # Look for quoted titles or first sentence
        quotes_match = re.search(r'["\']([^"\']+)["\']\s+(?:project|initiative|sprint)', text, re.I)
        if quotes_match:
            return quotes_match.group(1).strip()
        
        # First sentence (up to 50 chars)
        first_sentence = text.split('.')[0][:50].strip()
        return first_sentence if len(first_sentence) > 5 else "Untitled Project"
    
    def _extract_objectives(self, text: str) -> list[str]:
        """Extract list of objectives from text."""
        objectives = []
        
        # Look for bullet points or numbered lists
        for match in re.finditer(r'(?:^|\n)[\s]*[-*•][\s]*([^\n]+)', text, re.MULTILINE):
            obj = match.group(1).strip()
            if len(obj) > 5 and any(kw in obj.lower() for kw in ["goal", "achieve", "complete", "deliver", "build"]):
                objectives.append(obj)
        
        # Pattern-based extraction
        for pattern in self.OBJECTIVE_PATTERNS:
            for match in re.finditer(pattern, text, re.I):
                obj = match.group(1).strip()
                if len(obj) > 5:
                    objectives.append(obj)
        
        return objectives[:10]  # Limit to 10 objectives
    
    def _extract_deliverables(self, text: str) -> list[str]:
        """Extract deliverables from text."""
        deliverables = []
        
        # Specific artifact mentions
        artifact_patterns = [
            r"([\w\s]+(?:module|system|API|UI|interface|database|service|component))",
            r"([\w\s]+(?:documentation|docs?|spec|specification|report|analysis))",
            r"([\w\s]+(?:test|tests?|test suite|integration tests?))",
            r"([\w\s]+(?:campaign|launch|announcement|rollout))",
        ]
        
        for pattern in artifact_patterns:
            for match in re.finditer(pattern, text, re.I):
                deliverable = match.group(1).strip()
                if len(deliverable) > 3:
                    deliverables.append(deliverable)
        
        return list(set(deliverables))[:15]  # Deduplicate and limit
    
    def _extract_timeline(self, text: str) -> dict[str, Any] | None:
        """Extract timeline information."""
        now = timestamp_now()
        duration_days = None
        due_date = None
        
        # Check for explicit due dates
        for pattern in self.TIME_PATTERNS:
            match = re.search(pattern, text, re.I)
            if match:
                if "due" in pattern or "before" in pattern:
                    # Try to parse date
                    due_date_str = match.group(1)
                    try:
                        due_date = self._parse_relative_date(due_date_str)
                    except:
                        pass
                else:
                    # Duration
                    amount = int(match.group(1))
                    unit = match.group(2) if len(match.groups()) > 1 else "day"
                    if unit == "week":
                        duration_days = amount * 7
                    elif unit == "month":
                        duration_days = amount * 30
                    elif unit == "year":
                        duration_days = amount * 365
                    else:
                        duration_days = amount
        
        if not due_date and duration_days:
            due_date = now + timedelta(days=duration_days)
        
        if due_date:
            return {
                "start_date": now,
                "due_date": due_date,
                "estimated_duration": duration_days,
            }
        
        return None
    
    def _parse_relative_date(self, date_str: str) -> datetime:
        """Parse relative date strings."""
        now = timestamp_now()
        date_str = date_str.lower()
        
        # Simple month names
        months = {
            "january": 1, "february": 2, "march": 3, "april": 4,
            "may": 5, "june": 6, "july": 7, "august": 8,
            "september": 9, "october": 10, "november": 11, "december": 12,
        }
        
        for month_name, month_num in months.items():
            if month_name in date_str:
                # Extract day
                day_match = re.search(r'(\d{1,2})', date_str)
                day = int(day_match.group(1)) if day_match else 1
                year_match = re.search(r'20\d{2}', date_str)
                year = int(year_match.group(0)) if year_match else now.year
                return datetime(year, month_num, day)
        
        # Default: 30 days from now
        return now + timedelta(days=30)
    
    def _extract_risks(self, text: str) -> list[str]:
        """Extract potential risks from text."""
        risks = []
        text_lower = text.lower()
        
        for keyword in self.RISK_KEYWORDS:
            if keyword in text_lower:
                # Find context around risk keyword
                for match in re.finditer(rf'[^.]*\b{keyword}\b[^.]*\.', text, re.I):
                    risk = match.group(0).strip()
                    if len(risk) > 10:
                        risks.append(risk)
        
        return list(set(risks))[:10]
    
    def _extract_priority(self, text_lower: str) -> Priority:
        """Extract priority level from text."""
        for priority, keywords in self.PRIORITY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return priority
        return Priority.MEDIUM
    
    def _extract_constraints(self, text: str) -> list[str]:
        """Extract constraints from text."""
        constraints = []
        constraint_patterns = [
            r"(?:constraint|limited by|restricted to|must|cannot|budget of)\s*[:;]?([^;.]+)",
        ]
        for pattern in constraint_patterns:
            for match in re.finditer(pattern, text, re.I):
                constraint = match.group(1).strip()
                if len(constraint) > 5:
                    constraints.append(constraint)
        return constraints
    
    def _calculate_confidence(self, extracted: dict) -> float:
        """Calculate confidence score for the extraction."""
        score = 0.5  # base score
        
        # Required fields present
        if extracted["title"] and extracted["title"] != "Untitled Project":
            score += 0.2
        if len(extracted["objectives"]) > 0:
            score += 0.15
        if len(extracted["deliverables"]) > 0:
            score += 0.15
        
        return min(score, 1.0)
    
    def _identify_missing(self, extracted: dict) -> set[str]:
        """Identify missing required fields."""
        missing = set(ProjectSchema.REQUIRED_FIELDS)
        
        if extracted.get("title") and extracted["title"] != "Untitled Project":
            missing.discard("title")
        if len(extracted.get("objectives", [])) > 0:
            missing.discard("objectives")
        if len(extracted.get("deliverables", [])) > 0:
            missing.discard("deliverables")
        
        return missing
    
    def _generate_questions(self, extracted: dict) -> list[str]:
        """Generate clarification questions for missing data."""
        questions = []
        
        for field in self._identify_missing(extracted):
            hint = ProjectSchema.FIELD_HINTS.get(field, field)
            questions.append(f"What is the {field}? ({hint})")
        
        # Additional context questions
        if not extracted.get("timeline"):
            questions.append("What is the expected timeline or due date?")
        if not extracted.get("risks"):
            questions.append("Are there any known risks or dependencies we should track?")
        
        return questions


class ProjectRequest(BaseModel):
    """Result of parsing a project request."""
    
    model_config = ConfigDict(frozen=False)
    
    extracted_data: dict[str, Any]
    confidence: float
    missing_fields: set[str]
    clarification_questions: list[str]
    parsed_by: str
    parsed_at: datetime = Field(default_factory=timestamp_now)
    
    @property
    def is_valid(self) -> bool:
        """Check if request has minimum required information."""
        return len(self.missing_fields) == 0 and self.confidence >= 0.6


class SchemaEnforcer:
    """Enforce project schema and validate completeness."""
    
    def validate(self, data: dict[str, Any]) -> ValidationResult:
        """Validate project data against schema."""
        errors = []
        warnings = []
        
        # Check required fields
        for field in ProjectSchema.REQUIRED_FIELDS:
            if field not in data or not data[field]:
                errors.append(f"Missing required field: {field}")
        
        # Type validation
        if "timeline" in data and data["timeline"]:
            timeline = data["timeline"]
            if isinstance(timeline, dict):
                if "due_date" in timeline and not isinstance(timeline["due_date"], (str, datetime)):
                    errors.append("timeline.due_date must be a date string or datetime")
        
        # Business constraints
        if "budget" in data and data["budget"]:
            budget = data["budget"]
            if isinstance(budget, dict):
                if budget.get("allocated", 0) <= 0:
                    warnings.append("Budget should be greater than 0")
        
        # Cross-field validation
        if data.get("objectives") and data.get("deliverables"):
            objectives = data["objectives"]
            deliverables = data["deliverables"]
            if len(deliverables) < len(objectives) / 2:
                warnings.append("Fewer deliverables than objectives - consider if all objectives are covered")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )
    
    def hydrate_project(self, request: ProjectRequest) -> Project:
        """Convert a validated request to a full Project object."""
        data = request.extracted_data
        
        # Build timeline
        timeline_data = data.get("timeline", {})
        timeline = None
        if timeline_data:
            timeline = Timeline(
                start_date=timeline_data.get("start_date", timestamp_now()),
                due_date=timeline_data.get("due_date", timestamp_now() + timedelta(days=30)),
            )
        
        # Create project
        project = Project(
            title=data["title"],
            objectives=data.get("objectives", []),
            deliverables=data.get("deliverables", []),
            constraints=data.get("constraints", []),
            assumptions=data.get("assumptions", []),
            priority=data.get("priority", Priority.MEDIUM),
            timeline=timeline,
            status=ProjectStatus.DRAFT,
            created_by=request.parsed_by,
        )
        
        # Convert parsed risks to Risk objects
        for risk_desc in data.get("risks", []):
            project.risks.append(Risk(
                category="parsed",
                description=risk_desc,
                probability=0.3,  # default probability
                impact=0.5,  # default impact
            ))
        
        return project


class IntakeLayer:
    """Main entry point for the intake module."""
    
    def __init__(self):
        self.parser = NLPIntakeParser()
        self.enforcer = SchemaEnforcer()
    
    def process_request(
        self, 
        text: str, 
        agent_id: str = "system",
        context: dict[str, Any] | None = None
    ) -> tuple[ProjectRequest, Project | None]:
        """
        Process a natural language request through intake pipeline.
        
        Returns:
            Tuple of (parsed_request, project_or_none)
        """
        # Parse the request
        request = self.parser.parse(text, agent_id)
        
        # If insufficient data, return early with questions
        if not request.is_valid:
            return request, None
        
        # Validate extracted data
        validation = self.enforcer.validate(request.extracted_data)
        
        if not validation.is_valid:
            request.clarification_questions.extend(validation.errors)
            return request, None
        
        # Hydrate to full project
        project = self.enforcer.hydrate_project(request)
        
        return request, project
    
    def enrich_project(
        self, 
        project: Project, 
        answers: dict[str, Any]
    ) -> ValidationResult:
        """Enrich project with clarifying answers."""
        for key, value in answers.items():
            if hasattr(project, key):
                setattr(project, key, value)
            elif key == "timeline":
                if isinstance(value, dict):
                    project.timeline = Timeline(**value)
            elif key == "budget":
                from shared.models import Budget
                project.budget = Budget(**value)
        
        # Re-validate
        data = {
            "title": project.title,
            "objectives": project.objectives,
            "deliverables": project.deliverables,
        }
        return self.enforcer.validate(data)
