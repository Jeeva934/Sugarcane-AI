# ML data and model workflow

The image ZIP supplied for this project is the five-class Sugarcane Leaf
Disease Dataset hosted on Mendeley Data (DOI `10.17632/9424skmnrk.1`) and mirrored
on Kaggle. The Mendeley description reports 2,569 manually collected smartphone
images from Maharashtra, India. The supplied archive has 2,521 JPEGs. Kaggle
reports CC0 1.0; check the current source page before redistribution.

The dataset description says images were manually collected, but does not
establish independent expert verification of the labels. Do not claim expert
validation without separate documentation. This small, single-source dataset
supports a research prototype only; it is not independent field validation.
The image and environmental inference modules are not automatically activated.

## Audit image files

Organize images under class directories, preserve the original source data, and
record licences and plant/capture-session identifiers separately. Run:

```powershell
python ml\data_audit.py path\to\images
```

The audit reports file counts and exact byte-identical duplicates only. It does
not validate class labels, detect near-duplicates, or prove that data splits are
leakage-free.

## Train the experimental image classifier

Install the optional ML dependencies in the same Python environment used for
the backend. The pinned CPU wheels work without Docker or a GPU.

```powershell
python -m pip install -r ml\requirements.txt
Expand-Archive -LiteralPath C:\Users\yourname\Downloads\archive.zip -DestinationPath datasets\sugarcane_mendeley_v1
python ml\train_classifier.py --data-dir datasets\sugarcane_mendeley_v1 --pretrained --epochs 5
```

`--pretrained` explicitly opts into downloading official torchvision ImageNet
weights at training time; the web API never downloads model files. The default
run freezes the EfficientNetV2-S feature extractor and trains only the new
five-class output layer, a lighter transfer-learning baseline for CPU machines.
The script
deduplicates byte-identical images before creating stratified train/validation/
test splits and writes the split hashes, trained checkpoint, and actually
computed test metrics under `artifacts\image\`. It refuses to train from random
initialization on this small dataset.

The resulting checkpoint is **experimental and not production validated**.
It is not independent field validation; the held-out split shares the same
source and collection conditions. The recorded run scored 0.7839 accuracy and
0.7867 macro-F1 on 347 exact-deduplicated, stratified test images from that same
archive. These figures are dataset-split metrics, not field performance. The
application can run its experimental classifier adapter only after explicit
opt-in. Set the following in `.env`, install `ml\requirements.txt` in the
backend's Python environment, and restart the API:

```env
IMAGE_MODEL_PATH=artifacts/image/efficientnet_v2_s.pt
ENABLE_EXPERIMENTAL_IMAGE_MODEL=true
```

The API labels results experimental, returns uncalibrated model scores rather
than disease probabilities, does not create Grad-CAM++ explanations, and does
not save uploaded images or diagnoses to history. Independent field testing,
label provenance confirmation, and calibration/uncertainty validation remain
required before making diagnostic claims.

## Required before training or activation

- Document source, licence, collection protocol, label definitions, and dataset version.
- Keep all images from the same plant/capture session in one split.
- Use time- and location-aware splits for environmental data.
- Match disease labels to contemporaneous, verified occurrence records; weather alone is not a target.
- Save split manifests, random seeds, preprocessing, class mapping, artifact hash, and computed evaluation reports.
- Validate calibration and an uncertainty/abstention threshold before production use.
- Configure artifacts explicitly through `IMAGE_MODEL_PATH` and `RISK_MODEL_PATH`; startup never downloads weights.

The environmental XGBoost/SHAP/ALE and image YOLO/Grad-CAM++ components are not
implemented. An experimental EfficientNetV2 classifier training script is
provided for this dataset; its evaluation results must not be presented as
real-world diagnostic accuracy.
