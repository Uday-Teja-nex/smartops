from functools import lru_cache

from pydantic import Field, model_validator
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
    request_max_bytes: int = Field(default=2 * 1024 * 1024, ge=1024, le=16 * 1024 * 1024)
    mediamtx_webrtc_public_url: str = 'http://localhost:8889'
    mediamtx_rtsp_host: str = 'mediamtx'

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
        hide_input_in_errors=True,
    )

    @model_validator(mode='after')
    def validate_production(self):
        if self.environment.strip().lower() != 'production':
            return self
        for name, default in (
            ('jwt_secret', 'smartops-dev-secret-change-me'),
            ('internal_token', 'smartops-internal-dev-token'),
        ):
            value = getattr(self, name)
            if value == default or len(value.strip()) < 32:
                raise ValueError(f'Production requires a unique {name} of at least 32 characters')
        if self.evidence_storage_enabled and (
            self.minio_secret_key == 'smartopsminio' or len(self.minio_secret_key.strip()) < 16
        ):
            raise ValueError('Production requires a non-default object storage secret of at least 16 characters')
        if self.seed_demo_data:
            raise ValueError('Production requires seed_demo_data=false; demo accounts must not be seeded')
        if not self.cors_origin_list or any('*' in origin for origin in self.cors_origin_list):
            raise ValueError('Production requires explicit CORS origins without wildcards')
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
