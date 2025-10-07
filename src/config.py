"""Application configuration using Pydantic settings."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or defaults."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Data directory configuration
    data_dir: Path = Path("data")
    db_path: Path = Path("data/chatkit.sqlite")
    attachments_dir: Path = Path("data/attachments")

    # Attachment storage configuration
    public_base_url: str | None = None


def get_settings() -> Settings:
    """Get application settings singleton."""
    return Settings()
