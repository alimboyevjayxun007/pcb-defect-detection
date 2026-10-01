import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, String, Uuid
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _utcnow() -> datetime:
    """`datetime.utcnow()` Python 3.12+'da deprecated — tz-aware olib,
    keyin naive'ga aylantiramiz (DB ustuni `DateTime(timezone=False)`)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class InspectionMode(str, enum.Enum):
    SINGLE = "single"
    LIVE = "live"


class Verdict(str, enum.Enum):
    OK = "OK"
    NOK = "NOK"


class Inspection(Base):
    __tablename__ = "inspections"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    image_path: Mapped[str] = mapped_column(String(500), nullable=True)
    mode: Mapped[InspectionMode] = mapped_column(
        SAEnum(InspectionMode, name="inspection_mode"), default=InspectionMode.SINGLE
    )
    verdict: Mapped[Verdict] = mapped_column(SAEnum(Verdict, name="verdict"))
    inference_ms: Mapped[float] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    detections: Mapped[list["Detection"]] = relationship(
        "Detection", back_populates="inspection", cascade="all, delete-orphan"
    )


class Detection(Base):
    __tablename__ = "detections"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    inspection_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("inspections.id", ondelete="CASCADE")
    )
    defect_type: Mapped[str] = mapped_column(String(50))
    confidence: Mapped[float] = mapped_column(Float)
    bbox_x: Mapped[float] = mapped_column(Float)
    bbox_y: Mapped[float] = mapped_column(Float)
    bbox_w: Mapped[float] = mapped_column(Float)
    bbox_h: Mapped[float] = mapped_column(Float)

    inspection: Mapped["Inspection"] = relationship(
        "Inspection", back_populates="detections"
    )


class DefectType(Base):
    __tablename__ = "defect_types"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    description: Mapped[str] = mapped_column(String(500), nullable=True)
