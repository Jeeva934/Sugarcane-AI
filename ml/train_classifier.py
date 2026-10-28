"""Train an experimental EfficientNetV2 sugarcane leaf classifier.

The script removes byte-identical duplicates before splitting to prevent exact
copies from leaking across train, validation, and test partitions.
"""

import argparse
import hashlib
import json
import random
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from PIL import Image, UnidentifiedImageError
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support
from sklearn.model_selection import train_test_split
from torch import nn
from torch.utils.data import DataLoader, Dataset, TensorDataset
from torchvision import models, transforms

CLASSES = ("Healthy", "Mosaic", "RedRot", "Rust", "Yellow")
SOURCE_URL = "https://data.mendeley.com/datasets/9424skmnrk/1"
KAGGLE_URL = "https://www.kaggle.com/datasets/nirmalsankalana/sugarcane-leaf-disease-dataset"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


def image_records(data_dir: Path, session_manifest: Path | None = None) -> tuple[list[dict], dict]:
    if not data_dir.is_dir():
        raise FileNotFoundError(f"Dataset directory does not exist: {data_dir}")
    class_dirs = {child.name.casefold(): child for child in data_dir.iterdir() if child.is_dir()}
    missing = [name for name in CLASSES if name.casefold() not in class_dirs]
    if missing:
        raise ValueError(f"Missing class folders: {', '.join(missing)}")

    session_by_path: dict[str, str] = {}
    if session_manifest:
        session_payload = json.loads(session_manifest.read_text(encoding="utf-8"))
        if not isinstance(session_payload, dict):
            raise ValueError("Session manifest must map relative image paths to session identifiers.")
        session_by_path = {str(path): str(session) for path, session in session_payload.items()}

    hashes: dict[str, list[dict]] = defaultdict(list)
    invalid = []
    counts = Counter()
    for label in CLASSES:
        for path in sorted(class_dirs[label.casefold()].rglob("*")):
            if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            data = path.read_bytes()
            try:
                with Image.open(path) as image:
                    image.verify()
            except (UnidentifiedImageError, OSError, ValueError) as exc:
                invalid.append({"path": str(path.relative_to(data_dir)), "error": str(exc)})
                continue
            relative_path = str(path.relative_to(data_dir))
            if session_manifest and relative_path not in session_by_path:
                raise ValueError(f"Session manifest omitted image: {relative_path}")
            digest = hashlib.sha256(data).hexdigest()
            hashes[digest].append({
                "path": relative_path,
                "label": label,
                "sha256": digest,
                "session_id": session_by_path.get(relative_path, "unknown"),
            })
            counts[label] += 1

    cross_class = [
        entries for entries in hashes.values()
        if len({entry["label"] for entry in entries}) > 1
    ]
    if cross_class:
        raise ValueError(
            f"Found {len(cross_class)} identical-image groups assigned to conflicting classes. "
            "Resolve the labels before training."
        )
    unique = [sorted(entries, key=lambda entry: entry["path"])[0] for entries in hashes.values()]
    unique.sort(key=lambda entry: (entry["label"], entry["path"]))
    duplicate_groups = [entries for entries in hashes.values() if len(entries) > 1]
    report = {
        "raw_image_counts": dict(counts),
        "raw_image_total": sum(counts.values()),
        "unique_image_total": len(unique),
        "exact_duplicate_groups": len(duplicate_groups),
        "duplicate_files_removed": sum(len(group) - 1 for group in duplicate_groups),
        "invalid_images": invalid,
        "session_aware_splitting": bool(session_manifest),
    }
    return unique, report


def make_splits(records: list[dict], seed: int) -> dict[str, list[dict]]:
    session_ids = {record["session_id"] for record in records}
    session_aware = session_ids != {"unknown"}
    if not session_aware:
        labels = [record["label"] for record in records]
        train_records, holdout = train_test_split(records, test_size=0.30, random_state=seed, stratify=labels)
        holdout_labels = [record["label"] for record in holdout]
        validation_records, test_records = train_test_split(holdout, test_size=0.50, random_state=seed, stratify=holdout_labels)
        return {"train": list(train_records), "validation": list(validation_records), "test": list(test_records)}

    grouped: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        grouped[record["session_id"]].append(record)
    session_records = list(grouped.values())
    if len(session_records) < 3:
        raise ValueError("Session-aware splitting requires at least three capture sessions.")

    def session_label(entries: list[dict]) -> str:
        counts = Counter(entry["label"] for entry in entries)
        return counts.most_common(1)[0][0]

    session_labels = [session_label(entries) for entries in session_records]
    train_sessions, holdout_sessions = train_test_split(
        session_records, test_size=0.30, random_state=seed, stratify=session_labels
    )
    holdout_labels = [session_label(entries) for entries in holdout_sessions]
    holdout_counts = Counter(holdout_labels)
    stratify_holdout = holdout_labels if min(holdout_counts.values()) >= 2 else None
    if stratify_holdout is None:
        raise ValueError("Session-aware splitting requires at least two sessions per class in the validation/test split.")
    validation_sessions, test_sessions = train_test_split(
        holdout_sessions, test_size=0.50, random_state=seed, stratify=stratify_holdout
    )
    return {
        "train": [record for entries in train_sessions for record in entries],
        "validation": [record for entries in validation_sessions for record in entries],
        "test": [record for entries in test_sessions for record in entries],
    }


