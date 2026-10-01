# Train natijasi — PCB Defect Detection (YOLOv8n) — YAKUNIY VERSIYA

Bu hisobot **ikkinchi, tuzatilgan** train natijasidir. Birinchi urinishda topilgan
muammo va uning tuzatilishi haqida ham shaffof yozilgan — bu loyihaning haqiqiy
rivojlanish jarayoni, soxtalashtirilmagan.

## Jarayon: nima bo'ldi va nega ikki marta train qilindi

1. **1-urinish**: 693 ta original PKU PCB-DATASET rasmida (tasodifiy rasm darajasida
   train/val/test bo'lingan) train qilindi. Natija: mAP50 = 0.62.
2. **Foydalanuvchi savoli**: "Bu kattaroq dataset bilan emasmi, overfitting yo'qmi?"
3. **Aniqlangan jiddiy muammo**: Dataset atigi **10 ta fizik PCB platadan** iborat
   ekan (fayl nomi prefiksi: 01, 04-12). Split tasodifiy rasm darajasida qilingani
   uchun, **bitta fizik plataning turli rasmlari ham train'da, ham val/test'da**
   qolib ketgan edi — bu **board-level data leakage**. Model nuqsonni emas, balki
   "bu aniq plata qanday ko'rinishini" qisman yodlab olgan bo'lishi mumkin edi.
4. **Tuzatish**: Split **plata darajasida** qat'iy ajratildi — har bir plata FAQAT
   bitta split'ga tegishli (train: 7 plata, val: 2 plata, test: 1 plata). Kod ichida
   `assert` bilan tasdiqlangan.
5. **Dataset kattalashtirildi**: Foydalanuvchi so'rovi bilan, TDD-net maqolasining
   (Ding et al., 2019) o'z metodologiyasi takrorlandi — yuqori-rezolyutsiyali
   rasmlar 600×600 oynacha bilan kesildi, natijada 693 → **5,369 tile** hosil
   bo'ldi (stride=450, ya'ni oynalar orasida qisman qoplanish bilan).
6. **Qayta train qilindi** — shu, tuzatilgan, leakage'siz dataset'da.

## Dataset (yakuniy)

| Split | Tile soni | Fizik platalar |
|---|---|---|
| Train | 3,930 | 01, 04, 05, 06, 07, 08, 11 |
| Val | 1,124 | 09, 12 |
| Test | 315 | 10 |

Train/val/test orasida hech qanday umumiy fizik plata yo'q — kod ichida dasturiy
tekshirilgan (`assert`).

## Train sozlamalari

| Parametr | Qiymat |
|---|---|
| Model | YOLOv8n (nano) |
| Image size | 320×320 |
| Epochs | 25 (to'liq yakunlandi) |
| Batch | 16 |
| Device | CPU (2 yadro, GPU yo'q) |
| Train vaqti | ~3.4 soat |

## Natijalar — VAL va TEST taqqoslash (muhim!)

| Metrika | Val (09,12 — train vaqtida model "ko'rgan" yo'nalishdagi platalar) | **Test (10 — mutlaqo alohida)** |
|---|---|---|
| mAP50 | 0.973 | **0.847** |
| mAP50-95 | 0.527 | 0.430 |
| Precision | 0.975 | 0.835 |
| Recall | 0.943 | 0.879 |

**Bu ikkalasi orasidagi farq (0.97 → 0.85) muhim signal**: val metrikasi biroz
optimistik bo'lishi mumkinligini ko'rsatadi. Sabab — atigi 10 ta noyob plata
borligi uchun, qaysi platalar qaysi split'ga tushishiga qarab natija tabiiy
tebranadi. Bu **to'liq overfitting emas** (test natijasi ham baribir yaxshi,
tasodifiy darajadan ancha yuqori — 0.85 vs tasodifiy ~0.05-0.10 bo'lardi), lekin
**"haqiqiy" ishlash ko'rsatkichi sifatida TEST natijasini olish kerak, val emas**.

### Klass bo'yicha (TEST set — yakuniy, eng xolis baho):

| Klass | Precision | Recall | mAP50 |
|---|---|---|---|
| spurious_copper | 1.00 | 0.98 | **0.99** |
| missing_hole | 0.99 | 0.98 | **0.99** |
| open_circuit | 0.89 | 0.90 | 0.92 |
| mouse_bite | 0.95 | 0.79 | 0.87 |
| short | 0.93 | 0.80 | 0.84 |
| **spur** | **0.25** | 0.82 | **0.48** |

`spur` klassi test'da keskin pasaygan — board 10'dagi spur-tipidagi mis
bo'rtiqlari boshqa 9 platadagilardan vizual jihatdan farqlanishi, yoki shu
plata turida ko'proq "spur'ga o'xshash" tabiiy mis izlari borligi (false positive
ko'p) ehtimoli bor. Bu — kichik (10 ta plata) dataset'ning tabiiy zaif nuqtasi.

## Yodlab olish (memorization) tekshiruvi

Foydalanuvchi so'rovi bilan maxsus tekshirildi:
- **Train/val orasida duplikat fayl**: 0 ta (MD5 hash orqali tasdiqlandi)
- **Val'dagi ishonch darajalari**: tasodifiy namunada 0.26 dan 0.87 gacha tarqoq
  qiymatlar — agar model yodlab olgan bo'lsa, deyarli hamma joyda 0.95+ bo'lardi
- **Train vs val loss**: ikkalasi ham birga pasaydi, val loss hech qachon
  ko'tarilmadi — klassik sog'lom (overfit bo'lmagan) train egri chizig'i

**Xulosa: yodlab olish belgisi yo'q**, lekin val/test orasidagi farq shuni
ko'rsatadiki, **dataset'ning o'zi** (10 ta noyob plata) — bu algoritm emas,
dataset hajmi va xilma-xilligining tabiiy chegarasi.

## Halol yakuniy baho

**Productionga tayyor qismlar**: `missing_hole`, `spurious_copper` (mAP50 0.99) —
bu ikkalasi juda ishonchli. `open_circuit`, `mouse_bite`, `short` ham qoniqarli
(0.84-0.92).

**Ishonchsiz qism**: `spur` klassi (mAP50 0.48 test'da) — bu klass uchun ko'proq
va xilma-xil (ko'proq noyob plata turidagi) ma'lumot kerak.

**Algoritm va dataset tanlovi haqida**: YOLOv8n CPU uchun to'g'ri tanlov edi.
Asosiy cheklov — **algoritmda emas, dataset'da**: atigi 10 ta noyob fizik plata,
sun'iy (Photoshop) qo'shilgan nuqsonlar. Haqiqiy sanoat darajasidagi natija uchun:
yuzlab-minglab noyob plata turi, haqiqiy (sun'iy emas) nuqsonlar kerak bo'ladi.

## Keyingi qadamlar

1. Ko'proq noyob plata turi bilan dataset kengaytirish (ayniqsa `spur` klassi uchun)
2. GPU bilan kattaroq model (`yolov8s`/`yolov8m`) va kattaroq image size (640)
3. K-fold cross-validation (platalar bo'yicha) — har bir plata navbatma-navbat
   test sifatida ishlatilib, o'rtacha natija olinsa, yanada xolis baho chiqadi
