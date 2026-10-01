# PCB Defect Detection

PCB (bosma elektron plata)larning **yaroqli/yaroqsiz** ekanligini aniqlaydigan,
nuqsonning turi va joylashuvini ko'rsatadigan to'liq stack ilova.
Ham **bitta yuklangan rasm** orqali, ham **real-time kamera oqimi** orqali ishlaydi.

## Stack

| Qatlam | Texnologiya |
|---|---|
| ML / CV | YOLOv8 (Ultralytics), OpenCV |
| Backend | FastAPI, SQLAlchemy (async), Alembic, WebSocket |
| Frontend | React 18 + TypeScript, Vite, TailwindCSS, React Query |
| Ma'lumotlar bazasi | PostgreSQL 16 |
| Konteynerlash | Docker, docker-compose (multi-stage build) |
| CI/CD | GitHub Actions → GHCR → SSH deploy |

## Arxitektura

```
┌─────────────┐      REST (/api/inspect/image)       ┌──────────────┐
│   React     │ ───────────────────────────────────▶ │   FastAPI    │
│  (nginx)    │                                       │   backend    │
│             │ ◀──────── WebSocket (/api/inspect/live) ──────────── │
└─────────────┘                                       └──────┬───────┘
                                                               │
                                               ┌───────────────┼───────────────┐
                                               ▼               ▼               
                                        ┌─────────────┐  ┌──────────┐
                                        │ YOLO model  │  │PostgreSQL│
                                        │ (singleton) │  │          │
                                        └─────────────┘  └──────────┘
```

**Asosiy mantiq:** bitta YOLO object-detection modeli rasmda nuqsonlarni (bounding box +
klass + ishonch darajasi) topadi. Agar kamida bitta nuqson topilsa → `NOK` (yaroqsiz),
aks holda → `OK` (yaroqli). Model backend ishga tushganda (`startup` eventda) **bir marta**
xotiraga yuklanadi — bu real-time ishlash uchun kritik muhim.

## Tezkor ishga tushirish (Docker)

```bash
cp .env.example .env
# .env faylini tahrirlang (parollar va h.k.)

docker compose up -d --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000/docs (Swagger)
- PostgreSQL: localhost:5432

Birinchi marta ishga tushganda `alembic upgrade head` avtomatik bajariladi
(jadvallar yaratiladi + `defect_types` katalogi to'ldiriladi).

### Agar build "resolving provenance for metadata file" bosqichida osilib qolsa

Bu Docker Buildx'ning attestatsiya bosqichi — ba'zi tarmoq sharoitida juda sekin
yoki cheksiz kutishi mumkin (ma'lum Docker Desktop muammosi). `docker-compose.yml`da
`provenance: false` va `sbom: false` allaqachon o'rnatilgan, shuning uchun odatda
muammo chiqmasligi kerak. Agar Compose versiyangiz bu kalitlarni tanimasa
(`Additional property provenance is not allowed` xatosi) yoki yana osilib qolsa:

```bash
export BUILDX_NO_DEFAULT_ATTESTATIONS=1
docker compose up -d --build
```

yoki Docker Desktop'ni yangilang (`docker --version` — 24+ tavsiya etiladi).

## Model — allaqachon train qilingan va joylashtirilgan ✅

`backend/app/ml/best.pt` — bu repo ichida **haqiqatan train qilingan YOLOv8n model**
mavjud (demo/placeholder emas). PKU PCB-DATASET asosida (600×600 tile'larga kesilgan,
5,369 tile, 10 ta noyob fizik plata), 25 epoch, CPU'da train qilindi.

**Natija (test set — mutlaqo ko'rilmagan plata): mAP50 = 0.85, Precision = 0.84, Recall = 0.88.**

Bu ikkinchi, tuzatilgan versiya: birinchi urinishda **board-level data leakage**
aniqlanib (split fizik plata emas, tasodifiy rasm darajasida qilingan edi),
tuzatildi va plata darajasida qat'iy ajratilgan holda qayta train qilindi — shuning
uchun bu safar natija **xolis va ishonchli**. To'liq jarayon, val/test farqining
tahlili va klass-bo'yicha cheklovlar: `backend/training/results/TRAINING_REPORT.md`
(albatta o'qib chiqing — u yerda qaysi klasslar ishonchli, qaysi biri emasligi
batafsil yozilgan).

Ya'ni `docker compose up -d --build` qilishingiz bilan tizim **darhol real aniqlash
bilan ishlaydi** — qo'shimcha train qilish shart emas, lekin yaxshilash ixtiyoriy.

### O'zingiz qayta train qilmoqchi bo'lsangiz (to'liq qo'llanma: `backend/training/`)

`yolo detect train data=pcb_defects.yaml ...` to'g'ridan-to'g'ri ishlamaydi — bu fayl
avtomatik yaratilmaydi, uni dataset bilan birga olish kerak. To'liq qadamlar
`backend/training/README.md`'da yozilgan, qisqacha:

```bash
cd backend/training
pip install -r requirements.txt        # ultralytics + roboflow

