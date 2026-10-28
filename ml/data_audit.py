"""Audit image files for counts and exact duplicates without training a model."""

import argparse
import hashlib
import json
from collections import Counter, defaultdict

from PIL import Image
from pathlib import Path

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def difference_hash(path: Path) -> str:
    with Image.open(path) as image:
        grayscale = image.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    pixels = list(grayscale.getdata())
    bits = "".join("1" if pixels[index] > pixels[index + 1] else "0" for row in range(8) for index in range(8) for index in [row * 9 + index])
    return f"{int(bits, 2):016x}" if bits else "0" * 16


def audit_images(root: Path, include_near_duplicates: bool = False) -> dict:
    if not root.is_dir():
        raise FileNotFoundError(f"Image directory does not exist: {root}")
    counts = Counter()
    hashes: dict[str, list[str]] = defaultdict(list)
    near_hashes: dict[str, list[str]] = defaultdict(list)
    total = 0
    for path in sorted(item for item in root.rglob("*") if item.is_file() and item.suffix.lower() in IMAGE_SUFFIXES):
        label = path.parent.name
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        counts[label] += 1
        relative = str(path.relative_to(root))
        hashes[digest].append(relative)
        if include_near_duplicates:
            near_hashes[difference_hash(path)].append(relative)
        total += 1
    duplicates = [paths for paths in hashes.values() if len(paths) > 1]
    near_duplicates = [paths for paths in near_hashes.values() if len(paths) > 1]
    return {
        "dataset_root": str(root.resolve()),
        "image_count": total,
        "label_directory_counts": dict(sorted(counts.items())),
        "exact_duplicate_groups": duplicates,
        "near_duplicate_groups": near_duplicates if include_near_duplicates else None,
        "near_duplicate_method": "difference hash (64-bit)" if include_near_duplicates else None,
        "warning": "This audit does not verify labels, licences, independent expert review, or field suitability. Capture-session leakage requires a supplied manifest.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("images_dir", type=Path)
    parser.add_argument("--near-duplicates", action="store_true", help="Report perceptually similar images using 64-bit difference hashes.")
    args = parser.parse_args()
    print(json.dumps(audit_images(args.images_dir, args.near_duplicates), indent=2))


if __name__ == "__main__":
    main()
