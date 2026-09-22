"""Application configuration."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed settings shared by the application factory."""

    model_config = SettingsConfigDict(
        env_prefix="REPONYX_",
        env_file=".env",
        extra="ignore",
        frozen=True,
    )

    app_name: str = Field(default="Reponyx", min_length=1)
    environment: str = Field(default="development", min_length=1)
    log_level: str = Field(default="INFO", min_length=1)
    database_url: str = Field(default="postgresql+psycopg://reponyx:reponyx@localhost:5432/reponyx")
    openai_api_key: str | None = None
    ollama_base_url: str = "http://localhost:11434"
    workspace_root: str = "./workspaces"
    max_repository_bytes: int = 100_000_000
    max_file_bytes: int = 1_000_000
    max_files: int = 10_000
    embedding_provider: str = "deterministic"
    embedding_model: str = "hash-embedding-v1"
    embedding_dimensions: int = 64
    embedding_batch_size: int = 32
    embedding_timeout_seconds: float = 30.0
    semantic_weight: float = 0.65
    lexical_weight: float = 0.35
    retrieval_character_budget: int = 20_000
    investigation_model_provider: str = "deterministic"
    investigation_model: str = "deterministic-investigator-v1"
    investigation_timeout_seconds: float = 60.0
    investigation_max_iterations: int = 3
    investigation_max_source_bytes: int = 100_000
    execution_image: str = "reponyx-executor:phase4"
    execution_default_timeout_seconds: float = 120.0
    execution_max_timeout_seconds: float = 600.0
    execution_memory_limit: str = "512m"
    execution_cpu_limit: float = 1.0
    execution_pids_limit: int = 128
    execution_output_limit: int = 200_000
    execution_network_disabled: bool = True
    execution_root: str = "./executions"
    repair_workspace_root: str = "./repair-workspaces"
    repair_max_iterations: int = 5
    llm_provider: str = "mock"
    llm_model: str = "gpt-4.1-mini"
    llm_timeout_seconds: float = 60.0
    llm_max_output_tokens: int = 4_000
    llm_max_calls: int = 20
    llm_max_context_characters: int = 30_000
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"


@lru_cache
def get_settings() -> Settings:
    """Return one process-wide validated settings instance."""

    return Settings()
