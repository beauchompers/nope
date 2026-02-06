from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://nope:nope@localhost:5432/nope"
    secret_key: str = ""
    access_token_expire_minutes: int = 60  # 1 hour (reduced from 24h for security)
    edl_output_dir: str = "/app/edl"
    edl_base_url: str = ""  # e.g., "https://edl.example.com" - empty means use browser origin

    # Default credentials - usernames have defaults, passwords do not
    default_admin_user: str = "admin"
    default_admin_password: str = ""
    default_edl_user: str = "edl"
    default_edl_password: str = ""

    class Config:
        env_file = ".env"


def validate_settings(settings: Settings) -> None:
    """Validate settings at startup. Raises ValueError if invalid."""
    errors = []

    # Check secret key
    if not settings.secret_key:
        errors.append("SECRET_KEY is required")
    elif settings.secret_key == "change-me-in-production":
        errors.append("SECRET_KEY must be changed from the default value")

    # Check required passwords
    if not settings.default_admin_password:
        errors.append("DEFAULT_ADMIN_PASSWORD is required")
    else:
        from app.services.auth import validate_password_complexity

        try:
            validate_password_complexity(settings.default_admin_password)
        except ValueError as e:
            errors.append(f"DEFAULT_ADMIN_PASSWORD: {e}")

    if not settings.default_edl_password:
        errors.append("DEFAULT_EDL_PASSWORD is required")
    else:
        from app.services.auth import validate_password_complexity

        try:
            validate_password_complexity(settings.default_edl_password)
        except ValueError as e:
            errors.append(f"DEFAULT_EDL_PASSWORD: {e}")

    if errors:
        raise ValueError("Configuration errors:\n  - " + "\n  - ".join(errors))


settings = Settings()
