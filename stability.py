"""Predicts thermodynamic stability (E_above_hull) from the composition-derived features.

One row per material is used for training (E_above_hull does not depend on temperature). Accuracy is measured
by leaving one material out at a time, and that error is what the app reports next to every prediction.
"""
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.metrics import mean_absolute_error, r2_score, roc_auc_score
from sklearn.model_selection import LeaveOneOut, cross_val_predict

TARGET = "E_above_hull"
INFO_FILE = "stability_info.json"


def _model():
    return ExtraTreesRegressor(n_estimators=300, min_samples_leaf=2, random_state=0, n_jobs=-1)


def data_hash(model_dir):
    h = hashlib.sha1()
    for s in ("train", "val", "test"):
        f = Path(model_dir) / "processed" / f"X_{s}.npy"
        h.update(f.read_bytes() if f.exists() else b"")
    return h.hexdigest()[:16]


def _materials(frame, cols):
    return frame.round(6).drop_duplicates(subset=list(cols)).reset_index(drop=True)


def evaluate(frame, cols, limit):
    M = _materials(frame, cols)
    X, y = M[list(cols)], M[TARGET].to_numpy(float)
    p = cross_val_predict(_model(), X, y, cv=LeaveOneOut())
    stable = y <= limit
    info = {
        "limit": float(limit), "n_materials": int(len(M)), "base_rate": round(float(stable.mean()), 3),
        "loo_r2": round(float(r2_score(y, p)), 3), "loo_mae": round(float(mean_absolute_error(y, p)), 1),
        "loo_rmse": round(float(np.sqrt(np.mean((y - p) ** 2))), 1),
        "accuracy": round(float(np.mean((p <= limit) == stable)), 3),
        "majority_accuracy": round(float(max(stable.mean(), 1 - stable.mean())), 3),
        "auc": round(float(roc_auc_score(stable, -p)), 3) if 0 < stable.sum() < len(stable) else None,
    }
    return info


def load_or_fit(frame, cols, model_dir, limit):
    """Fit the final model (about a second). Cross-validated metrics come from a cached JSON when it still
    matches the training data, otherwise they are recomputed once."""
    model_dir = Path(model_dir)
    h = data_hash(model_dir)
    info = None
    f = model_dir / INFO_FILE
    try:
        cached = json.loads(f.read_text())
        if cached.get("data_hash") == h and cached.get("limit") == float(limit) and cached.get("cols") == list(cols):
            info = cached
    except Exception:
        pass
    if info is None:
        info = evaluate(frame, cols, limit)
        info.update(data_hash=h, cols=list(cols))
        try:
            f.write_text(json.dumps(info, indent=1))
        except Exception:
            pass
    M = _materials(frame, cols)
    model = _model().fit(M[list(cols)], M[TARGET].to_numpy(float))
    return model, info, list(cols)


def predict(model, info, cols, row):
    """row: one-row DataFrame that contains the composition columns."""
    e = float(model.predict(row[cols])[0])
    sigma = max(float(info["loo_rmse"]), 1e-6)
    p = 0.5 * (1 + math.erf((info["limit"] - e) / (sigma * math.sqrt(2))))
    return {"kind": "predicted", "ehull": round(e, 1), "limit": info["limit"], "stable": bool(e <= info["limit"]),
            "p_stable": round(p, 3), "sigma": info["loo_rmse"],
            "cv": {k: info[k] for k in ("n_materials", "loo_mae", "accuracy", "majority_accuracy", "auc")}}
