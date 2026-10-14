from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+psycopg://pipeline:pipeline@localhost:5432/pipeline"
    REDIS_URL: str = "redis://localhost:6379/0"
    CONTACT_EMAIL: str = "you@example.com"
    LLM_PROVIDER: str = Field("ollama", pattern="^(ollama|template)$")
    OLLAMA_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1:8b"
    SMTP_PROBE_ENABLED: bool = False
    SMTP_PROBE_DOMAINS: str = ""
    DAILY_SEND_CAP: int = 20
    DRY_RUN_DEFAULT: bool = True
    CONTROL_API_TOKEN: str = ""
    DATA_DIR: Path = Path("./data")
    PROFILE_PATH: Path = Path("./profile.yaml")
    QUEUE_MODE: str = Field("rq", pattern="^(rq|thread|none)$")  # thread: in-process runner (free hosting); none: tests
    PROFILE_YAML: str = ""  # inline profile (for hosts without the file)
    DEFAULT_RATE_LIMIT_SECONDS: float = 2.0

    @field_validator("DATABASE_URL")
    @classmethod
    def _driver(cls, v: str) -> str:
        for prefix in ("postgres://", "postgresql://"):  # Neon/Render hand out driverless URLs
            if v.startswith(prefix):
                return "postgresql+psycopg://" + v[len(prefix):]
        return v

    @property
    def smtp_domains(self) -> set[str]:
        return {d.strip().lower() for d in self.SMTP_PROBE_DOMAINS.split(",") if d.strip()}

    @property
    def user_agent(self) -> str:
        return f"CompanyPipeline/0.1 (+contact: {self.CONTACT_EMAIL})"


@lru_cache
def get_settings() -> Settings:
    return Settings()
