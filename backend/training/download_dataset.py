"""
Roboflow'dan PCB defect dataset'ini yuklab olish.

Ishlatishdan oldin:
1. https://roboflow.com saytida bepul ro'yxatdan o'ting
2. Account Settings → API Key'dan o'z kalitingizni oling
3. Quyidagi ROBOFLOW_API_KEY o'rniga shu kalitni qo'ying (yoki ROBOFLOW_API_KEY env
   o'zgaruvchisi sifatida bering)
4. workspace/project/version qiymatlarini tanlagan dataset sahifasidagi
   "show download code" bo'limidan ko'chiring — pastdagilar faqat namuna.

    pip install roboflow
    python download_dataset.py
"""
import os
from roboflow import Roboflow

API_KEY = os.getenv("ROBOFLOW_API_KEY", "SIZNING_API_KEYINGIZ")

# NAMUNA qiymatlar — o'zingiz tanlagan Roboflow Universe dataset sahifasidan
# "show download code" orqali aniq workspace/project/version'ni oling.
WORKSPACE = "bare-pcb-defects"
PROJECT = "obj-detection-pcb-defects-yolov8"
VERSION = 1

if __name__ == "__main__":
    if API_KEY == "SIZNING_API_KEYINGIZ":
        raise SystemExit(
            "Avval ROBOFLOW_API_KEY ni sozlang: "
            "export ROBOFLOW_API_KEY=sizning_kalitingiz"
        )

    rf = Roboflow(api_key=API_KEY)
    project = rf.workspace(WORKSPACE).project(PROJECT)
    version = project.version(VERSION)
    dataset = version.download("yolov8")

    print(f"\nDataset yuklandi: {dataset.location}")
    print(f"data.yaml yo'li: {dataset.location}/data.yaml")
    print("\nTrain qilish uchun:")
    print(f'  yolo detect train data="{dataset.location}/data.yaml" model=yolov8s.pt epochs=100 imgsz=640')
