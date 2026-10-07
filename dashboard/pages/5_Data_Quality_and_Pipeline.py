import plotly.express as px
import streamlit as st

from common import page, safe_query, style_chart

page("Data Quality & Pipeline Runs", "🧪")

runs = safe_query("""SELECT run_id, triggered_by, status, started_at, finished_at,
                            round(extract(epoch FROM finished_at - started_at)::numeric, 1) AS duration_s, message
                     FROM audit.pipeline_runs ORDER BY started_at DESC LIMIT 50""")
st.subheader("Pipeline runs")
st.dataframe(runs, use_container_width=True, hide_index=True)
if runs.empty:
    st.stop()
run_id = st.selectbox("Inspect run", runs.run_id)

st.subheader("Ingestion log (extraction date, source, status, row count)")
st.dataframe(safe_query("""SELECT source_name, source_type, extracted_at, status, row_count, failed_row_count,
                                  raw_path, left(checksum_sha256, 12) AS sha256, error_message
                           FROM audit.ingestion_log WHERE run_id = :r ORDER BY id""", r=run_id),
             use_container_width=True, hide_index=True)

st.subheader("Data-quality checks")
dq = safe_query("""SELECT check_name, table_name, severity, passed, observed_value, expectation
                   FROM audit.dq_results WHERE run_id = :r ORDER BY id""", r=run_id)
if not dq.empty:
    st.metric("Checks passed", f"{int(dq.passed.sum())} / {len(dq)}")
    dq["result"] = dq.passed.map({True: "✅ PASS", False: "❌ FAIL"})
    st.dataframe(dq.drop(columns="passed"), use_container_width=True, hide_index=True)

st.subheader("Rejected records")
rej = safe_query("""SELECT stage, source_name, rule_name, record_key, reason, record, logged_at
                    FROM audit.rejected_records WHERE run_id = :r ORDER BY id""", r=run_id)
if rej.empty:
    st.success("No records were rejected in this run - every source row passed all validation rules.")
else:
    fig = px.bar(rej.groupby("rule_name").size().reset_index(name="rows"), x="rows", y="rule_name",
                 orientation="h", color_discrete_sequence=["#2a78d6"], text="rows", labels={"rule_name": ""})
    st.plotly_chart(style_chart(fig, 260), use_container_width=True)
    st.dataframe(rej, use_container_width=True, hide_index=True)

st.subheader("Warehouse row counts")
st.dataframe(safe_query("""
    SELECT 'staging.stg_uci_student' AS table_name, count(*) AS rows FROM staging.stg_uci_student
    UNION ALL SELECT 'clean.student', count(*) FROM clean.student
    UNION ALL SELECT 'clean.enrollment', count(*) FROM clean.enrollment
    UNION ALL SELECT 'analytics.dim_student', count(*) FROM analytics.dim_student
    UNION ALL SELECT 'analytics.dim_subject', count(*) FROM analytics.dim_subject
    UNION ALL SELECT 'analytics.dim_term', count(*) FROM analytics.dim_term
    UNION ALL SELECT 'analytics.fact_student_term', count(*) FROM analytics.fact_student_term
    UNION ALL SELECT 'analytics.fact_enrollment', count(*) FROM analytics.fact_enrollment
    UNION ALL SELECT 'analytics.mart_student_subject', count(*) FROM analytics.mart_student_subject
    UNION ALL SELECT 'analytics.mart_subject_term_summary', count(*) FROM analytics.mart_subject_term_summary
    UNION ALL SELECT 'analytics.mart_student_overview', count(*) FROM analytics.mart_student_overview
    UNION ALL SELECT 'ml.risk_predictions', count(*) FROM ml.risk_predictions"""),
    use_container_width=True, hide_index=True)
