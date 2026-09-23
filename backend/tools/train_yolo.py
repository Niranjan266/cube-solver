"""
Train your own YOLO sticker detector (optional).

The classical detector already handles clean, well-lit scans.  A YOLO model
earns its keep on awkward angles, cluttered desks and phone cameras held at
arm's length.  There is no off-the-shelf cube-sticker model on the Hugging Face
Hub, so this trains one.

Quick start
-----------
    pip install ultralytics huggingface-hub datasets
    python tools/train_yolo.py --list-datasets       # what's on the Hub
    python tools/train_yolo.py --data mycube.yaml --epochs 80

Then point the app at the result:
    set CUBE_YOLO_MODEL=runs\\detect\\train\\weights\\best.pt      (Windows)
    export CUBE_YOLO_MODEL=runs/detect/train/weights/best.pt      (macOS/Linux)

Labelling
---------
One class, ``sticker``, one box per visible facelet.  ~300 hand-labelled
photos of your own cube in your own lighting beats a large generic set.
Label with Label Studio, CVAT or Roboflow and export in YOLO format.

Starting points on the Hub (images you can label or fine-tune from):
    datasets/seandavidreed/rubiks_cube_segmentation
    datasets/ProgrammerGnome/Rubik_YOLOv7
    datasets/ProgrammerGnome/data_ORIGINAL_rubik_resized_augmented
"""

from __future__ import annotations

import argparse
import textwrap
from pathlib import Path

HUB_DATASETS = [
    ("seandavidreed/rubiks_cube_segmentation",
     "segmentation masks of cube faces - convert masks to boxes"),
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


def main() -> None:
    p = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(__doc__ or ""),
    )
    p.add_argument("--data", default="cube.yaml", help="Ultralytics dataset yaml")
    p.add_argument("--model", default="yolov8n.pt", help="starting weights")
    p.add_argument("--epochs", type=int, default=80)
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--list-datasets", action="store_true")
    p.add_argument("--write-yaml", action="store_true",
                   help="drop a starter cube.yaml next to this script")
    args = p.parse_args()

    if args.list_datasets:
        print("Cube image datasets on the Hugging Face Hub:\n")
        for repo, why in HUB_DATASETS:
            print(f"  https://huggingface.co/datasets/{repo}\n      {why}")
        print("\nDownload one with:\n"
              "  huggingface-cli download --repo-type dataset <repo> --local-dir data/")
        return

    if args.write_yaml:
        out = Path(args.data)
        out.write_text(DATA_YAML, encoding="utf-8")
        print(f"wrote {out.resolve()} - edit the paths, then re-run without --write-yaml")
        return

    try:
        from ultralytics import YOLO
    except ImportError:
        raise SystemExit("pip install ultralytics first")

    if not Path(args.data).exists():
        raise SystemExit(
            f"{args.data} not found. Run with --write-yaml to create a starter file."
        )

    model = YOLO(args.model)
    model.train(
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        # a cube face is a tight lattice of same-shaped boxes: heavy geometric
        # augmentation hurts, colour augmentation helps
        degrees=12, translate=0.10, scale=0.35, shear=3.0,
        fliplr=0.0, mosaic=0.4,
        hsv_h=0.02, hsv_s=0.6, hsv_v=0.5,
    )
    print("\nDone. Point CUBE_YOLO_MODEL at runs/detect/train/weights/best.pt")


if __name__ == "__main__":
    main()
