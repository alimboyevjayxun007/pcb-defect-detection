from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "model_loaded" in body


def test_defect_types_schema_import():
    # Modellar va sxemalar to'g'ri import bo'lishini tekshiradi
    from app.schemas.inspection import DefectTypeOut
    item = DefectTypeOut(name="mouse_bite", description="test")
    assert item.name == "mouse_bite"


def test_verdict_from_detections_empty():
    from app.services.inference import InferenceService
    assert InferenceService.verdict_from_detections([]) == "OK"


def test_verdict_from_detections_nonempty():
    from app.services.inference import InferenceService
    dets = [{"defect_type": "spur", "confidence": 0.9, "bbox_x": 0, "bbox_y": 0, "bbox_w": 10, "bbox_h": 10}]
    assert InferenceService.verdict_from_detections(dets) == "NOK"
