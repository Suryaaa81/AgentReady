from __future__ import annotations

from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DATABASE_PATH = Path(__file__).resolve().parents[1] / "agentready_dev.db"
BACKEND_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ENV_PATH,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    DATABASE_URL: str = f"sqlite:///{DEFAULT_DATABASE_PATH.as_posix()}"

    # Server
    ENV: str = "development"
    CORS_ORIGINS: str = "http://localhost:5173"

    # Phase 4 — Gemini
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    MAX_AGENT_TOOL_ROUNDS: int = 8

    # Phase 5 — Razorpay (not used yet)
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @model_validator(mode="after")
    def check_secrets_in_production(self) -> Settings:
        if self.ENV.lower() == "production":
            missing = []
            if not self.GEMINI_API_KEY:
                missing.append("GEMINI_API_KEY")
            if not self.RAZORPAY_KEY_ID:
                missing.append("RAZORPAY_KEY_ID")
            if not self.RAZORPAY_KEY_SECRET:
                missing.append("RAZORPAY_KEY_SECRET")
            if not self.RAZORPAY_WEBHOOK_SECRET:
                missing.append("RAZORPAY_WEBHOOK_SECRET")
            if missing:
                raise ValueError(f"Missing critical secrets in production: {', '.join(missing)}")
        return self


settings = Settings()
