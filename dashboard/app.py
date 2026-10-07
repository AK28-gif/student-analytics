"""Streamlit dashboard - home / overview page.   Run: streamlit run dashboard/app.py"""
import plotly.express as px
import streamlit as st

from common import (RISK_COLORS, RISK_ORDER, STATUS_COLORS, SUBJECT_COLORS, mart, page, safe_query,
                    sidebar_filters, style_chart)

page("Student Performance & Dropout-Risk Dashboard")
st.caption("Source: UCI Student Performance dataset (Cortez & Silva, 2008) - two Portuguese secondary schools, "
           "Mathematics and Portuguese. Data flows UCI -> Airflow ETL -> PostgreSQL warehouse -> this dashboard.")

df = sidebar_filters(mart())
if df.empty:
    st.warning("No enrolments match the current filters.")
    st.stop()

# ---- KPI row ----
n_students = df.student_id.nunique()
pass_rate = (df.pass_status == "Pass").mean() * 100
c = st.columns(5)
c[0].metric("Students", f"{n_students:,}", help="Distinct students (standardised ids across both subjects)")
c[1].metric("Enrolments", f"{len(df):,}", help="Student x subject")
c[2].metric("Pass rate", f"{pass_rate:.1f}%", help="Final grade G3 >= 10 / 20")
c[3].metric("Avg attendance", f"{df.attendance_pct.mean():.1f}%",
            help="(120 sessions - absences) / 120. See data dictionary.")
c[4].metric("High-risk enrolments", f"{(df.risk_level == 'High').sum():,}",
            help="Rule-based early-warning score >= 5 (uses G1/G2, attendance, failures...)")

st.divider()
left, right = st.columns(2)
with left:
    st.subheader("Pass / fail by subject")
    g = df.groupby(["subject_name", "pass_status"]).size().reset_index(name="enrolments")
    fig = px.bar(g, x="subject_name", y="enrolments", color="pass_status", barmode="group", text="enrolments",
                 color_discrete_map=STATUS_COLORS, category_orders={"pass_status": ["Pass", "Fail"]},
                 labels={"subject_name": "", "pass_status": "Result"})
    fig.update_traces(textposition="outside", marker_line_width=2, marker_line_color="rgba(0,0,0,0)")
    st.plotly_chart(style_chart(fig), use_container_width=True)
with right:
    st.subheader("Early-warning risk level by subject")
    g = df.groupby(["subject_name", "risk_level"]).size().reset_index(name="enrolments")
    fig = px.bar(g, x="enrolments", y="subject_name", color="risk_level", orientation="h", text="enrolments",
                 color_discrete_map=RISK_COLORS, category_orders={"risk_level": RISK_ORDER},
                 labels={"subject_name": "", "risk_level": "Risk"})
    st.plotly_chart(style_chart(fig), use_container_width=True)

st.subheader("Final grade distribution")
fig = px.histogram(df, x="final_grade", color="subject_name", barmode="group", nbins=21,
                   color_discrete_map=SUBJECT_COLORS, labels={"final_grade": "Final grade G3 (0-20)",
                                                              "subject_name": "Subject"})
fig.add_vline(x=9.5, line_dash="dash", line_color="#898781", annotation_text="Pass mark (10)")
st.plotly_chart(style_chart(fig, 320), use_container_width=True)

runs = safe_query("""SELECT run_id, triggered_by, status, started_at, finished_at, message
                     FROM audit.pipeline_runs ORDER BY started_at DESC LIMIT 1""")
if not runs.empty:
    r = runs.iloc[0]
    st.info(f"Last pipeline run **{r.run_id}** ({r.triggered_by}) - **{r.status}** at "
            f"{r.finished_at:%Y-%m-%d %H:%M UTC}. {r.message or ''}")

st.markdown("""
**Pages** (sidebar): Performance Analysis · High-Risk Students · Student Profile & Intervention ·
Risk Prediction (FastAPI model) · Data Quality & Pipeline · Model Monitoring
""")
