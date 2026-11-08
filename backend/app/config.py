"""
SpeechShield backend configuration.

Loaded from environment variables via pydantic-settings.
"""

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
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

    # --- Model inference device (kept on CPU) ---
    device: str = "cpu"

    # --- Audio preprocessing device (independent of model inference) ---
    preprocessing_device: Literal["cpu", "cuda"] = "cpu"

    # --- Database (Layer 3) ---
    database_url: str = "sqlite:///./data/speechshield.db"

    # --- Authentication (Layer 3) ---
    jwt_secret_key: str = "dev-insecure-change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # --- Rate limiting (Layer 3) ---
    rate_limit_per_minute: int = 60

    # --- Session cookies (Layer 6) ---
    session_cookie_name: str = "speechshield_session"
    csrf_cookie_name: str = "speechshield_csrf"
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    cookie_path: str = "/"

    # --- Audio upload (Layer 5) ---
    audio_storage_dir: str = "data/audio_uploads"
    max_upload_size_bytes: int = 10 * 1024 * 1024
    max_audio_duration_seconds: float = 30.0
    max_audio_channels: int = 2
    min_sample_rate: int = 8000
    max_sample_rate: int = 96000
    max_decoded_samples: int = 96000 * 30 * 2
    upload_rate_limit_per_minute: int = 10

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

    @field_validator("jwt_secret_key")
    @classmethod
    def _validate_jwt_secret(cls, v: str) -> str:
        if len(v) < 16:
            raise ValueError("jwt_secret_key must be at least 16 characters")
        return v

    @field_validator("jwt_algorithm")
    @classmethod
    def _validate_jwt_algorithm(cls, v: str) -> str:
        allowed = {"HS256"}
        if v not in allowed:
            raise ValueError(f"jwt_algorithm must be one of {sorted(allowed)}")
        return v

    @model_validator(mode="after")
    def _validate_production_secret(self) -> "Settings":
        insecure = {
            "dev-insecure-change-me-in-production",
            "change-me",
            "secret",
            "password",
            "",
        }
        if self.environment == "production" and (
            self.jwt_secret_key in insecure or len(self.jwt_secret_key) < 32
        ):
            raise ValueError(
                "Production jwt_secret_key must be a high-entropy secret of at least 32 characters "
                "and must not be a default/placeholder value. "
                'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(32))"'
            )
        return self

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
