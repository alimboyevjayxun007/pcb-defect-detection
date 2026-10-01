import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DetectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    defect_type: str
    confidence: float
    bbox_x: float
    bbox_y: float
    bbox_w: float
    bbox_h: float


class InspectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    mode: str
    verdict: str
    inference_ms: float | None = None
    created_at: datetime
    image_url: str | None = None
    detections: list[DetectionOut] = []


class InspectionListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    mode: str
    verdict: str
    created_at: datetime
    defect_count: int = 0


class DefectTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    description: str | None = None


class LiveFramePayload(BaseModel):
    """Incoming message over the WebSocket for live detection."""
    image_base64: str


class LiveFrameResult(BaseModel):
    verdict: str
    inference_ms: float
    detections: list[DetectionOut]
