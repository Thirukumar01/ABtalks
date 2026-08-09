import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment or .env file."""
    
    ENV: str = "development"
    DB_PATH: str = "data/agent.db"
    OPENAI_API_KEY: str = ""
    NEWS_API_KEY: str = ""
    DEFAULT_POSTING_INTERVAL_MINUTES: int = 30
    FALLBACK_MODEL: str = "gpt-4o-mini"
    LOG_LEVEL: str = "INFO"
    DAILY_POST_CAP_DEFAULT: int = 10
    
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
    DATABASE_URL: str = "sqlite:///./data/agent.db"
    
    @property
    def sqlite_db_path(self) -> Path:
        """Resolves the SQLite database file path and ensures parent directory exists."""
        raw_path = self.DB_PATH
        if self.DATABASE_URL.startswith("sqlite:///"):
            raw_path = self.DATABASE_URL.replace("sqlite:///", "")
        p = Path(raw_path)
        if not p.is_absolute():
            # Check project root
            root_path = Path(__file__).resolve().parent.parent / p
            if root_path.exists():
                return root_path
            parent_cwd_path = Path.cwd().parent / p
            if parent_cwd_path.exists():
                return parent_cwd_path
            p = Path.cwd() / p
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def database_url(self) -> str:
        """Constructs SQLite database URL from DB_PATH."""
        return f"sqlite:///{self.sqlite_db_path.as_posix()}"


settings = Settings()

