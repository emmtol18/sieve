from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://localhost:5432/neural_sieve_v3"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiry_days: int = 7
    fuel_api_key: str = ""
    fuel_api_base: str = "https://api.fuel1.ai/v1"
    fuel_model: str = "openai/gpt-oss-120b:eu"
    fuel_search_model: str = "openai/gpt-oss-120b:eu"
    host: str = "localhost"
    port: int = 8421
    user_email: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8421/auth/google/callback"
    cors_origins: str = "http://localhost:8421"

    model_config = {"env_prefix": "SIEVE_", "env_file": ".env"}


settings = Settings()
