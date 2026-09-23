from pydantic import BaseModel, Field


class DatabaseHealth(BaseModel):
    ready: bool = Field(
        description="Whether the database was initialised and reachable when last checked."
    )
    reason: str | None = Field(
        default=None, description="Why it is not ready: the error class, never a connection string."
    )
    checked_at: str | None = Field(
        default=None, description="When readiness was last checked (UTC, ISO 8601)."
    )


class HealthStatus(BaseModel):
    service: str = Field(description="Service name exposed to the frontend shell.")
    status: str = Field(description='"ok", or "degraded" when the database is not usable.')
    environment: str = Field(description="Named environment for local or deployed runs.")
    version: str = Field(description="Application version surfaced to the UI.")
    database: DatabaseHealth | None = Field(
        default=None, description="Database readiness, as last observed."
    )
