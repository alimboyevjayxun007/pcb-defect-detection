"""`/api/inspect/image` endpoint uchun integratsion testlar."""
import cv2
import numpy as np
import pytest

from app.routers.inspect import MAX_UPLOAD_BYTES


def _fake_jpeg_bytes(width: int = 64, height: int = 64) -> bytes:
    """Tasodifiy piksellardan kichik, haqiqiy dekodlanadigan JPEG yaratadi."""
    img = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    return buf.tobytes()


@pytest.mark.asyncio
async def test_inspect_image_success(async_client):
    files = {"file": ("board.jpg", _fake_jpeg_bytes(), "image/jpeg")}
    resp = await async_client.post("/api/inspect/image", files=files)

    assert resp.status_code == 200
    body = resp.json()
    # Testda model yuklanmagan (lifespan ishlamagan) — shuning uchun
    # InferenceService "demo" rejimida bo'sh natija qaytaradi -> har doim OK.
    assert body["verdict"] == "OK"
    assert body["detections"] == []
    assert body["mode"] == "single"
    assert body["image_url"].startswith("/api/inspect/result-image/")
    assert "id" in body


@pytest.mark.asyncio
async def test_inspect_image_empty_file_returns_400(async_client):
    files = {"file": ("empty.jpg", b"", "image/jpeg")}
    resp = await async_client.post("/api/inspect/image", files=files)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_inspect_image_corrupted_file_returns_400(async_client):
    files = {"file": ("bad.jpg", b"bu haqiqiy rasm emas, shunchaki matn", "image/jpeg")}
    resp = await async_client.post("/api/inspect/image", files=files)
    assert resp.status_code == 400
    assert "dekodlab" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_inspect_image_too_large_returns_413(async_client):
    oversized = b"\x00" * (MAX_UPLOAD_BYTES + 1)
    files = {"file": ("huge.jpg", oversized, "image/jpeg")}
    resp = await async_client.post("/api/inspect/image", files=files)
    assert resp.status_code == 413


@pytest.mark.asyncio
async def test_inspect_image_saved_and_retrievable_in_history(async_client):
    files = {"file": ("board.jpg", _fake_jpeg_bytes(), "image/jpeg")}
    create_resp = await async_client.post("/api/inspect/image", files=files)
    inspection_id = create_resp.json()["id"]

    list_resp = await async_client.get("/api/inspections")
    assert list_resp.status_code == 200
    ids = [item["id"] for item in list_resp.json()]
    assert inspection_id in ids

    detail_resp = await async_client.get(f"/api/inspections/{inspection_id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["id"] == inspection_id
