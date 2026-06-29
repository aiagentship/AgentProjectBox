"""Persistence layer for AgentProjectBox - JSON file storage."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from datetime import datetime

from shared.models import Project, Agent
from shared.utils import timestamp_now


class PersistenceLayer:
    """Simple JSON-based persistence for projects and agents."""
    
    def __init__(self, data_dir: str | None = None):
        """
        Initialize persistence layer.
        
        Args:
            data_dir: Directory to store data files. Defaults to ./apb_data
        """
        if data_dir is None:
            data_dir = os.path.join(os.path.expanduser("~"), ".agentprojectbox")
        
        self.data_dir = Path(data_dir)
        self.projects_file = self.data_dir / "projects.json"
        self.agents_file = self.data_dir / "agents.json"
        self.audit_file = self.data_dir / "audit.json"
        
        # Ensure directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Load existing data
        self._projects: dict[str, dict] = {}
        self._agents: dict[str, dict] = {}
        self._audit_events: list[dict] = []
        
        self._load_all()
    
    def _load_all(self) -> None:
        """Load all data from files."""
        if self.projects_file.exists():
            try:
                with open(self.projects_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._projects = data.get('projects', {})
                    self._audit_events = data.get('audit_events', [])
            except (json.JSONDecodeError, IOError):
                self._projects = {}
                self._audit_events = []
        
        if self.agents_file.exists():
            try:
                with open(self.agents_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._agents = data.get('agents', {})
            except (json.JSONDecodeError, IOError):
                self._agents = {}
    
    def save_project(self, project: Project) -> None:
        """Save a project to persistent storage."""
        self._projects[project.id] = project.model_dump()
        self._save_projects()
    
    def load_project(self, project_id: str) -> Project | None:
        """Load a project by ID."""
        if project_id not in self._projects:
            return None
        
        data = self._projects[project_id]
        return Project.model_validate(data)
    
    def delete_project(self, project_id: str) -> bool:
        """Delete a project."""
        if project_id in self._projects:
            del self._projects[project_id]
            self._save_projects()
            return True
        return False
    
    def list_projects(self) -> list[Project]:
        """List all projects."""
        return [Project.model_validate(data) for data in self._projects.values()]
    
    def save_agent(self, agent: Agent) -> None:
        """Save an agent to persistent storage."""
        self._agents[agent.id] = agent.model_dump()
        self._save_agents()
    
    def load_agent(self, agent_id: str) -> Agent | None:
        """Load an agent by ID."""
        if agent_id not in self._agents:
            return None
        
        data = self._agents[agent_id]
        return Agent.model_validate(data)
    
    def delete_agent(self, agent_id: str) -> bool:
        """Delete an agent."""
        if agent_id in self._agents:
            del self._agents[agent_id]
            self._save_agents()
            return True
        return False
    
    def list_agents(self) -> list[Agent]:
        """List all agents."""
        return [Agent.model_validate(data) for data in self._agents.values()]
    
    def log_audit_event(self, event: dict[str, Any]) -> None:
        """Log an audit event."""
        self._audit_events.append(event)
        # Keep only last 1000 events to prevent file growth
        if len(self._audit_events) > 1000:
            self._audit_events = self._audit_events[-1000:]
        self._save_projects()  # Audit is stored with projects file
    
    def get_audit_events(self, project_id: str | None = None, limit: int = 100) -> list[dict]:
        """Get audit events, optionally filtered by project."""
        if project_id:
            events = [e for e in self._audit_events if e.get('resource_id') == project_id]
        else:
            events = self._audit_events
        
        return events[-limit:]
    
    def _save_projects(self) -> None:
        """Save projects to file."""
        data = {
            'projects': self._projects,
            'audit_events': self._audit_events,
            'last_updated': timestamp_now().isoformat()
        }
        with open(self.projects_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)
    
    def _save_agents(self) -> None:
        """Save agents to file."""
        data = {
            'agents': self._agents,
            'last_updated': timestamp_now().isoformat()
        }
        with open(self.agents_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)
    
    def export_backup(self, output_path: str) -> None:
        """Export all data to a backup file."""
        backup_data = {
            'projects': self._projects,
            'agents': self._agents,
            'audit_events': self._audit_events,
            'exported_at': timestamp_now().isoformat()
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, indent=2, default=str)
    
    def import_backup(self, backup_path: str) -> dict[str, int]:
        """Import data from a backup file. Returns counts of imported items."""
        with open(backup_path, 'r', encoding='utf-8') as f:
            backup_data = json.load(f)
        
        imported = {'projects': 0, 'agents': 0}
        
        if 'projects' in backup_data:
            for pid, pdata in backup_data['projects'].items():
                self._projects[pid] = pdata
                imported['projects'] += 1
        
        if 'agents' in backup_data:
            for aid, adata in backup_data['agents'].items():
                self._agents[aid] = adata
                imported['agents'] += 1
        
        if 'audit_events' in backup_data:
            self._audit_events.extend(backup_data['audit_events'])
        
        self._save_projects()
        self._save_agents()
        
        return imported