# 1) Dataset yuklab olish (Roboflow API key kerak, bepul)
export ROBOFLOW_API_KEY=sizning_kalitingiz
python download_dataset.py             # data.yaml bilan birga yuklaydi

# 2) Train qilish — natija avtomatik ../app/ml/best.pt ga ko'chiriladi
python train.py --data "Obj-detection-pcb-defects-yolov8-1/data.yaml" --epochs 100

# 3) Backendni qayta ishga tushirish
docker compose up -d --build backend
```

GPU'siz kompyuterda train sekin ishlaydi — shuning uchun `backend/training/train_colab.ipynb`
tayyor qilingan: Google Colab'ga yuklab, bepul GPU bilan 100 epoch ~15-25 daqiqada tugaydi.

Tavsiya etilgan dataset: **Augmented PCB Defect** (Roboflow/DatasetNinja, 10,668 rasm,
6 klass: mouse_bite, missing_hole, spurious_copper, spur, open_circuit, short) — YOLO
formatida to'g'ridan-to'g'ri export qilinadi.

## Lokal rivojlantirish (Docker'siz)

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

export DATABASE_URL="postgresql+asyncpg://pcb_user:pcb_password@localhost:5432/pcb_defects"
alembic upgrade head

uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Testlar

```bash
# Backend — 22 test (unit + integratsion, xotiradagi SQLite bilan)
cd backend
DATABASE_URL="sqlite+aiosqlite:///./test.db" pytest -v

# Frontend — 6 test (Vitest)
cd frontend
npm run lint && npm run test && npm run build
```

To'liq test ro'yxati va nima tekshirilgani: `INFO.md` → "Testlar" bo'limi.

## CI/CD

`.github/workflows/ci-cd.yml` quyidagi bosqichlarni bajaradi:

1. **Lint & test** — backend (ruff + pytest) va frontend (eslint + tsc + build) parallel
2. **Docker build & push** — `main`/`develop`'ga push bo'lganda, image'lar GHCR'ga push qilinadi
3. **Deploy** — faqat `main` branch uchun, SSH orqali production serverga
   `docker compose pull && up -d` qilinadi

Kerakli GitHub Secrets: `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY` (production deploy uchun).

## Production

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

`docker-compose.prod.yml` — DB portini tashqariga ochmaydi, GHCR'dan tayyor image
pull qiladi (local build qilmaydi), resurs limitlarini qo'yadi, `--reload` o'rniga
`--workers 2` bilan ishga tushadi.

## Loyiha strukturasi

```
pcb-defect-detection/
├── backend/
│   ├── app/
│   │   ├── core/          → config, database
│   │   ├── models/        → SQLAlchemy modellari
│   │   ├── schemas/       → Pydantic sxemalar
│   │   ├── services/      → inference.py (YOLO wrapper, singleton)
│   │   ├── routers/       → inspect.py (REST+WS), history.py
│   │   └── main.py
│   ├── alembic/           → DB migratsiyalar
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/    → ImageUpload, LiveDetection, DetectionCanvas, VerdictBadge
│   │   ├── hooks/         → useLiveInspection (WebSocket)
│   │   ├── api/           → client.ts
│   │   └── types/
│   ├── Dockerfile
│   └── nginx.conf
├── .github/workflows/ci-cd.yml
├── docker-compose.yml
└── docker-compose.prod.yml
```

## API endpointlari

| Method | Endpoint | Tavsif |
|---|---|---|
| `POST` | `/api/inspect/image` | Bitta rasmni yuklab tahlil qilish |
| `WS` | `/api/inspect/live` | Real-time frame-by-frame aniqlash |
| `GET` | `/api/inspections` | Tekshiruvlar tarixi |
| `GET` | `/api/inspections/{id}` | Bitta tekshiruv tafsiloti |
| `GET` | `/api/inspect/result-image/{filename}` | Annotatsiya qilingan rasm |
| `GET` | `/api/defect-types` | Nuqson turlari katalogi |
| `GET` | `/api/health` | Health-check (model yuklangani, env) |
