import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.routers import history, inspect
from app.services.inference import inference_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Ilova ishga tushmoqda — YOLO modeli yuklanmoqda...")
    inference_service.load_model()
    yield
    logger.info("Ilova to'xtatilmoqda.")


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(inspect.router)
app.include_router(history.router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Kutilmagan (handle qilinmagan) xatoliklarni toza JSON javobga aylantiradi.
    Bu bo'lmasa, mijozga xom Python stack trace (ichki fayl yo'llari, kod
    tafsilotlari) chiqib ketishi mumkin edi — xavfsizlik va UX nuqtai nazaridan
    noto'g'ri."""
    logger.exception("Kutilmagan xatolik: %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Serverda kutilmagan xatolik yuz berdi"},
    )


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "model_loaded": inference_service.is_ready(),
        "env": settings.ENV,
    }
