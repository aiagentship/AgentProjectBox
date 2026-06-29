"""Configuration management for AgentProjectBox."""

import os
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DatabaseConfig:
    """Database configuration."""
    url: str = field(default_factory=lambda: os.getenv("APB_DB_URL", "sqlite:///./agentprojectbox.db"))
    echo: bool = field(default_factory=lambda: os.getenv("APB_DB_ECHO", "false").lower() == "true")


@dataclass
class RedisConfig:
    """Redis/Cache configuration."""
    url: str = field(default_factory=lambda: os.getenv("APB_REDIS_URL", "redis://localhost:6379"))
    prefix: str = "apb:"


@dataclass
class AuthConfig:
    """Authentication configuration."""
    secret_key: str = field(default_factory=lambda: os.getenv("APB_SECRET_KEY", "dev-secret-key"))
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60


@dataclass
class MonteCarloConfig:
    """Monte Carlo simulation configuration."""
    iterations: int = 1000
    confidence_threshold: float = 0.7
    buffer_multiplier: float = 1.5


@dataclass
class NotificationConfig:
    """Notification/Alert configuration."""
    slack_webhook_url: str | None = field(default_factory=lambda: os.getenv("APB_SLACK_WEBHOOK"))
    email_smtp_host: str | None = field(default_factory=lambda: os.getenv("APB_SMTP_HOST"))
    email_smtp_port: int = field(default_factory=lambda: int(os.getenv("APB_SMTP_PORT", "587")))
    email_from: str = field(default_factory=lambda: os.getenv("APB_EMAIL_FROM", "alerts@agentprojectbox.ai"))
    default_channels: list[str] = field(default_factory=lambda: ["slack"])


@dataclass
class LogConfig:
    """Logging configuration."""
    level: str = field(default_factory=lambda: os.getenv("APB_LOG_LEVEL", "INFO"))
    format: str = "json"
    structured: bool = True


@dataclass
class AgentProjectBoxConfig:
    """Main configuration container."""
    env: str = field(default_factory=lambda: os.getenv("APB_ENV", "development"))
    debug: bool = field(default_factory=lambda: os.getenv("APB_DEBUG", "false").lower() == "true")
    
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)
    monte_carlo: MonteCarloConfig = field(default_factory=MonteCarloConfig)
    notifications: NotificationConfig = field(default_factory=NotificationConfig)
    logging: LogConfig = field(default_factory=LogConfig)
    
    # Feature flags
    enable_swarm_mode: bool = field(default_factory=lambda: os.getenv("APB_SWARM_MODE", "true").lower() == "true")
    enable_compliance: bool = field(default_factory=lambda: os.getenv("APB_COMPLIANCE", "true").lower() == "true")
    auto_allocate: bool = field(default_factory=lambda: os.getenv("APB_AUTO_ALLOCATE", "true").lower() == "true")
    
    # Paths
    data_dir: str = field(default_factory=lambda: os.getenv("APB_DATA_DIR", "./data"))
    log_dir: str = field(default_factory=lambda: os.getenv("APB_LOG_DIR", "./logs"))
    
    # API settings
    api_host: str = field(default_factory=lambda: os.getenv("APB_API_HOST", "0.0.0.0"))
    api_port: int = field(default_factory=lambda: int(os.getenv("APB_API_PORT", "8000")))
    
    @property
    def is_production(self) -> bool:
        return self.env == "production"
    
    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary (for serialization)."""
        return {
            "env": self.env,
            "debug": self.debug,
            "api_host": self.api_host,
            "api_port": self.api_port,
            "is_production": self.is_production,
        }


# Global config instance
config = AgentProjectBoxConfig()
