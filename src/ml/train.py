"""Train baseline + advanced models, track everything in MLflow, register the champion.

    python -m src.ml.train

Steps
 1. Load the analytical feature snapshot (data/processed/student_features.csv, DVC-tracked)
 2. Student-grouped, stratified train / validation / test split
 3. Fit Logistic Regression (baseline), Random Forest, XGBoost
 4. Log params, metrics, confusion matrix, feature importance and the model to MLflow
 5. Choose the champion on validation F1, register it in the MLflow Model Registry
    (alias "champion") and export it to models/champion/ for the FastAPI / Docker service.
"""
import hashlib
import json
import shutil
from datetime import datetime, timezone

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import mlflow  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from mlflow.models import infer_signature  # noqa: E402
from mlflow.tracking import MlflowClient  # noqa: E402
from sklearn.compose import ColumnTransformer  # noqa: E402
from sklearn.ensemble import RandomForestClassifier  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import (ConfusionMatrixDisplay, accuracy_score, f1_score,  # noqa: E402
                             precision_score, recall_score, roc_auc_score)
from sklearn.model_selection import StratifiedGroupKFold  # noqa: E402
from sklearn.pipeline import Pipeline  # noqa: E402
from sklearn.preprocessing import OneHotEncoder, StandardScaler  # noqa: E402
from xgboost import XGBClassifier  # noqa: E402

from src.common import config  # noqa: E402
from src.common.logging_utils import get_logger  # noqa: E402
from src.ml.features import feature_lists, load_params, make_target, prepare_frame  # noqa: E402

log = get_logger("train")


def file_md5(path) -> str:
    return hashlib.md5(open(path, "rb").read()).hexdigest()


def grouped_split(y, groups, params):
    """Stratified + grouped (by student) split into train / val / test index arrays."""
    s = params["split"]
    seed = s["random_state"]
    n_test = round(1 / s["test_fraction"])
    outer = StratifiedGroupKFold(n_splits=n_test, shuffle=True, random_state=seed)
    trainval_idx, test_idx = next(outer.split(np.zeros(len(y)), y, groups))
    n_val = round((1 - s["test_fraction"]) / s["val_fraction"])
    inner = StratifiedGroupKFold(n_splits=n_val, shuffle=True, random_state=seed)
    tr, va = next(inner.split(np.zeros(len(trainval_idx)), y[trainval_idx], groups[trainval_idx]))
    return trainval_idx[tr], trainval_idx[va], test_idx


def build_preprocessor(params):
    num, cat, boo = feature_lists(params)
    return ColumnTransformer([
        ("num", StandardScaler(), num),
        ("cat", OneHotEncoder(handle_unknown="ignore"), cat),
        ("bool", "passthrough", boo),
    ])


def build_models(params, y_train):
    m = params["models"]
    pos_weight = float((y_train == 0).sum() / max((y_train == 1).sum(), 1))
    seed = params["split"]["random_state"]
    return {
        "logistic_regression": LogisticRegression(**m["logistic_regression"], random_state=seed),
        "random_forest": RandomForestClassifier(**m["random_forest"], random_state=seed, n_jobs=-1),
        "xgboost": XGBClassifier(**m["xgboost"], scale_pos_weight=pos_weight, eval_metric="logloss",
                                 random_state=seed, n_jobs=4),
    }


def evaluate(model, X, y, threshold, prefix):
    proba = model.predict_proba(X)[:, 1]
    pred = (proba >= threshold).astype(int)
    return {
        f"{prefix}_accuracy": accuracy_score(y, pred),
        f"{prefix}_precision": precision_score(y, pred, zero_division=0),
        f"{prefix}_recall": recall_score(y, pred, zero_division=0),
        f"{prefix}_f1": f1_score(y, pred, zero_division=0),
        f"{prefix}_roc_auc": roc_auc_score(y, proba),
    }, proba


def feature_importance(pipe) -> pd.DataFrame:
    names = pipe.named_steps["prep"].get_feature_names_out()
    est = pipe.named_steps["model"]
    values = np.abs(est.coef_[0]) if hasattr(est, "coef_") else est.feature_importances_
    return (pd.DataFrame({"feature": names, "importance": values})
            .sort_values("importance", ascending=False).reset_index(drop=True))


