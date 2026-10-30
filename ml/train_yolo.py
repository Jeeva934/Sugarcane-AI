import os
import shutil
from pathlib import Path
from ultralytics import YOLO

def train_yolo():
    data_yaml = Path("datasets/yolo_leaf_detection/data.yaml").resolve()
    print(f"Loading base YOLO11n model...")
    model = YOLO("yolo11n.pt")
    
    output_dir = Path("artifacts/detector")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Starting YOLO11 training on sugarcane leaf dataset...")
    # Train with 5 epochs, imgsz=320, batch=16 for CPU efficiency
    results = model.train(
        data=str(data_yaml),
        epochs=5,
        imgsz=320,
        batch=16,
        workers=0,
        device="cpu",
        project="artifacts/detector/runs",
        name="yolo11_sugarcane_leaf",
        exist_ok=True,
        verbose=True
    )
    
    print("Training finished! Evaluating detector metrics...")
    metrics = model.val(data=str(data_yaml), split="val", imgsz=320, device="cpu")
    
    # Save the trained model checkpoint to artifacts/detector/yolo11_leaf.pt
    best_weights = Path("artifacts/detector/runs/yolo11_sugarcane_leaf/weights/best.pt")
    target_weights = output_dir / "yolo11_leaf.pt"
    if best_weights.is_file():
        shutil.copy2(best_weights, target_weights)
        print(f"Copied best detector weights to {target_weights}")
    else:
        # Fallback to last.pt if best.pt is not distinct
        last_weights = Path("artifacts/detector/runs/yolo11_sugarcane_leaf/weights/last.pt")
        if last_weights.is_file():
            shutil.copy2(last_weights, target_weights)
            print(f"Copied last detector weights to {target_weights}")
            
    print("\n--- Detector Performance Metrics ---")
    print(f"mAP50: {metrics.box.map50:.4f}")
    print(f"mAP50-95: {metrics.box.map:.4f}")
    print(f"Precision: {metrics.box.mp:.4f}")
    print(f"Recall: {metrics.box.mr:.4f}")
    
    import json
    metrics_summary = {
        "mAP50": float(metrics.box.map50),
        "mAP50_95": float(metrics.box.map),
        "precision": float(metrics.box.mp),
        "recall": float(metrics.box.mr),
        "fitness": float(metrics.box.fitness)
    }
    with open(output_dir / "detector_metrics.json", "w") as f:
        json.dump(metrics_summary, f, indent=2)

if __name__ == "__main__":
    train_yolo()

