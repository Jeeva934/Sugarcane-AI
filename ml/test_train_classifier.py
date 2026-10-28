import json
from pathlib import Path

import pytest
from PIL import Image

from ml.train_classifier import CLASSES, image_records, make_splits


def create_class_images(root: Path, images_per_class: int = 10):
    for label_index, label in enumerate(CLASSES):
        class_dir = root / label
        class_dir.mkdir(parents=True)
        for index in range(images_per_class):
            image = Image.new("RGB", (16, 16), (label_index * 30, index * 20, 10))
            image.save(class_dir / f"{label}_{index}.jpg")


def test_identical_images_are_collapsed_before_splitting(tmp_path):
    create_class_images(tmp_path)
    class_dir = tmp_path / "Healthy"
    (class_dir / "Healthy_0_copy.jpg").write_bytes((class_dir / "Healthy_0.jpg").read_bytes())

    records, report = image_records(tmp_path)
    assert report["raw_image_total"] == len(CLASSES) * 10 + 1
    assert report["unique_image_total"] == len(CLASSES) * 10
    assert report["duplicate_files_removed"] == 1

    splits = make_splits(records, seed=42)
    hashes = {name: {record["sha256"] for record in rows} for name, rows in splits.items()}
    assert not (hashes["train"] & hashes["validation"])
    assert not (hashes["train"] & hashes["test"])
    assert not (hashes["validation"] & hashes["test"])


def test_session_manifest_keeps_capture_sessions_out_of_different_splits(tmp_path):
    create_class_images(tmp_path, images_per_class=40)
    manifest = {}
    for label in CLASSES:
        for index, path in enumerate(sorted((tmp_path / label).glob("*.jpg"))):
            manifest[str(path.relative_to(tmp_path))] = f"{label}-session-{index // 2}"
    manifest_path = tmp_path / "sessions.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    records, report = image_records(tmp_path, manifest_path)
    assert report["session_aware_splitting"] is True
    splits = make_splits(records, seed=42)
    session_sets = [{record["session_id"] for record in rows} for rows in splits.values()]
    assert len(session_sets[0].intersection(session_sets[1])) == 0
    assert len(session_sets[0].intersection(session_sets[2])) == 0
    assert len(session_sets[1].intersection(session_sets[2])) == 0


def test_conflicting_labels_for_identical_images_are_rejected(tmp_path):
    create_class_images(tmp_path)
    image = (tmp_path / "Healthy" / "Healthy_0.jpg").read_bytes()
    (tmp_path / "Mosaic" / "same_as_healthy.jpg").write_bytes(image)

    with pytest.raises(ValueError, match="conflicting classes"):
        image_records(tmp_path)
