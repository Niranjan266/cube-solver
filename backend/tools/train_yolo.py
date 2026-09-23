"""
Train your own YOLO sticker detector (optional).

The classical detector already handles clean, well-lit scans.  A YOLO model
earns its keep on awkward angles, cluttered desks and phone cameras held at
arm's length.  There is no off-the-shelf cube-sticker model on the Hugging Face
Hub, so this trains one.

Quick start (run from backend/)
-------------------------------
    pip install huggingface_hub
    python tools/train_yolo.py --prepare-hf          # download + convert labels
    pip install ultralytics
    python tools/train_yolo.py --train               # train (or print the command)

``--prepare-hf`` downloads ``seandavidreed/rubiks_cube_segmentation`` (a
Roboflow YOLOv8 *segmentation* export: 197 images, 162 classes such as ``R_14``
= colour letter + sticker position) and writes a detection copy to
``data/yolo_stickers``: every polygon becomes an axis-aligned box and every
class becomes ``sticker`` (``--classes colour`` keeps the six colours instead).
The app only uses YOLO to *locate* stickers; colour is decided by its own
classifier.

Then point the app at the result:
    set CUBE_YOLO_MODEL=runs\\detect\\train\\weights\\best.pt      (Windows)
    export CUBE_YOLO_MODEL=runs/detect/train/weights/best.pt      (macOS/Linux)

Labelling your own photos
-------------------------
One class, ``sticker``, one box per visible facelet.  ~300 hand-labelled
photos of your own cube in your own lighting beats a large generic set.
Label with Label Studio, CVAT or Roboflow and export in YOLO format.
"""

from __future__ import annotations

import argparse
import ast
import os
import re
import shutil
import statistics
import textwrap
from collections import Counter
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
DEFAULT_REPO = "seandavidreed/rubiks_cube_segmentation"
DEFAULT_OUT = BACKEND / "data" / "yolo_stickers"
SPLITS = ("train", "valid", "test")
COLOURS = ["B", "G", "O", "R", "W", "Y"]

HUB_DATASETS = [
    ("seandavidreed/rubiks_cube_segmentation",
     "YOLOv8 polygons, 27 stickers/image - use --prepare-hf"),
    ("ProgrammerGnome/Rubik_YOLOv7",
     "already in YOLO label format"),
    ("ProgrammerGnome/Rubik_Original_YOLOv7",
     "real photos, YOLO labels"),
    ("ProgrammerGnome/data_ORIGINAL_rubik_resized_augmented",
     "1213 augmented real photos, unlabelled"),
]

DATA_YAML = """\
# minimal Ultralytics dataset file - edit the paths and you are done
path: ./cube-dataset
train: images/train
val: images/val
names:
  0: sticker
"""


# --------------------------------------------------------------------------- #
# Hugging Face dataset -> single-class detection dataset
# --------------------------------------------------------------------------- #
def _read_names(yaml_path: Path) -> list:
    text = yaml_path.read_text(encoding="utf-8")
    try:
        import yaml  # pyyaml ships with huggingface_hub

        names = yaml.safe_load(text)["names"]
    except Exception:
        m = re.search(r"^names:\s*(\[.*\])", text, re.M)
        if not m:
            raise SystemExit(f"could not find class names in {yaml_path}")
        names = ast.literal_eval(m.group(1))
    if isinstance(names, dict):
        names = [names[k] for k in sorted(names)]
    return list(names)


