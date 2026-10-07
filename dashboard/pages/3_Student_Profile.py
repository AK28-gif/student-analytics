import plotly.express as px
import streamlit as st

from common import SUBJECT_COLORS, intervention_suggestions, latest_predictions, mart, page, style_chart

page("Student Profile & Intervention", "🧑‍🎓")
df = mart()
preds = latest_predictions()

ids = df.sort_values(["risk_score", "student_id"], ascending=[False, True]).student_id.unique().tolist()
sid = st.selectbox("Student (sorted by highest risk first)", ids)
s = df[df.student_id == sid]
first = s.iloc[0]

c = st.columns(5)
c[0].metric("School", first.school_name)
c[1].metric("Sex / age", f"{first.sex} / {first.age}")
c[2].metric("Subjects", len(s))
c[3].metric("Avg final grade", f"{s.final_grade.mean():.1f}")
c[4].metric("Highest risk", s.sort_values("risk_score").iloc[-1].risk_level)

with st.expander("Background"):
    st.write({
        "Address": "Urban" if first.address_type == "U" else "Rural", "Family size": first.family_size,
        "Parents": "together" if first.parent_status == "T" else "apart", "Guardian": first.guardian,
        "Mother education (0-4)": int(first.mother_education), "Father education (0-4)": int(first.father_education),
        "Internet at home": bool(first.internet_access), "Wants higher education": bool(first.wants_higher_education),
        "Health (1-5)": int(first.health),
    })

terms = s.melt(id_vars=["subject_name"], value_vars=["grade_p1", "grade_p2", "final_grade"],
               var_name="term", value_name="grade")
terms["term"] = terms.term.map({"grade_p1": "Period 1", "grade_p2": "Period 2", "final_grade": "Final"})
fig = px.line(terms, x="term", y="grade", color="subject_name", markers=True, color_discrete_map=SUBJECT_COLORS,
              range_y=[0, 20], labels={"term": "", "grade": "Grade (0-20)", "subject_name": "Subject"})
fig.update_traces(line_width=2, marker_size=9)
fig.add_hline(y=10, line_dash="dash", line_color="#898781", annotation_text="Pass mark")
st.subheader("Grade trajectory")
st.plotly_chart(style_chart(fig, 340), use_container_width=True)

st.subheader("Risk assessment & recommended interventions")
for _, row in s.iterrows():
    prob = None
    if not preds.empty:
        p = preds[(preds.student_id == sid) & (preds.subject_code == row.subject_code)]
        prob = float(p.fail_probability.iloc[0]) if not p.empty else None
    icon = {"High": "🔴", "Medium": "🟠", "Low": "🟢"}[row.risk_level]
    with st.container(border=True):
        st.markdown(f"**{row.subject_name}** - {icon} **{row.risk_level} risk** (score {row.risk_score}/10)"
                    + (f" · ML fail probability **{prob:.0%}**" if prob is not None else ""))
        a, b, cc, d = st.columns(4)
        a.metric("Attendance", f"{row.attendance_pct:.1f}%", f"{row.absences} absences", delta_color="off")
        b.metric("Internal marks (avg G1,G2)", f"{row.avg_internal_marks:.1f}", f"{row.grade_trend:+d} trend")
        cc.metric("Past failures", int(row.prior_failures))
        d.metric("Final grade", f"{row.final_grade} ({row.pass_status})")
        st.caption(f"Triggered rules: {row.risk_reasons}")
        for tip in intervention_suggestions(row):
            st.markdown(f"- {tip}")
