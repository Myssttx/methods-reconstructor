from functools import lru_cache
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
    app_agent_timeout_seconds: int = 300

    # GCP / Vertex (optional)
    gcp_project_id: str = ""
    gcp_region: str = "us-central1"
    vertex_ai_location: str = "us-central1"
    gemini_model_pro: str = "gemini-2.5-pro"
    gemini_model_flash: str = "gemini-2.5-flash"
    gemini_embedding_model: str = "text-embedding-005"

    # LLM provider
    google_api_key: str = ""
    anthropic_api_key: str = ""
    llm_provider: Literal["auto", "gemini", "anthropic", "offline"] = "auto"

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
    def resolved_llm_provider(self) -> str:
        """Choose actual provider based on what's configured."""
        if self.llm_provider != "auto":
            return self.llm_provider
        if self.google_api_key:
            return "gemini"
        if self.anthropic_api_key:
            return "anthropic"
        return "offline"


@lru_cache
def get_settings() -> Settings:
    return Settings()
