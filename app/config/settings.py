"""
Session 2.5: Application Configuration.
Reads all environment variables from .env and validates them.
"""

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Main application settings.
    All values come from the .env file or environment variables.
    """

    # ===== Environment =====
    environment: str = Field(default="development", description="Environment name")
    log_level: str = Field(default="INFO", description="Logging level")

    # ===== MongoDB =====
    mongo_user: str = Field(default="admin")
    mongo_password: str = Field(default="password123")
    mongo_host: str = Field(default="localhost")
    mongo_port: int = Field(default=27017)
    mongo_db: str = Field(default="careerai")

    @property
    def mongo_uri(self) -> str:
        """Construct MongoDB connection URI."""
        return f"mongodb://{self.mongo_user}:{self.mongo_password}@{self.mongo_host}:{self.mongo_port}"

    # ===== Redis =====
    redis_url: str = Field(default="redis://localhost:6379")
    redis_db: int = Field(default=0)

    # ===== RabbitMQ =====
    rabbitmq_user: str = Field(default="guest")
    rabbitmq_password: str = Field(default="guest")
    rabbitmq_host: str = Field(default="localhost")
    rabbitmq_port: int = Field(default=5672)

    @property
    def rabbitmq_url(self) -> str:
        """Construct RabbitMQ AMQP URL."""
        return f"amqp://{self.rabbitmq_user}:{self.rabbitmq_password}@{self.rabbitmq_host}:{self.rabbitmq_port}/"

    # ===== Scraping Settings =====
    scrape_limit: int = Field(default=10, description="Default number of jobs to fetch")
    scrape_concurrent: int = Field(default=1, description="Number of concurrent scraping requests")
    request_timeout: int = Field(default=30, description="HTTP request timeout in seconds")
    user_agent: str = Field(
        default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        description="Default User-Agent header",
    )

    # ===== Adzuna API =====
    adzuna_app_id: str = Field(default="", description="Adzuna App ID")
    adzuna_api_key: str = Field(default="", description="Adzuna API Key")

    # ===== Jooble API =====
    jooble_api_key: str = Field(default="", description="Jooble API Key")

    class Config:
        """Pydantic config to read from .env file."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.
    The @lru_cache ensures we only load the .env file once.
    """
    return Settings()


# Create a global settings instance for easy imports
settings = get_settings()