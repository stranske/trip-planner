from pydantic import BaseModel, Field


class HealthStatus(BaseModel):
    service: str = Field(description="Service name exposed to the frontend shell.")
    status: str = Field(description="Operational state for the current process.")
    environment: str = Field(description="Named environment for local or deployed runs.")
    version: str = Field(description="Application version surfaced to the UI.")
