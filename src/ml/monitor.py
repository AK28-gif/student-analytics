"""Model monitoring: feature drift, class distribution, prediction performance,
API latency/failures -> retraining recommendation.

    python -m src.ml.monitor                   # current data = analytics mart (latest pipeline run)
    python -m src.ml.monitor --source api      # current data = inputs received by the FastAPI service
    python -m src.ml.monitor --simulate-drift  # demo: perturb current data to show the retrain trigger

Writes reports/monitoring/latest.json + latest.html and a row in ml.monitoring_reports.

Retraining criteria (params.yaml -> monitoring):
  * share of drifted features > drift_share_threshold, OR
    (numeric feature drifted = PSI > psi_threshold AND KS-test p < 0.05; categorical = PSI only)
  * any key feature drifted, OR
  * F1 on newly labelled data dropped > f1_drop_threshold vs. test F1 at training time, OR
  * predicted fail-rate moved > positive_rate_shift vs. the training reference.
"""
import argparse
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp
from sklearn.metrics import f1_score
from sqlalchemy import text

from src.common import config, db
from src.common.logging_utils import get_logger
from src.ml.features import feature_lists, load_params, make_target, prepare_frame
from src.ml.predict import load_champion

log = get_logger("monitor")
EPS = 1e-4


def psi_numeric(ref: pd.Series, cur: pd.Series, bins: int = 10) -> float:
    ref, cur = ref.dropna(), cur.dropna()
    edges = np.unique(np.quantile(ref, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:  # (almost) constant feature: compare value frequencies instead
        return psi_categorical(ref.astype(str), cur.astype(str))
    edges[0], edges[-1] = -np.inf, np.inf
    r = np.histogram(ref, edges)[0] / len(ref)
    c = np.histogram(cur, edges)[0] / max(len(cur), 1)
    r, c = np.clip(r, EPS, None), np.clip(c, EPS, None)
    return float(np.sum((c - r) * np.log(c / r)))


def psi_categorical(ref: pd.Series, cur: pd.Series) -> float:
    cats = set(ref.unique()) | set(cur.unique())
    r = ref.value_counts(normalize=True).reindex(cats, fill_value=0).clip(lower=EPS)
    c = cur.value_counts(normalize=True).reindex(cats, fill_value=0).clip(lower=EPS)
    return float(np.sum((c - r) * np.log(c / r)))


def load_api_inputs() -> pd.DataFrame:
    if not config.PREDICTION_LOG.exists():
        return pd.DataFrame()
    rows = [json.loads(l) for l in config.PREDICTION_LOG.read_text().splitlines() if l.strip()]
    return pd.DataFrame([r["input"] for r in rows if r.get("status") == "ok" and r.get("input")])


def api_health() -> dict:
    if not config.PREDICTION_LOG.exists():
        return {"requests": 0, "error_rate": None, "p95_latency_ms": None}
    rows = [json.loads(l) for l in config.PREDICTION_LOG.read_text().splitlines() if l.strip()]
    if not rows:
        return {"requests": 0, "error_rate": None, "p95_latency_ms": None}
    lat = [r["latency_ms"] for r in rows if r.get("latency_ms") is not None]
    return {"requests": len(rows),
            "error_rate": round(sum(r.get("status") != "ok" for r in rows) / len(rows), 4),
            "p95_latency_ms": round(float(np.percentile(lat, 95)), 2) if lat else None}


def simulate_drift(df: pd.DataFrame, seed: int = 7) -> pd.DataFrame:
    """Demo only: a cohort with lower period grades and more absences."""
    rng = np.random.default_rng(seed)
    d = df.copy()
    for c in ("grade_p1", "grade_p2"):
        d[c] = (d[c] - rng.integers(1, 5, len(d))).clip(0, 20)
    d["avg_internal_marks"] = (d["grade_p1"] + d["grade_p2"]) / 2
    d["grade_trend"] = d["grade_p2"] - d["grade_p1"]
    d["absences"] = (d["absences"] * 1.8 + rng.integers(0, 10, len(d))).clip(0, 93)
    d["attendance_pct"] = ((config.SESSIONS_PER_YEAR - d["absences"]) / config.SESSIONS_PER_YEAR * 100).clip(0, 100)
    return d


def run_monitoring(source: str = "mart", simulate: bool = False) -> dict:
    model, meta = load_champion()
    params = load_params(config.CHAMPION_DIR / "params.yaml")
    mon = load_params()["monitoring"]
    num, cat, boo = feature_lists(params)
    reference = pd.read_csv(config.CHAMPION_DIR / "reference_data.csv")

    labels = None
    if source == "api":
        raw = load_api_inputs()
        if raw.empty:
            raise RuntimeError("No successful API requests logged yet - call /predict first.")
    else:
        with db.transaction() as conn:
            raw = pd.read_sql(text("SELECT * FROM analytics.mart_student_subject"), conn)
    if simulate:
        raw = simulate_drift(raw)
    current = prepare_frame(raw, params)
    if "final_grade" in raw.columns:
        labels = make_target(raw, params).to_numpy()

    # 1) feature drift
    features = []
    for c in num + cat + boo:
        if c in num:
            psi = psi_numeric(reference[c], current[c])
            ks_p = float(ks_2samp(reference[c].dropna(), current[c].dropna()).pvalue)
        else:
            psi = psi_categorical(reference[c].astype(str), current[c].astype(str))
            ks_p = None
        features.append({"feature": c, "psi": round(psi, 4), "ks_pvalue": None if ks_p is None else round(ks_p, 4),
                         "ref_mean": round(float(pd.to_numeric(reference[c], errors="coerce").mean()), 3) if c not in cat else None,
                         "cur_mean": round(float(pd.to_numeric(current[c], errors="coerce").mean()), 3) if c not in cat else None,
                         # numeric: PSI must exceed the threshold AND the KS test must agree (p < 0.05);
                         # this avoids false alarms from PSI noise on small samples
                         "drifted": psi > mon["psi_threshold"] and (ks_p is None or ks_p < 0.05)})
    drifted = [f["feature"] for f in features if f["drifted"]]
    drift_share = len(drifted) / len(features)

    # 2) class / prediction distribution
    proba = model.predict_proba(current)[:, 1]
    thr = meta["decision_threshold"]
    ref_pos = float((reference["fail_probability"] >= thr).mean())
    cur_pos = float((proba >= thr).mean())

    # 3) performance (only when ground truth is available)
    ref_f1 = meta["metrics"].get("test_f1")
    cur_f1 = float(f1_score(labels, (proba >= thr).astype(int))) if labels is not None else None
    actual_rate = float(labels.mean()) if labels is not None else None

    # 4) service health
    api = api_health()

    reasons = []
    if len(current) < mon.get("min_rows", 30):
        drifted, drift_share = [], 0.0
        log.warning("Only %s rows - too few for reliable drift statistics, drift checks skipped", len(current))
    if drift_share > mon["drift_share_threshold"]:
        reasons.append(f"{drift_share:.0%} of features drifted (> {mon['drift_share_threshold']:.0%})")
    key = [f for f in drifted if f in mon["key_features"]]
    if key:
        reasons.append(f"key features drifted: {', '.join(key)}")
    if cur_f1 is not None and ref_f1 is not None and ref_f1 - cur_f1 > mon["f1_drop_threshold"]:
        reasons.append(f"F1 dropped from {ref_f1:.3f} to {cur_f1:.3f}")
    if abs(cur_pos - ref_pos) > mon["positive_rate_shift"]:
        reasons.append(f"predicted fail-rate moved {ref_pos:.1%} -> {cur_pos:.1%}")
    if api["error_rate"] is not None and api["error_rate"] > 0.05:
        reasons.append(f"API error rate {api['error_rate']:.1%} (> 5%) - investigate service")

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(), "model_version": meta["model_version"],
        "model_type": meta["model_type"], "dataset": f"{source}{' (simulated drift)' if simulate else ''}",
        "rows": int(len(current)), "drift_share": round(drift_share, 3), "drifted_features": drifted,
        "reference_positive_rate": round(ref_pos, 3), "current_positive_rate": round(cur_pos, 3),
        "actual_fail_rate": None if actual_rate is None else round(actual_rate, 3),
        "reference_f1": ref_f1, "current_f1": None if cur_f1 is None else round(cur_f1, 3),
        "api": api, "retrain_recommended": bool(reasons), "reasons": reasons, "features": features,
    }
    _save(report)
    log.info("Monitoring (%s): drift_share=%.2f drifted=%s pos_rate %.3f->%.3f f1=%s retrain=%s %s",
             report["dataset"], drift_share, drifted, ref_pos, cur_pos, report["current_f1"],
             report["retrain_recommended"], reasons)
    return report


def _save(report: dict) -> None:
    out = config.REPORTS_DIR / "monitoring"
    out.mkdir(parents=True, exist_ok=True)
    (out / "latest.json").write_text(json.dumps(report, indent=2))
    rows = "".join(
        f"<tr class={'drift' if f['drifted'] else ''}><td>{f['feature']}</td><td>{f['psi']}</td>"
        f"<td>{f['ks_pvalue'] if f['ks_pvalue'] is not None else '-'}</td><td>{f['ref_mean'] if f['ref_mean'] is not None else '-'}</td>"
        f"<td>{f['cur_mean'] if f['cur_mean'] is not None else '-'}</td><td>{'YES' if f['drifted'] else 'no'}</td></tr>"
        for f in sorted(report["features"], key=lambda f: -f["psi"]))
    html = f"""<!doctype html><html><head><meta charset=utf-8><title>Model monitoring report</title>
<style>body{{font-family:system-ui,sans-serif;margin:2rem;max-width:960px}}table{{border-collapse:collapse;width:100%}}
td,th{{border:1px solid #ccc;padding:4px 8px;text-align:left}}tr.drift{{background:#fde2e2}}
.ok{{color:#1a7f37}}.bad{{color:#c62828}}</style></head><body>
<h1>Model monitoring report</h1>
<p>{report['created_at']} &middot; model v{report['model_version']} ({report['model_type']}) &middot; dataset: {report['dataset']} ({report['rows']} rows)</p>
<h2 class="{'bad' if report['retrain_recommended'] else 'ok'}">Retraining recommended: {'YES' if report['retrain_recommended'] else 'NO'}</h2>
<ul>{''.join(f'<li>{r}</li>' for r in report['reasons']) or '<li>No retraining criteria triggered</li>'}</ul>
<h3>Summary</h3><ul>
<li>Drift share: {report['drift_share']:.0%} ({len(report['drifted_features'])} features)</li>
<li>Predicted fail-rate: reference {report['reference_positive_rate']:.1%} &rarr; current {report['current_positive_rate']:.1%}</li>
<li>F1: reference (test) {report['reference_f1']} &rarr; current {report['current_f1']}</li>
<li>API: {report['api']['requests']} requests, error rate {report['api']['error_rate']}, p95 latency {report['api']['p95_latency_ms']} ms</li></ul>
<h3>Feature drift (PSI &gt; threshold highlighted)</h3>
<table><tr><th>Feature</th><th>PSI</th><th>KS p-value</th><th>Ref mean</th><th>Current mean</th><th>Drifted</th></tr>{rows}</table>
</body></html>"""
    (out / "latest.html").write_text(html)
    try:
        db.run("""INSERT INTO ml.monitoring_reports (model_version, dataset, drift_share, drifted_features,
                     reference_positive_rate, current_positive_rate, reference_f1, current_f1, api_requests,
                     api_error_rate, api_p95_latency_ms, retrain_recommended, reasons, report)
                  VALUES (:v, :d, :ds, :df, :rp, :cp, :rf, :cf, :ar, :ae, :al, :rr, :rs, CAST(:rep AS JSONB))""",
               v=report["model_version"], d=report["dataset"], ds=report["drift_share"],
               df=", ".join(report["drifted_features"]), rp=report["reference_positive_rate"],
               cp=report["current_positive_rate"], rf=report["reference_f1"], cf=report["current_f1"],
               ar=report["api"]["requests"], ae=report["api"]["error_rate"], al=report["api"]["p95_latency_ms"],
               rr=report["retrain_recommended"], rs="; ".join(report["reasons"]), rep=json.dumps(report))
    except Exception as exc:  # monitoring report files are still written if the DB is unavailable
        log.warning("Could not store monitoring report in PostgreSQL: %s", exc)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--source", choices=["mart", "api"], default="mart")
    p.add_argument("--simulate-drift", action="store_true")
    a = p.parse_args()
    run_monitoring(a.source, a.simulate_drift)
