from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SmartOps API"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://smartops:smartops@postgres:5432/smartops"
    redis_url: str = "redis://redis:6379/0"
    model_provider: str = "ollama"
    orchestrator_name: str = "langgraph"
    cors_origins: str = "http://localhost:3000"
    source_root: str = "/app/sample-data/input"
    candidate_queue: str = "smartops:candidate_jobs"
    dead_letter_queue: str = "smartops:candidate_jobs:dead"
    seed_demo_data: bool = True

    # Evidence object storage (MinIO locally; any S3-compatible store later).
    minio_endpoint: str = "http://minio:9000"
    minio_public_endpoint: str = "http://localhost:9000"
    minio_access_key: str = "smartops"
    minio_secret_key: str = "smartopsminio"
    minio_bucket: str = "smartops-evidence"
    minio_region: str = "us-east-1"
    evidence_url_ttl_seconds: int = 600
    evidence_storage_enabled: bool = True

    # Auth. Local-dev defaults; production deployments must override both
    # secrets (tracked in docs/DEPLOYMENT_READINESS.md).
    jwt_secret: str = "smartops-dev-secret-change-me"
    jwt_ttl_minutes: int = 12 * 60
    internal_token: str = "smartops-internal-dev-token"

    model_config = SettingsConfigDict(
        env_prefix="SMARTOPS_",
        extra="ignore",
        protected_namespaces=("settings_",),
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
