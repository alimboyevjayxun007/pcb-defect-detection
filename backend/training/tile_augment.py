"""
PKU PCB-DATASET'ning yuqori-rezolyutsiyali 693 rasmini TDD-net maqolasidagi
("TDD-Net: A Tiny Defect Detection Network for PCBs", Ding et al. 2019) uslubda
600x600 sliding-window bo'laklarga kesib, kattaroq (~10k) YOLO dataset hosil qiladi.

Original rasm -> ko'p sonli 600x600 tile -> har bir tile'dagi ko'rinadigan
defektlar YOLO label sifatida saqlanadi.

Train/val/test bo'linishi ORIGINAL rasm darajasida qilinadi (bitta rasmning
tile'lari turli splitlarga tushib ketmasligi uchun — bu data leakage'ni oldini oladi).
"""
import random
import xml.etree.ElementTree as ET
from pathlib import Path

import cv2

SRC = Path("/home/claude/ironbrotherstyle/pcb-dataset")
DST = Path("/tmp/pcb-train/dataset_yolo_large")

CLASSES = ["missing_hole", "mouse_bite", "open_circuit", "short", "spur", "spurious_copper"]
CLASS_TO_ID = {c: i for i, c in enumerate(CLASSES)}

TILE = 600
STRIDE = 450  # ~CPU vaqtiga mos hajm uchun sozlangan (oldin 300 -> 11k tile, juda uzoq)
MIN_VISIBLE_RATIO = 0.35  # bbox'ning kamida shuncha qismi tile ichida bo'lsa saqlanadi

random.seed(42)
SPLIT = {"train": 0.8, "val": 0.15, "test": 0.05}


def load_annotation(xml_path: Path):
    tree = ET.parse(xml_path)
    root = tree.getroot()
    size_el = root.find("size")
    w = int(size_el.find("width").text)
    h = int(size_el.find("height").text)

    boxes = []
    for obj in root.findall("object"):
        name = obj.find("name").text.strip().lower().replace(" ", "_")
        if name not in CLASS_TO_ID:
            continue
        bnd = obj.find("bndbox")
        xmin = float(bnd.find("xmin").text)
        ymin = float(bnd.find("ymin").text)
        xmax = float(bnd.find("xmax").text)
        ymax = float(bnd.find("ymax").text)
        boxes.append((CLASS_TO_ID[name], xmin, ymin, xmax, ymax))
    return w, h, boxes


def tile_image(img_path, w, h, boxes, out_img_dir, out_lbl_dir, prefix):
    img = cv2.imread(str(img_path))
    if img is None:
        return 0

    count = 0
    xs = list(range(0, max(w - TILE, 0) + 1, STRIDE)) or [0]
    ys = list(range(0, max(h - TILE, 0) + 1, STRIDE)) or [0]
    if xs[-1] != max(w - TILE, 0):
        xs.append(max(w - TILE, 0))
    if ys[-1] != max(h - TILE, 0):
        ys.append(max(h - TILE, 0))

    tw = min(TILE, w)
    th = min(TILE, h)

    seen_tiles = set()
    for tx in xs:
        for ty in ys:
            key = (tx, ty)
            if key in seen_tiles:
                continue
            seen_tiles.add(key)

            tile_lines = []
            for cls_id, xmin, ymin, xmax, ymax in boxes:
                # bbox va tile kesishmasi
                ix1 = max(xmin, tx)
                iy1 = max(ymin, ty)
                ix2 = min(xmax, tx + tw)
                iy2 = min(ymax, ty + th)
                if ix2 <= ix1 or iy2 <= iy1:
                    continue

                orig_area = (xmax - xmin) * (ymax - ymin)
                inter_area = (ix2 - ix1) * (iy2 - iy1)
                if orig_area <= 0 or inter_area / orig_area < MIN_VISIBLE_RATIO:
                    continue

                # tile ichidagi nisbiy koordinatalar (clip qilingan)
                bx1 = ix1 - tx
                by1 = iy1 - ty
                bx2 = ix2 - tx
                by2 = iy2 - ty

                xc = (bx1 + bx2) / 2 / tw
                yc = (by1 + by2) / 2 / th
                bw = (bx2 - bx1) / tw
                bh = (by2 - by1) / th
                tile_lines.append(f"{cls_id} {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}")

            if not tile_lines:
                continue  # faqat defekt bor tile'larni saqlaymiz

            tile_img = img[ty:ty + th, tx:tx + tw]
            tile_name = f"{prefix}_x{tx}_y{ty}"
            cv2.imwrite(str(out_img_dir / f"{tile_name}.jpg"), tile_img,
                        [cv2.IMWRITE_JPEG_QUALITY, 95])
            (out_lbl_dir / f"{tile_name}.txt").write_text("\n".join(tile_lines))
            count += 1

    return count


