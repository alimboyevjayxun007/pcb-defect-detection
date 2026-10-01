"""
Inference service — YOLO modelini bitta marta xotiraga yuklaydi (singleton)
va rasm/frame ustida predict qiladi.

Nega singleton: har bir HTTP yoki WebSocket so'rovida modelni qayta yuklash
real-time ishlashni butunlay o'ldiradi (bir model yuklash 1-3 soniya vaqt oladi).
Shuning uchun model faqat ilova ishga tushganda (FastAPI startup event) bir marta
yuklanadi va butun ilova hayoti davomida xotirada qoladi.
"""
import logging
import time
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

from app.core.config import settings

logger = logging.getLogger("inference")


class InferenceService:
    _instance: "InferenceService | None" = None

    def __init__(self):
        self.model: YOLO | None = None
        self.class_names: dict[int, str] = {}

    @classmethod
    def get_instance(cls) -> "InferenceService":
        if cls._instance is None:
            cls._instance = InferenceService()
        return cls._instance

    def load_model(self):
        """Startup eventda chaqiriladi. Model vaznini diskdan o'qiydi."""
        model_path = Path(settings.MODEL_PATH)
        if not model_path.exists():
            logger.warning(
                "Model fayli topilmadi: %s — demo/placeholder rejimda ishga tushiriladi. "
                "Haqiqiy natija olish uchun train qilingan best.pt faylni shu yo'lga joylashtiring.",
                model_path,
            )
            self.model = None
            return

        self.model = YOLO(str(model_path))
        self.class_names = self.model.names
        logger.info("YOLO modeli yuklandi: %s, klasslar: %s", model_path, self.class_names)

    def is_ready(self) -> bool:
        return self.model is not None

    def predict(self, image: np.ndarray) -> tuple[list[dict], float]:
        """
        image: BGR numpy array (OpenCV formatida)
        Qaytaradi: (detections_list, inference_ms)
        """
        start = time.perf_counter()

        if self.model is None:
            # Model hali joylanmagan bo'lsa — bo'sh natija (OK) qaytaramiz,
            # bu backend va frontendni modelsiz ham sinash imkonini beradi.
            elapsed_ms = (time.perf_counter() - start) * 1000
            return [], elapsed_ms

        results = self.model.predict(
            source=image,
            conf=settings.CONFIDENCE_THRESHOLD,
            iou=settings.IOU_THRESHOLD,
            imgsz=settings.INFERENCE_IMG_SIZE,
            device=settings.DEVICE,
            verbose=False,
        )

        elapsed_ms = (time.perf_counter() - start) * 1000

        detections = []
        if results and len(results) > 0:
            boxes = results[0].boxes
            for box in boxes:
                xyxy = box.xyxy[0].tolist()  # [x1, y1, x2, y2]
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                cls_name = self.class_names.get(cls_id, str(cls_id))

                x1, y1, x2, y2 = xyxy
                detections.append(
                    {
                        "defect_type": cls_name,
                        "confidence": round(conf, 4),
                        "bbox_x": round(x1, 2),
                        "bbox_y": round(y1, 2),
                        "bbox_w": round(x2 - x1, 2),
                        "bbox_h": round(y2 - y1, 2),
                    }
                )

        return detections, elapsed_ms

    @staticmethod
    def verdict_from_detections(detections: list[dict]) -> str:
        return "NOK" if len(detections) > 0 else "OK"

    @staticmethod
    def draw_detections(image: np.ndarray, detections: list[dict]) -> np.ndarray:
        """Bounding box'larni rasm ustiga chizadi (REST /inspect/image uchun)."""
        annotated = image.copy()
        for det in detections:
            x1, y1 = int(det["bbox_x"]), int(det["bbox_y"])
            x2, y2 = int(det["bbox_x"] + det["bbox_w"]), int(det["bbox_y"] + det["bbox_h"])
            label = f'{det["defect_type"]} {det["confidence"]:.2f}'

            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 0, 255), 2)
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(annotated, (x1, y1 - th - 8), (x1 + tw + 4, y1), (0, 0, 255), -1)
            cv2.putText(
                annotated, label, (x1 + 2, y1 - 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA
            )
        return annotated


inference_service = InferenceService.get_instance()
