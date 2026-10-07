import streamlit as st

from common import RISK_ORDER, latest_predictions, mart, page, sidebar_filters

page("High-Risk Student List", "🚨")
st.caption("Rule-based early-warning score (Part 1, uses information available before the final exam) "
           "combined with the ML model's fail probability (Part 2) when batch predictions exist.")

df = sidebar_filters(mart())
preds = latest_predictions()
if not preds.empty:
    df = df.merge(preds[["student_id", "subject_code", "fail_probability", "risk_band"]],
                  on=["student_id", "subject_code"], how="left").rename(columns={"risk_band": "ml_risk_band"})

c1, c2, c3 = st.columns(3)
levels = c1.multiselect("Rule-based risk level", RISK_ORDER, default=["High"])
min_prob = c2.slider("Min. ML fail probability", 0.0, 1.0, 0.0, 0.05, disabled=preds.empty)
search = c3.text_input("Search student id", placeholder="STU00042")

view = df[df.risk_level.isin(levels)]
if not preds.empty:
    view = view[view.fail_probability.fillna(0) >= min_prob]
if search:
    view = view[view.student_id.str.contains(search.strip(), case=False)]

cols = ["student_id", "subject_name", "school", "sex", "age", "grade_p1", "grade_p2", "avg_internal_marks",
        "attendance_pct", "prior_failures", "risk_score", "risk_level", "risk_reasons"]
if not preds.empty:
    cols += ["fail_probability", "ml_risk_band"]
cols += ["final_grade", "pass_status"]
view = view.sort_values(["risk_score"] + (["fail_probability"] if not preds.empty else []), ascending=False)

st.metric("Students needing intervention", f"{view.student_id.nunique():,}", help=f"{len(view)} enrolments")
st.dataframe(
    view[cols], use_container_width=True, hide_index=True, height=520,
    column_config={
        "fail_probability": st.column_config.ProgressColumn("ML fail prob.", min_value=0, max_value=1, format="%.2f"),
        "attendance_pct": st.column_config.NumberColumn("Attendance %", format="%.1f"),
        "risk_score": st.column_config.NumberColumn("Risk score", help="0-10, >=5 High, 3-4 Medium"),
        "final_grade": st.column_config.NumberColumn("Final grade (actual)"),
    },
)
st.download_button("Download list as CSV", view[cols].to_csv(index=False), "high_risk_students.csv", "text/csv")
