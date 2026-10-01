"""Pytest fixtures — testlar uchun xotiradagi (in-memory) SQLite DB va
async HTTP klient tayyorlaydi. Haqiqiy PostgreSQL yoki og'ir YOLO modelini
yuklash shart emas: InferenceService lifespan orqali yuklanmagani uchun
`model=None` holatida qoladi, bu esa predict() ni tez va deterministik
(doim bo'sh natija) qiladi — demo rejim sifatida kodning o'zida mo'ljallangan.
"""
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app


@pytest_asyncio.fixture
async def async_client():
    # StaticPool + check_same_thread=False: aiosqlite ":memory:" bazasi
    # standart holatda har bir yangi connection uchun ALOHIDA (bo'sh) baza
    # ochadi. StaticPool bitta connection'ni butun test davomida qayta
    # ishlatadi — shuning uchun turli session'lar (masalan, so'rov qiluvchi
    # AsyncClient va alohida db_session fixture'i) bitta xotiradagi bazani
    # ko'radi, aks holda "no such table" xatosi chiqardi.
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        future=True,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    TestSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def _get_db_override():
        async with TestSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db_override

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(async_client):  # noqa: ARG001 — async_client DB'ni tayyorlaydi
    """async_client fixture'i orqali yaratilgan bazaga to'g'ridan-to'g'ri
    yozish kerak bo'lgan testlar uchun (masalan, defect_types seed qilish)."""
    override = app.dependency_overrides[get_db]
    async for session in override():
        yield session
        break
