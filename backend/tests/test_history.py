"""`/api/inspections`, `/api/defect-types` endpointlari uchun testlar."""
import uuid

import pytest

from app.models.inspection import DefectType


@pytest.mark.asyncio
async def test_list_inspections_empty(async_client):
    resp = await async_client.get("/api/inspections")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_inspection_not_found_returns_404(async_client):
    resp = await async_client.get(f"/api/inspections/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_defect_types_empty_without_seed(async_client):
    # Testlarda Alembic migratsiyasi ishlatilmaydi (Base.metadata.create_all
    # orqali yaratiladi), shuning uchun seed qator yo'q — bu kutilgan holat.
    resp = await async_client.get("/api/defect-types")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_defect_types_returns_seeded_rows(async_client, db_session):
    db_session.add(DefectType(name="spur", description="test nuqson"))
    await db_session.commit()

    resp = await async_client.get("/api/defect-types")
    assert resp.status_code == 200
    names = [d["name"] for d in resp.json()]
    assert "spur" in names
