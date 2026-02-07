from pydantic import BaseSettings, SettingsConfigDict, Field

class Settings(BaseSettings):
    db_user: str
    db_port: int
    db_name: str
    db_password: str
    db_host: str
    DATABASE_URL: str
    api_key: str
    AV_KEY: str
    TAVILY_API_KEY: str
    SECRET_KEY: str
    model_config = SettingsConfigDict(
        env_file = ".env",
        extra = "ignore"
    )

def get_settings():
    return Settings()
    