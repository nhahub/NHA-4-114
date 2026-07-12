"""
config.py
─────────
All application configuration loaded from environment variables (or .env).

Pattern: import settings from here — never read os.environ directly in other modules.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",          # ignore unknown env vars (e.g. NEXT_PUBLIC_*, POSTGRES_USER)
    )

    # ── Database ───────────────────────────────────────────────────────────────
    POSTGRES_URL: str = "postgresql+asyncpg://svs:svs@localhost:5432/svs"

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── AI model ──────────────────────────────────────────────────────────────
    MODEL_PATH: str = "models/yolov8n.pt"
    WEAPON_MODEL_PATH: str = "models/runs/weapon_detection_v1/weights/best.pt"
    WEAPON_IMGSZ: int = 416

    # ── Object storage ────────────────────────────────────────────────────────
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "svs-media"

    # ── Server ────────────────────────────────────────────────────────────────
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ── CORS ──────────────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # ── Worker ────────────────────────────────────────────────────────────────
    MAX_FPS: int = 15
    JPEG_QUALITY: int = 75

    # ── JWT Authentication ─────────────────────────────────────────────────────
    JWT_SECRET_KEY: str = "change-me-in-production-min-32-chars"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 8

    # ── First superuser (seeded automatically on first startup) ───────────────
    FIRST_SUPERUSER: str = "admin"
    FIRST_SUPERUSER_PASSWORD: str = "changeme"


settings = Settings()