from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    # Application process is up. Model readiness is reported separately.
    application: str = "available"
    model_ready: bool
    model_error: str | None = None
