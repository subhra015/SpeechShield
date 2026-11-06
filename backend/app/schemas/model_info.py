from pydantic import BaseModel


class ModelInfoResponse(BaseModel):
    model_version: str
    architecture: str
    checkpoint_sha256: str | None
    expected_sha256: str | None
    sha256_verified: bool
    parameter_count: int | None
    device: str
    threshold: float | None
    classification_threshold: float | None
    uncertain_confidence_threshold: float | None
    target_sample_rate: int | None
    target_length_seconds: float | None
    n_mels: int | None
    inference_status: str
    preprocessing_parity_verified: bool = False
    inference_ready: bool = False
    # Preprocessing parity is unverified.
    inference_production_ready: bool = False
    notes: str = (
        "Layer 0: model loaded and integrity-verified. "
        "Inference is BLOCKED pending preprocessing parity verification. "
        "No prediction endpoint is exposed."
    )
