from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PLATFORM_", extra="ignore")

    database_url: str | None = None
    temporal_address: str | None = None
    temporal_namespace: str = "default"
    temporal_task_queue: str = "agent-runs"
    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_jwks_url: str | None = None
    oidc_tenant_claim: str = "tenant_id"
    otel_enabled: bool = True
    otel_traces_endpoint: str | None = None
    sentry_dsn: str | None = None
    sentry_environment: str = "development"
    sentry_traces_sample_rate: float = Field(default=0.0, ge=0, le=1)

    @field_validator("sentry_dsn")
    @classmethod
    def sentry_dsn_must_use_https(cls, value: str | None) -> str | None:
        if value and not value.startswith("https://"):
            raise ValueError("sentry_dsn must use https")
        return value

    @field_validator("database_url")
    @classmethod
    def database_must_be_async_postgres(cls, value: str | None) -> str | None:
        if value and not value.startswith("postgresql+asyncpg://"):
            raise ValueError("database_url must use postgresql+asyncpg")
        return value
