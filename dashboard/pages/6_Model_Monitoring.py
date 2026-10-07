import json

import pandas as pd
import plotly.express as px
import streamlit as st

from common import config, page, query, style_chart

page("Model Performance & Monitoring", "📡")

comparison = config.REPORTS_DIR / "training" / "model_comparison.csv"
meta_file = config.CHAMPION_DIR / "metadata.json"
if not comparison.exists() or not meta_file.exists():
    st.warning("No trained model yet - run `make train`.")
    st.stop()

meta = json.loads(meta_file.read_text())
st.success(f"Champion: **{meta['model_type']}** - registered as `{meta['model_name']}` v{meta['model_version']} "
           f"(MLflow alias `champion`), trained {meta['trained_at'][:16]} UTC on data md5 `{meta['data_md5'][:10]}`")

st.subheader("Model comparison (MLflow runs)")
cmp = pd.read_csv(comparison)
cols = ["model", "val_f1", "val_roc_auc", "test_accuracy", "test_precision", "test_recall", "test_f1", "test_roc_auc"]
st.dataframe(cmp[cols], use_container_width=True, hide_index=True)
long = cmp.melt(id_vars="model", value_vars=["test_precision", "test_recall", "test_f1", "test_roc_auc"],
                var_name="metric", value_name="value")
fig = px.bar(long, x="metric", y="value", color="model", barmode="group", text=long.value.round(2),
             color_discrete_sequence=["#2a78d6", "#eb6834", "#1baf7a"], range_y=[0, 1.05],
             labels={"metric": "", "value": "Test score"})
st.plotly_chart(style_chart(fig, 340), use_container_width=True)

c1, c2 = st.columns(2)
cm = config.REPORTS_DIR / "training" / f"confusion_matrix_{meta['model_type']}.png"
if cm.exists():
    c1.image(str(cm), caption="Champion confusion matrix (test set)")
fi = config.REPORTS_DIR / "training" / f"feature_importance_{meta['model_type']}.csv"
if fi.exists():
    top = pd.read_csv(fi).head(12).iloc[::-1]
    fig = px.bar(top, x="importance", y="feature", orientation="h", color_discrete_sequence=["#2a78d6"],
                 labels={"feature": ""}, title="Top features")
    c2.plotly_chart(style_chart(fig, 380), use_container_width=True)

st.subheader("Drift & retraining monitor")
rep_file = config.REPORTS_DIR / "monitoring" / "latest.json"
if not rep_file.exists():
    st.info("No monitoring report yet - run `make monitor`.")
else:
    rep = json.loads(rep_file.read_text())
    (st.error if rep["retrain_recommended"] else st.success)(
        f"Retraining recommended: **{'YES' if rep['retrain_recommended'] else 'NO'}** "
        f"({rep['dataset']}, {rep['created_at'][:16]} UTC)")
    for r in rep["reasons"]:
        st.markdown(f"- {r}")
    k = st.columns(4)
    k[0].metric("Drifted features", f"{len(rep['drifted_features'])}", f"{rep['drift_share']:.0%} of features",
                delta_color="off")
    k[1].metric("Predicted fail-rate", f"{rep['current_positive_rate']:.1%}",
                f"{(rep['current_positive_rate'] - rep['reference_positive_rate']) * 100:+.1f} pp vs training",
                delta_color="inverse")
    k[2].metric("F1 on current labels", rep["current_f1"] if rep["current_f1"] is not None else "n/a",
                f"reference {rep['reference_f1']}", delta_color="off")
    api = rep["api"]
    k[3].metric("API requests / p95 latency", f"{api['requests']}",
                f"{api['p95_latency_ms']} ms" if api["p95_latency_ms"] else "no traffic", delta_color="off")
    feats = pd.DataFrame(rep["features"]).sort_values("psi", ascending=False)
    feats["status"] = feats.drifted.map({True: "Drifted", False: "Stable"})
    fig = px.bar(feats.head(15).iloc[::-1], x="psi", y="feature", color="status", orientation="h",
                 color_discrete_map={"Drifted": "#d03b3b", "Stable": "#2a78d6"}, labels={"feature": ""},
                 title="Population Stability Index (top 15)")
    fig.add_vline(x=0.2, line_dash="dash", line_color="#898781", annotation_text="drift threshold 0.2")
    st.plotly_chart(style_chart(fig, 460), use_container_width=True)

try:
    hist = query("""SELECT created_at, dataset, model_version, drift_share, current_positive_rate, current_f1,
                           api_requests, api_p95_latency_ms, retrain_recommended, reasons
                    FROM ml.monitoring_reports ORDER BY created_at DESC LIMIT 20""")
    st.subheader("Monitoring history")
    st.dataframe(hist, use_container_width=True, hide_index=True)
except Exception:
    pass
