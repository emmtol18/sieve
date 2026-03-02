from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://localhost:5432/neural_sieve_v3"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiry_days: int = 7
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    search_model: str = "gpt-4o-mini"
    host: str = "0.0.0.0"
    port: int = 8420
    sieve_api_url: str = "http://localhost:8420"
    sieve_api_key: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8420/auth/google/callback"

    model_config = {"env_prefix": "SIEVE_", "env_file": ".env"}


settings = Settings()
