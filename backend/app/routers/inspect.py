import base64
import logging
import uuid

import cv2
import numpy as np
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.database import get_db
from app.models.inspection import Detection, Inspection, InspectionMode, Verdict
from app.schemas.inspection import DetectionOut, InspectionOut, LiveFrameResult
from app.services.inference import inference_service

router = APIRouter(prefix="/api/inspect", tags=["inspect"])
logger = logging.getLogger("inspect")

# 15 MB — bundan katta fayl darhol rad etiladi (noto'g'ri/hujum maqsadli
# ulkan fayllar serverni band qilib qo'yishining oldini oladi)
MAX_UPLOAD_BYTES = 15 * 1024 * 1024


def _decode_image(raw_bytes: bytes) -> np.ndarray:
    arr = np.frombuffer(raw_bytes, dtype=np.uint8)
    image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Rasmni dekodlab bo'lmadi — fayl buzilgan yoki formati noto'g'ri")
    return image


def _run_inference_and_annotate(image: np.ndarray, result_path: str):
    """CPU-og'ir qismlar (YOLO predict + rasm chizish/yozish) — bu funksiya
    threadpool'da chaqiriladi, shuning uchun asyncio event loop'ni
    blocklamaydi (boshqa parallel so'rovlar/WS mijozlari kutib qolmaydi)."""
    detections, inference_ms = inference_service.predict(image)
    verdict = inference_service.verdict_from_detections(detections)
    annotated = inference_service.draw_detections(image, detections)
    cv2.imwrite(result_path, annotated)
    return detections, inference_ms, verdict


@router.post("/image", response_model=InspectionOut)
async def inspect_image(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Bitta yuklangan rasmni tahlil qiladi: YOLO bilan predict, natijani DB'ga saqlaydi,
    annotatsiya qilingan rasmni diskka yozadi va to'liq natijani qaytaradi."""
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Bo'sh fayl yuklandi")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Fayl juda katta (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB)",
        )

    try:
        image = _decode_image(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    inspection_id = uuid.uuid4()
    filename = f"{inspection_id}.jpg"
    result_path = f"{settings.RESULT_DIR}/{filename}"

    # Og'ir CPU ishini (inference + rasm yozish) threadpool'ga chiqaramiz —
    # aks holda bu chaqiriq butun FastAPI event loop'ni (demak, boshqa barcha
    # so'rovlarni ham) o'z vaqtiga qadar blocklab qo'yadi.
    detections, inference_ms, verdict = await run_in_threadpool(
        _run_inference_and_annotate, image, result_path
    )

    inspection = Inspection(
        id=inspection_id,
        image_path=result_path,
        mode=InspectionMode.SINGLE,
        verdict=Verdict(verdict),
        inference_ms=inference_ms,
    )
    db.add(inspection)
    await db.flush()

    for det in detections:
        db.add(Detection(inspection_id=inspection_id, **det))

    await db.commit()
    await db.refresh(inspection, attribute_names=["detections"])

    return InspectionOut(
        id=inspection.id,
        mode=inspection.mode.value,
        verdict=inspection.verdict.value,
        inference_ms=inspection.inference_ms,
        created_at=inspection.created_at,
        image_url=f"/api/inspect/result-image/{filename}",
        detections=[DetectionOut.model_validate(d) for d in inspection.detections],
    )


@router.websocket("/live")
async def inspect_live(websocket: WebSocket):
    """Real-time aniqlash uchun WebSocket oqimi.

    Frontend kameradan olingan har bir frame'ni base64 JPEG sifatida yuboradi,
    backend YOLO bilan predict qiladi va natijani (verdikt + box'lar) darhol qaytaradi.
    DB'ga yozish bu yerda amalga oshirilmaydi (tezlik uchun) — faqat canli overlay.
    """
    await websocket.accept()
    logger.info("Live inspection WebSocket ulandi")
    try:
        while True:
            payload = await websocket.receive_json()
            image_b64 = payload.get("image_base64", "")

            try:
                raw = base64.b64decode(image_b64.split(",")[-1])
                image = _decode_image(raw)
            except Exception as exc:
                await websocket.send_json({"error": f"Frame dekodlanmadi: {exc}"})
                continue

            # Threadpool'da — bitta mijozning og'ir frame'i boshqa ulangan
            # mijozlar yoki REST so'rovlarini bloklamasligi uchun.
            detections, inference_ms = await run_in_threadpool(
                inference_service.predict, image
            )
            verdict = inference_service.verdict_from_detections(detections)

            result = LiveFrameResult(
                verdict=verdict,
                inference_ms=round(inference_ms, 2),
                detections=[DetectionOut(**d) for d in detections],
            )
            await websocket.send_json(result.model_dump())
    except WebSocketDisconnect:
        logger.info("Live inspection WebSocket uzildi")
