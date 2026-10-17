"""Environment configuration (.env.example documents every variable)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    app_env: Literal["development", "test", "staging", "production"] = "development"
    log_level: str = "info"
    api_base_url: str = "http://localhost:8000"
    frontend_origin: str = "http://localhost:3000"

    database_url: str = "postgresql+psycopg://app:app@localhost:5432/hackatl"
    artifact_store_uri: str = "file://./artifacts"

    session_secret: SecretStr = SecretStr("")
    session_ttl_s: int = 7 * 24 * 3600
    auth_dev_login_enabled: bool = False

    # Anthropic / LLM gateway
    anthropic_api_key: SecretStr | None = None
    anthropic_model: str = "claude-opus-5-5"
    anthropic_model_fast: str | None = None
    agent_model_overrides: str = ""
    anthropic_effort: Literal["low", "medium", "high", "xhigh", "max"] = "high"
    llm_server_fallbacks: bool = True
    llm_max_tokens_per_assessment: int = 400_000
    llm_max_usd_per_assessment: float = 10.0
    llm_request_timeout_s: float = 600.0
    llm_max_retries: int = 4

    # GitHub
    github_app_id: str | None = None
    github_app_private_key_path: Path | None = None
    github_webhook_secret: SecretStr | None = None
    github_oauth_client_id: str | None = None
    github_oauth_client_secret: SecretStr | None = None
    github_api_url: str = "https://api.github.com"
    github_web_url: str = "https://github.com"
    webhook_max_bytes: int = 1_048_576

    # Workers
    worker_lease_s: int = 60
    worker_poll_interval_s: float = 1.0
    orchestrator_factory: str = Field(
        default="security_agents.api:build_orchestrator",
        description="module:callable returning an Orchestrator; see backend/host.py",
    )
    code_intelligence_factory: str = "code_intelligence.api:build_service"

    # RL
    rl_checkpoint_path: Path | None = None

    # Rate limits (in-process, docs/13)
    rate_limit_per_minute: int = 60
    assessment_starts_per_hour: int = 5
    webhooks_per_minute: int = 100

    @property
    def is_dev(self) -> bool:
        return self.app_env in ("development", "test")

    def model_for(self, agent: str) -> str:
        for item in filter(None, (p.strip() for p in self.agent_model_overrides.split(","))):
            name, _, model = item.partition("=")
            if name.strip() == agent and model.strip():
                return model.strip()
        return self.anthropic_model


@lru_cache
def get_settings() -> Settings:
    return Settings()
