"""
SpeechShield backend configuration.

Loaded from environment variables via pydantic-settings.
"""

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Root of the backend package (speechshield/backend)
BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_ARTIFACT_DIR = BACKEND_DIR / "artifacts" / "v4"
DEFAULT_CHECKPOINT = DEFAULT_ARTIFACT_DIR / "checkpoints" / "best_v4.pt"
DEFAULT_CONFIG_JSON = DEFAULT_ARTIFACT_DIR / "v4_config.json"
DEFAULT_MANIFEST_JSON = DEFAULT_ARTIFACT_DIR / "v4_artifact_manifest.json"
DEFAULT_MODEL_DEF = DEFAULT_ARTIFACT_DIR / "model_def.py"
DEFAULT_PREPROCESSING_JSON = DEFAULT_ARTIFACT_DIR / "preprocessing_config.json"


class Settings(BaseSettings):
    # --- API metadata ---
    app_name: str = "SpeechShield API"
    app_version: str = "0.1.0-layer0"
    environment: Literal["development", "test", "production"] = "development"
    debug: bool = False
    log_level: str = "INFO"

    # --- CORS ---
    frontend_origin: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- Model artifacts (private local storage) ---
    artifact_dir: str = Field(default=str(DEFAULT_ARTIFACT_DIR))
    checkpoint_filename: str = "checkpoints/best_v4.pt"
    model_config_filename: str = "v4_config.json"
    artifact_manifest_filename: str = "v4_artifact_manifest.json"

    # --- Inference device (CPU only in Layer 0) ---
    device: str = "cpu"

    # --- Optional integrity override (leave empty to use manifest) ---
    expected_checkpoint_sha256: str | None = None

    @field_validator("frontend_origin")
    @classmethod
    def _validate_origins(cls, v: str) -> str:
        origins = [o.strip() for o in v.split(",") if o.strip()]
        if not origins:
            raise ValueError("frontend_origin must contain at least one origin")
        for o in origins:
            if "*" in o:
                raise ValueError("Wildcard CORS origins are not allowed")
        return v

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in allowed:
            raise ValueError(f"log_level must be one of {sorted(allowed)}")
        return v.upper()

    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def allowed_origins(self) -> list[str]:
        return [o.strip() for o in self.frontend_origin.split(",") if o.strip()]

    def resolved_artifact_dir(self) -> Path:
        p = Path(self.artifact_dir)
        if not p.is_absolute():
            p = (BACKEND_DIR / p).resolve()
        return p

    def resolved_checkpoint_path(self) -> Path:
        return (self.resolved_artifact_dir() / self.checkpoint_filename).resolve()

    def resolved_config_path(self) -> Path:
        return (self.resolved_artifact_dir() / self.model_config_filename).resolve()

    def resolved_manifest_path(self) -> Path:
        return (self.resolved_artifact_dir() / self.artifact_manifest_filename).resolve()


settings = Settings()
