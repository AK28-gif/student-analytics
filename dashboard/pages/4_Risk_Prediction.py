"""What-if risk prediction through the FastAPI model service (Part 2 integration)."""
import requests
import streamlit as st

from common import config, mart, page

page("Risk Prediction (ML model via FastAPI)", "🤖")
api = st.sidebar.text_input("API URL", config.API_URL)

try:
    health = requests.get(f"{api}/health", timeout=3).json()
    info = requests.get(f"{api}/model", timeout=3).json()
    st.success(f"API online · model **{info['model_type']}** v{info['model_version']} · "
               f"test F1 {info['metrics'].get('test_f1')} · test ROC-AUC {info['metrics'].get('test_roc_auc')}")
except Exception:
    st.error(f"FastAPI service not reachable at {api}. Start it with `make api` or `make docker-up`.")
    st.stop()

df = mart()
prefill = st.selectbox("Pre-fill from an existing enrolment (optional)",
                       ["-"] + (df.student_id + " · " + df.subject_code).tolist())
base = df.iloc[0] if prefill == "-" else df[(df.student_id + " · " + df.subject_code) == prefill].iloc[0]

with st.form("predict"):
    c1, c2, c3, c4 = st.columns(4)
    subject_code = c1.selectbox("Subject", ["MAT", "POR"], index=["MAT", "POR"].index(base.subject_code))
    school = c2.selectbox("School", ["GP", "MS"], index=["GP", "MS"].index(base.school))
    sex = c3.selectbox("Sex", ["F", "M"], index=["F", "M"].index(base.sex))
    age = c4.number_input("Age", 15, 22, int(base.age))
    grade_p1 = c1.slider("Period 1 grade (G1)", 0, 20, int(base.grade_p1))
    grade_p2 = c2.slider("Period 2 grade (G2)", 0, 20, int(base.grade_p2))
    absences = c3.number_input("Absences so far", 0, 93, int(base.absences))
    prior_failures = c4.number_input("Past class failures", 0, 4, int(base.prior_failures))
    study_time = c1.select_slider("Weekly study time", [1, 2, 3, 4], int(base.study_time),
                                  format_func=lambda v: {1: "<2h", 2: "2-5h", 3: "5-10h", 4: ">10h"}[v])
    going_out = c2.slider("Going out with friends (1-5)", 1, 5, int(base.going_out))
    higher = c3.checkbox("Wants higher education", bool(base.wants_higher_education))
    support = c4.checkbox("Extra school support", bool(base.school_support))
    submitted = st.form_submit_button("Predict fail risk", type="primary")

if submitted:
    payload = {
        "subject_code": subject_code, "school": school, "sex": sex, "age": age, "address_type": base.address_type,
        "family_size": base.family_size, "parent_status": base.parent_status,
        "mother_education": int(base.mother_education), "father_education": int(base.father_education),
        "mother_job": base.mother_job, "father_job": base.father_job, "reason": base.reason,
        "guardian": base.guardian, "travel_time": int(base.travel_time), "study_time": study_time,
        "prior_failures": prior_failures, "family_relationship": int(base.family_relationship),
        "free_time": int(base.free_time), "going_out": going_out, "weekday_alcohol": int(base.weekday_alcohol),
        "weekend_alcohol": int(base.weekend_alcohol), "health": int(base.health), "absences": absences,
        "grade_p1": grade_p1, "grade_p2": grade_p2, "school_support": support,
        "family_support": bool(base.family_support), "paid_classes": bool(base.paid_classes),
        "extra_activities": bool(base.extra_activities), "attended_nursery": bool(base.attended_nursery),
        "wants_higher_education": higher, "internet_access": bool(base.internet_access),
        "romantic": bool(base.romantic), "student_id": None if prefill == "-" else base.student_id,
    }
    r = requests.post(f"{api}/predict", json=payload, timeout=10)
    if r.ok:
        p = r.json()
        icon = {"High": "🔴", "Medium": "🟠", "Low": "🟢"}[p["risk_band"]]
        st.metric("Probability of failing the subject", f"{p['fail_probability']:.0%}")
        st.markdown(f"{icon} **{p['risk_band']} risk** - predicted outcome: "
                    f"**{'FAIL' if p['predicted_fail'] else 'PASS'}** (model v{p['model_version']}, {p['model_type']})")
        st.progress(p["fail_probability"])
        st.caption("Every request is logged (inputs, output, latency) and used by the monitoring job.")
    else:
        st.error(f"API error {r.status_code}: {r.text}")
