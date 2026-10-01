# PCB Defect Detection — model train qilish

Sizdagi xatolik (`'pcb_defects.yaml' does not exist`) sababi oddiy: `yolo detect train`
buyrug'i **dataset'ning o'zi** (rasmlar + annotatsiyalar + ularni tasvirlovchi `.yaml` fayl)
mavjud bo'lishini talab qiladi — bu fayl avtomatik yaratilmaydi, uni siz dataset bilan
birga olishingiz yoki o'zingiz yozishingiz kerak.

Quyida to'liq, boshidan oxirigacha ishlaydigan yo'l ko'rsatilgan.

## 1-qadam: Datasetni yuklab olish

Eng oson yo'l — **Roboflow Universe**'dan tayyor, YOLOv8 formatida export qilingan
dataset olish (annotatsiyalar va `data.yaml` avtomatik birga keladi):

1. https://universe.roboflow.com ga kiring (bepul akkaunt kerak)
2. "Augmented PCB Defect" yoki "PCB Defects" deb qidiring — masalan:
   `https://universe.roboflow.com/bare-pcb-defects`
3. Dataset sahifasida **"Download Dataset"** tugmasini bosing
4. Format sifatida **"YOLOv8"** ni tanlang
5. "show download code" orqali kod oling — bunday ko'rinishda bo'ladi:

```python
from roboflow import Roboflow
rf = Roboflow(api_key="SIZNING_API_KEYINGIZ")
project = rf.workspace("bare-pcb-defects").project("obj-detection-pcb-defects-yolov8")
version = project.version(1)
dataset = version.download("yolov8")
```

Buni `backend/training/download_dataset.py` fayliga joylashtirib ishga tushiring:

```bash
cd backend/training
pip install roboflow
python download_dataset.py
```

Natijada joriy papkada shunday struktura hosil bo'ladi:

```
Obj-detection-pcb-defects-yolov8-1/
├── data.yaml          ← aynan shu faylni data= parametrida ko'rsatasiz
├── train/images/ ...
├── valid/images/ ...
└── test/images/ ...
```

## 2-qadam: Train qilish

```bash
cd backend/training
yolo detect train data="Obj-detection-pcb-defects-yolov8-1/data.yaml" model=yolov8s.pt epochs=100 imgsz=640
```

Yoki tayyor `train.py` scriptini ishlating (progress va natijani avtomatik
`backend/app/ml/best.pt`ga ko'chiradi):

```bash
python train.py --data "Obj-detection-pcb-defects-yolov8-1/data.yaml" --epochs 100
```

## 3-qadam: Natijani tekshirish

```bash
yolo detect val model=../app/ml/best.pt data="Obj-detection-pcb-defects-yolov8-1/data.yaml"
```

mAP@0.5 qiymati 0.85+ bo'lsa — backend'da ishlatish uchun yetarli.

## Muhim eslatmalar

- **CPU'da train qilish sekin** (100 epoch ~2-5 soat). Agar GPU bo'lmasa, Google
  Colab'dan foydalaning (bepul GPU, tayyor `train_colab.ipynb` papkada bor).
- `epochs=100` boshlang'ich nuqta — natija yomon bo'lsa `epochs=150-200` ga oshiring
  yoki `yolov8m.pt` (kattaroq model) sinab ko'ring.
- Dataset klass nomlari (`data.yaml` ichidagi `names:`) backend kodidagi hech narsaga
  bog'liq emas — `inference.py` klass nomlarini modelning o'zidan (`self.model.names`)
  avtomatik oladi, shuning uchun qo'shimcha sozlash kerak emas.
