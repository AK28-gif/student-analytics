import plotly.express as px
import streamlit as st

from common import SCHOOL_COLORS, STATUS_COLORS, SUBJECT_COLORS, mart, page, safe_query, sidebar_filters, style_chart

page("Performance Analysis", "📈")
df = sidebar_filters(mart())
if df.empty:
    st.warning("No enrolments match the current filters.")
    st.stop()

# 1. Attendance vs marks
st.subheader("1 · Attendance vs. final marks")
fig = px.scatter(df, x="attendance_pct", y="final_grade", color="subject_name", opacity=0.6,
                 color_discrete_map=SUBJECT_COLORS,
                 hover_data={"student_id": True, "absences": True, "avg_internal_marks": True},
                 labels={"attendance_pct": "Attendance (%)", "final_grade": "Final grade (0-20)",
                         "subject_name": "Subject"})
fig.update_traces(marker=dict(size=8, line=dict(width=1, color="rgba(255,255,255,0.8)")))
fig.add_hline(y=9.5, line_dash="dash", line_color="#898781", annotation_text="Pass mark")
st.plotly_chart(style_chart(fig, 420), use_container_width=True)

band = df.assign(attendance_band=df.attendance_pct.apply(
    lambda p: "< 75%" if p < 75 else "75-85%" if p < 85 else "85-95%" if p < 95 else ">= 95%"))
tbl = (band.groupby("attendance_band")
       .agg(enrolments=("student_id", "count"), avg_final_grade=("final_grade", "mean"),
            pass_rate=("pass_status", lambda s: (s == "Pass").mean() * 100))
       .reindex(["< 75%", "75-85%", "85-95%", ">= 95%"]).dropna().round(1))
st.dataframe(tbl, use_container_width=True)
st.caption(f"Correlation attendance vs final grade: r = {df.attendance_pct.corr(df.final_grade):.2f}. "
           "Interpretation: in this dataset absences alone are a weak predictor; internal marks matter far more.")

# 2. Subject-wise pass/fail
st.subheader("2 · Subject-wise pass / fail distribution by school")
g = df.groupby(["subject_name", "school", "pass_status"]).size().reset_index(name="enrolments")
g["share"] = g.enrolments / g.groupby(["subject_name", "school"]).enrolments.transform("sum") * 100
fig = px.bar(g, x="school", y="share", color="pass_status", facet_col="subject_name", text=g.share.round(0),
             color_discrete_map=STATUS_COLORS, category_orders={"pass_status": ["Pass", "Fail"]},
             labels={"share": "% of enrolments", "school": "School", "pass_status": "Result"},
             hover_data=["enrolments"])
fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
st.plotly_chart(style_chart(fig), use_container_width=True)

# 3. Department & semester (term) performance
st.subheader("3 · Department and term performance")
summ = safe_query("SELECT * FROM analytics.mart_subject_term_summary")
summ = summ[summ.school.isin(df.school.unique()) & summ.subject_name.isin(df.subject_name.unique())]
c1, c2 = st.columns(2)
with c1:
    fig = px.line(summ, x="term_name", y="avg_grade", color="department", line_dash="school", markers=True,
                  color_discrete_sequence=["#2a78d6", "#eb6834"],
                  category_orders={"term_name": ["Period 1", "Period 2", "Final"]},
                  labels={"term_name": "Term", "avg_grade": "Average grade", "department": "Department"})
    fig.update_traces(line_width=2, marker_size=8)
    st.plotly_chart(style_chart(fig), use_container_width=True)
with c2:
    pivot = summ.pivot_table(index=["department", "school"], columns="term_name", values="pass_rate_pct")
    pivot = pivot[[c for c in ["Period 1", "Period 2", "Final"] if c in pivot.columns]]
    fig = px.imshow(pivot.values, x=list(pivot.columns), y=[f"{d} · {s}" for d, s in pivot.index],
                    color_continuous_scale=["#cde2fb", "#86b6ef", "#2a78d6", "#104281"], text_auto=".0f",
                    labels={"color": "Pass rate %"}, aspect="auto")
    fig.update_layout(title="Pass rate % by department, school and term")
    st.plotly_chart(style_chart(fig), use_container_width=True)

# 4. Drivers
st.subheader("4 · Study time and past failures")
c1, c2 = st.columns(2)
with c1:
    labels = {1: "<2h", 2: "2-5h", 3: "5-10h", 4: ">10h"}
    fig = px.box(df.assign(study=df.study_time.map(labels)), x="study", y="final_grade", color="subject_name",
                 color_discrete_map=SUBJECT_COLORS, category_orders={"study": list(labels.values())},
                 labels={"study": "Weekly study time", "final_grade": "Final grade", "subject_name": "Subject"})
    st.plotly_chart(style_chart(fig), use_container_width=True)
with c2:
    g = df.groupby(["prior_failures", "school"]).agg(
        pass_rate=("pass_status", lambda s: (s == "Pass").mean() * 100), n=("student_id", "count")).reset_index()
    fig = px.bar(g, x="prior_failures", y="pass_rate", color="school", barmode="group", hover_data=["n"],
                 color_discrete_map=SCHOOL_COLORS,
                 labels={"prior_failures": "Past class failures", "pass_rate": "Pass rate %", "school": "School"})
    st.plotly_chart(style_chart(fig), use_container_width=True)
