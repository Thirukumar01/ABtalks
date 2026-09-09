import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment or .env file."""

    ENV: str = "development"
    APP_NAME: str = "ABtalks Autonomous AI Creator"
    APP_VERSION: str = "1.0.0"

    # Use DB_PATH as the single source of truth.
    # Vercel: /tmp is writable.
    DB_PATH: str = "/tmp/agent.db"
    DATABASE_URL: str = ""

    OPENAI_API_KEY: str = ""
    NEWS_API_KEY: str = ""

    DEFAULT_POSTING_INTERVAL_MINUTES: int = 30
    FALLBACK_MODEL: str = "gpt-4o-mini"
    LOG_LEVEL: str = "INFO"
    DAILY_POST_CAP_DEFAULT: int = 10
    AGENT_TRIGGER_SECRET: str = ""
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]
    ENABLE_INTERNAL_SCHEDULER: bool = False

    # Discovery configuration
    RSS_FEEDS: list[str] = [
        "https://techcrunch.com/category/artificial-intelligence/feed/",
        "https://feeds.feedburner.com/venturebeat/Swh7",
        "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
        "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml"
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def sqlite_db_path(self) -> Path:
        """Return a writable SQLite database path."""

        p = Path(self.DB_PATH)

        # Vercel's project filesystem is read-only.
        # /tmp is the writable location.
        if not p.is_absolute():
            p = Path("/tmp") / p

        p.parent.mkdir(parents=True, exist_ok=True)

        return p

    @property
    def database_url(self) -> str:
        """Construct SQLite database URL."""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return f"sqlite:///{self.sqlite_db_path.as_posix()}"


settings = Settings()
