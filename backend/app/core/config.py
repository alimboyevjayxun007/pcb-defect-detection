import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App
    APP_NAME: str = "PCB Defect Detection API"
    ENV: str = os.getenv("ENV", "development")
    DEBUG: bool = ENV != "production"

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://pcb_user:pcb_password@db:5432/pcb_defects",
    )

    # ML model
    MODEL_PATH: str = os.getenv("MODEL_PATH", "app/ml/best.pt")
    CONFIDENCE_THRESHOLD: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.35"))
    IOU_THRESHOLD: float = float(os.getenv("IOU_THRESHOLD", "0.45"))
    # Model backend/app/ml/best.pt imgsz=320'da train qilingan (TRAINING_REPORT.md).
    # Standart qiymat shu bilan mos bo'lishi kerak — aks holda train/inference
    # o'lcham nomuvofiqligi aniqlik pasayishiga olib kelishi mumkin.
    INFERENCE_IMG_SIZE: int = int(os.getenv("INFERENCE_IMG_SIZE", "320"))
    DEVICE: str = os.getenv("DEVICE", "cpu")  # "cpu" | "cuda:0"

    # Storage
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "app/storage/uploads")
    RESULT_DIR: str = os.getenv("RESULT_DIR", "app/storage/results")

    # CORS
    CORS_ORIGINS: list[str] = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS", "http://localhost:5173,http://localhost:3000"
        ).split(",")
        if origin.strip()
    ]

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()

os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.RESULT_DIR, exist_ok=True)
