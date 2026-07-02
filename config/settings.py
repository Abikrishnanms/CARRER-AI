from pydantic_settings import BaseSettings,SettingsConfigDict

class Settings(BaseSettings):
    """
    Central configuration class for CareerAI.
    Loads configuration values from the .env file.

    """
    #==============================
    #Application Settings
    #==============================

    APP_NAME: str = "CareerAI"
    APP_ENV:  str = "development"
    DEBUG: bool = True

    #=============================
    #POSTGRESQL
    #=============================

    DB_HOST: str
    DB_PORT: int
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str

    #=============================
    #REDIS
    #=============================

    REDIS_HOST: str
    REDIS_PORT: str

    #============================
    #RABBITMQ
    #============================

    RABBITMQ_HOST: str
    RABBITMQ_PORT: int
    RABBITMQ_USER: str
    RABBITMQ_PASSWORD: str

       # Read values from .env
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )


settings = Settings()