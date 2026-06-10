import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_env: Literal["development", "staging", "production"] = "development"
    app_log_level: str = "INFO"
    app_cors_origins: str = "http://localhost:3000"
    app_max_recursion_depth: int = 5
    app_per_paper_token_budget: int = 500_000
    app_agent_timeout_seconds: int = 600
    app_max_concurrent_jobs: int = 2
    app_max_concurrent_claims: int = 4
    app_max_concurrent_llm_chunks: int = 3
    app_max_methods_chunk_chars: int = 3_000
    app_llm_chunk_timeout_seconds: float = 15.0
    app_extraction_wall_budget_seconds: float = 35.0
    app_methods_extraction_mode: Literal["hybrid", "llm", "rules"] = "hybrid"
    app_large_methods_sentence_threshold: int = 40
    app_max_assembly_chars: int = 100_000
    app_max_queue_depth: int = 50  # C-5: max pending jobs in Redis queue

    # Auth (C-4: set API_KEY env var to enable X-API-Key protection)
    api_key: str = ""  # empty = open access (dev mode)
    app_use_llm_assembly: bool = False
    app_reuse_cached_claims: bool = True
    app_prompt_version: str = "2026-06-09"
    llm_temperature: float = 0.0

    # GCP / Vertex (optional)
    gcp_project_id: str = ""
    gcp_region: str = "us-central1"
    google_application_credentials: str = ""
    vertex_ai_location: str = "us-central1"
    gemini_model_pro: str = "gemini-3.0-pro"
    gemini_model_flash: str = "gemini-3.0-flash"
    gemini_embedding_model: str = "text-embedding-005"
    enable_vertex_embeddings: bool = False

    # LLM provider
    google_api_key: str = ""
    anthropic_api_key: str = ""
    llm_provider: Literal["auto", "gemini", "anthropic", "offline"] = "auto"
    llm_request_timeout_seconds: float = 180.0
    llm_max_tokens: int = 8192  # max output tokens per LLM call (used by Anthropic)

    # Elastic
    elastic_cloud_id: str = ""
    elastic_api_key: str = ""
    elastic_url: str = "http://localhost:9200"
    elastic_papers_index: str = "papers"
    elastic_claims_index: str = "claims"

    # Firestore
    firestore_database: str = "(default)"
    firestore_collection_jobs: str = "jobs"
    firestore_collection_reconstructions: str = "reconstructions"

    # GCS
    gcs_bucket_uploads: str = "methods-reconstructor-uploads"
    gcs_bucket_exports: str = "methods-reconstructor-exports"

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""  # L-9: set REDIS_PASSWORD for production

    # External APIs
    openalex_email: str = ""
    semantic_scholar_api_key: str = ""
    unpaywall_email: str = ""
    grobid_url: str = "http://localhost:8070"

    # Local fallback paths
    local_storage_root: str = "./.local_storage"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.app_cors_origins.split(",") if o.strip()]

    @property
    def adc_credentials_path(self) -> str:
        if self.google_application_credentials:
            configured = Path(self.google_application_credentials).expanduser()
            if configured.is_file():
                return str(configured)
        default = Path.home() / ".config/gcloud/application_default_credentials.json"
        return str(default) if default.is_file() else ""

    @property
    def resolved_gcp_project_id(self) -> str:
        if self.gcp_project_id:
            return self.gcp_project_id
        if not self.adc_credentials_path:
            return ""
        try:
            payload = json.loads(Path(self.adc_credentials_path).read_text())
        except (OSError, json.JSONDecodeError):
            return ""
        return str(payload.get("quota_project_id") or "")

    @property
    def resolved_llm_provider(self) -> str:
        """Choose actual provider based on what's configured."""
        if self.llm_provider != "auto":
            return self.llm_provider
        if self.google_api_key:
            return "gemini"
        if self.resolved_gcp_project_id:
            return "gemini"
        if self.anthropic_api_key:
            return "anthropic"
        return "offline"

    @property
    def methods_extraction_version(self) -> str:
        return (
            f"{self.app_prompt_version}:rules-v3:{self.app_methods_extraction_mode}:"
            f"large-{self.app_large_methods_sentence_threshold}:"
            f"{self.gemini_model_flash}:{self.llm_temperature:g}:"
            f"chunk-{self.app_max_methods_chunk_chars}:"
            f"timeout-{self.app_llm_chunk_timeout_seconds:g}:"
            f"budget-{self.app_extraction_wall_budget_seconds:g}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
