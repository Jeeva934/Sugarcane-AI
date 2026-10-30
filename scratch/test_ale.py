import numpy as np
import pandas as pd
from xgboost import XGBClassifier
from PyALE import ale
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

X = pd.DataFrame({
    'temp': np.random.uniform(15, 35, 100),
    'rh': np.random.uniform(40, 95, 100)
})
y = (X['temp'] > 25) & (X['rh'] > 70)

clf = XGBClassifier(n_estimators=10, max_depth=3, eval_metric='logloss')
clf.fit(X, y)

class ModelProbWrapper:
    def __init__(self, m):
        self.m = m
    def predict(self, df):
        return self.m.predict_proba(df)[:, 1]

wrapper = ModelProbWrapper(clf)
fig, ax = plt.subplots()
ale_res = ale(X=X, model=wrapper, feature=['temp'], grid_size=10, plot=False)
print("ALE computed successfully:", ale_res.head(3))
