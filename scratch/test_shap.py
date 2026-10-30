import numpy as np
import pandas as pd
from xgboost import XGBClassifier
import shap
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

X = pd.DataFrame({
    'temp': np.random.uniform(15, 35, 100),
    'rh': np.random.uniform(40, 95, 100)
})
y = ((X['temp'] > 25) & (X['rh'] > 70)).astype(int)

# Test 1: base_score=0.5
clf = XGBClassifier(n_estimators=10, max_depth=3, eval_metric='logloss', base_score=0.5)
clf.fit(X, y)

try:
    explainer = shap.TreeExplainer(clf)
    shap_vals = explainer(X)
    print("TreeExplainer with base_score=0.5 worked!")
except Exception as e:
    print("TreeExplainer failed:", e)

# Test 2: Generic Explainer / Exact / Kernel or xgboost version
try:
    explainer2 = shap.Explainer(clf.predict, X)
    shap_vals2 = explainer2(X[:20])
    print("Generic Explainer worked, shape:", shap_vals2.shape)
except Exception as e:
    print("Generic Explainer failed:", e)