class LeafDataset(Dataset):
    def __init__(self, records: list[dict], data_dir: Path, transform):
        self.records = records
        self.data_dir = data_dir
        self.transform = transform
        self.label_indexes = {label: index for index, label in enumerate(CLASSES)}

    def __len__(self):
        return len(self.records)

    def __getitem__(self, index):
        record = self.records[index]
        with Image.open(self.data_dir / record["path"]) as source:
            image = source.convert("RGB")
        return self.transform(image), self.label_indexes[record["label"]]


def save_json(path: Path, payload: dict):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True, help="Extracted dataset root containing the five class folders.")
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/image"))
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--input-size", type=int, default=192)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--session-manifest", type=Path, help="JSON mapping every relative image path to a capture/session identifier.")
    parser.add_argument("--pretrained", action="store_true", help="Download/use official torchvision ImageNet weights for transfer learning.")
    args = parser.parse_args()
    if args.epochs < 1 or args.batch_size < 1 or args.input_size < 96:
        parser.error("--epochs and --batch-size must be positive and --input-size must be at least 96.")
    if not args.pretrained:
        parser.error(
            "This small dataset should not be trained from random initialization. "
            "Review the official torchvision weight terms, then pass --pretrained to opt in."
        )

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    records, data_report = image_records(args.data_dir, args.session_manifest)
    if data_report["invalid_images"]:
        save_json(args.output_dir / "invalid_images.json", {"images": data_report["invalid_images"]})
        raise ValueError(f"{len(data_report['invalid_images'])} unreadable images found; see invalid_images.json.")
    per_class = Counter(record["label"] for record in records)
    if set(per_class) != set(CLASSES) or min(per_class.values()) < 10:
        raise ValueError("Each of the five classes must have at least 10 unique, readable images.")
    splits = make_splits(records, args.seed)
    split_hashes = {name: {record["sha256"] for record in items} for name, items in splits.items()}
    if any(split_hashes[a] & split_hashes[b] for a, b in (("train", "validation"), ("train", "test"), ("validation", "test"))):
        raise RuntimeError("Exact duplicate leakage detected between data splits.")
    if data_report["session_aware_splitting"]:
        split_sessions = {name: {row["session_id"] for row in items} for name, items in splits.items()}
        if any(split_sessions[a] & split_sessions[b] for a, b in (("train", "validation"), ("train", "test"), ("validation", "test"))):
            raise RuntimeError("Capture-session leakage detected between data splits.")
    split_manifest = {
        name: [{"path": row["path"], "label": row["label"], "sha256": row["sha256"]} for row in items]
        for name, items in splits.items()
    }
    save_json(args.output_dir / "split_manifest.json", split_manifest)

    augmentation = transforms.Compose([
        transforms.RandomResizedCrop(args.input_size, scale=(0.75, 1.0)),
        transforms.RandomHorizontalFlip(),
        transforms.ColorJitter(brightness=0.12, contrast=0.12, saturation=0.12),
        transforms.ToTensor(),
        transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ])
    evaluation_transform = transforms.Compose([
        transforms.Resize(args.input_size + 32),
        transforms.CenterCrop(args.input_size),
        transforms.ToTensor(),
        transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ])
    image_loaders = {
        "train": DataLoader(LeafDataset(splits["train"], args.data_dir, augmentation), batch_size=args.batch_size, shuffle=False, num_workers=0),
        "validation": DataLoader(LeafDataset(splits["validation"], args.data_dir, evaluation_transform), batch_size=args.batch_size, shuffle=False, num_workers=0),
        "test": DataLoader(LeafDataset(splits["test"], args.data_dir, evaluation_transform), batch_size=args.batch_size, shuffle=False, num_workers=0),
    }

    weights = models.EfficientNet_V2_S_Weights.DEFAULT
    model = models.efficientnet_v2_s(weights=weights)
    model.classifier[-1] = nn.Linear(model.classifier[-1].in_features, len(CLASSES))
    model.features.requires_grad_(False)
    model.to(device)

    def cache_features(loader):
        feature_batches = []
        label_batches = []
        model.eval()
        with torch.inference_mode():
            for images, labels in loader:
                images = images.to(device)
                features = model.features(images)
                features = model.avgpool(features)
                feature_batches.append(torch.flatten(features, 1).cpu())
                label_batches.append(labels)
        return TensorDataset(torch.cat(feature_batches), torch.cat(label_batches))

    print("Extracting frozen EfficientNetV2 features once per split...", flush=True)
    loaders = {
        name: DataLoader(cache_features(loader), batch_size=args.batch_size, shuffle=name == "train", num_workers=0)
        for name, loader in image_loaders.items()
    }

    class_counts = Counter(record["label"] for record in splits["train"])
    class_weights = torch.tensor([len(splits["train"]) / (len(CLASSES) * class_counts[label]) for label in CLASSES], dtype=torch.float32, device=device)
    criterion = nn.CrossEntropyLoss(weight=class_weights)
    optimizer = torch.optim.AdamW(model.classifier.parameters(), lr=1e-3, weight_decay=1e-4)
    best_validation_loss = float("inf")
    best_state = None
    history = []

    for epoch in range(args.epochs):
        model.train()
        train_loss = 0.0
        train_items = 0
        for features, labels in loaders["train"]:
            features, labels = features.to(device), labels.to(device)
            optimizer.zero_grad(set_to_none=True)
            logits = model.classifier(features)
            loss = criterion(logits, labels)
            loss.backward()
            optimizer.step()
            train_loss += loss.item() * labels.size(0)
            train_items += labels.size(0)

        model.eval()
        validation_loss = 0.0
        validation_items = 0
        with torch.inference_mode():
            for features, labels in loaders["validation"]:
                features, labels = features.to(device), labels.to(device)
                logits = model.classifier(features)
                validation_loss += criterion(logits, labels).item() * labels.size(0)
                validation_items += labels.size(0)
        validation_loss /= validation_items
        epoch_row = {
            "epoch": epoch + 1,
            "training_loss": train_loss / train_items,
            "validation_loss": validation_loss,
        }
        history.append(epoch_row)
        print(json.dumps(epoch_row), flush=True)
        if validation_loss < best_validation_loss:
            best_validation_loss = validation_loss
            best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}

    if best_state is None:
        raise RuntimeError("Training did not produce a validation checkpoint.")
    model.load_state_dict(best_state)
    model.eval()
    true_labels = []
    predicted_labels = []
    scores = []
    with torch.inference_mode():
        for features, labels in loaders["test"]:
            features = features.to(device)
            logits = model.classifier(features)
            probabilities = torch.softmax(logits, dim=1).cpu().numpy()
            scores.extend(probabilities.tolist())
            predicted_labels.extend(probabilities.argmax(axis=1).tolist())
            true_labels.extend(labels.numpy().tolist())

    precision, recall, f1, _ = precision_recall_fscore_support(
        true_labels, predicted_labels, labels=range(len(CLASSES)), average=None, zero_division=0
    )
    macro = precision_recall_fscore_support(true_labels, predicted_labels, average="macro", zero_division=0)
    metrics = {
        "test_sample_count": len(true_labels),
        "accuracy": accuracy_score(true_labels, predicted_labels),
        "macro_precision": macro[0],
        "macro_recall": macro[1],
        "macro_f1": macro[2],
        "per_class": {
            label: {"precision": float(precision[i]), "recall": float(recall[i]), "f1": float(f1[i])}
            for i, label in enumerate(CLASSES)
        },
        "confusion_matrix": confusion_matrix(true_labels, predicted_labels, labels=range(len(CLASSES))).tolist(),
    }
    trained_at = datetime.now(timezone.utc).isoformat()
    checkpoint = {
        "architecture": "torchvision.efficientnet_v2_s",
        "class_names": list(CLASSES),
        "state_dict": best_state,
        "input_size": args.input_size,
        "backbone_frozen": True,
        "normalization": {"mean": IMAGENET_MEAN, "std": IMAGENET_STD},
        "model_version": f"experimental-{trained_at[:10]}-seed{args.seed}",
    }
    torch.save(checkpoint, args.output_dir / "efficientnet_v2_s.pt")
    report = {
        "status": "experimental_not_production_validated",
        "dataset_source": SOURCE_URL,
        "download_source": KAGGLE_URL,
        "license_reported_by_kaggle": "CC0 1.0; verify dataset page before redistribution",
        "label_verification": "Dataset page describes manual collection; it does not establish independent expert verification. Confirm before research claims.",
        "official_source_image_count": 2569,
        "archive_image_count": data_report["raw_image_total"],
        "data_audit": data_report,
        "unique_class_counts": dict(per_class),
        "split_counts": {name: len(items) for name, items in splits.items()},
        "pretrained_weights": "torchvision EfficientNet_V2_S_Weights.DEFAULT",
        "pretrained_weight_downloaded_during_explicit_training": True,
        "seed": args.seed,
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "input_size": args.input_size,
        "device": str(device),
        "history": history,
        "test_metrics": metrics,
        "interpretation_warning": "Test metrics are from this dataset split only. They are not independent field validation, calibrated probabilities, or a claim of real-world diagnostic accuracy.",
        "trained_at_utc": trained_at,
    }
    save_json(args.output_dir / "evaluation.json", report)
    save_json(args.output_dir / "class_names.json", {"class_names": list(CLASSES)})
    print(json.dumps({"checkpoint": str(args.output_dir / "efficientnet_v2_s.pt"), "evaluation": str(args.output_dir / "evaluation.json"), "test_metrics": metrics}, indent=2))


if __name__ == "__main__":
    main()
