"""Shared helpers for the Streamlit dashboard: DB access, filters, colour mapping."""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.common import config, db  # noqa: E402

# Colour follows the entity (fixed order, never by rank). Status colours are reserved for
# pass/fail and risk and are always shown with a text label.
SUBJECT_COLORS = {"Mathematics": "#2a78d6", "Portuguese Language": "#eb6834"}
SCHOOL_COLORS = {"GP": "#2a78d6", "MS": "#eb6834"}
STATUS_COLORS = {"Pass": "#0ca30c", "Fail": "#d03b3b"}
RISK_COLORS = {"Low": "#0ca30c", "Medium": "#fab219", "High": "#d03b3b"}
RISK_ORDER = ["High", "Medium", "Low"]


def page(title: str, icon: str = "🎓"):
    st.set_page_config(page_title=f"{title} | Student Analytics", page_icon=icon, layout="wide")
    st.title(title)


@st.cache_data(ttl=300, show_spinner=False)
def query(sql: str, **params) -> pd.DataFrame:
    with db.get_engine().connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)


def safe_query(sql: str, **params) -> pd.DataFrame:
    try:
        return query(sql, **params)
    except Exception as exc:
        st.error(f"Could not query the warehouse - is PostgreSQL running and has the pipeline been run? ({exc})")
        st.stop()


def mart() -> pd.DataFrame:
    return safe_query("SELECT * FROM analytics.mart_student_subject")


def latest_predictions() -> pd.DataFrame:
    try:
        return query("""SELECT * FROM ml.risk_predictions
                        WHERE model_version = (SELECT model_version FROM ml.risk_predictions
                                               ORDER BY scored_at DESC LIMIT 1)""")
    except Exception:
        return pd.DataFrame()


def sidebar_filters(df: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.header("Filters")
    schools = st.sidebar.multiselect("School", sorted(df.school.unique()), default=sorted(df.school.unique()),
                                     format_func=lambda s: f"{s} - {'Gabriel Pereira' if s == 'GP' else 'Mousinho da Silveira'}")
    subjects = st.sidebar.multiselect("Subject / department", sorted(df.subject_name.unique()),
                                      default=sorted(df.subject_name.unique()))
    sexes = st.sidebar.multiselect("Sex", ["F", "M"], default=["F", "M"])
    ages = st.sidebar.slider("Age", int(df.age.min()), int(df.age.max()), (int(df.age.min()), int(df.age.max())))
    out = df[df.school.isin(schools) & df.subject_name.isin(subjects) & df.sex.isin(sexes) & df.age.between(*ages)]
    st.sidebar.caption(f"{len(out):,} of {len(df):,} enrolments selected")
    if st.sidebar.button("Refresh data"):
        st.cache_data.clear()
        st.rerun()
    return out


def style_chart(fig, height=380):
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=40, b=10),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, title=None),
                      hoverlabel=dict(namelength=-1))
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridwidth=1)
    return fig


def intervention_suggestions(row) -> list:
    tips = []
    reasons = str(row.get("risk_reasons", ""))
    if "internal marks" in reasons:
        tips.append("Assign subject tutor / remedial sessions before the final assessment")
    if "attendance" in reasons:
        tips.append("Attendance follow-up with student and guardian")
    if "failures" in reasons:
        tips.append("Academic mentor check-in (history of failed classes)")
    if "Declining" in reasons:
        tips.append("Review recent assessments to identify the topics causing the drop")
    if "study time" in reasons:
        tips.append("Study-skills workshop / structured study plan")
    if "higher education" in reasons:
        tips.append("Career guidance & motivation counselling")
    return tips or ["No intervention needed - keep monitoring"]


__all__ = ["config", "page", "query", "safe_query", "mart", "latest_predictions", "sidebar_filters", "style_chart",
           "SUBJECT_COLORS", "SCHOOL_COLORS", "STATUS_COLORS", "RISK_COLORS", "RISK_ORDER", "intervention_suggestions"]
