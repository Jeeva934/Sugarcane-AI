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
than disease probabilities, and saves prediction metadata without saving
uploaded images. A Grad-CAM++ heatmap is included when it can be generated.
Independent field testing, label provenance confirmation, and
calibration/uncertainty validation remain required before making diagnostic
claims.

## Export and verify ONNX parity

The optional ONNX export is generated locally from the trained PyTorch
checkpoint; it is not checked into the repository. Install the ML dependencies
and run:

```powershell
python ml\export_onnx.py
python -m pytest ml\test_edge_cases.py::test_offline_onnx_inference -q
```

The parity test exports the ONNX file first when it is missing, then compares
CPU ONNX Runtime probabilities with PyTorch probabilities on the same
preprocessed image. The test skips if the optional trained checkpoint is
unavailable. The exported model is for offline parity evaluation; the web
application's browser fallback is not ONNX inference.

## Required before training or activation

- Document source, licence, collection protocol, label definitions, and dataset version.
- Keep all images from the same plant/capture session in one split.
- Use time- and location-aware splits for environmental data.
- Match disease labels to contemporaneous, verified occurrence records; weather alone is not a target.
- Save split manifests, random seeds, preprocessing, class mapping, artifact hash, and computed evaluation reports.
- Validate calibration and an uncertainty/abstention threshold before production use.
- Configure artifacts explicitly through `IMAGE_MODEL_PATH` and `RISK_MODEL_PATH`; startup never downloads weights.

## Environmental risk model status

The application can save a farm GPS point and optional soil-test pH, and can
request current weather for that point. Browser GPS requires the user's
permission; it records one point and does not map a field boundary. Open-Meteo
weather is not disease-observation data, and soil pH must be measured and
entered by the user.

No environmental-risk dataset or trained artifact is included in this
repository. `ml/train_risk_model.py` requires
an admin export named `datasets/environmental/verified-environmental-observations.csv`.
An empty header-only starter is provided at
`ml/verified-environmental-observations-template.csv`; it is
not training data and must not be filled with generated or guessed labels.
Farmers can submit field reports from Environmental Risk; reports remain
unverified until an admin records a verification method and evidence reference.
Only explicitly consented, verified reports are included in the admin CSV
export. Training also requires at least 10 distinct dates and at least 10
present and 10 absent labels for a disease in each chronological train,
validation, and test split. Insufficient data causes training to stop rather
than fabricate labels.

Install the optional ML dependencies and train after the verified CSV has
been downloaded from the Admin page:

```powershell
python -m pip install -r ml\requirements.txt
python ml\train_risk_model.py --data datasets\environmental\verified-environmental-observations.csv
```

The script trains a separate XGBoost presence/absence classifier per disease
and writes temporal holdout metrics, SHAP global importance values, and ALE
plots under `artifacts\environmental\`. These observation-time associations
are not a future disease forecast; a lead-time claim requires labels collected
after a defined future window and independent field validation. The app does
not automatically activate trained artifacts.

The backend adapter looks for `xgboost_<disease>.json` in the configured
`RISK_MODEL_PATH` directory (for example `xgboost_redrot.json`). After a
verified dataset and artifact exist, set `ENABLE_EXPERIMENTAL_RISK_MODEL=true`
in the backend `.env` and restart the API. The result is an uncalibrated
observation-time association score, not a future forecast or diagnosis.

The Mendeley Sugarcane Leaf Disease Dataset
([DOI 10.17632/9424skmnrk.1](https://data.mendeley.com/datasets/9424skmnrk/1))
contains leaf images and disease classes only; it has no matching farm
weather/incidence rows and cannot train this environmental model. Open-Meteo's
[Historical Weather API](https://archive-api.open-meteo.com/v1/archive) can
supply past weather features, but disease outcomes still must come from
expert-verified field or laboratory observations with consent. Do not join
image labels to unrelated weather or generate labels with an LLM.

### Synthetic pipeline demo (not for disease prediction)

To demonstrate that the XGBoost/SHAP/ALE software path can run before real
field records are collected, use:

```powershell
python ml\generate_and_train_environmental_demo.py
```

This creates 3,000 synthetic rows under `datasets\environmental_demo\` and
five demo-only models plus SHAP/ALE outputs under
`artifacts\environmental_demo\`. Labels are generated from arbitrary code
rules, not research or observed disease cases. The CSV deliberately does not
match the verified-data training schema, and model filenames use
`demo_xgboost_` so the application inference adapter will not load them.
Metrics from this run only show that the demo training code executed; they
have no agricultural or predictive meaning.

The current UI uses GPS, optional soil-test pH, and current/cached Open-Meteo
weather to show conditions and general monitoring tips. These readings alone
are not a disease diagnosis. Image YOLO/Grad-CAM++ components are not
implemented, and the experimental EfficientNetV2 image classifier cannot
substitute for weather-linked disease occurrence records.