def plot_confusion(y, proba, threshold, title, path):
    fig, ax = plt.subplots(figsize=(4, 4))
    ConfusionMatrixDisplay.from_predictions(y, (proba >= threshold).astype(int), display_labels=["Pass", "Fail"],
                                            ax=ax, colorbar=False, cmap="Blues")
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def main():
    params = load_params()
    threshold = params["selection"]["decision_threshold"]
    df = pd.read_csv(config.FEATURES_FILE)
    data_md5 = file_md5(config.FEATURES_FILE)
    X = prepare_frame(df, params)
    y = make_target(df, params).to_numpy()
    groups = df["student_id"].to_numpy()
    tr, va, te = grouped_split(y, groups, params)
    log.info("Split sizes train=%s val=%s test=%s | fail rate train=%.3f val=%.3f test=%.3f",
             len(tr), len(va), len(te), y[tr].mean(), y[va].mean(), y[te].mean())

    mlflow.set_tracking_uri(config.MLFLOW_TRACKING_URI)
    mlflow.set_experiment(config.MLFLOW_EXPERIMENT)
    reports = config.REPORTS_DIR / "training"
    reports.mkdir(parents=True, exist_ok=True)

    results = []
    for name, estimator in build_models(params, y[tr]).items():
        pipe = Pipeline([("prep", build_preprocessor(params)), ("model", estimator)])
        with mlflow.start_run(run_name=name) as run:
            pipe.fit(X.iloc[tr], y[tr])
            val_m, _ = evaluate(pipe, X.iloc[va], y[va], threshold, "val")
            test_m, test_proba = evaluate(pipe, X.iloc[te], y[te], threshold, "test")
            train_m, _ = evaluate(pipe, X.iloc[tr], y[tr], threshold, "train")
            metrics = {**train_m, **val_m, **test_m}

            mlflow.set_tags({"model_type": name, "target": "fail (G3 < 10)", "data_md5": data_md5,
                             "split": "stratified grouped by student_id"})
            mlflow.log_params({f"{name}.{k}": v for k, v in params["models"][name].items()})
            mlflow.log_params({"threshold": threshold, "n_train": len(tr), "n_val": len(va), "n_test": len(te),
                               "n_features": X.shape[1], "data_file": str(config.FEATURES_FILE.name)})
            mlflow.log_metrics(metrics)

            cm_path = reports / f"confusion_matrix_{name}.png"
            plot_confusion(y[te], test_proba, threshold, f"{name} (test)", cm_path)
            fi = feature_importance(pipe)
            fi_path = reports / f"feature_importance_{name}.csv"
            fi.to_csv(fi_path, index=False)
            mlflow.log_artifact(str(cm_path))
            mlflow.log_artifact(str(fi_path))
            mlflow.log_dict(params, "params.yaml")

            sample = X.iloc[tr].head(5)
            mlflow.sklearn.log_model(pipe, artifact_path="model",
                                     signature=infer_signature(sample, pipe.predict_proba(sample)),
                                     input_example=sample)
            log.info("%-20s val_f1=%.3f val_auc=%.3f test_f1=%.3f test_auc=%.3f", name, metrics["val_f1"],
                     metrics["val_roc_auc"], metrics["test_f1"], metrics["test_roc_auc"])
            results.append({"model": name, "run_id": run.info.run_id, "pipeline": pipe, **metrics})

    comparison = pd.DataFrame([{k: v for k, v in r.items() if k != "pipeline"} for r in results])
    comparison.round(4).to_csv(reports / "model_comparison.csv", index=False)
    best = sorted(results, key=lambda r: (r["val_f1"], r["val_roc_auc"]), reverse=True)[0]
    log.info("Champion: %s (val_f1=%.3f)", best["model"], best["val_f1"])

    # ---- Model registry ----
    client = MlflowClient()
    mv = mlflow.register_model(f"runs:/{best['run_id']}/model", config.REGISTERED_MODEL_NAME)
    client.set_registered_model_alias(config.REGISTERED_MODEL_NAME, "champion", mv.version)
    client.set_model_version_tag(config.REGISTERED_MODEL_NAME, mv.version, "model_type", best["model"])
    client.set_model_version_tag(config.REGISTERED_MODEL_NAME, mv.version, "data_md5", data_md5)
    client.update_model_version(config.REGISTERED_MODEL_NAME, mv.version,
                                description=f"{best['model']} - val F1 {best['val_f1']:.3f}, "
                                            f"test F1 {best['test_f1']:.3f}, test AUC {best['test_roc_auc']:.3f}")
    log.info("Registered %s version %s with alias 'champion'", config.REGISTERED_MODEL_NAME, mv.version)

    # ---- Export champion for serving (FastAPI / Docker) + monitoring reference ----
    out = config.CHAMPION_DIR
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    joblib.dump(best["pipeline"], out / "model.joblib")
    ref = X.iloc[tr].copy()
    ref["target"] = y[tr]
    ref["fail_probability"] = best["pipeline"].predict_proba(X.iloc[tr])[:, 1]
    ref.to_csv(out / "reference_data.csv", index=False)
    metadata = {
        "model_name": config.REGISTERED_MODEL_NAME,
        "model_version": str(mv.version),
        "model_type": best["model"],
        "mlflow_run_id": best["run_id"],
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "data_md5": data_md5,
        "decision_threshold": threshold,
        "target": "fail = final grade (G3) < 10",
        "features": {"numeric": params["features"]["numeric"], "categorical": params["features"]["categorical"],
                     "boolean": params["features"]["boolean"]},
        "metrics": {k: round(float(v), 4) for k, v in best.items() if k.startswith(("train_", "val_", "test_"))},
    }
    (out / "metadata.json").write_text(json.dumps(metadata, indent=2))
    shutil.copy(config.PARAMS_FILE, out / "params.yaml")

    # DVC metrics file
    (config.REPORTS_DIR / "metrics.json").write_text(json.dumps({
        "champion": best["model"], "model_version": int(mv.version),
        **{r["model"]: {k: round(float(r[k]), 4) for k in ("val_f1", "val_roc_auc", "test_f1", "test_roc_auc",
                                                             "test_precision", "test_recall", "test_accuracy")}
           for r in results}}, indent=2))
    log.info("Champion exported to %s", out)


if __name__ == "__main__":
    main()
