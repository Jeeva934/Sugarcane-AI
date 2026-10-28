"""Audit image files for counts and exact duplicates without training a model."""

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def audit_images(root: Path) -> dict:
    if not root.is_dir():
        raise FileNotFoundError(f"Image directory does not exist: {root}")
    counts = Counter()
    hashes: dict[str, list[str]] = defaultdict(list)
    total = 0
    for path in sorted(item for item in root.rglob("*") if item.is_file() and item.suffix.lower() in IMAGE_SUFFIXES):
        label = path.parent.name
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        counts[label] += 1
        hashes[digest].append(str(path.relative_to(root)))
        total += 1
    duplicates = [paths for paths in hashes.values() if len(paths) > 1]
    return {
        "dataset_root": str(root.resolve()),
        "image_count": total,
        "label_directory_counts": dict(sorted(counts.items())),
        "exact_duplicate_groups": duplicates,
        "warning": "This audit does not verify labels, licences, plant/session leakage, or model suitability.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("images_dir", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit_images(args.images_dir), indent=2))


if __name__ == "__main__":
    main()
