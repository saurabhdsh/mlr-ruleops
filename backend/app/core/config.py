from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore", case_sensitive=False)

    app_name: str = "MLR RuleOps"
    app_env: str = "demo"
    secret_key: str = "change-me-in-production-use-a-long-random-string"
    jwt_secret: str = "change-me-jwt-secret-use-a-long-random-string"
    jwt_expiry_minutes: int = 480
    jwt_algorithm: str = "HS256"

    database_url: str = "postgresql+psycopg://ruleops:ruleops@localhost:5432/ruleops"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080"

    llm_provider: Literal["openai", "azure_openai", "anthropic", "bedrock", "deterministic"] = "deterministic"
    llm_confidence_threshold: float = 0.72

    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_deployment: str = ""
    azure_openai_api_version: str = "2024-10-21"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"

    aws_region: str = "us-east-1"
    aws_profile: str = "default"
    bedrock_model: str = "anthropic.claude-3-haiku-20240307-v1:0"

    servicenow_base_url: str = ""
    servicenow_username: str = ""
    servicenow_password: str = ""

    jira_base_url: str = ""
    jira_email: str = ""
    jira_api_token: str = ""

    seed_reviews: int = 200
    seed_on_startup: bool = True

    prompt_template_version: str = "ticket-interpret-v1"
    output_schema_version: str = "change-intent-v1"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def llm_credentials_available(self) -> bool:
        if self.llm_provider == "openai":
            return bool(self.openai_api_key)
        if self.llm_provider == "azure_openai":
            return bool(self.azure_openai_api_key and self.azure_openai_endpoint and self.azure_openai_deployment)
        if self.llm_provider == "anthropic":
            return bool(self.anthropic_api_key)
        if self.llm_provider == "bedrock":
            return True
        return False

    @property
    def effective_llm_provider(self) -> str:
        if self.llm_provider == "deterministic":
            return "deterministic"
        if self.llm_credentials_available:
            return self.llm_provider
        return "deterministic"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
