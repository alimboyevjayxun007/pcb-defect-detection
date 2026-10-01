"""
PCB defect detection uchun YOLOv8 modelini train qilish.

Ishlatish:
    python train.py --data "path/to/data.yaml" --epochs 100 --model yolov8s.pt

Train tugagach, eng yaxshi vazn (best.pt) avtomatik ravishda
../app/ml/best.pt ga ko'chiriladi — backend shu faylni to'g'ridan-to'g'ri ishlatadi.
"""
import argparse
import shutil
from pathlib import Path

from ultralytics import YOLO

THIS_DIR = Path(__file__).parent
BACKEND_ML_DIR = THIS_DIR.parent / "app" / "ml"


def main():
    parser = argparse.ArgumentParser(description="PCB defect YOLOv8 train script")
    parser.add_argument("--data", required=True, help="data.yaml fayli yo'li")
    parser.add_argument("--model", default="yolov8s.pt", help="Boshlang'ich model (pretrained)")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--device", default="", help="'' = avtomatik, 'cpu', yoki '0' (GPU)")
    args = parser.parse_args()

    data_path = Path(args.data).resolve()
    if not data_path.exists():
        raise SystemExit(
            f"Xato: '{data_path}' topilmadi.\n"
            f"Avval dataset yuklab oling: python download_dataset.py\n"
            f"yoki README.md'dagi qo'llanmaga qarang."
        )

    print(f"Train boshlanmoqda: model={args.model}, data={data_path}, epochs={args.epochs}")

    model = YOLO(args.model)
    results = model.train(
        data=str(data_path),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        project=str(THIS_DIR / "runs"),
        name="pcb_train",
    )

    best_weights = Path(results.save_dir) / "weights" / "best.pt"
    if not best_weights.exists():
        raise SystemExit(f"Train tugadi, lekin {best_weights} topilmadi — logga qarang.")

    BACKEND_ML_DIR.mkdir(parents=True, exist_ok=True)
    dest = BACKEND_ML_DIR / "best.pt"
    shutil.copy(best_weights, dest)

    print(f"\n✅ Train tugadi. Model saqlandi: {dest}")
    print("Endi backend konteynerini qayta ishga tushiring:")
    print("  docker compose up -d --build backend")


if __name__ == "__main__":
    main()
