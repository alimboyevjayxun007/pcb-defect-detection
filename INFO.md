# INFO.md — PCB Defect Detection: to'liq texnik hujjat

Bu fayl loyihadagi **har bir backend va frontend fayli**, ulardagi **har bir funksiya**,
ularning bir-biriga qanday ta'sir qilishi, va **model qanday tayyorlanganini** batafsil
tushuntiradi. Hujjat oxirida halol "kuchli/zaif tomonlar" bo'limi ham bor.

---

## 1. Umumiy oqim (request lifecycle)

```
Foydalanuvchi (browser)
   │
   ├─ Rasm yuklash:  POST /api/inspect/image  (multipart/form-data)
   │      React (ImageUpload.tsx) -> axios (client.ts) -> nginx -> FastAPI (inspect.py)
   │      -> InferenceService.predict() -> DB yozish -> annotatsiya rasm saqlash -> javob
   │
   └─ Real-time:     WS /api/inspect/live
          React (LiveDetection.tsx) -> useLiveInspection.ts -> nginx (ws proxy) -> FastAPI
          -> har bir frame uchun InferenceService.predict() -> DB'siz, faqat javob
```

Model backend ishga tushgan zahoti (`main.py`dagi `lifespan`) **bir marta** xotiraga
yuklanadi va butun process hayoti davomida saqlanadi (`InferenceService` singleton) —
har bir so'rovda qayta yuklanmaydi.

---

## 2. BACKEND — fayl va funksiya darajasida

### `backend/app/main.py`
FastAPI ilovasining kirish nuqtasi.

- `lifespan(app)` — async context manager. Server ishga tushganda
  `inference_service.load_model()`ni chaqiradi (model diskdan RAM'ga o'qiladi),
  server to'xtaganda log yozadi. FastAPI'ning `lifespan=` parametriga uzatiladi —
  bu "startup/shutdown event" ning zamonaviy ekvivalenti.
- `app = FastAPI(...)` — ilova obyekti, `lifespan` bilan bog'langan.
- `CORSMiddleware` — `settings.CORS_ORIGINS` ro'yxatidagi domenlardan kelgan
  so'rovlarga ruxsat beradi (frontend boshqa portda ishlaganda zarur).
- `app.include_router(inspect.router)` / `history.router` — ikkita router modulini
  asosiy ilovaga ulaydi.
- `unhandled_exception_handler(request, exc)` — **yangi qo'shilgan global
  exception handler**. Oldin har qanday kutilmagan Python xatoligi (masalan,
  kutilmagan `None` yoki tashqi kutubxona xatosi) mijozga xom stack trace
  bilan 500 qaytarardi. Endi bu handler uni ushlab, serverda to'liq log
  yozadi (`logger.exception`) va mijozga faqat toza `{"detail": "..."}`
  xabarini qaytaradi — ichki tafsilotlar tashqariga chiqmaydi.
- `health()` — `GET /api/health`. Model yuklangan-yuklanmaganini (`is_ready()`) va
  joriy environment'ni qaytaradi. **Eslatma**: model yuklanmagan bo'lsa ham status
  200 qaytaradi — Docker healthcheck buni "sog'lom" deb hisoblaydi, garchi aniqlash
  ishlamasa ham.

### `backend/app/core/config.py`
Pydantic `BaseSettings` orqali barcha konfiguratsiya (`.env`dan yoki environment
o'zgaruvchilaridan o'qiladi):

- `DATABASE_URL`, `MODEL_PATH`, `CONFIDENCE_THRESHOLD` (0.35), `IOU_THRESHOLD` (0.45),
  `INFERENCE_IMG_SIZE` (640 — **modelning o'zi 320'da train qilingan, pastda izoh
  bor**), `DEVICE` (cpu/cuda), `UPLOAD_DIR`, `RESULT_DIR`, `CORS_ORIGINS`.
- Modul yuklanganda `os.makedirs(...)` orqali upload/result papkalarini avtomatik
  yaratadi — bu import vaqtida side-effect, odatda yomon amaliyot hisoblanadi
  (import qilish fayl tizimiga yozishga olib kelmasligi kerak), lekin bu loyiha
  hajmida amaliy zarar keltirmaydi.

### `backend/app/core/database.py`
Async SQLAlchemy sozlamalari.

