from pydantic import BaseSettings, SettingsConfigDict, Field

class Settings(BaseSettings):
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
    