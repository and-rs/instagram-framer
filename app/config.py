import math
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_core import PydanticUseDefault
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    frame_background: str = Field(default="#f7f3ea", alias="FRAME_BACKGROUND")
    frame_shadow_opacity: float = Field(default=0.22, alias="FRAME_SHADOW_OPACITY")
    generated_ttl_seconds: int = Field(default=3600, alias="GENERATED_TTL_SECONDS")
    max_upload_count: int = Field(default=10, alias="MAX_UPLOAD_COUNT")
    max_upload_mb: int = Field(default=50, alias="MAX_UPLOAD_MB")
    max_output_mb: int = Field(default=20, alias="MAX_OUTPUT_MB")
    max_image_pixels: int = Field(default=120_000_000, alias="MAX_IMAGE_PIXELS")
    generated_dir: Path = Path("generated")

    @field_validator(
        "generated_ttl_seconds",
        "max_upload_count",
        "max_upload_mb",
        "max_output_mb",
        "max_image_pixels",
        mode="before",
    )
    @classmethod
    def parse_int_prefix(cls, value: Any) -> Any:
        if isinstance(value, str):
            parts = value.strip().split()
            if not parts:
                raise PydanticUseDefault()
            return parts[0]
        return value

    @field_validator("frame_background", "frame_shadow_opacity", mode="before")
    @classmethod
    def parse_value_prefix(cls, value: Any) -> Any:
        if isinstance(value, str):
            parts = value.strip().split()
            if not parts:
                raise PydanticUseDefault()
            return parts[0]
        return value

    @field_validator("frame_shadow_opacity")
    @classmethod
    def validate_shadow_opacity(cls, value: float) -> float:
        if not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError("FRAME_SHADOW_OPACITY must be between 0 and 1")
        return value

    @field_validator("max_output_mb", "max_image_pixels")
    @classmethod
    def validate_positive_limit(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("output and image limits must be greater than zero")
        return value


settings = Settings()
