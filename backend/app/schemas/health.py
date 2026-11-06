from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    application: str = "available"
    checkpoint_loaded: bool
    inference_ready: bool = False
    model_ready: bool
    model_error: str | None = None
