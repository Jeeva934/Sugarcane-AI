import json
import time
import torch
from pathlib import Path
from PIL import Image
from torchvision import models, transforms
from ultralytics import YOLO
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix

CLASSES = ("Healthy", "Mosaic", "RedRot", "Rust", "Yellow")

def run_comparison():
    print("Loading models for comparison...")
    # 1. Load EfficientNetV2 classifier
    classifier_path = Path("artifacts/image/efficientnet_v2_s.pt")
    checkpoint = torch.load(classifier_path, map_location="cpu")
    
    classifier = models.efficientnet_v2_s(weights=None)
    classifier.classifier[-1] = torch.nn.Linear(classifier.classifier[-1].in_features, len(CLASSES))
    classifier.load_state_dict(checkpoint["state_dict"])
    classifier.eval()
    
    input_size = checkpoint.get("input_size", 192)
    norm = checkpoint.get("normalization", {"mean": [0.485, 0.456, 0.406], "std": [0.229, 0.224, 0.225]})
    preprocess = transforms.Compose([
        transforms.Resize(input_size + 32),
        transforms.CenterCrop(input_size),
        transforms.ToTensor(),
        transforms.Normalize(tuple(norm["mean"]), tuple(norm["std"])),
    ])
    
    # 2. Load YOLO11 leaf detector
    detector_path = Path("artifacts/detector/yolo11_leaf.pt")
    if not detector_path.is_file():
        # Fallback to runs directory if copy is pending
        fallback = Path("artifacts/detector/runs/yolo11_sugarcane_leaf/weights/best.pt")
        if fallback.is_file():
            detector_path = fallback
        else:
            detector_path = Path("yolo11n.pt")
    detector = YOLO(str(detector_path))
    print(f"YOLO detector loaded from {detector_path}")
    
    # 3. Load Dataset 1 Holdout Test Split
    with open("artifacts/image/split_manifest.json", "r") as f:
        manifest = json.load(f)
    test_records = manifest["test"]
    ds1_root = Path("datasets/mendeley_v1/Sugarcane Leaf Disease Dataset")
    
    print(f"\n--- Evaluating on Dataset 1 Test Set ({len(test_records)} images) ---")
    y_true = []
    y_pred_baseline = []
    y_pred_yolo = []
    times_baseline = []
    times_yolo = []
    
    for r in test_records:
        img_path = ds1_root / r["path"]
        if not img_path.is_file():
            continue
        true_cls = r["label"]
        y_true.append(true_cls)
        
        # --- Baseline Pipeline ---
        t0 = time.perf_counter()
        with Image.open(img_path) as img:
            rgb_full = img.convert("RGB")
            tensor_base = preprocess(rgb_full).unsqueeze(0)
            with torch.inference_mode():
                out_base = classifier(tensor_base)
                pred_base = CLASSES[torch.argmax(out_base, dim=1).item()]
        t_base = (time.perf_counter() - t0) * 1000
        times_baseline.append(t_base)
        y_pred_baseline.append(pred_base)
        
        # --- YOLO11 + EfficientNet Pipeline ---
        t1 = time.perf_counter()
        # Step 1: Detect leaf
        yolo_res = detector(str(img_path), verbose=False, imgsz=320, conf=0.25)
        boxes = yolo_res[0].boxes
        
        with Image.open(img_path) as img:
            rgb_full = img.convert("RGB")
            if len(boxes) > 0:
                # Take highest confidence box
                box = boxes[0].xyxy[0].cpu().numpy()
                x1, y1, x2, y2 = map(int, box)
                # Ensure valid crop
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(rgb_full.width, max(x1 + 10, x2)), min(rgb_full.height, max(y1 + 10, y2))
                cropped = rgb_full.crop((x1, y1, x2, y2))
            else:
                cropped = rgb_full
                
            tensor_yolo = preprocess(cropped).unsqueeze(0)
            with torch.inference_mode():
                out_yolo = classifier(tensor_yolo)
                pred_yolo = CLASSES[torch.argmax(out_yolo, dim=1).item()]
        t_yolo = (time.perf_counter() - t1) * 1000
        times_yolo.append(t_yolo)
        y_pred_yolo.append(pred_yolo)
        
    acc_base = accuracy_score(y_true, y_pred_baseline)
    acc_yolo = accuracy_score(y_true, y_pred_yolo)
    macro_base = precision_recall_fscore_support(y_true, y_pred_baseline, average="macro", zero_division=0)
    macro_yolo = precision_recall_fscore_support(y_true, y_pred_yolo, average="macro", zero_division=0)
    
    avg_t_base = sum(times_baseline) / len(times_baseline)
    avg_t_yolo = sum(times_yolo) / len(times_yolo)
    
    print("\n=== Dataset 1 Test Set Comparison ===")
    print(f"Whole-Image Baseline:")
    print(f"  Accuracy: {acc_base * 100:.2f}% | Macro-F1: {macro_base[2] * 100:.2f}% | Latency: {avg_t_base:.1f} ms")
    print(f"YOLO11 Detection + Classifier Pipeline:")
    print(f"  Accuracy: {acc_yolo * 100:.2f}% | Macro-F1: {macro_yolo[2] * 100:.2f}% | Latency: {avg_t_yolo:.1f} ms")
    
    # 4. External Field Generalization Comparison (Dataset 2 subset: 150 field samples)
    print("\n--- Evaluating External Field Generalization (Dataset 2 Sample: 150 images) ---")
    ds2_root = Path("datasets/mendeley_v2_supplementary/Sugarcane Disease Dataset")
    ds2_samples = []
    
    for fld, mapped in [("Healthy Leaves", "Healthy"), ("Diseases/BrownRust", "Rust"), ("Diseases/YellowLeaf", "Yellow")]:
        p = ds2_root / fld
        for img_file in sorted(p.glob("*.jpg"))[:50]:
            ds2_samples.append((img_file, mapped))
            
    ext_true = []
    ext_base = []
    ext_yolo = []
    
    for img_path, target_cls in ds2_samples:
        ext_true.append(target_cls)
        # Base
        with Image.open(img_path) as img:
            t_b = preprocess(img.convert("RGB")).unsqueeze(0)
            with torch.inference_mode():
                ext_base.append(CLASSES[torch.argmax(classifier(t_b), dim=1).item()])
        # YOLO
        res = detector(str(img_path), verbose=False, imgsz=320, conf=0.25)
        boxes = res[0].boxes
        with Image.open(img_path) as img:
            rgb = img.convert("RGB")
            if len(boxes) > 0:
                box = boxes[0].xyxy[0].cpu().numpy()
                x1, y1 = max(0, int(box[0])), max(0, int(box[1]))
                x2, y2 = min(rgb.width, max(x1 + 10, int(box[2]))), min(rgb.height, max(y1 + 10, int(box[3])))
                c = rgb.crop((x1, y1, x2, y2))
            else:
                c = rgb
            t_y = preprocess(c).unsqueeze(0)
            with torch.inference_mode():
                ext_yolo.append(CLASSES[torch.argmax(classifier(t_y), dim=1).item()])
                
    ext_acc_base = accuracy_score(ext_true, ext_base)
    ext_acc_yolo = accuracy_score(ext_true, ext_yolo)
    
    print("\n=== External Field Dataset Comparison ===")
    print(f"Whole-Image Baseline Accuracy: {ext_acc_base * 100:.2f}%")
    print(f"YOLO11 + Classifier Accuracy:   {ext_acc_yolo * 100:.2f}%")
    
    # Save comparison report
    comparison_data = {
        "dataset_1_test": {
            "sample_count": len(y_true),
            "baseline": {
                "accuracy": acc_base,
                "macro_f1": macro_base[2],
                "avg_latency_ms": avg_t_base
            },
            "yolo_pipeline": {
                "accuracy": acc_yolo,
                "macro_f1": macro_yolo[2],
                "avg_latency_ms": avg_t_yolo
            }
        },
        "dataset_2_field_sample": {
            "sample_count": len(ext_true),
            "baseline_accuracy": ext_acc_base,
            "yolo_pipeline_accuracy": ext_acc_yolo
        }
    }
    
    with open("artifacts/detector/comparison_report.json", "w") as f:
        json.dump(comparison_data, f, indent=2)
    print("\nSaved comparison report to artifacts/detector/comparison_report.json")

if __name__ == "__main__":
    run_comparison()

