"""InferenceService'ning sof (DB'siz) mantiqiy funksiyalari uchun unit testlar."""
import numpy as np

from app.services.inference import InferenceService


def test_verdict_from_detections_empty():
    assert InferenceService.verdict_from_detections([]) == "OK"


def test_verdict_from_detections_nonempty():
    dets = [{"defect_type": "spur", "confidence": 0.9, "bbox_x": 0, "bbox_y": 0, "bbox_w": 10, "bbox_h": 10}]
    assert InferenceService.verdict_from_detections(dets) == "NOK"


def test_is_ready_false_when_model_not_loaded():
    svc = InferenceService()
    assert svc.is_ready() is False


def test_predict_without_loaded_model_returns_empty_fast():
    svc = InferenceService()  # load_model() chaqirilmagan -> self.model is None
    image = np.zeros((64, 64, 3), dtype=np.uint8)

    detections, inference_ms = svc.predict(image)

    assert detections == []
    assert inference_ms >= 0
    # "Demo rejim" — model yo'q bo'lsa ham xato tashlamasligi kerak.


def test_get_instance_is_singleton():
    a = InferenceService.get_instance()
    b = InferenceService.get_instance()
    assert a is b


def test_draw_detections_draws_boxes_without_mutating_input():
    image = np.zeros((50, 50, 3), dtype=np.uint8)
    dets = [{"defect_type": "spur", "confidence": 0.77, "bbox_x": 5, "bbox_y": 5, "bbox_w": 10, "bbox_h": 10}]

    annotated = InferenceService.draw_detections(image, dets)

    assert annotated.shape == image.shape
    # Original rasm o'zgarmagan bo'lishi kerak (draw_detections .copy() ishlatadi)
    assert np.array_equal(image, np.zeros((50, 50, 3), dtype=np.uint8))
    # Annotatsiya qilingan rasmda chizilgan piksellar bo'lishi kerak
    assert not np.array_equal(annotated, image)