def _line_to_box(parts: list) -> tuple | None:
    """``cls cx cy w h`` or ``cls x1 y1 x2 y2 ...`` -> (cx, cy, w, h), clipped."""
    vals = [float(v) for v in parts[1:]]
    if len(vals) == 4:
        cx, cy, w, h = vals
        x0, y0, x1, y1 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
    elif len(vals) >= 6 and len(vals) % 2 == 0:
        xs, ys = vals[0::2], vals[1::2]
        x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    else:
        return None
    x0, y0 = max(0.0, x0), max(0.0, y0)
    x1, y1 = min(1.0, x1), min(1.0, y1)
    if x1 - x0 <= 1e-4 or y1 - y0 <= 1e-4:
        return None
    return (x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0


def prepare_hf(repo: str, out: Path, classes: str) -> Path:
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        raise SystemExit("pip install huggingface_hub first")

    raw = out / "_raw"
    print(f"downloading {repo} -> {raw}")
    snapshot_download(repo_id=repo, repo_type="dataset", local_dir=str(raw))

    src_names = _read_names(raw / "data.yaml")
    if classes == "colour":
        out_names = COLOURS
        remap = {}
        for i, n in enumerate(src_names):
            letter = str(n).split("_")[0].upper()
            if letter not in COLOURS:
                raise SystemExit(f"unexpected class name {n!r}")
            remap[i] = COLOURS.index(letter)
    else:
        out_names = ["sticker"]
        remap = {i: 0 for i in range(len(src_names))}

    hist: Counter = Counter()
    per_image: list = []
    report = []
    kinds: Counter = Counter()
    for split in SPLITS:
        img_dir, lab_dir = raw / split / "images", raw / split / "labels"
        if not img_dir.is_dir():
            continue
        o_img, o_lab = out / split / "images", out / split / "labels"
        if o_img.parent.exists():
            shutil.rmtree(o_img.parent)
        o_img.mkdir(parents=True)
        o_lab.mkdir(parents=True)
        n_img = 0
        for img in sorted(img_dir.iterdir()):
            if not img.is_file():
                continue
            try:  # hardlink when possible: no second copy of every image
                os.link(img, o_img / img.name)
            except OSError:
                shutil.copy2(img, o_img / img.name)
            n_img += 1
            lines_out = []
            lab = lab_dir / (img.stem + ".txt")
            if lab.exists():
                for line in lab.read_text(encoding="utf-8").splitlines():
                    parts = line.split()
                    if len(parts) < 5:
                        continue
                    kinds["box" if len(parts) == 5 else "polygon"] += 1
                    box = _line_to_box(parts)
                    if box is None:
                        kinds["dropped"] += 1
                        continue
                    c = remap[int(parts[0])]
                    hist[out_names[c]] += 1
                    lines_out.append(f"{c} " + " ".join(f"{v:.6f}" for v in box))
            (o_lab / (img.stem + ".txt")).write_text(
                "\n".join(lines_out) + ("\n" if lines_out else ""), encoding="utf-8"
            )
            per_image.append(len(lines_out))
        report.append((split, n_img))

    yaml_path = out / "data.yaml"
    names_block = "\n".join(f"  {i}: {n}" for i, n in enumerate(out_names))
    split_lines = [f"train: train/images", f"val: valid/images"]
    if (out / "test").is_dir():
        split_lines.append("test: test/images")
    yaml_path.write_text(
        f"# generated by tools/train_yolo.py --prepare-hf from {repo}\n"
        f"# source labels: {dict(kinds)}; converted to axis-aligned boxes\n"
        f"path: {out.resolve().as_posix()}\n"
        + "\n".join(split_lines)
        + f"\nnames:\n{names_block}\n",
        encoding="utf-8",
    )

    print(f"\nsource: {len(src_names)} classes, e.g. {src_names[:3]} ... {src_names[-1]}")
    print(f"source label lines: {dict(kinds)}")
    for split, n in report:
        print(f"  {split:5s}: {n} images")
    if per_image:
        print(f"boxes per image: min {min(per_image)}  median "
              f"{statistics.median(per_image)}  max {max(per_image)}  "
              f"(total {sum(per_image)})")
        print(f"  distribution: {dict(sorted(Counter(per_image).items()))}")
    print(f"class histogram: {dict(hist)}")
    print(f"\nwrote {yaml_path}")
    print("next: python tools/train_yolo.py --train")
    return yaml_path


# --------------------------------------------------------------------------- #
# Training
# --------------------------------------------------------------------------- #
AUG = dict(
    # a cube face is a tight lattice of same-shaped boxes: heavy geometric
    # augmentation hurts, colour augmentation helps
    degrees=12, translate=0.10, scale=0.35, shear=3.0,
    fliplr=0.0, mosaic=0.4,
    hsv_h=0.02, hsv_s=0.6, hsv_v=0.5,
)


def train(data: str, model_name: str, epochs: int, imgsz: int,
          print_only: bool = False) -> None:
    if not Path(data).exists():
        raise SystemExit(
            f"{data} not found. Run --prepare-hf (or --write-yaml) first."
        )
    data_arg = Path(data).as_posix()
    if " " in data_arg:
        data_arg = f'"{data_arg}"'
    cli = (f"yolo detect train data={data_arg} model={model_name} "
           f"imgsz={imgsz} epochs={epochs} "
           + " ".join(f"{k}={v}" for k, v in AUG.items()))
    try:
        from ultralytics import YOLO
    except ImportError:
        YOLO = None
    if YOLO is None or print_only:
        if YOLO is None:
            print("ultralytics is not installed - not training.  "
                  "`pip install ultralytics`, then run:\n")
        print(f"  {cli}\n")
        print("Afterwards point the app at the weights:\n"
              "  set CUBE_YOLO_MODEL=runs\\detect\\train\\weights\\best.pt   (Windows)\n"
              "  export CUBE_YOLO_MODEL=runs/detect/train/weights/best.pt  (macOS/Linux)\n"
              "and compare against the classical detector with tools/bench_vision.py")
        return

    model = YOLO(model_name)
    model.train(data=data, epochs=epochs, imgsz=imgsz, **AUG)
    print("\nDone. Point CUBE_YOLO_MODEL at runs/detect/train/weights/best.pt "
          "and benchmark it with tools/bench_vision.py")


def main() -> None:
    p = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(__doc__ or ""),
    )
    p.add_argument("--data", default=None,
                   help="Ultralytics dataset yaml (default: cube.yaml, or the "
                        "--prepare-hf output with --train)")
    p.add_argument("--model", default="yolov8n.pt", help="starting weights")
    p.add_argument("--epochs", type=int, default=80)
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--list-datasets", action="store_true")
    p.add_argument("--write-yaml", action="store_true",
                   help="drop a starter cube.yaml next to this script")
    p.add_argument("--prepare-hf", action="store_true",
                   help="download a Hub dataset and convert it to sticker boxes")
    p.add_argument("--repo", default=DEFAULT_REPO, help="Hub dataset for --prepare-hf")
    p.add_argument("--out", default=str(DEFAULT_OUT),
                   help="output folder for --prepare-hf")
    p.add_argument("--classes", choices=["sticker", "colour"], default="sticker",
                   help="one 'sticker' class (default) or six colour classes")
    p.add_argument("--train", action="store_true",
                   help="train on the prepared data if ultralytics is installed, "
                        "else print the exact command")
    p.add_argument("--print-only", action="store_true",
                   help="with --train: only print the command")
    args = p.parse_args()

    if args.list_datasets:
        print("Cube image datasets on the Hugging Face Hub:\n")
        for repo, why in HUB_DATASETS:
            print(f"  https://huggingface.co/datasets/{repo}\n      {why}")
        print("\nPrepare the first one in one step with:\n"
              "  python tools/train_yolo.py --prepare-hf")
        return

    if args.write_yaml:
        out = Path(args.data or "cube.yaml")
        out.write_text(DATA_YAML, encoding="utf-8")
        print(f"wrote {out.resolve()} - edit the paths, then re-run without --write-yaml")
        return

    if args.prepare_hf:
        yaml_path = prepare_hf(args.repo, Path(args.out), args.classes)
        if args.train:
            train(str(yaml_path), args.model, args.epochs, args.imgsz, args.print_only)
        return

    if args.train:
        data = args.data or str(Path(args.out) / "data.yaml")
        train(data, args.model, args.epochs, args.imgsz, args.print_only)
        return

    # legacy behaviour: train straight away on --data (default cube.yaml)
    data = args.data or "cube.yaml"
    try:
        import ultralytics  # noqa: F401
    except ImportError:
        raise SystemExit("pip install ultralytics first")
    train(data, args.model, args.epochs, args.imgsz)


if __name__ == "__main__":
    main()
