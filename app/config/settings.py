from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Central configuration class for CareerAI.
    Loads configuration values from the .env file.
    """
    
    # ==============================
    # Application Settings
    # ==============================
    APP_NAME: str = "CareerAI"
    APP_ENV: str = "development"
    DEBUG: bool = True
    
    # ==============================
    # POSTGRESQL
    # ==============================
    DB_HOST: str
    DB_PORT: int
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str
    
    # Database pool settings
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_RECYCLE: int = 3600
    
    # ==============================
    # REDIS
    # ==============================
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_DB: int = 0
    
    # ==============================
    # RABBITMQ
    # ==============================
    RABBITMQ_HOST: str
    RABBITMQ_PORT: int
    RABBITMQ_USER: str
    RABBITMQ_PASSWORD: str

    #==============================
    #MONGODB
    #==============================
    MONGO_HOST: str = "localhost"
    MONGO_PORT: int = 27017
    MONGO_DB_NAME: str = "career_ai"
    MONGO_USER: str = ""
    MONGO_PASSWORD: str = ""

    #===============================
    #ADZUNA API
    #===============================

    ADZUNA_APP_ID : str = ""
    ADZUNA_APP_KEY : str = ""
    
    # ==============================
    # SCRAPING SETTINGS
    # ==============================
    SCRAPE_DELAY: float = 2.0  # Seconds between requests
    TIMEOUT: int = 30  # Request timeout
    MAX_RETRIES: int = 3
    SCRAPE_PAGES: int = 2
    
    # ==============================
    # LOGGING
    # ==============================
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/app.log"
    
    # ==============================
    # PLATFORMS
    # ==============================
    ENABLED_PLATFORMS: dict = {
        'indeed': {
            'base_url': 'https://www.indeed.com',
            'rate_limit': 2.0,
            'enabled': True,
        },
        'naukri': {
            'base_url': 'https://www.naukri.com',
            'rate_limit': 3.0,
            'enabled': True,
        },
        'shine': {
            'base_url': 'https://www.shine.com',
            'rate_limit': 2.0,
            'enabled': True,
        },
        'iimjobs': {
            'base_url': 'https://www.iimjobs.com',
            'rate_limit': 1.0,
            'enabled': True,
        },
    }
    
    # Read values from .env
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )
    
    # ==============================
    # COMPUTED PROPERTIES
    # ==============================
    
    @property
    def DATABASE_URL(self) -> str:
        """Construct PostgreSQL connection URL"""
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    @property
    def REDIS_URL(self) -> str:
        """Construct Redis connection URL"""
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @property
    def MONGO_URI(self) -> str:
        """Construct MongoDB connection URL"""
        if self.MONGO_USER and self.MONGO_PASSWORD:
            return f"mongodb://{self.MONGO_USER}:{self.MONGO_PASSWORD}@{self.MONGO_HOST}:{self.MONGO_PORT}/{self.MONGO_DB_NAME}"
        return f"mongodb://{self.MONGO_HOST}:{self.MONGO_PORT}/{self.MONGO_DB_NAME}"
    
    @property
    def RABBITMQ_URL(self) -> str:
        """Construct RabbitMQ connection URL"""
        return f"amqp://{self.RABBITMQ_USER}:{self.RABBITMQ_PASSWORD}@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}/"


# Create global settings instance
settings = Settings()