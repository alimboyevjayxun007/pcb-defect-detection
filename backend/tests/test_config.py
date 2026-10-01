"""Settings/config.py uchun testlar — CORS parsing va model o'lcham mosligi."""
from app.core.config import settings


def test_cors_origins_has_no_blank_or_whitespace_entries():
    for origin in settings.CORS_ORIGINS:
        assert origin == origin.strip()
        assert origin != ""


def test_cors_origins_default_contains_localhost():
    assert "http://localhost:5173" in settings.CORS_ORIGINS
    assert "http://localhost:3000" in settings.CORS_ORIGINS


def test_inference_img_size_matches_trained_model():
    # backend/app/ml/best.pt imgsz=320'da train qilingan
    # (backend/training/results/TRAINING_REPORT.md). Standart qiymat
    # shunga mos bo'lishi kerak — aks holda train/inference o'lcham
    # nomuvofiqligi aniqlikni pasaytiradi.
    assert settings.INFERENCE_IMG_SIZE == 320