def main():
    for split in SPLIT:
        (DST / "images" / split).mkdir(parents=True, exist_ok=True)
        (DST / "labels" / split).mkdir(parents=True, exist_ok=True)

    xml_files = sorted((SRC / "Annotations").rglob("*.xml"))
    print(f"Original rasm (XML) soni: {len(xml_files)}")

    # MUHIM: split FIZIK PLATA (board ID) darajasida qilinadi, rasm darajasida emas.
    # Dataset atigi 10 ta noyob fizik platadan iborat (fayl nomi prefiksi: 01,04-12).
    # Agar split tasodifiy rasm bo'yicha qilinsa, bitta plataning turli rasmlari
    # ham train'da, ham val/test'da qolib ketishi mumkin -> model nuqsonni emas,
    # balki "bu plata qanday ko'rinishini" yodlab olishi mumkin (board-level leakage).
    # Shuning uchun har bir plata FAQAT bitta split'ga tegishli bo'ladi.
    TEST_BOARDS = {"10"}
    VAL_BOARDS = {"09", "12"}
    # qolgan platalar (01,04,05,06,07,08,11) -> train

    def board_id_of(xml_path: Path) -> str:
        return xml_path.stem.split("_")[0]

    splits_map = {}
    for f in xml_files:
        bid = board_id_of(f)
        if bid in TEST_BOARDS:
            splits_map[f] = "test"
        elif bid in VAL_BOARDS:
            splits_map[f] = "val"
        else:
            splits_map[f] = "train"

    board_split_check = {}
    for f, s in splits_map.items():
        board_split_check.setdefault(board_id_of(f), set()).add(s)
    for bid, splits in sorted(board_split_check.items()):
        assert len(splits) == 1, f"Plata {bid} bir nechta split'ga tushib qolgan: {splits}"
    print("Board-level split tasdiqlandi: har bir plata faqat bitta split'da.")

    n = len(xml_files)

    totals = {"train": 0, "val": 0, "test": 0}

    for idx, (xml_path, split) in enumerate(splits_map.items()):
        root_tree = ET.parse(xml_path)
        filename = root_tree.getroot().find("filename").text
        class_folder = xml_path.parent.name
        img_path = SRC / "images" / class_folder / filename
        if not img_path.exists():
            continue

        w, h, boxes = load_annotation(xml_path)
        prefix = f"{class_folder}_{Path(filename).stem}"

        n_tiles = tile_image(
            img_path, w, h, boxes,
            DST / "images" / split, DST / "labels" / split,
            prefix,
        )
        totals[split] += n_tiles

        if (idx + 1) % 100 == 0:
            print(f"  ...{idx + 1}/{n} original rasm qayta ishlandi")

    print(f"\nYakuniy tile soni: train={totals['train']}, val={totals['val']}, test={totals['test']}")
    print(f"JAMI: {sum(totals.values())}")

    yaml_content = f"""path: {DST}
train: images/train
val: images/val
test: images/test

names:
"""
    for i, c in enumerate(CLASSES):
        yaml_content += f"  {i}: {c}\n"

    (DST / "data.yaml").write_text(yaml_content)
    print(f"data.yaml yozildi: {DST / 'data.yaml'}")


if __name__ == "__main__":
    main()