- `engine` — `create_async_engine(DATABASE_URL, echo=DEBUG)`. `echo=DEBUG` degani:
  development muhitida **har bir SQL so'rovi konsolga chop etiladi** (debugging uchun
  foydali, production'da performance uchun zararli — lekin `ENV=production`da
  `DEBUG=False` bo'lib avtomatik o'chadi).
- `AsyncSessionLocal` — session factory, `expire_on_commit=False` (commit'dan keyin
  obyektlar "stale" bo'lib qolmaydi, javobda ishlatish mumkin).
- `Base` — barcha ORM modellari meros oladigan asos klass.
- `get_db()` — FastAPI dependency generator: har bir so'rov uchun yangi session ochadi,
  so'rov tugagach yopadi (`finally: await session.close()`).

### `backend/app/models/inspection.py`
SQLAlchemy ORM jadvallari (3 ta):

- `InspectionMode` (enum: `single`/`live`), `Verdict` (enum: `OK`/`NOK`).
- `Inspection` — bitta tekshiruv yozuvi: `id` (UUID), `image_path`, `mode`, `verdict`,
  `inference_ms`, `created_at`, va `detections` (bir-ko'pga bog'lanish,
  `cascade="all, delete-orphan"` — Inspection o'chirilsa, uning Detection'lari ham
  avtomatik o'chadi).
- `Detection` — bitta topilgan nuqson: `defect_type`, `confidence`, va bbox'ning
  x/y/w/h koordinatalari (piksellarda, **normallashtirilmagan** — rasmning original
  o'lchamiga bog'liq; shuning uchun frontend ko'rsatishda original o'lchamni bilishi
  kerak).
- `DefectType` — statik katalog jadvali (6 qator, migratsiyada seed qilingan):
  mouse_bite, missing_hole, spurious_copper, spur, open_circuit, short.

### `backend/app/schemas/inspection.py`
Pydantic sxemalar — ORM obyektlarini JSON javobga aylantirish uchun
(`model_config = ConfigDict(from_attributes=True)` orqali ORM obyektidan to'g'ridan-
to'g'ri o'qiydi):

- `DetectionOut`, `InspectionOut`, `InspectionListItem`, `DefectTypeOut` — chiqish
  sxemalari.
- `LiveFramePayload` — WebSocket orqali kiruvchi xabar shakli (`image_base64`).
- `LiveFrameResult` — WebSocket orqali chiquvchi javob shakli.

### `backend/app/services/inference.py` — **eng muhim fayl**
`InferenceService` — YOLO modelini boshqaradigan singleton klass.

- `get_instance()` — classmethod, klassik singleton pattern (`_instance` statik
  o'zgaruvchida saqlanadi). Modul oxirida `inference_service = InferenceService.get_instance()`
  orqali global yagona nusxa yaratiladi — butun ilova shu bitta obyektni import qiladi.
- `load_model()` — `MODEL_PATH`dan `ultralytics.YOLO(...)`ni yuklaydi, `class_names`ni
  saqlaydi. Agar fayl topilmasa — xatolik tashlamaydi, shunchaki `self.model = None`
  qilib "demo rejim"da davom etadi (predict har doim bo'sh natija qaytaradi).
- `is_ready()` — model yuklanganini tekshiradi (`/api/health` shuni ishlatadi).
- `predict(image)` — **asosiy inference funksiyasi**. OpenCV BGR numpy array qabul
  qiladi, `model.predict(conf=0.35, iou=0.45, imgsz=320, device="cpu")` chaqiradi
  (`imgsz` endi model train qilingan o'lcham — 320 — bilan mos, oldin standart
  640 edi), natijadagi har bir box'ni oddiy `dict`ga aylantiradi (`defect_type`,
  `confidence`, `bbox_x/y/w/h`). Vaqtni `time.perf_counter()` bilan o'lchab
  `inference_ms` qaytaradi. **Muhim**: bu funksiya o'zi hali ham **sinxron va
  CPU-og'ir** — lekin endi uni chaqiruvchi router (`inspect.py`) buni
  `run_in_threadpool` orqali chaqiradi, shuning uchun asyncio event loop'ni
  endi blocklamaydi (tuzatilgan bug, pastga qarang).
- `verdict_from_detections(detections)` — static method. Mantiq juda sodda:
  `len(detections) > 0 -> "NOK"`, aks holda `"OK"`. Ya'ni **bironta nuqson topilsa
  (hatto past ishonch darajasida bo'lsa ham, threshold'dan o'tgan bo'lsa) — plata
  butunlay "yaroqsiz" deb belgilanadi**. Klasslar orasida og'irlik farqi yo'q (masalan,
  `spur`ning past precision'i hisobga olinmaydi).
- `draw_detections(image, detections)` — OpenCV orqali rasm ustiga qizil
  to'rtburchak + label chizadi (`cv2.rectangle`, `cv2.putText`). Faqat REST
  `/inspect/image` yo'lida ishlatiladi (annotatsiya qilingan faylni diskka saqlash
  uchun) — real-time WS yo'lida ishlatilmaydi, chunki bbox chizish frontendda
  (`DetectionCanvas.tsx`) canvas orqali bajariladi (tezroq, server yukini kamaytiradi).

### `backend/app/routers/inspect.py`
Ikkita asosiy endpoint.

- `MAX_UPLOAD_BYTES` — 15 MB chegara (yangi qo'shildi) — bundan katta fayl
  darhol `413`bilan rad etiladi.
- `_decode_image(raw_bytes)` — xom baytlarni `cv2.imdecode` orqali OpenCV rasmiga
  aylantiradi, muvaffaqiyatsiz bo'lsa `ValueError` tashlaydi.
- `_run_inference_and_annotate(image, result_path)` — **yangi qo'shilgan
  yordamchi funksiya**. `predict()` + `verdict_from_detections()` +
  `draw_detections()` + `cv2.imwrite()`ni bir joyga jamlaydi va bu funksiyaning
  o'zi `run_in_threadpool` orqali chaqiriladi — CPU-og'ir qismlar endi
  FastAPI'ning asyncio event loop'ini blocklamaydi (**tuzatilgan eng jiddiy
  bug**: oldin bu kod to'g'ridan-to'g'ri `async def` ichida chaqirilardi,
  bitta inference davomida butun server — barcha boshqa so'rovlar va WS
  mijozlari — muzlab qolardi).
- `inspect_image(file, db)` — `POST /api/inspect/image`:
  1. Faylni o'qiydi; bo'sh (`400`) yoki 15MB'dan katta (`413`) bo'lsa rad etadi.
  2. `_decode_image`ni `try/except` bilan chaqiradi — dekodlash xatosi endi
     xom 500 emas, toza `HTTPException(400, ...)` qaytaradi (tuzatildi).
  3. `_run_inference_and_annotate`ni threadpool'da chaqiradi (yuqoridagi fix).
  4. `Inspection` va har bir `Detection` qatorini DB'ga yozadi (`db.flush()` —
     commit'dan oldin ID'larni olish uchun).
  5. To'liq `InspectionOut` javobini qaytaradi, ichida `image_url` — annotatsiya
     qilingan rasmni keyinroq olish uchun yo'l.
- `inspect_live(websocket)` — `WS /api/inspect/live`:
  - `websocket.accept()` bilan ulanishni ochadi, keyin cheksiz tsiklda
    `receive_json()` orqali frame kutadi.
  - Har bir frame: base64'dan dekodlanadi (`,` belgisidan keyingi qism olinadi —
    `data:image/jpeg;base64,...` prefiksini kesib tashlash uchun), `predict()`
    endi **shu yerda ham `run_in_threadpool` orqali** chaqiriladi — bitta
    og'ir frame boshqa ulangan mijozlarni yoki REST so'rovlarini bloklamaydi
    (tuzatildi), natija **DB'ga yozilmasdan** to'g'ridan-to'g'ri qaytariladi
    (tezlik uchun ataylab shunday qilingan).
  - `WebSocketDisconnect` ushlanadi — mijoz uzilganda toza log yozib chiqadi.

### `backend/app/routers/history.py`
Tarix va katalog endpointlari. Endi frontendda **`History.tsx` orqali to'liq
ishlatiladi** (ilgari yozilgan-u, UI'da chaqirilmagan edi — tuzatildi).

- `list_inspections(limit, offset, db)` — `GET /api/inspections`. SQL
  `outerjoin` + `group_by` + `func.count` orqali har bir tekshiruv uchun
  nuqson sonini hisoblab, sahifalangan ro'yxat qaytaradi.
- `get_inspection(inspection_id, db)` — `GET /api/inspections/{id}`. `selectinload`
  orqali bog'liq `detections`ni bitta qo'shimcha so'rovda oldindan yuklaydi (N+1
  muammosining oldini oladi). Topilmasa 404.
- `get_result_image(filename)` — `GET /api/inspect/result-image/{filename}`.
  Annotatsiya qilingan JPEG faylni diskdan `FileResponse` orqali qaytaradi.
- `list_defect_types(db)` — `GET /api/defect-types`. Statik katalogni qaytaradi.

### `backend/alembic/` — migratsiyalar
- `env.py` — Alembic'ning standart runtime konfiguratsiyasi, `DATABASE_URL`ni
  `settings`dan oladi.
- `versions/0001_initial.py` — yagona migratsiya: 3 jadval (`inspections`,
  `detections`, `defect_types`) yaratadi, 2 ta Postgres ENUM turi
  (`inspection_mode`, `verdict`) e'lon qiladi, va `defect_types`ni 6 qator bilan
  oldindan to'ldiradi (`op.bulk_insert`). `downgrade()` — hammasini teskari
  tartibda o'chiradi.

### `backend/tests/` — to'liq test to'plami (22 test, barchasi o'tadi)

Ilgari faqat 4 ta yengil test bor edi (health-check va sof funksiyalar).
Endi quyidagilar qo'shildi:

- **`conftest.py`** — `async_client` fixture: xotiradagi SQLite (`StaticPool`
  bilan — bitta connection butun test davomida saqlanadi, aks holda har bir
  session alohida bo'sh bazaga ulanardi) orqali haqiqiy DB bilan ishlaydigan
  `AsyncClient` yaratadi, `get_db` dependency'sini almashtiradi. `db_session`
  fixture'i — to'g'ridan-to'g'ri bazaga yozish kerak bo'lgan testlar uchun.
  **Muhim**: `app.models.inspection`dagi UUID ustunlari Postgres-maxsus
  `postgresql.UUID` o'rniga **dialektga bog'liq bo'lmagan `sqlalchemy.Uuid`**
  turiga o'tkazildi (haqiqiy tuzatish, faqat test uchun emas) — aks holda
  SQLite ustida `CREATE TABLE` umuman ishlamay, DB bilan ishlaydigan birorta
  test yozib bo'lmasdi.
- **`test_inspect.py`** (5 test) — muvaffaqiyatli yuklash, bo'sh fayl (400),
  buzilgan fayl (400), 15MB'dan katta fayl (413), yuklangan tekshiruvning
  tarixda ko'rinishi.
- **`test_history.py`** (4 test) — bo'sh ro'yxat, topilmagan ID (404),
  `defect_types`ning seed'siz bo'sh qaytishi, qo'lda qo'shilgan qatorning
  qaytishi.
- **`test_inference_service.py`** (6 test) — `verdict_from_detections`,
  `is_ready()`, model yuklanmagan holatda `predict()`ning tez va xavfsiz
  ishlashi, singleton xususiyati, `draw_detections()`ning original rasmni
  o'zgartirmasligi.
- **`test_config.py`** (3 test) — `CORS_ORIGINS`da bo'sh/probel qatorlar
  yo'qligi, standart qiymatlar, `INFERENCE_IMG_SIZE`ning train qilingan
  modelga (320) mos ekanligi.
- **`test_health.py`** (4 test) — eski testlar, o'zgarishsiz saqlangan.

CI'da ishlatilgani kabi mahalliy ishga tushirish:

```bash
cd backend
DATABASE_URL="sqlite+aiosqlite:///./test.db" pytest -v
# natija: 22 passed
```

### `backend/Dockerfile`
`python:3.11-slim` asosida: OpenCV uchun kerakli tizim kutubxonalari
(`libgl1`, `libglib2.0-0`) o'rnatiladi, `requirements.txt` o'rnatiladi, kod
nusxalanadi, storage papkalari yaratiladi, `HEALTHCHECK` orqali `/api/health`
davriy tekshiriladi.

### `backend/training/` — train pipeline
- `download_dataset.py` — Roboflow API orqali dataset yuklash skripti
  (**amalda ishlatilmadi** — Roboflow tarmoq orqali bloklangan edi, haqiqiy
  dataset GitHub orqali qo'lda olindi).
- `tile_augment.py` — **haqiqatda ishlatilgan** skript. PASCAL VOC XML
  annotatsiyalarini o'qiydi, har bir original rasmni 600×600 oynacha (stride=450)
  bilan kesadi, har bir bo'lak uchun YOLO formatidagi label yozadi. **Eng muhim
  qismi**: split **fizik plata ID'si bo'yicha** qilinadi (rasm bo'yicha emas) —
  `TEST_BOARDS`, `VAL_BOARDS` to'plamlari qattiq belgilangan, va kod ichida
  `assert` bilan har bir plata faqat bitta split'ga tushganini tasdiqlaydi
  (data leakage'ning oldini olish uchun).
- `train.py` — umumiy train skripti (`ultralytics.YOLO(...).train(...)`), tugagach
  `best.pt`ni avtomatik `../app/ml/best.pt`ga ko'chiradi.
- `train_colab.ipynb` — Google Colab'da bepul GPU bilan train qilish uchun notebook.
- `results/TRAINING_REPORT.md` — to'liq, halol train hisobot (pastda qisqacha
  ko'chirilgan).

---

## 3. FRONTEND — fayl va funksiya darajasida

### `src/main.tsx`
Ilovaning kirish nuqtasi. `ReactDOM.createRoot` bilan DOM'ga ilova chizadi,
`QueryClientProvider` orqali butun ilovani React Query bilan o'raydi (server
holatini keshlash/boshqarish uchun).

### `src/App.tsx`
Uchta tab orasida almashtiruvchi asosiy komponent (`tab` state: `"image"` /
`"live"` / `"history"`). `ImageUpload`, `LiveDetection` yoki `History`ni
shartli ko'rsatadi. (Ilgari "Tarix" tab'i yo'q edi — roast bo'limida
topilgandan so'ng qo'shildi, pastga qarang.)

### `src/api/client.ts`
Barcha backend chaqiruvlari shu yerda markazlashgan (`axios` instance, baseURL=`/api`,
nginx orqali backend'ga proksilanadi):

- `inspectImage(file)` — `FormData` orqali `POST /inspect/image`.
- `listInspections(limit)`, `getInspection(id)`, `listDefectTypes()` — history
  endpointlari uchun funksiyalar. Endi **`History.tsx` komponenti orqali
  to'liq ishlatiladi** (ilgari yozilgan-u, UI'da chaqirilmagan edi).
- `buildLiveSocketUrl()` — joriy sahifa protokoliga qarab `ws://` yoki `wss://`
  URL quradi (xavfsiz/xavfsiz-bo'lmagan ulanishni avtomatik moslashtiradi).
  `client.test.ts`da test qilingan.

### `src/components/History.tsx` — **yangi qo'shilgan komponent**
Tekshiruvlar tarixini ko'rsatadi (roast bo'limida topilgan bo'shliqni to'ldiradi).

- `listQuery` (`useQuery`) — `listInspections(50)` orqali so'nggi 50 ta
  tekshiruvni jadval shaklida ko'rsatadi (sana, rejim, verdikt, nuqson soni).
- Qatorga bosilganda `selectedId` o'rnatiladi, `detailQuery` shu ID uchun
  `getInspection(id)`ni chaqiradi (`enabled: !!selectedId` — ID tanlanmagunча
  so'rov yuborilmaydi) va o'ng panelda annotatsiya qilingan rasm + nuqsonlar
  ro'yxatini ko'rsatadi.

### `src/types/index.ts`
TypeScript interfeyslari — backend Pydantic sxemalariga mos keladi (`Detection`,
`InspectionResult`, `InspectionListItem`, `LiveFrameResult`, `DefectType`). Bu
ikki tilning (Python/TypeScript) sxemalari qo'lda qo'lda sinxron ushlab turiladi —
avtomatik generatsiya (masalan, OpenAPI'dan) yo'q, shuning uchun backend sxema
o'zgarsa, bu faylni qo'lda yangilash kerak bo'ladi.

### `src/components/ImageUpload.tsx`
Bitta rasm yuklash oqimi.

- `handleFileChange(e)` — tanlangan faylni oladi, avval klient tarafida
  tur (`image/*`) va hajm (max 15MB, backend bilan mos) tekshiradi, so'ng
  `URL.createObjectURL` orqali preview yaratadi. **Eski preview URL yangisi
  o'rnatilishidan oldin va komponent unmount bo'lganda `URL.revokeObjectURL`
  bilan tozalanadi** (ilgari bu tozalash umuman yo'q edi — memory leak edi,
  tuzatildi). `Image` obyekti orqali asl o'lchamni (`naturalWidth/Height`)
  o'qiydi, so'ng `mutation.mutate(file)` orqali backend'ga yuboradi.
- `useMutation` (React Query) — yuklash holatini (`isPending`, `isError`, `data`)
  boshqaradi, qo'lda `useState` yozishni shart qilmaydi.
- Natija kelganda: `VerdictBadge` + `DetectionCanvas` (bbox overlay) + nuqsonlar
  ro'yxatini matn sifatida ko'rsatadi.

### `src/components/LiveDetection.tsx`
Kamera orqali real-time oqim.

- `startCamera()` — `navigator.mediaDevices.getUserMedia()` orqali kamerani
  so'raydi, `<video>` elementiga ulaydi, so'ng `connect()` (WebSocket) chaqiradi.
- `stopCamera()` (`useCallback` bilan) — kamera trek'larini to'xtatadi
  (`track.stop()`), `disconnect()` chaqiradi.
- `useEffect` (frame yuborish tsikli) — `FRAME_INTERVAL_MS=250`da (4 FPS) har safar
  joriy video frame'ni yashirin `<canvas>`ga chizadi, JPEG'ga (`quality=0.7`)
  aylantiradi va `sendFrame()` orqali WebSocket'ga yuboradi — faqat `status === "open"`
  bo'lgandagina.
- `useEffect(() => stopCamera, [stopCamera])` — komponent unmount bo'lganda
  tozalash (`stopCamera` endi `useCallback` bilan o'ralgan — ESLint
  `exhaustive-deps` ogohlantirishi to'g'ri hal qilindi, eski versiyada bu
  bo'sh `[]` dependency bilan yozilgan edi).

### `src/hooks/useLiveInspection.ts`
WebSocket ulanishini boshqaruvchi custom hook.

- `connect()` — yangi `WebSocket` ochadi, 4 ta event handler o'rnatadi
  (`onopen/onclose/onerror/onmessage`). `onclose` ichida **avtomatik qayta
  ulanish** logikasi bor: 2 soniyadan keyin `connect()`ni qayta chaqiradi —
  **lekin faqat `manualCloseRef.current` `false` bo'lsagina** (tuzatilgan
  bug, pastga qarang).
- `disconnect()` — `manualCloseRef.current = true` qilib belgilaydi
  (foydalanuvchi ataylab uzganini bildiradi), reconnect timer'ni tozalaydi,
  socket'ni yopadi, state'ni `"idle"`ga qaytaradi.
- `sendFrame(base64)` — socket ochiq bo'lsagina JSON xabar yuboradi.
- **Tuzatilgan bug**: avvalgi versiyada `disconnect()` socket'ni yopgandan
  keyin ham, socket'ning o'z `onclose` handler'i (brauzerda asinxron
  ishga tushadi) baribir 2 soniyadan keyin yangi ulanish ochib yuborardi —
  ya'ni "to'xtatish" tugmasi fonda kamerasiz WebSocket'ni qayta tiklardi.
  Endi `manualCloseRef` flag orqali `onclose` "bu ataylab uzilgan edi,
  qayta ulanma" deb bilib oladi. `useLiveInspection.test.ts`da 3 ta test
  bilan tasdiqlangan (ataylab uzish, kutilmagan uzilish, unmount).

### `src/components/DetectionCanvas.tsx`
Bbox'larni rasm/video ustiga chizadigan shaffof `<canvas>` overlay.

- Asl rasm o'lchami (`sourceWidth/Height`) bilan ko'rsatiladigan o'lcham
  (`displayWidth/Height`) orasidagi nisbatni (`scaleX/scaleY`) hisoblaydi,
  har bir detection uchun shkalalangan to'rtburchak va label chizadi.
  `COLORS` xaritasi orqali har bir nuqson turi uchun alohida rang tayinlaydi.

### `src/components/VerdictBadge.tsx`
Sodda taqdim etuvchi komponent — `"OK"`/`"NOK"`ga qarab yashil/qizil
rangli belgi (badge) chiqaradi.

### `src/test/setup.ts` va frontend testlar — **yangi qo'shilgan**

Ilgari frontendda birorta test yo'q edi (faqat `lint` + `tsc` + `build`
tekshirilardi). Endi Vitest + React Testing Library + jsdom o'rnatildi:

- **`VerdictBadge.test.tsx`** (2 test) — "OK" → "YAROQLI", "NOK" → "YAROQSIZ"
  matnlari to'g'ri chiqishini tekshiradi.
- **`api/client.test.ts`** (1 test) — `buildLiveSocketUrl()` to'g'ri
  `ws(s)://.../api/inspect/live` qaytarishini tekshiradi.
- **`hooks/useLiveInspection.test.ts`** (3 test) — **eng muhim test fayli**,
  yuqorida tasvirlangan reconnect bug'ini soxta (`FakeWebSocket`) va
  soxta vaqt (`vi.useFakeTimers`) orqali regressiyadan himoya qiladi:
  1. `disconnect()`dan keyin 5 soniya o'tsa ham qayta ulanish OCHILMAYDI.
  2. Kutilmagan uzilishda (disconnect() chaqirilmasdan) 2 soniyadan keyin
     qayta ulanish OCHILADI (bu — kerakli xususiyat, buzilmasligi kerak).
  3. Komponent unmount bo'lganda ham qayta ulanish bo'lmaydi.

Ishga tushirish: `cd frontend && npm test` → **6 passed**.

### Konfiguratsiya fayllari
- `vite.config.ts` — Vite build sozlamalari (`@` alias → `src/`, `test.environment: "jsdom"`).
- `tailwind.config.cjs`, `postcss.config.cjs` — **`.cjs` kengaytmasi bilan**
  (chunki `package.json`da `"type": "module"` bor — `.js` bilan ESM xatosi
  chiqishi aniqlangan va tuzatilgan edi).
- `tsconfig.json` — TypeScript compiler sozlamalari.
- `nginx.conf` — production konteynerida statik fayllarni xizmat qiladi,
  `/api/`ni backend'ga proksilaydi, WebSocket uchun `Upgrade`/`Connection`
  header'larini to'g'ri uzatadi.

---

## 4. MODEL — qanday tayyorlandi

1. **Dataset**: GitHub'dan (`Ironbrotherstyle/PCB-DATASET`, PKU universiteti
   to'plami) — 693 original yuqori-rezolyutsiyali rasm, 10 ta noyob fizik
   PCB plata, 6 nuqson klassi, PASCAL VOC XML formatida annotatsiya.
2. **Augmentatsiya**: `tile_augment.py` — har bir rasm 600×600 oynacha bilan
   kesildi (TDD-net maqolasi uslubi), natijada **5,369 tile** hosil bo'ldi.
3. **Split**: fizik plata darajasida qattiq ajratildi (train: 7 plata/3,930
   tile, val: 2 plata/1,124 tile, test: 1 plata/315 tile) — bitta plata faqat
   bitta split'ga tushadi (board-level data leakage'ning oldini olish uchun).
4. **Train**: YOLOv8n (nano), imgsz=320, batch=16, 25 epoch, CPU'da (~3.4 soat).
5. **Natija (test, mutlaqo ko'rilmagan plata)**: mAP50=0.847, Precision=0.835,
   Recall=0.879. Klass bo'yicha: `missing_hole`/`spurious_copper` juda ishonchli
   (0.99), `spur` zaif (0.48).
6. **Tekshirilgan narsalar**: data leakage (topildi va tuzatildi), overfitting
   (yo'q — train/val loss birga pasayadi), underfitting (yo'q), yodlab olish/
   memorization (yo'q — MD5 duplikat tekshiruvi 0 ta, ishonch darajalari tarqoq).

To'liq jarayon: `backend/training/results/TRAINING_REPORT.md`.

---

## 5. Imkoniyatlar va cheklovlar (xulosa)

**Ishlaydi:**
- Bitta rasm yuklab tahlil qilish (bbox + klass + ishonch + OK/NOK), klient va
  server tarafida fayl validatsiyasi (tur + 15MB hajm limiti) bilan.
- Kameradan real-time oqim (~4 FPS, WebSocket orqali), endi event loop'ni
  blocklamasdan (threadpool orqali).
- Tekshiruvlar tarixini ko'rish — ro'yxat + tafsilot (`History.tsx`).
- Natijalarning DB'ga saqlanishi (faqat rasm rejimida).
- Docker bilan bir buyruqda to'liq ishga tushirish, CI/CD orqali avtomatik
  build/push/deploy/test.
- Haqiqiy, o'zi train qilingan YOLOv8n modeli (demo/placeholder emas), endi
  inference o'lchami train o'lchami bilan mos (320).
- To'liq test qamrovi: backend 22 test (unit + integratsion), frontend 6 test
  (shu jumladan reconnect bug uchun regression test).

**Hali ham cheklov sifatida qolgan (atayin, kod bilan hal qilib bo'lmaydigan):**
- `spur` klassi ishonchsiz (test mAP50=0.48) — bu klass uchun qo'shimcha,
  xilma-xil dataset kerak (ko'proq noyob fizik plata).
- Autentifikatsiya, rate-limiting yo'q — faqat ichki/demo foydalanish uchun
  mos, ochiq internetga xavfsiz joylashtirish uchun emas.
- Bir nechta WS mijoz bir vaqtda ulansa, har biri CPU navbatida kutadi
  (threadpool bitta CPU'ni bo'lishadi — bu GPU yo'qligi/CPU-only muhitning
  tabiiy cheklovi, kod arxitekturasining emas).

---

## 6. Roast bo'limida topilgan muammolar — holati

| # | Joy | Muammo | Holati |
|---|---|---|---|
| 1 | `inspect.py` | Sinxron `predict()` async endpoint/WS ichida — event loop'ni blocklaydi | ✅ Tuzatildi — `run_in_threadpool` |
| 2 | `inspect.py` | Decode xatoliklari uchun handler yo'q — xom 500 qaytadi | ✅ Tuzatildi — `HTTPException(400)` |
| 3 | `inference.py` | Bitta global confidence threshold 6 klass uchun (spur zaif klassga ham baland ishonch beriladi) | ⚠️ Qolmoqda — dataset cheklovi, kod bilan to'liq hal qilib bo'lmaydi (TRAINING_REPORT.md'da izohlangan) |
| 4 | Frontend | History sahifasi yo'q, lekin backend API bor | ✅ Tuzatildi — `History.tsx` qo'shildi |
| 5 | `useLiveInspection.ts` | `disconnect()`dan keyin ham `onclose` orqali avtomatik qayta ulanish ishga tushib qoladi | ✅ Tuzatildi — `manualCloseRef` flag + 3 regression test |
| 6 | `ImageUpload.tsx` | `URL.createObjectURL` tozalanmaydi (memory leak) | ✅ Tuzatildi — `revokeObjectURL` |
| 7 | `config.py` | `INFERENCE_IMG_SIZE=640` standart, lekin model 320'da train qilingan | ✅ Tuzatildi — standart 320 |
| 8 | Umumiy | Autentifikatsiya/rate-limit yo'q, DB paroli ochiq matnda | ⚠️ Qolmoqda — ichki/demo foydalanish uchun ataylab soddalashtirilgan, production uchun qo'shimcha ish kerak |
| 9 | Testlar | Juda yuzaki — integratsion testlar yo'q | ✅ Tuzatildi — backend 22 test, frontend 6 test |
| 10 | `main.py` | Healthcheck model yuklanmagan holatda ham 200 qaytaradi | ⚠️ Qolmoqda — ataylab shunday qoldirildi (demo rejimda konteyner "sog'lom" ko'rinishi kerak, aks holda `best.pt`siz hech qachon ishga tushmaydi) |
| 11 | `inspect.py` | Yuklanadigan fayl hajmi/turi cheklanmagan | ✅ Tuzatildi — 15MB limit + tur tekshiruvi (backend va frontendda) |
| 12 | `models/inspection.py` | Postgres-maxsus UUID turi SQLite bilan test yozishga xalaqit berardi | ✅ Tuzatildi — `sqlalchemy.Uuid` (dialektga bog'liq emas) |
| 13 | `LiveDetection.tsx` | ESLint `exhaustive-deps` ogohlantirishi (`max-warnings 0` bilan CI'ni chippa chiqarardi) | ✅ Tuzatildi — `stopCamera` `useCallback` bilan o'ralgan |
| 14 | `config.py`, `models/inspection.py` | Pydantic/`datetime.utcnow()` deprecation ogohlantirishlari | ✅ Tuzatildi — `SettingsConfigDict`, tz-aware `_utcnow()` |

**Qasddan tuzatilmagan narsalar** (3, 8, 10) — bular kod xatosi emas, balki
loyihaning ataylab tanlangan doirasi/cheklovi: #3 va #8 alohida loyiha
(ko'proq dataset, auth qatlami) talab qiladi, #10 esa demo-do'stlik uchun
ataylab shunday qilingan dizayn qarori.

Barcha kod tuzatishlari ushbu repoga push qilingandan so'ng **real ishga
tushirilib tasdiqlandi**: backend 22/22 test, frontend 6/6 test, `ruff
check` — toza, `eslint --max-warnings 0` — toza, `tsc -b && vite build` —
muvaffaqiyatli.
