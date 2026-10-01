import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.models.inspection import DefectType, Detection, Inspection
from app.schemas.inspection import DefectTypeOut, DetectionOut, InspectionListItem, InspectionOut

router = APIRouter(prefix="/api", tags=["history"])


@router.get("/inspections", response_model=list[InspectionListItem])
async def list_inspections(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(
            Inspection.id,
            Inspection.mode,
            Inspection.verdict,
            Inspection.created_at,
            func.count(Detection.id).label("defect_count"),
        )
        .outerjoin(Detection, Detection.inspection_id == Inspection.id)
        .group_by(Inspection.id)
        .order_by(Inspection.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(stmt)).all()
    return [
        InspectionListItem(
            id=r.id, mode=r.mode.value, verdict=r.verdict.value,
            created_at=r.created_at, defect_count=r.defect_count,
        )
        for r in rows
    ]


@router.get("/inspections/{inspection_id}", response_model=InspectionOut)
async def get_inspection(inspection_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    stmt = (
        select(Inspection)
        .where(Inspection.id == inspection_id)
        .options(selectinload(Inspection.detections))
    )
    inspection = (await db.execute(stmt)).scalar_one_or_none()
    if inspection is None:
        raise HTTPException(status_code=404, detail="Tekshiruv topilmadi")

    filename = inspection.image_path.split("/")[-1] if inspection.image_path else None
    return InspectionOut(
        id=inspection.id,
        mode=inspection.mode.value,
        verdict=inspection.verdict.value,
        inference_ms=inspection.inference_ms,
        created_at=inspection.created_at,
        image_url=f"/api/inspect/result-image/{filename}" if filename else None,
        detections=[DetectionOut.model_validate(d) for d in inspection.detections],
    )


@router.get("/inspect/result-image/{filename}")
async def get_result_image(filename: str):
    path = f"{settings.RESULT_DIR}/{filename}"
    return FileResponse(path, media_type="image/jpeg")


@router.get("/defect-types", response_model=list[DefectTypeOut])
async def list_defect_types(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(DefectType))).scalars().all()
    return [DefectTypeOut.model_validate(r) for r in rows]
