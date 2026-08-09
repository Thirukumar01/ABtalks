from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings and environment configuration."""
    APP_NAME: str = "ABTalks Autonomous AI Creator"
    APP_VERSION: str = "1.0.0"
    ENV: str = "development"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DATABASE_URL: str = "sqlite:///./data/agent.db"
    DB_PATH: str = "data/agent.db"
    LOG_LEVEL: str = "INFO"

    # LLM & Scheduler settings
    LLM_API_KEY: Optional[str] = ""
    OPENAI_API_KEY: Optional[str] = ""
    NEWS_API_KEY: Optional[str] = ""
    LLM_MODEL: str = "gpt-4o-mini"
    FALLBACK_MODEL: str = "gpt-4o-mini"
    PUBLISH_INTERVAL_MINUTES: int = 30
    DISCOVERY_INTERVAL_MINUTES: int = 30
    DEFAULT_POSTING_INTERVAL_MINUTES: int = 30
    MAX_POSTS_PER_DAY: int = 10
    MIN_POSTS_PER_DAY: int = 4
    DAILY_POST_CAP_DEFAULT: int = 10
    TIMEZONE: str = "UTC"

    # Discovery configuration
    RSS_FEEDS: list[str] = [
        "https://techcrunch.com/category/artificial-intelligence/feed/",
        "https://feeds.feedburner.com/venturebeat/Swh7",
        "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
        "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml"
    ]

    # CORS
    CORS_ORIGINS: List[str] = ["*"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def sqlite_db_path(self) -> Path:
        """Resolves the SQLite database file path and ensures parent directory exists."""
        raw_path = self.DB_PATH
        if self.DATABASE_URL.startswith("sqlite:///"):
            raw_path = self.DATABASE_URL.replace("sqlite:///", "")
        p = Path(raw_path)
        if not p.is_absolute():
            # Check project root if DB exists there
            root_path = Path(__file__).resolve().parents[2] / p
            if root_path.exists():
                return root_path
            # Also check parent of cwd
            parent_cwd_path = Path.cwd().parent / p
            if parent_cwd_path.exists():
                return parent_cwd_path
            p = Path.cwd() / p
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def database_url(self) -> str:
        """Constructs SQLite database URL from resolved sqlite_db_path."""
        return f"sqlite:///{self.sqlite_db_path.as_posix()}"


settings = Settings()

