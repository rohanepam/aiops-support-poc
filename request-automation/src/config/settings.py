from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    adapter_mode: str = "mock"  # mock | live
    confidence_threshold: int = 80
    entity_lookup_path: str = "entity_lookup/databases.yaml"
    log_level: str = "INFO"

    jsm_base_url: str = ""
    jsm_email: str = ""
    jsm_api_token: str = ""

    bedrock_model_id: str = "anthropic.claude-3-haiku-20240307-v1:0"
    aws_region: str = "us-east-1"

    @field_validator("entity_lookup_path")
    @classmethod
    def resolve_lookup_path(cls, value: str) -> str:
        path = Path(value)
        if path.is_file():
            return str(path.resolve())
        candidate = _PROJECT_ROOT / value
        if candidate.is_file():
            return str(candidate.resolve())
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
